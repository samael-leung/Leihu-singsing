"""Windows installation orchestration and Ollama streamed download contracts."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import installer as I
import ollama_setup as O
import pipeline as P


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.report=MagicMock()

    def test_find_per_user_install_without_refreshed_path(self):
        exe=self.root/'Programs'/'Ollama'/'ollama.exe'
        exe.parent.mkdir(parents=True); exe.touch()
        with patch.object(O.shutil,'which',return_value=None), patch.dict(O.os.environ,{'LOCALAPPDATA':str(self.root)}):
            self.assertEqual(O.find_ollama(),exe)

    def test_running_service_is_reused(self):
        with patch.object(O,'service_ready',return_value=True), patch.object(O.subprocess,'Popen') as spawn:
            O.ensure_service('http://127.0.0.1:11434',self.root)
        spawn.assert_not_called()

    def test_remote_service_is_never_started_locally(self):
        with patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',return_value=Path('ollama')), patch.object(O.subprocess,'Popen') as spawn:
            with self.assertRaises(RuntimeError): O.ensure_service('https://remote.example',self.root)
        spawn.assert_not_called()

    def test_service_start_preserves_model_cache_setting(self):
        with patch.object(O,'service_ready',side_effect=[False,True]), patch.object(O,'find_ollama',return_value=Path('ollama')), patch.object(O.subprocess,'Popen') as spawn, patch.dict(O.os.environ,{'OLLAMA_MODELS':'custom-cache'}):
            O.ensure_service('http://127.0.0.1:12345',self.root)
        self.assertEqual(spawn.call_args.args[0],['ollama','serve'])
        self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_HOST'],'127.0.0.1:12345')
        self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_MODELS'],'custom-cache')

    def test_failed_service_start_is_reported(self):
        process=MagicMock(); process.poll.return_value=1
        with patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',return_value=Path('ollama')), patch.object(O.subprocess,'Popen',return_value=process):
            with self.assertRaisesRegex(RuntimeError,'啟動失敗'): O.ensure_service('http://127.0.0.1:11434',self.root)

    def test_stream_download_checks_success_and_reports_bytes(self):
        lines=[{'status':'pulling manifest'}, {'status':'pulling blob','total':100,'completed':50}, {'status':'verifying sha256 digest'}, {'status':'success'}]
        raw=b''.join(json.dumps(item).encode()+b'\n' for item in lines)
        with patch.object(O,'urlopen',return_value=io.BytesIO(raw)) as send:
            O.pull_model('http://localhost:11434','qwen2.5:14b',self.report)
        req=send.call_args.args[0]
        self.assertEqual(req.full_url,'http://localhost:11434/api/pull')
        self.assertEqual(json.loads(req.data),{'model':'qwen2.5:14b','stream':True})
        self.assertIn('GB',self.report.call_args_list[1].args[1])

    def test_stream_error_or_disconnect_does_not_count_as_success(self):
        for raw in (b'{"status":"pulling manifest"}\n', b'{"error":"checksum mismatch"}\n', b'bad JSON\n'):
            with self.subTest(raw=raw), patch.object(O,'urlopen',return_value=io.BytesIO(raw)):
                with self.assertRaises((RuntimeError,ValueError)): O.pull_model('http://localhost:11434','qwen2.5:14b',self.report)

    def test_existing_model_is_loaded_without_download(self):
        with patch.object(O,'model_present',return_value=True), patch.object(O,'pull_model') as pull, patch.object(O,'api',return_value={'done':True,'response':'OK'}) as api:
            O.prepare_model('http://localhost:11434','qwen2.5:14b',self.report)
        pull.assert_not_called()
        body=api.call_args.args[2]
        self.assertTrue(body['prompt'])  # Empty prompts with keep_alive=0 only unload a model.
        self.assertEqual(body['keep_alive'],0)
        self.assertEqual(body['options']['num_predict'],8)

    def test_interrupted_pull_retries_and_then_loads(self):
        with patch.object(O,'model_present',side_effect=[False,True]), patch.object(O,'pull_model',side_effect=[URLError('offline'),None]) as pull, patch.object(O.time,'sleep'), patch.object(O,'api',return_value={'done':True,'response':'OK'}):
            O.prepare_model('http://localhost:11434','custom:14b',self.report)
        self.assertEqual(pull.call_count,2)

    def test_failed_pull_stops_after_three_attempts(self):
        with patch.object(O,'model_present',return_value=False), patch.object(O,'pull_model',side_effect=URLError('offline')) as pull, patch.object(O.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'續傳'): O.prepare_model('http://localhost:11434','custom:14b',self.report)
        self.assertEqual(pull.call_count,3)

    def test_downloaded_model_must_appear_in_tags(self):
        with patch.object(O,'model_present',return_value=False), patch.object(O,'pull_model'), patch.object(O,'api') as api:
            with self.assertRaisesRegex(RuntimeError,'找不到模型'): O.prepare_model('http://localhost:11434','custom:14b',self.report)
        api.assert_not_called()

    def test_model_load_failure_is_reported(self):
        for result in ({'done':False}, {'done':True,'response':''}, {'error':'not enough memory'}):
            with self.subTest(result=result), patch.object(O,'model_present',return_value=True), patch.object(O,'api',return_value=result):
                with self.assertRaisesRegex(RuntimeError,'無法載入'): O.prepare_model('http://localhost:11434','custom:14b',self.report)

    def test_untagged_names_match_latest(self):
        with patch.object(O,'api',return_value={'models':[{'name':'custom:latest'}]}):
            self.assertTrue(O.model_present('http://localhost:11434','custom'))


class InstallerOllamaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.patches=[patch.object(I,'ROOT',self.root), patch.object(I,'DL',self.root/'downloads'),
                      patch.object(I,'say'),patch.object(I,'progress'),
                      patch.object(P,'load_config',return_value={'ollama_url':'http://127.0.0.1:11434','ollama_model':'qwen2.5:14b'}),
                      patch.object(O,'ensure_service'),patch.object(O,'prepare_model')]
        for item in self.patches: item.start(); self.addCleanup(item.stop)

    def test_existing_ollama_is_reused(self):
        with patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',return_value=Path('ollama.exe')), patch.object(I,'download') as download:
            self.assertTrue(I.prepare_ollama())
        download.assert_not_called()
        ownership=json.loads((self.root/'ollama-install.json').read_text())
        self.assertFalse(ownership['installed_by_app'])
        self.assertEqual(O.prepare_model.call_args.args[:2],('http://127.0.0.1:11434','qwen2.5:14b'))

    def test_official_installer_is_verified_before_execution(self):
        setup=self.root/'OllamaSetup.exe'; setup.touch()
        with patch.object(I.sys,'platform','win32'), patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',side_effect=[None,Path('ollama.exe')]), patch.object(I,'download',return_value=setup) as download, patch.object(I,'powershell',return_value='VERIFIED') as signature, patch.object(I,'run',return_value=0) as run:
            self.assertTrue(I.prepare_ollama())
        self.assertEqual(download.call_args.args[0],'https://ollama.com/download/OllamaSetup.exe')
        self.assertIn('Get-AuthenticodeSignature',signature.call_args.args[0])
        self.assertIn("$sig.Status -ne 'Valid'",signature.call_args.args[0])
        self.assertIn('/VERYSILENT',run.call_args.args[0])
        ownership=json.loads((self.root/'ollama-install.json').read_text())
        self.assertTrue(ownership['installed_by_app'])
        self.assertEqual(ownership['models'],['qwen2.5:14b'])

    def test_unverified_installer_is_not_executed(self):
        setup=self.root/'OllamaSetup.exe'; setup.touch()
        with patch.object(I.sys,'platform','win32'), patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',return_value=None), patch.object(I,'download',return_value=setup), patch.object(I,'powershell',return_value=''), patch.object(I,'run') as run:
            self.assertFalse(I.prepare_ollama())
        run.assert_not_called(); self.assertFalse(setup.exists())
        O.prepare_model.assert_not_called()

    def test_remote_unavailable_service_does_not_install_locally(self):
        P.load_config.return_value['ollama_url']='https://remote.example'
        with patch.object(O,'service_ready',return_value=False), patch.object(O,'find_ollama',return_value=None), patch.object(I,'download') as download:
            self.assertFalse(I.prepare_ollama())
        download.assert_not_called()

    def test_custom_configured_model_is_preserved(self):
        P.load_config.return_value.update(ollama_url='https://remote.example',ollama_model='custom:14b')
        with patch.object(O,'service_ready',return_value=True), patch.object(I,'download') as download:
            self.assertTrue(I.prepare_ollama())
        download.assert_not_called()
        self.assertEqual(O.prepare_model.call_args.args[:2],('https://remote.example','custom:14b'))

    def test_failed_model_preparation_is_not_success(self):
        O.prepare_model.side_effect=RuntimeError('download interrupted')
        with patch.object(O,'service_ready',return_value=True): self.assertFalse(I.prepare_ollama())

    def test_main_failure_leaves_no_completion_marker_or_launch(self):
        marker=self.root/'installed.json'; marker.write_text('{"version":"old"}')
        with patch.object(I,'stop_app'),patch.object(I,'clean_stale'),patch.object(I,'detect_gpu',return_value=('cpu','CPU')),patch.object(I,'install_torch',return_value=True),patch.object(I,'install_packages',return_value=True),patch.object(I,'prefetch_models'),patch.object(I,'prepare_ollama',return_value=False),patch.object(I,'stage'),patch.object(I,'launch') as launch,patch.object(I,'verify') as verify,patch.object(I.sys,'argv',['installer.py','--launch']):
            self.assertEqual(I.main(),1)
        self.assertFalse(marker.exists()); launch.assert_not_called(); verify.assert_not_called()


if __name__=='__main__': unittest.main()
