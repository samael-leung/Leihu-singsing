"""Mac launcher routing and safety guards without installing host software."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MacLauncherTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'folder with spaces'
        (self.root / 'setup').mkdir(parents=True)
        (self.root / 'stubs').mkdir()
        for name in ['setup/install-mac.sh', 'setup/start-mac.sh', 'Start-Mac.command', 'Install-Mac.command']:
            shutil.copy(ROOT / name, self.root / name)
        self.env = dict(os.environ, PATH=str(self.root / 'stubs') + ':' + os.environ['PATH'])
        self.stub('uname', 'if [ "$1" = -s ]; then echo Darwin; else echo arm64; fi')
        self.stub('sw_vers', 'echo 14.0')

    def stub(self, name, script):
        path = self.root / 'stubs' / name
        path.write_text('#!/bin/bash\n' + script + '\n')
        path.chmod(0o755)

    def run_script(self, name, *args):
        return subprocess.run(['bash', str(self.root / name), *args], env=self.env,
                              cwd='/', capture_output=True, text=True, timeout=10)

    def test_launch_uses_project_venv_from_any_working_directory(self):
        (self.root / '.venv/bin').mkdir(parents=True)
        python = self.root / '.venv/bin/python'
        python.write_text('#!/bin/bash\nprintf "%s\\n" "$PWD" "$@"\n')
        python.chmod(0o755)
        for args, script in [((), 'app.py'), (('desktop',), 'desktop.py')]:
            result = self.run_script('Start-Mac.command', *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(self.root), script])
        self.assertEqual(self.run_script('Start-Mac.command', 'invalid').returncode, 2)

    def test_missing_venv_reports_install_step(self):
        result = self.run_script('Start-Mac.command')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install-mac.sh', result.stderr)

    def test_non_mac_install_does_not_touch_user_data(self):
        self.stub('uname', 'echo Linux')
        for name in ['config.json', 'song-request-links.json']:
            (self.root / name).write_text('existing-data')
        result = self.run_script('Install-Mac.command')
        self.assertNotEqual(result.returncode, 0)
        for name in ['config.json', 'song-request-links.json']:
            self.assertEqual((self.root / name).read_text(), 'existing-data')
        self.assertFalse((self.root / '.venv').exists())

    def test_rosetta_and_older_os_are_rejected_before_installation(self):
        self.stub('uname', 'if [ "$1" = -s ]; then echo Darwin; else echo x86_64; fi')
        result = self.run_script('Install-Mac.command')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Rosetta', result.stderr)
        self.stub('uname', 'if [ "$1" = -s ]; then echo Darwin; else echo arm64; fi')
        self.stub('sw_vers', 'echo 13.6')
        result = self.run_script('Install-Mac.command')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('macOS 14', result.stderr)

    def test_official_ollama_app_is_found_without_shell_path(self):
        from unittest.mock import patch
        import ollama_setup as O
        target = Path('/Applications/Ollama.app/Contents/Resources/ollama')
        with patch.object(O.sys, 'platform', 'darwin'), patch.object(O.shutil, 'which', return_value=None), patch.object(Path, 'is_file', autospec=True, side_effect=lambda path: path == target):
            self.assertEqual(O.find_ollama(), target)
