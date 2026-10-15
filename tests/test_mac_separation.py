"""Mac CPU provider choice and real subprocess crash/cancellation boundaries."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audio_separator.separator import Separator
import pipeline as P
import uvr_worker as W


class MacSeparationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        change = patch.object(P, 'ROOT', self.root)
        change.start()
        self.addCleanup(change.stop)
        self.cfg = dict(P.DEFAULT_CONFIG, openai_api_key='must-not-enter-worker')

    def worker(self, source):
        (self.root / 'uvr_worker.py').write_text(source)

    def test_cpu_separator_never_selects_mps_or_coreml(self):
        with patch.object(Separator, 'configure_mps', side_effect=AssertionError('CoreML is unsafe')), patch.object(Separator, 'configure_cuda', side_effect=AssertionError('Mac path must use CPU')):
            sep = P._uvr_separator(True, model_file_dir=str(self.root), output_dir=str(self.root))
        self.assertEqual(str(sep.torch_device), 'cpu')
        self.assertIsNone(sep.torch_device_mps)
        self.assertEqual(sep.onnx_execution_provider, ['CPUExecutionProvider'])

    def test_mac_dispatches_worker_and_other_platforms_keep_existing_path(self):
        for platform, worker in (('darwin', True), ('win32', False), ('linux', False)):
            with patch.object(P.sys, 'platform', platform), patch.object(P, '_separate_uvr_worker') as isolated, patch.object(P, '_separate_uvr_direct') as direct:
                P.separate_uvr(self.root, self.cfg, lambda *args: None)
            self.assertEqual(isolated.called, worker)
            self.assertEqual(direct.called, not worker)

    def test_progress_is_forwarded_and_only_model_config_is_sent(self):
        self.worker("""import sys,json
data=json.loads(sys.stdin.readline())
assert set(data['models'])=={'separation_model','karaoke_model','karaoke_quality'}
assert 'must-not-enter-worker' not in json.dumps(data)
print('LEIHU_UVR_PROGRESS '+json.dumps({'step':'second model','progress':.35}),flush=True)
""")
        events = []
        P._separate_uvr_worker(self.root, self.cfg, lambda *args: events.append(args))
        self.assertIn(('second model', .35), events)

    def test_native_sigsegv_is_reported_without_killing_parent(self):
        self.worker("""import sys,resource,signal,os
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
sys.stdin.readline()
os.kill(os.getpid(),signal.SIGSEGV)
""")
        with self.assertRaisesRegex(P.UserError, '子程序異常結束'):
            P._separate_uvr_worker(self.root, self.cfg, lambda *args: None)
        self.assertTrue((self.root / 'logs/uvr-worker.log').is_file())

    def test_cancel_terminates_child_instead_of_leaving_it_running(self):
        self.worker("""import sys,json,time
sys.stdin.readline()
print('LEIHU_UVR_PROGRESS '+json.dumps({'step':'started','progress':.1}),flush=True)
time.sleep(60)
""")
        def cancel(step, progress):
            if step == 'started':
                raise P.JobCancelled()
        original = P.subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(P.subprocess, 'Popen', side_effect=spawn), self.assertRaises(P.JobCancelled):
            P._separate_uvr_worker(self.root, self.cfg, cancel)
        self.assertIsNotNone(children[0].poll())

    def test_silent_native_inference_can_be_cancelled(self):
        self.worker("import sys,time;sys.stdin.readline();time.sleep(60)")
        calls = []
        def cancel(step, progress):
            calls.append(step)
            if len(calls) > 1:
                raise P.JobCancelled()
        original = P.subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(P.subprocess, 'Popen', side_effect=spawn), self.assertRaises(P.JobCancelled):
            P._separate_uvr_worker(self.root, self.cfg, cancel)
        self.assertIsNotNone(children[0].poll())

    def test_worker_exits_when_app_parent_disappears(self):
        with patch.object(W.os, 'kill', side_effect=ProcessLookupError()), patch.object(W.os, '_exit') as exit_worker:
            W.watch_parent(123)
        exit_worker.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()
