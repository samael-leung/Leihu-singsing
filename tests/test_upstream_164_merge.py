"""Concurrent metadata/usage writes and bounded queues with custom features."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import ai_api as A
import app as web
import pipeline as P


class Upstream164Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        for name, value in [('LIB', self.song.parent), ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'songaa', 'title': 'Concurrent song', 'steps': {}, 'notes': []})

    def test_concurrent_metadata_updates_do_not_corrupt_or_lose_fields(self):
        def writer(index):
            for value in range(30):
                P.update_meta(self.song, **{f'field{index}': value})
                self.assertEqual(P.read_meta(self.song)['id'], 'songaa')
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(writer, range(8)))
        result = json.loads((self.song / 'meta.json').read_text())
        self.assertTrue(all(result[f'field{i}'] == 29 for i in range(8)))
        self.assertFalse(list(self.song.glob('*.tmp')))

    def test_duplicate_json_repair_retains_first_complete_song_and_alignment_source(self):
        original = {'id': 'songaa', 'title': 'Recovered', 'steps': {'pitch': True}, 'lyrics_source': 'forced_alignment'}
        (self.song / 'meta.json').write_text(json.dumps(original) + '{"partial":')
        with patch.object(P, 'log_error'):
            self.assertEqual(P.read_meta(self.song), original)
        self.assertEqual(json.loads((self.song / 'meta.json').read_text()), original)
        self.assertEqual(P.list_songs()[0]['title'], 'Recovered')

    def test_truncated_metadata_reconstruction_preserves_existing_audio(self):
        (self.song / 'meta.json').write_text('{"title":"Retained song", "artist":"Artist", "key":-2,')
        for stem in ('mix', 'lead', 'back', 'inst'):
            (self.song / f'{stem}.flac').write_bytes(b'untouched-audio')
        with patch.object(P, 'log_error'):
            result = P.read_meta(self.song)
        self.assertEqual(result['title'], 'Retained song')
        self.assertEqual(result['artist'], 'Artist')
        self.assertEqual(result['key'], -2)
        self.assertTrue(result['steps']['separate'])
        self.assertEqual((self.song / 'lead.flac').read_bytes(), b'untouched-audio')

    def test_queue_summary_caps_custom_playlist_and_upstream_process_jobs(self):
        queued = [{'kind': 'process' if i % 2 else 'playlist', 'status': 'queued', 'id': str(i)} for i in range(45)]
        running = {'kind': 'process', 'status': 'running', 'id': 'active'}
        with patch.object(web, 'jobs', Mock(active=lambda: [running, *queued])), \
             patch.object(web, 'vjobs', Mock(active=lambda: [])):
            result = web._jobs_for_ui()
        self.assertEqual(result['queued_total'], 45)
        self.assertEqual(len(result['jobs']), 31)
        self.assertEqual(result['jobs'][0], running)

    def test_provider_usage_concurrent_writes_use_valid_complete_json(self):
        with patch.object(A, 'USAGE_PATH', self.root / 'usage.json'):
            def record(i):
                return A.record('test-model', 10, 20, 'align', f'song{i}', active_provider='openai')
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(record, range(40)))
            result = json.loads((self.root / 'usage.json').read_text())
        self.assertEqual(len(result['calls']), 40)
        self.assertEqual({c['song'] for c in result['calls']}, {f'song{i}' for i in range(40)})

    def test_share_window_uses_separate_browser_profile_and_preserves_regular_browser(self):
        with patch.object(P, 'ROOT', self.root), patch.object(web, '_app_browser', return_value='msedge.exe'), \
             patch.object(web.subprocess, 'Popen') as launch:
            response = web.app.test_client().post('/api/open-app', json={})
        self.assertEqual(response.json, {'ok': True, 'app': True})
        args = launch.call_args.args[0]
        self.assertIn('--user-data-dir=' + str(self.root / '.appwin'), args)
        self.assertIn(f'--app=http://{web.HOST}:{web.PORT}/', args)
        self.assertTrue((self.root / '.appwin').is_dir())
