"""Exercise 2.1 live processing together with the custom AI and sync APIs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app as web
import pipeline as P


class Upstream210Tests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.song = self.root / 'library' / 'song210'
        self.song.mkdir(parents=True)
        for name, value in [('ROOT', self.root), ('LIB', self.song.parent),
                            ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        live = patch.dict(P.LIVE_HOLD, apps=[], live_seen=0, override_until=0, checked=0)
        live.start(); self.addCleanup(live.stop)
        P.save_config(dict(P.DEFAULT_CONFIG, ai_mode='api', api_provider='gemini',
                           gemini_api_key='fixture-gemini', openai_api_key='fixture-openai',
                           vocal_quality='standard', karaoke_quality='standard'))
        P.write_meta(self.song, {'id': self.song.name, 'title': '同步測試', 'steps': {}, 'notes': []})
        self.client = web.app.test_client()

    def test_status_returns_custom_ai_and_live_heartbeat_together(self):
        with patch.object(P, 'module_status', return_value={'cuda': False}):
            result = self.client.get('/api/status?live=1')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['ai_provider'], 'gemini')
        self.assertTrue(result.json['ai_ready'])
        self.assertTrue(result.json['live']['hold'])
        self.assertIn('hqv', result.json)
        self.assertNotIn('fixture-gemini', result.text)

    def test_monitor_and_live_settings_preserve_all_provider_keys(self):
        result = self.client.post('/api/config', json={'monitor_out': 'Headphones',
            'vocal_quality': 'high', 'pause_while_streaming': False, 'font': 'sans'})
        self.assertEqual(result.status_code, 200)
        cfg = P.load_config()
        self.assertEqual(cfg['monitor_out'], 'Headphones')
        self.assertEqual(cfg['vocal_quality'], 'high')
        self.assertFalse(cfg['pause_while_streaming'])
        self.assertEqual(cfg['gemini_api_key'], 'fixture-gemini')
        self.assertEqual(cfg['openai_api_key'], 'fixture-openai')
        self.assertNotIn('fixture-', result.text)

    def test_local_bridge_works_but_remote_origins_and_hosts_are_rejected(self):
        self.assertEqual(self.client.get('/api/song-request/library').status_code, 200)
        self.assertEqual(self.client.post('/api/remote/open', json={'id': self.song.name}).status_code, 200)
        for path, body in [('/api/song-request/selection', {'song': {}}),
                           ('/api/config', {'monitor_out': 'Changed'}),
                           ('/api/remote/open', {'id': self.song.name})]:
            result = self.client.post(path, json=body, headers={'Origin': 'https://other.example'})
            self.assertEqual(result.status_code, 403)
        self.assertEqual(self.client.get('/api/song-request/library',
            headers={'Host': 'other.example'}).status_code, 403)

    def test_live_import_uses_light_models_and_keeps_persistent_ai_settings(self):
        cfg = P.load_config()
        cfg.update(vocal_quality='high', karaoke_quality='high', auto_recognize_lyrics=True)
        P.save_config(cfg)
        P.live_touch()
        with patch.object(P, 'step_import'), patch.object(P, 'step_separate') as separate, \
             patch.object(P, 'step_pitch'), patch.object(P, 'measure_stem_loudness'), \
             patch.object(P, 'search_lyrics_later') as search, patch.object(P, 'step_lyrics') as recognize:
            P.process_song(self.song.name, ['import', 'separate', 'pitch', 'lyrics'])(Mock())
        used = separate.call_args.args[1]
        self.assertEqual(used['vocal_quality'], 'standard')
        self.assertEqual(used['karaoke_quality'], 'standard')
        self.assertEqual(used['api_provider'], 'gemini')
        self.assertTrue(P.read_meta(self.song)['live_light'])
        self.assertTrue(search.call_args.kwargs['apply_first'])
        recognize.assert_not_called()
        self.assertEqual(P.load_config()['vocal_quality'], 'high')
        self.assertTrue(P.load_config()['auto_recognize_lyrics'])

    def test_live_scheduler_skips_background_work_and_resumes_afterward(self):
        with patch.object(P.threading, 'Thread'):
            jobs = P.Jobs(live_safe=True)
        background = jobs.submit('process', self.song.name, Mock(), label='upgrade')
        foreground = jobs.submit('playlist', 'next-song', Mock(), label='playlist:batch')
        self.assertEqual(jobs._next(True, 1)[0], foreground)
        self.assertEqual(jobs._next(True, 1), (None, None, True))
        self.assertEqual(jobs._next(False, 1)[0], background)

    def test_windows_streaming_detection_calls_tasklist_and_matches_process_names(self):
        result = Mock(stdout='"obs64.exe","1234","Console"\n"Other.exe","4567"')
        with patch.object(P.sys, 'platform', 'win32'), \
             patch.object(P.subprocess, 'run', return_value=result) as run:
            self.assertEqual(P._running_apps(['obs64.exe', 'VTube Studio.exe']), ['obs64.exe'])
        self.assertEqual(run.call_args.args[0], ['tasklist', '/FO', 'CSV', '/NH'])

    def test_upgrade_skips_already_upgraded_and_queued_songs(self):
        songs = [dict(id='new', steps={'separate': True}, separation='uvr'),
                 dict(id='done', steps={'separate': True, 'pitch': True}, separation='uvr', vocal_model='bs_roformer'),
                 dict(id='queued', steps={'separate': True}, separation='uvr')]
        with patch.object(P, 'hqv_ready', return_value=True), \
             patch.object(P, 'vocal_model', return_value=P.HQ_VOCAL), \
             patch.object(P, 'list_songs', return_value=songs), \
             patch.object(web.jobs, 'find', side_effect=lambda kind, sid, label: 'job' if sid == 'queued' else None), \
             patch.object(web.jobs, 'submit') as submit:
            result = self.client.post('/api/upgrade-separation', json={})
        self.assertEqual(result.json['queued'], 1)
        self.assertEqual(submit.call_args.args[:2], ('process', 'new'))

    def test_conversion_keeps_original_wording_and_japanese(self):
        self.assertEqual(P.to_taiwan('出租车里的信息'), '出租車裡的信息')
        self.assertEqual(P.to_taiwan('君と一緒に歩いていく'), '君と一緒に歩いていく')

    def test_reseparation_marks_timing_problem_without_overwriting_custom_lyrics(self):
        lrc = '[00:01.00]<00:01.00>保<00:01.50>留\n'
        (self.song / 'lyrics.lrc').write_text(lrc)
        P.update_meta(self.song, lyrics_source='forced_alignment')
        with patch.object(P, 'lyrics_timing_fit', return_value=.3):
            P.check_lyrics_after_reseparate(self.song, .9)
        meta = P.read_meta(self.song)
        self.assertEqual(meta['lyrics_recheck']['fit'], .3)
        self.assertEqual(meta['lyrics_source'], 'forced_alignment')
        self.assertEqual((self.song / 'lyrics.lrc').read_text(), lrc)
        (self.song / 'lyrics.lrc').write_text(lrc + '[00:03.00]已修正\n')
        self.assertIsNone(P.list_songs()[0]['lyrics_recheck'])
