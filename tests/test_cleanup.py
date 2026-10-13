"""Run filesystem and model-boundary checks using PowerShell when available."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PWSH = os.environ.get('LEIHU_TEST_PWSH') or shutil.which('pwsh') or shutil.which('powershell')


@unittest.skipUnless(PWSH, 'PowerShell is required for cleanup filesystem tests')
class CleanupTests(unittest.TestCase):
    def test_cleanup_boundaries_and_retry(self):
        with tempfile.TemporaryDirectory() as workspace:
            result = subprocess.run([PWSH, '-NoProfile', '-File', str(Path(__file__).with_name('cleanup_smoke.ps1')),
                                     '-Workspace', workspace], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Cleanup functional checks passed: 26', result.stdout)


if __name__ == '__main__':
    unittest.main()
