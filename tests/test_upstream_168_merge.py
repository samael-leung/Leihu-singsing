"""Upstream 1.6.8 features coexist with custom lyrics, providers and updates."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import numpy as np
import soundfile as sf

import ai_api as A
import app as web
import installer as I
import pipeline as P

# The desktop entry point redirects stdout/stderr and changes cwd on import.
# Keep those application side effects from hiding the test runner's results.
_cwd = Path.cwd()
with patch.object(sys, 'stdout'), patch.object(sys, 'stderr'):
    import desktop
os.chdir(_cwd)


class Upstream168Tests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        for change in (patch.object(P, 'LIB', self.song.parent),
                       patch.object(P, 'CONFIG_PATH', self.root / 'config.json'),
                       patch.object(A, 'USAGE_PATH', self.root / 'usage.json')):
            change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'songaa', 'title': 'Sample', 'steps': {'import': True},
                                'duration': 90, 'notes': []})
        self.client = web.app.test_client()

    def test_chorus_analysis_combines_existing_flac_tracks_without_modifying_them(self):
        for name, signal in [('lead', np.full(3200, .1)), ('back', np.full(2800, .2))]:
            sf.write(self.song / (name + '.flac'), signal, P.PITCH_SR)
        original = (self.song / 'lead.flac').read_bytes()
        lead = P.analysis_vocal(self.song)
        P.update_meta(self.song, vocal_mode='all')
        combined = P.analysis_vocal(self.song)
        self.assertEqual(len(combined), 2800)
        np.testing.assert_allclose(lead, .1, atol=.0001)
        np.testing.assert_allclose(combined, .3, atol=.0001)
        self.assertEqual((self.song / 'lead.flac').read_bytes(), original)

    def test_whisper_failed_cuda_probe_falls_back_before_transcription(self):
        cuda = Mock(model=SimpleNamespace(device='cuda'))
        cuda.detect_language.side_effect = RuntimeError('missing cublas64_12.dll')
        cpu = Mock()
        factory = Mock(side_effect=[cuda, cpu])
        with patch.dict(sys.modules, {'faster_whisper': SimpleNamespace(WhisperModel=factory)}):
            self.assertIs(P._whisper_model({}), cpu)
        self.assertEqual(factory.call_args_list[0].kwargs['device'], 'auto')
        self.assertEqual(factory.call_args_list[1].kwargs['device'], 'cpu')
        cuda.detect_language.assert_called_once()

    def test_fresh_torch_install_resolves_dependencies_before_gpu_probe(self):
        wheel = self.root / 'torch.whl'
        wheel.touch()
        with patch.object(I, 'installed_versions', return_value={}), \
             patch.object(I, '_wheel_links', return_value=[('https://example.test/torch', 'torch.whl', 'digest')]), \
             patch.object(I, 'download', return_value=wheel), patch.object(I, 'pip', return_value=0) as pip, \
             patch.object(I, 'say'), patch.object(I, 'progress'):
            self.assertTrue(I.install_torch('cu128'))
        calls = [call.args for call in pip.call_args_list]
        self.assertIn('--no-deps', calls[0])
        self.assertNotIn('--no-deps', calls[1])
        self.assertIn('torch==' + I.TORCH['torch'] + '+cu128', calls[1])

    def test_desktop_launch_uses_console_python_without_a_visible_console(self):
        (self.root / 'logs').mkdir()
        (self.root / 'python.exe').touch()
        with patch.object(desktop, 'ROOT', self.root), \
             patch.object(desktop.sys, 'executable', str(self.root / 'pythonw.exe')), \
             patch.object(desktop.sys, 'platform', 'win32'), \
             patch.object(desktop.subprocess, 'Popen') as launch:
            desktop.start_server(8765)
        self.assertEqual(launch.call_args.args[0][0], str(self.root / 'python.exe'))
        self.assertEqual(launch.call_args.kwargs['creationflags'], 0x08000000)
        launch.call_args.kwargs['stdout'].close()

    def test_max_quality_uses_override_and_keeps_user_lyrics(self):
        text = '[00:01.00]User edited\n'
        (self.song / 'lyrics.lrc').write_text(text)
        P.update_meta(self.song, lyrics_source='forced_alignment')
        with patch.object(P, 'hq_ready', return_value=True), \
             patch.object(P, 'process_song', return_value=Mock()) as process, \
             patch.object(web.jobs, 'find', return_value=None), \
             patch.object(web.jobs, 'submit', return_value='job') as submit:
            result = self.client.post('/api/songs/songaa/process',
                                      json={'vocal_mode': 'all', 'max_quality': True})
        self.assertEqual(result.json, {'job': 'job'})
        self.assertEqual(P.read_meta(self.song)['vocal_mode'], 'all')
        self.assertEqual(process.call_args.kwargs['cfg_override'],
                         {'karaoke_quality': 'high', 'karaoke_overlap': 4})
        self.assertEqual(submit.call_args.kwargs['label'], 'max')
        self.assertEqual((self.song / 'lyrics.lrc').read_text(), text)

    def test_hallucination_cleanup_does_not_rewrite_manual_or_forced_lyrics(self):
        text = '[00:01.00]優優獨播劇場\n[00:03.00]Real lyric\n'
        for source in ('manual', 'forced_alignment', 'openai', 'whisper'):
            with self.subTest(source=source):
                P.update_meta(self.song, lyrics_source=source)
                (self.song / 'lyrics.lrc').write_text(text)
                (self.song / 'lyrics_auto.lrc').write_text(text)
                response = self.client.get('/api/songs/songaa/lyrics')
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('獨播', (self.song / 'lyrics_auto.lrc').read_text())
                self.assertEqual('獨播' in (self.song / 'lyrics.lrc').read_text(), source != 'whisper')

    def test_autoshift_finds_long_intro_and_keeps_already_correct_times(self):
        times = [0, 5, 13, 24]
        phrases = [(t + 37.3, t + 38) for t in times]
        (self.song / 'pitch.json').write_text('{}')
        with patch.object(P, 'voice_phrases', return_value=phrases):
            result = self.client.post('/api/songs/songaa/lyrics/autoshift', json={'times': times})
            self.assertEqual(result.status_code, 200)
            self.assertAlmostEqual(result.json['offset'], 37.3, delta=.03)
            self.assertEqual(result.json['scale'], 1)
            self.assertIsNone(P.voice_fit([a for a, _ in phrases], self.song))

    def test_timing_popup_state_and_commands_stay_with_their_owner(self):
        with web._TCOND:
            before = dict(web.TIMING)
            web.TIMING.update(state={}, sseq=0, cmds=[], cseq=0, seen={})
        self.addCleanup(lambda: web.TIMING.update(before))
        self.client.post('/api/timing/state', json={'owner': 'testa', 'lines': [[1, 'A']], 't': 4})
        result = self.client.get('/api/timing/state?owner=testa&after=0')
        self.assertEqual(result.json['lines'], [[1, 'A']])
        self.client.post('/api/timing/cmd', json={'owner': 'testb', 'cmd': {'a': 'pause'}})
        self.client.post('/api/timing/cmd', json={'owner': 'testa', 'cmd': {'a': 'now', 'i': 0}})
        result = self.client.get('/api/timing/cmds?owner=testa&after=0')
        self.assertEqual(result.json['cmds'], [{'a': 'now', 'i': 0}])
        page = self.client.get('/timing?owner=testa')
        self.assertEqual(page.status_code, 200)
        page.close()

    def test_claude_alignment_disables_initial_thinking_and_falls_back_on_older_models(self):
        P.save_config(dict(P.DEFAULT_CONFIG, ai_mode='api', api_provider='claude',
                           anthropic_api_key='local-test-key'))
        tool = {'name': 'set_line_times', 'input_schema': {'type': 'object',
                'properties': {'times': {'type': 'array', 'items': {'type': 'number'},
                                          'minItems': 2, 'maxItems': 2}}, 'required': ['times']}}
        reply = {'content': [{'type': 'tool_use', 'name': 'set_line_times', 'input': {'times': [1, 3]}}],
                 'stop_reason': 'tool_use', 'usage': {'input_tokens': 10, 'output_tokens': 10}}
        with patch.object(A, 'urlopen', side_effect=[HTTPError('https://api.anthropic.com', 400, '', {}, None),
                                                    io.BytesIO(json.dumps(reply).encode())]) as send:
            result, _ = A.ask_tool('Align', tool, 2000, 'align')
        self.assertEqual(result, {'times': [1, 3]})
        first, second = [json.loads(c.args[0].data) for c in send.call_args_list]
        self.assertEqual(first['thinking'], {'type': 'between_tools'})
        self.assertNotIn('thinking', second)
        self.assertEqual(second['tool_choice']['type'], 'tool')
        self.assertEqual(A.summary()['total']['calls'], 1)


class IntegrationUpdateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for name, value in [('UPDATE', dict(web.UPDATE, latest=None, can_install=False, state='')),
                            ('_UPDATE_ASSET', {})]:
            change = patch.object(web, name, value)
            change.start(); self.addCleanup(change.stop)
        self.data = b'fixture updater bytes'
        self.name = 'LeihuLiantai-windows-ai-choice-99.0.0-Update.exe'
        self.asset = {'name': self.name, 'browser_download_url': web.ASSET_PREFIX + self.name,
                      'size': len(self.data), 'digest': 'sha256:' + hashlib.sha256(self.data).hexdigest()}

    def check(self, asset):
        with patch.object(web.time, 'sleep'), patch.object(P, '_http_json',
                return_value={'tag_name': 'v99.0.0', 'assets': [asset]}) as read, \
             patch.object(web, '_installed_copy', return_value=True):
            web.check_update()
        read.assert_called_once_with(web.UPDATE_MANIFEST)

    def test_integrated_manifest_offers_only_own_branch_program_updater(self):
        self.check(self.asset)
        self.assertTrue(web.UPDATE['can_install'])
        self.assertEqual(web._UPDATE_ASSET, {k: self.asset[k] for k in ('name', 'size', 'digest')} |
                         {'url': self.asset['browser_download_url']})

    def test_original_author_releases_other_branches_and_invalid_digests_are_not_installable(self):
        for change in ({'browser_download_url': 'https://github.com/LeihuTW/Leihu-singsing/releases/download/x/a.exe'},
                       {'browser_download_url': self.asset['browser_download_url'].replace('leihu-song-request-sync', 'main')},
                       {'name': '../other.exe'}, {'digest': 'sha256:bad'}, {'size': 0}):
            with self.subTest(change=change):
                self.check(dict(self.asset, **change))
                self.assertFalse(web.UPDATE['can_install'])
                self.assertEqual(web._UPDATE_ASSET, {})

    def test_verified_update_launches_silently_at_current_install_path(self):
        self.check(self.asset)
        with patch.object(web.tempfile, 'gettempdir', return_value=str(self.root)), \
             patch.object(web, 'Path', Path), patch.object(P, 'ROOT', self.root / 'installed app'), \
             patch('urllib.request.urlopen', return_value=io.BytesIO(self.data)), \
             patch.object(web.subprocess, 'Popen') as launch:
            web._download_and_install()
        self.assertEqual(web.UPDATE['state'], 'installing')
        self.assertIn(' /S /D=' + str(self.root / 'installed app'), launch.call_args.args[0])
        self.assertEqual((self.root / 'LeihuLiantai-update' / self.name).read_bytes(), self.data)

    def test_bad_hash_is_rejected_before_any_installer_is_executed(self):
        self.check(self.asset)
        with patch.object(web.tempfile, 'gettempdir', return_value=str(self.root)), \
             patch('urllib.request.urlopen', return_value=io.BytesIO(b'corrupt')), \
             patch.object(web.subprocess, 'Popen') as launch, patch.object(P, 'log_error'):
            web._download_and_install()
        self.assertEqual(web.UPDATE['state'], 'error')
        launch.assert_not_called()
        self.assertFalse((self.root / 'LeihuLiantai-update' / self.name).exists())

    def test_secure_runtime_installation_can_receive_program_updates(self):
        (self.root / 'secure-runtime' / 'Scripts').mkdir(parents=True)
        for name in ('secure-runtime/Scripts/pythonw.exe', 'secure-runtime/leihu-ready.json', 'installed.json'):
            (self.root / name).touch()
        with patch.object(P, 'ROOT', self.root), patch.object(web.sys, 'platform', 'win32'):
            self.assertTrue(web._installed_copy())

    def test_install_requires_same_origin_json_and_a_verified_update(self):
        client = web.app.test_client()
        with patch.object(web.threading, 'Thread') as thread:
            self.assertEqual(client.post('/api/update/install', data='{}').status_code, 415)
            self.assertEqual(client.post('/api/update/install', json={},
                headers={'Origin': 'https://other.example'}).status_code, 403)
            self.assertEqual(client.post('/api/update/install', json={}).status_code, 400)
            thread.assert_not_called()
