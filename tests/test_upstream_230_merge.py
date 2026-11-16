"""2.3 exports, history and storage must coexist with playlist and sync state."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask
import app as web
import exporter as EX
import pipeline as P
import song_request as SR
import youtube_playlist as Y


class Upstream230Tests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.lib = self.root / 'library'; self.lib.mkdir()
        self.models = self.root / 'models'; self.models.mkdir()
        for name, value in [('ROOT', self.root), ('LIB', self.lib), ('DEFAULT_LIB', self.lib),
                            ('MODELS', self.models), ('DEFAULT_MODELS', self.models),
                            ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        for name, value in [('SETLIST_PATH', self.root / 'setlist.json'), ('SETLIST_DIR', self.root / 'setlists')]:
            change = patch.object(web, name, value)
            change.start(); self.addCleanup(change.stop)
        P.save_config(dict(P.DEFAULT_CONFIG, ai_mode='api', api_provider='gemini',
                           gemini_api_key='fixture-secret', ai_setup_complete=True))
        self.song = self.lib / 'song230'; self.song.mkdir()
        P.write_meta(self.song, dict(id=self.song.name, title='同步測試', artist='歌手', category='中文歌',
            key=-2, steps={'import': True, 'separate': True, 'pitch': True}, notes=[],
            source_url='https://www.youtube.com/watch?v=abcdefghijk'))
        (self.song / 'lyrics.lrc').write_text('[00:01.00]<00:01.00>原<00:01.50>詞\n')
        self.client = web.app.test_client()

    def jobs(self):
        with patch.object(P.threading, 'Thread'):
            return P.Jobs(live_safe=True, pipeline=True)

    def test_pause_resume_playlist_keeps_durable_batch_queued_without_an_error(self):
        jobs = self.jobs()
        batch = Y.create([{'video_id': 'lmnopqrstuv', 'title': '播放清單歌曲'}], None, jobs)
        jid, fn = jobs.pending.pop()
        jobs.state[jid]['status'] = 'running'; jobs.running[jid] = 'gpu'
        jobs.set_paused(True)
        with patch.object(P, 'youtube_job', return_value=lambda report: report('separation', .2)):
            jobs._work(jid, fn)
        self.assertEqual(jobs.get(jid)['status'], 'queued')
        row = Y.status(batch['id'], jobs)['items'][0]
        self.assertEqual(row['status'], 'queued'); self.assertIsNone(row['error'])
        self.assertIsNone(jobs._next(False, 1)[0])
        self.assertTrue(P.load_config()['queue_paused'])
        jobs.set_paused(False)
        next_jid, next_fn, _ = jobs._next(False, 1)
        self.assertEqual(next_jid, jid)
        jobs.running[jid] = 'gpu'
        with patch.object(P, 'youtube_job', return_value=lambda report: report('complete', 1)):
            jobs._work(jid, next_fn)
        self.assertEqual(Y.status(batch['id'], jobs)['items'][0]['status'], 'done')

    def test_playlist_priority_and_postprocessing_overlap_preserve_same_song_exclusion(self):
        jobs = self.jobs()
        first = jobs.submit('process', 'song230', Mock(), label='all')
        next_song = jobs.submit('playlist', 'next230', Mock(), label='playlist:batch')
        self.assertTrue(jobs.to_front(next_song))
        self.assertEqual(jobs._next(False, 1)[0], next_song)
        jobs.running[first] = 'post'
        self.assertTrue(jobs._can_start(jobs.get(next_song), 1))
        self.assertFalse(jobs._can_start(dict(jobs.get(next_song), song='song230'), 1))

    def test_move_and_adopt_keep_lyrics_batches_models_keys_and_song_links(self):
        batch = self.lib / '.youtube-batches' / 'fixture.json'; batch.parent.mkdir()
        batch.write_text('{"items":[]}')
        (self.models / 'fixture.bin').write_bytes(b'model-cache')
        bridge = Flask('storage-sync-fixture')
        SR.register(bridge, list_songs=P.list_songs, links_file=self.root / 'links.json')
        client = bridge.test_client()
        link = dict(title='同步測試', artist='歌手', songId='song230')
        self.assertEqual(client.post('/api/song-request/links', json=link).status_code, 200)
        original = (self.song / 'lyrics.lrc').read_bytes()
        target = self.root / 'moved'
        P.move_storage(str(target), ['library', 'models'], Mock())
        self.assertEqual(P.LIB, target / 'library')
        self.assertEqual((P.LIB / 'song230' / 'lyrics.lrc').read_bytes(), original)
        self.assertEqual((P.LIB / '.youtube-batches' / 'fixture.json').read_bytes(), batch.read_bytes())
        self.assertEqual((P.MODELS / 'fixture.bin').read_bytes(), b'model-cache')
        self.assertTrue(self.song.exists())
        self.assertEqual(P.load_config()['gemini_api_key'], 'fixture-secret')
        self.assertEqual(client.get('/api/song-request/links').json, [link])
        self.assertEqual(client.get('/api/song-request/library').json[0]['id'], 'song230')
        P.adopt_storage(str(self.lib))
        self.assertEqual(P.LIB, self.lib)
        self.assertEqual(client.get('/api/song-request/library').json[0]['id'], 'song230')

    def test_export_html_xlsx_and_reimportable_csv_keep_canonical_metadata(self):
        before = (self.song / 'meta.json').read_bytes()
        with patch.object(P, 'downloads_dir', return_value=self.root / 'exports'):
            for fmt in ['html', 'xlsx', 'csv']:
                result = self.client.post('/api/export/songlist', json={'format': fmt})
                self.assertEqual(result.status_code, 200, result.text)
                path = Path(result.json['path']); self.assertTrue(path.is_file())
                if fmt == 'xlsx':
                    with zipfile.ZipFile(path) as archive:
                        self.assertIsNone(archive.testzip())
                        self.assertIn('同步測試', archive.read('xl/worksheets/sheet1.xml').decode())
                elif fmt == 'csv':
                    rows = P.read_sheet(path.read_bytes(), path.name)
                    self.assertEqual(rows[0]['song'], '同步測試')
                else:
                    self.assertIn('同步測試', path.read_text('utf-8-sig'))
        self.assertEqual((self.song / 'meta.json').read_bytes(), before)

    def test_history_archives_and_exports_previous_session_without_touching_ai_keys(self):
        with patch.object(web.time, 'time', return_value=1000):
            self.client.post('/api/setlist/add', json=dict(id='song230', title='同步測試', artist='歌手', played=45))
        with patch.object(web.time, 'time', return_value=1000 + web.SETLIST_GAP + 1):
            self.client.post('/api/setlist/add', json=dict(id='next230', title='下一場', artist='歌手'))
        history = self.client.get('/api/setlist/history').json
        self.assertEqual(len(history), 2)
        old = next(item for item in history if item['file'])
        with patch.object(P, 'downloads_dir', return_value=self.root / 'exports'):
            result = self.client.post('/api/export/setlist', json={'format': 'xlsx', 'file': old['file']})
        self.assertEqual(result.status_code, 200)
        with zipfile.ZipFile(result.json['path']) as archive:
            self.assertIn('同步測試', archive.read('xl/worksheets/sheet1.xml').decode())
        self.assertEqual(P.load_config()['gemini_api_key'], 'fixture-secret')

    def test_pause_api_and_live_status_include_custom_playlist_work(self):
        jobs = self.jobs()
        jid = jobs.submit('playlist', 'queued230', Mock(), label='playlist:batch')
        with patch.object(web, 'jobs', jobs), patch.object(P, 'module_status', return_value={'cuda': False}):
            self.assertTrue(self.client.post('/api/jobs/pause-all', json={'on': True}).json['paused'])
            self.assertIsNone(jobs._next(False, 1)[0])
            self.assertTrue(self.client.get('/api/status').json['live']['paused'])
            self.client.post('/api/jobs/pause-all', json={'on': False})
            self.assertEqual(jobs._next(False, 1)[0], jid)
