"""Upstream optimizations must not hide or disable existing import workflows."""
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app as web
import gpu_worker as G
import pipeline as P


class Upstream231Tests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.lib = self.root / 'library'; self.lib.mkdir()
        self.models = self.root / 'models'; self.models.mkdir()
        for name, value in [('LIB', self.lib), ('CONFIG_PATH', self.root / 'config.json'),
                            ('MODELS', self.models)]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        P.save_config(dict(P.DEFAULT_CONFIG, yt_enabled=False))
        with patch.object(P.threading, 'Thread'):
            jobs = P.Jobs(live_safe=True, pipeline=True)
        change = patch.object(web, 'jobs', jobs)
        change.start(); self.addCleanup(change.stop)
        self.jobs = jobs
        self.client = web.app.test_client()

    def test_single_youtube_import_works_for_new_and_previously_disabled_configs(self):
        for disabled, vid in [(None, 'abcdefghijk'), (False, 'lmnopqrstuv')]:
            cfg = dict(P.DEFAULT_CONFIG)
            if disabled is False:
                cfg['yt_enabled'] = False
            P.save_config(cfg)
            result = self.client.post('/api/youtube', json={'url': 'https://youtu.be/' + vid})
            self.assertEqual(result.status_code, 200, result.text)
            meta = P.read_meta(P.song_dir(result.json['id']))
            self.assertIn(vid, meta['source_url'])
            self.assertEqual(meta['dl_state'], 'queued')
        self.assertEqual(len(self.jobs.pending), 2)
        self.assertTrue(all(job['label'] == 'youtube' for job in self.jobs.state.values()))

    def test_csv_sheet_resolve_and_batch_download_preserve_key_and_artist(self):
        data = '歌手,曲名,KEY,語言,YouTube\n測試歌手,保留下載,-2,中文,https://youtu.be/abcdefghijk\n'.encode('utf-8-sig')
        sheet = self.client.post('/api/youtube/sheet', data={'file': (io.BytesIO(data), 'songs.csv')})
        self.assertEqual(sheet.status_code, 200)
        resolved = self.client.post('/api/youtube/resolve', json={'sheet': sheet.json['rows']})
        self.assertEqual(resolved.status_code, 200)
        result = self.client.post('/api/youtube/batch', json={'items': resolved.json['items']})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json['added'], 1)
        song = P.list_songs()[0]
        P.set_dl_state(P.song_dir(song['id']), None)
        song = P.read_meta(P.song_dir(song['id']))
        self.assertEqual((song['title'], song['artist'], song['key']), ('保留下載', '測試歌手', -2))
        with patch.object(P, 'downloads_dir', return_value=self.root / 'exports'):
            template = self.client.post('/api/sheet-template', json={})
        self.assertEqual(template.status_code, 200)
        self.assertTrue(Path(template.json['path']).is_file())

    def test_custom_playlist_import_and_history_work_without_unlocking(self):
        result = self.client.post('/api/youtube/playlist/import', json={'items': [
            {'video_id': 'abcdefghijk', 'title': '播放清單歌曲'}]})
        self.assertEqual(result.status_code, 200, result.text)
        bid = result.json['id']
        self.assertEqual(self.client.get('/api/youtube/playlist/batches/' + bid).status_code, 200)
        self.assertEqual(self.client.post('/api/youtube/playlist/batches/' + bid + '/stop', json={}).status_code, 200)
        self.assertEqual(self.client.post('/api/youtube/playlist/batches/' + bid + '/retry', json={}).status_code, 200)
        blocked = self.client.post('/api/youtube', json={'url': 'https://youtu.be/lmnopqrstuv'},
                                   headers={'Origin': 'https://other.example'})
        self.assertEqual(blocked.status_code, 403)

    def test_storage_move_allows_song_reads_and_still_blocks_writes(self):
        song = self.lib / 'song231'; song.mkdir()
        P.write_meta(song, {'id': 'song231', 'title': '原歌名', 'steps': {}, 'notes': []})
        with patch.dict(P.STORAGE, moving=True):
            self.assertEqual(self.client.get('/api/songs/song231').status_code, 200)
            result = self.client.patch('/api/songs/song231', json={'title': '搬移中修改'})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(P.read_meta(song)['title'], '原歌名')

    def test_vram_advice_keeps_the_existing_manual_parallel_choice(self):
        P.save_config(dict(P.DEFAULT_CONFIG, parallel_separation=True))
        for size, recommended in [(8 * 1024**3, False), (10 * 1024**3, True), (24 * 1024**3, True)]:
            with self.subTest(size=size), patch.object(P, 'gpu_info', return_value={'ok': True, 'vram': size}):
                self.assertEqual(P.parallel_ok(), recommended)
                self.assertEqual(self.jobs._slots(False), 2)
                self.assertEqual(self.jobs._slots(True), 1)

    def test_old_successful_probe_cache_is_refreshed_to_record_vram(self):
        cache = self.models / 'gpu_probe.json'
        cache.write_text(json.dumps({'ok': True, 'torch': 'fixture-torch'}))
        info = {'ok': True, 'vram': 24 * 1024**3, 'note': '', 'cc': 8}
        with patch.object(P, '_GPU_INFO', None), patch.object(P, '_torch_version', return_value='fixture-torch'), \
             patch.object(G.POOL, 'call', return_value=info) as probe:
            self.assertEqual(P.gpu_info()['vram'], info['vram'])
        probe.assert_called_once_with('probe')
        self.assertEqual(json.loads(cache.read_text())['vram'], info['vram'])

    def test_poll_log_filter_keeps_failures_and_non_poll_operations(self):
        quiet = web._QuietPolls()
        def record(msg):
            return logging.LogRecord('werkzeug', logging.INFO, '', 0, msg, (), None)
        self.assertFalse(quiet.filter(record('127.0.0.1 "GET /api/status HTTP/1.1" 200 -')))
        self.assertTrue(quiet.filter(record('127.0.0.1 "GET /api/status HTTP/1.1" 500 -')))
        self.assertTrue(quiet.filter(record('127.0.0.1 "POST /api/youtube HTTP/1.1" 200 -')))

    def test_large_app_log_rotates_to_a_backup_before_server_start(self):
        previous_cwd = Path.cwd()
        with patch.object(sys, 'stdout'), patch.object(sys, 'stderr'):
            import desktop
        os.chdir(previous_cwd)
        logs = self.root / 'logs'; logs.mkdir()
        path = logs / 'app.log'
        with path.open('wb') as f:
            f.seek(10 * 1024 * 1024); f.write(b'last-log-entry')
        before = path.stat().st_size
        with patch.object(desktop, 'ROOT', self.root), patch.object(desktop.subprocess, 'Popen') as start:
            desktop.start_server(8765)
        start.call_args.kwargs['stdout'].close()
        self.assertEqual((logs / 'app.log.old').stat().st_size, before)
        self.assertEqual(path.stat().st_size, 0)
