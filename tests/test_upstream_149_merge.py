"""Exercise upstream 1.4.9 behavior alongside the custom integration."""
import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

import app as web
import pipeline as P
import share as SH


class Upstream149Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.song = self.root / 'library' / 'sample01'
        self.song.mkdir(parents=True)
        for name, value in [('LIB', self.song.parent), ('MODELS', self.root / 'models'),
                            ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'sample01', 'title': 'Sample', 'steps': {}, 'notes': []})
        self.client = web.app.test_client()

    def test_missing_hq_model_uses_standard_until_background_download_completes(self):
        cfg = dict(P.DEFAULT_CONFIG, karaoke_quality='high')
        with patch.object(P, 'hq_ready', return_value=False), patch.object(P, 'start_hq_download') as download:
            self.assertEqual(P.karaoke_model(cfg), cfg['karaoke_model'])
            download.assert_called_once()
        with patch.object(P, 'hq_ready', return_value=True), patch.object(P, 'start_hq_download') as download:
            self.assertEqual(P.karaoke_model(cfg), P.HQ_KARAOKE)
            download.assert_not_called()

    def test_unreliable_recognition_preserves_all_custom_alignment_sources(self):
        model = Mock()
        model.detect_language.return_value = ('en', 0.99, [])
        model.transcribe.return_value = ([], SimpleNamespace(language='en'))
        for source in ['online', 'import', 'manual', 'claude', 'openai', 'gemini', 'ollama', 'forced_alignment', None]:
            with self.subTest(source=source):
                P.update_meta(self.song, lyrics_source=source)
                (self.song / 'lyrics.lrc').write_text('[00:01.00]Keep these corrected lyrics\n')
                with patch.object(P, 'module_status', return_value={'whisper': True}), \
                     patch.object(P, '_whisper_model', return_value=model), \
                     patch.object(P, 'read_audio', return_value=np.zeros(P.PITCH_SR)):
                    P.step_lyrics(self.song, P.DEFAULT_CONFIG, lambda *args: None)
                result = self.client.get('/api/songs/sample01/lyrics').json
                self.assertTrue(result['unreliable'])
                self.assertEqual(result['lrc'], '[00:01.00]Keep these corrected lyrics\n' if source else '')
                self.assertEqual(result['source'], source)

    def test_switch_and_edit_online_lyrics_keeps_recognized_and_aligned_files_separate(self):
        original = '[00:01.00]Recognized\n'
        online = '[00:02.00]Online\n'
        aligned = '[00:03.00]<00:03.00>Aligned\n'
        for name, text in [('lyrics_auto.lrc', original), ('lyrics_online.lrc', online), ('lyrics.lrc', aligned)]:
            (self.song / name).write_text(text)
        P.update_meta(self.song, lyrics_source='forced_alignment', lyrics_quality={'ok': True})
        self.assertEqual(self.client.get('/api/songs/sample01/lyrics').json['source'], 'forced_alignment')
        self.assertEqual(self.client.post('/api/songs/sample01/lyrics/use', json={'which': 'online'}).json['lrc'], online)
        edited = '[00:04.00]Online\n'
        self.assertEqual(self.client.put('/api/songs/sample01/lyrics', json={'lrc': edited}).status_code, 200)
        self.assertEqual((self.song / 'lyrics_online.lrc').read_text(), edited)
        self.assertEqual((self.song / 'lyrics_auto.lrc').read_text(), original)
        self.assertEqual(self.client.post('/api/songs/sample01/lyrics/use', json={'which': 'auto'}).json['lrc'], original)

    def test_csv_batch_upload_and_deduplication_coexist_with_playlist_routes(self):
        data = '歌手,曲名\n郭靜,下一個天亮\n'.encode('utf-8-sig')
        response = self.client.post('/api/youtube/sheet', data={'file': (io.BytesIO(data), 'songs.csv')})
        self.assertEqual(response.json['lines'], ['郭靜 下一個天亮'])
        self.assertEqual(response.json['rows'][0]['artist'], '郭靜')
        self.assertEqual(response.json['rows'][0]['song'], '下一個天亮')
        from test_youtube_playlist import Jobs
        jobs = Jobs()
        video = {'url': 'https://youtu.be/abcdefghijk', 'title': 'Next dawn'}
        with patch.object(web, 'jobs', jobs):
            response = self.client.post('/api/youtube/batch', json={'items': [video, video]})
        self.assertEqual(response.json, {'added': 1, 'skipped': 1, 'updated': 0})
        self.assertEqual(len(jobs.workers), 1)
        self.assertEqual(len(P.list_songs()), 2)
        self.assertEqual(self.client.get('/api/youtube/playlist/batches').status_code, 200)

    def test_mixdown_uses_selected_stems_and_leaves_library_audio_unchanged(self):
        from test_youtube_playlist import Jobs
        jobs = Jobs()
        for name, amplitude in [('lead', .3), ('back', .1), ('inst', .2)]:
            sf.write(str(self.song / f'{name}.wav'), np.full((1000, 2), amplitude), P.SR, subtype='FLOAT')
        originals = {p.name: p.read_bytes() for p in self.song.glob('*.wav')}
        with patch.object(web, 'jobs', jobs), patch.object(P, 'downloads_dir', return_value=self.root / 'downloads'):
            result = self.client.post('/api/songs/sample01/mixdown', json={
                'fmt': 'wav', 'vol': {'lead': 0, 'back': .5, 'inst': 1}, 'norm': False})
            self.assertEqual(result.status_code, 200)
            jobs.run(result.json['job'])
        output, rate = sf.read(result.json['file'], always_2d=True)
        self.assertEqual(rate, P.SR)
        self.assertTrue(np.allclose(output, .25, atol=1e-4))
        self.assertEqual({p.name: p.read_bytes() for p in self.song.glob('*.wav')}, originals)

    def test_export_limiter_preserves_quiet_audio_and_contains_overload(self):
        quiet = np.full((2, P.SR), .2, dtype=np.float32)
        np.testing.assert_array_equal(SH.peak_limit(quiet, P.SR), quiet)
        overloaded = quiet.copy()
        overloaded[:, P.SR // 2] = [3, -3]
        limited = SH.peak_limit(overloaded, P.SR)
        self.assertLessEqual(float(np.abs(limited).max()), 10 ** (-1 / 20) + 1e-6)
        np.testing.assert_array_equal(limited[:, :100], quiet[:, :100])

    def test_queue_reordering_changes_execution_order(self):
        jobs = P.Jobs()
        started, release, done = threading.Event(), threading.Event(), threading.Event()
        order = []
        def block(report):
            started.set(); release.wait(5)
        with patch.object(web, 'jobs', jobs):
            jobs.submit('process', 'sample01', block)
            self.assertTrue(started.wait(2))
            first = jobs.submit('process', 'sample01', lambda report: order.append('first'))
            second = jobs.submit('process', 'sample01', lambda report: order.append('second'))
            jobs.submit('process', 'sample01', lambda report: done.set())
            try:
                self.assertEqual(self.client.post(f'/api/jobs/{second}/move', json={'delta': -1}).status_code, 200)
            finally:
                release.set()
            self.assertTrue(done.wait(3))
            self.assertEqual(order, ['second', 'first'])
