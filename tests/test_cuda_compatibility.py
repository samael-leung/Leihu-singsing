"""Exercise the actual CUDA probe and fallback without requiring a GPU."""
import unittest
from unittest.mock import Mock, patch

import torch
import pipeline as P
import app as web


class CudaCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.previous = P._CUDA_OK, P.CUDA_NOTE
        P._CUDA_OK, P.CUDA_NOTE = None, ''
        self.addCleanup(self.restore)

    def restore(self):
        P._CUDA_OK, P.CUDA_NOTE = self.previous

    def test_cpu_only_does_not_attempt_cuda_allocation(self):
        with patch.object(torch.cuda, 'is_available', return_value=False), patch.object(torch, 'ones') as allocate:
            self.assertFalse(P.cuda_ok())
            self.assertEqual(P.CUDA_NOTE, '')
            allocate.assert_not_called()

    def test_supported_gpu_is_probed_once(self):
        tensor = Mock()
        tensor.__mul__ = Mock(return_value=tensor)
        tensor.sum.return_value.item.return_value = 128.0
        with patch.object(torch.cuda, 'is_available', return_value=True), patch.object(torch, 'ones', return_value=tensor) as allocate:
            self.assertTrue(P.cuda_ok())
            self.assertTrue(P.cuda_ok())
            allocate.assert_called_once_with(64, device='cuda:0')

    def test_incompatible_gpu_falls_back_and_status_reports_reason(self):
        with patch.object(torch.cuda, 'is_available', return_value=True), patch.object(torch.cuda, 'get_device_name', return_value='GTX 1080'), patch.object(torch, 'ones', side_effect=RuntimeError('no kernel image is available')) as allocate:
            self.assertFalse(P.cuda_ok())
            status = web.app.test_client().get('/api/status').get_json()
            self.assertFalse(status['modules']['cuda'])
            self.assertIn('GTX 1080', status['cuda_note'])
            self.assertIn('CPU', status['cuda_note'])
            allocate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
