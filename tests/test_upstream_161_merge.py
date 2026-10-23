"""Upstream FLAC storage, remote opening and playlist compatibility."""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

import app as web
import installer as I
import pipeline as P
import youtube_playlist as Y
from test_youtube_playlist import Jobs, VIDEOS


class Upstream161Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        for name, value in [('LIB', self.song.parent), ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'songaa', 'title': '親愛的那不是愛情', 'steps': {'import': True}, 'notes': []})
        self.client = web.app.test_client()

    def test_remote_open_rejects_browser_origins_and_checks_key(self):
        body = {'id': 'songaa', 'key': -3}
        self.assertEqual(self.client.post('/api/remote/open', json=body, headers={'Origin': 'http://localhost'}).status_code, 403)
        with patch.dict(web.REMOTE, {'seq': 0, 'id': None, 'key': 0}):
            self.assertEqual(self.client.post('/api/remote/open', json=body).json, {'seq': 1})
            self.assertEqual(web.REMOTE['id'], 'songaa')
            self.assertEqual(web.REMOTE['key'], -3)
        self.assertEqual(self.client.post('/api/remote/open', json=dict(body, key=7)).status_code, 400)

    def test_pcm_compaction_preserves_samples_and_old_audio_api_works(self):
        signal = np.arange(1000, dtype=np.int16).reshape(-1, 1)
        sf.write(str(self.song / 'lead.wav'), signal, P.SR, subtype='PCM_16')
        self.assertEqual(self.client.get('/api/songs/songaa/audio/lead').status_code, 200)
        P.compact_song(self.song)
        self.assertFalse((self.song / 'lead.wav').exists())
        actual, rate = sf.read(str(P.stem_path(self.song, 'lead')), dtype='int16', always_2d=True)
        np.testing.assert_array_equal(actual, signal)
        self.assertEqual(rate, P.SR)
        self.assertEqual(self.client.get('/api/songs/songaa/audio/lead').status_code, 200)

    def test_search_finds_traditional_title_using_simplified_input(self):
        result = self.client.get('/api/songs/search?q=亲爱的那不是爱情')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['match'], ['songaa'])

    def test_playlist_retry_resumes_flac_without_redownloading_and_runs_after_hook(self):
        jobs = Jobs()
        batch = Y.create(VIDEOS[:1], None, jobs)
        sid = batch['items'][0]['song_id']; song = P.song_dir(sid)
        P.update_meta(song, steps={'import': True})
        sf.write(str(song / 'mix.flac'), np.zeros(1000), P.SR)
        after = Mock()
        # Recreate the queue after restart, where the old job cannot be recovered.
        jobs = Jobs(); Y.retry(batch['id'], jobs, after=after)
        with patch.object(P, 'process_song', return_value=lambda report: None) as process, patch.object(P, 'youtube_job') as download:
            jobs.run(next(iter(jobs.workers)))
        process.assert_called_once_with(sid, ['separate', 'pitch', 'lyrics'])
        download.assert_not_called(); after.assert_called_once_with(sid)
        self.assertEqual(Y.status(batch['id'], jobs)['items'][0]['status'], 'done')

    def test_youtube_pause_is_not_marked_as_completed_playlist_import(self):
        jobs = Jobs(); batch = Y.create(VIDEOS[:1], None, jobs)
        sid = batch['items'][0]['song_id']; after = Mock()
        def paused(sid, url):
            return lambda report: P.update_meta(P.song_dir(sid), dl_state='paused')
        with patch.object(P, 'youtube_job', side_effect=paused):
            jobs.run(batch['items'][0]['job'])
        self.assertEqual(Y.status(batch['id'], jobs)['items'][0]['status'], 'paused')
        Y.retry(batch['id'], jobs)
        self.assertEqual(Y.status(batch['id'], jobs)['items'][0]['status'], 'queued')

    def test_installer_uses_interpreter_abi_for_patched_python_environment(self):
        digest = 'a' * 64
        links = ''.join(f'<a href="https://download.pytorch.org/{name}-{version}%2Bcpu-cp313-cp313-win_amd64.whl#sha256={digest}">wheel</a>'
                        for name, version in I.TORCH.items())
        with patch.object(I.sys, 'version_info', SimpleNamespace(major=3, minor=13)), \
             patch('urllib.request.urlopen', side_effect=lambda *args, **kwargs: io.BytesIO(links.encode())):
            result = I._wheel_links('cpu')
        self.assertEqual(len(result), 3)
        self.assertTrue(all('cp313-cp313' in filename and sha == digest for _, filename, sha in result))
