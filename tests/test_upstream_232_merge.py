"""CPU isolation and lead repair must coexist with the custom import/queue flows."""
import tempfile
import threading
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import app as web
import gpu_worker as G
import pipeline as P


class Upstream232Tests(unittest.TestCase):
    def test_long_missing_lead_is_recovered_but_audible_harmony_is_preserved(self):
        back = np.ones(2400, dtype=np.float32)
        gain, sec, _ = P._lead_gap_gain(np.zeros_like(back), back, 100)
        self.assertGreater(sec, 20)
        self.assertGreater(float(gain[1200]), .99)
        gain, sec, _ = P._lead_gap_gain(back * .7, back, 100)
        self.assertIsNone(gain)
        self.assertEqual(sec, 0)

    def test_short_missing_verse_needs_timed_lyrics(self):
        lead = np.ones(2000, dtype=np.float32)
        back = np.ones_like(lead)
        lead[500:900] = 0
        self.assertIsNone(P._lead_gap_gain(lead, back, 100)[0])
        gain, sec, stats = P._lead_gap_gain(lead, back, 100, [(5.2, 8.8)])
        self.assertIsNotNone(gain)
        self.assertGreater(sec, 3)
        self.assertEqual(stats['moved_lines'], 1)

    def test_repair_preserves_the_summed_audio_and_rechecks_changed_lyrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'lead.flac').touch(); (d / 'back.flac').touch()
            (d / 'lyrics.lrc').write_text('[00:01.00]一句歌詞\n[00:05.00]另一句\n')
            lead = np.zeros((2, 2400), dtype=np.float32)
            back = np.ones_like(lead)
            saved = {}
            with patch.object(P, 'SR', 100), patch.object(P, 'read_audio', side_effect=[lead, back]), \
                 patch.object(P, 'save_stem', side_effect=lambda d, k, y: saved.update({k: y})), \
                 patch.object(P, '_split_note'), patch.object(P, 'update_meta') as update:
                self.assertGreater(P.fix_lead_gaps(d), 20)
            np.testing.assert_allclose(saved['lead'] + saved['back'], lead + back)
            meta = dict(id='song', steps={'separate': True}, separation='uvr', **update.call_args.kwargs)
            with patch.object(P, 'song_dir', return_value=d):
                self.assertFalse(P.lead_fix_needed(meta))
                with patch.object(P, '_lrc_stamp', return_value=meta['lead_fix_lrc'] + 1):
                    self.assertTrue(P.lead_fix_needed(meta))

    def test_cpu_requests_never_use_the_gpu_or_parent_fallback(self):
        with patch.object(G.CPU_POOL, 'call', return_value='cpu') as cpu, \
             patch.object(G.POOL, 'call') as gpu, patch.object(G, '_local') as local:
            self.assertEqual(G.call('pitch', 'audio', cpu=True), 'cpu')
            cpu.assert_called_once_with('pitch', 'audio', progress=None, low=True)
            gpu.assert_not_called(); local.assert_not_called()

    def test_stalled_pitch_retries_in_the_cpu_worker(self):
        with patch.object(G, '_BROKEN', {'until': 0}), patch.object(P, 'parallel_ok', return_value=True), \
             patch.object(P, 'live_status', return_value={'hold': False}), \
             patch.object(G.POOL, 'call', side_effect=G.GpuStalled('fixture stall')), \
             patch.object(G.CPU_POOL, 'call', return_value='recovered') as cpu, \
             patch.object(P, 'gpu_stalled_mark') as mark, patch.object(G, '_local') as local:
            self.assertEqual(G.call('pitch', 'audio'), 'recovered')
            mark.assert_called_once(); cpu.assert_called_once(); local.assert_not_called()

    def test_stalled_separation_returns_to_the_pipeline_for_cpu_retry(self):
        with patch.object(G, '_BROKEN', {'until': 0}), patch.object(P, 'parallel_ok', return_value=True), \
             patch.object(P, 'live_status', return_value={'hold': False}), \
             patch.object(G.POOL, 'call', side_effect=G.GpuStalled('fixture stall')), \
             patch.object(P, 'gpu_stalled_mark') as mark, patch.object(G, '_local') as local:
            with self.assertRaises(G.GpuStalled):
                G.call('separate', 'model')
            mark.assert_called_once(); local.assert_not_called()

    def test_small_card_serializes_by_default_and_keeps_manual_parallel(self):
        lock = threading.Lock()
        with patch.object(G, '_GPU_GATE', lock), patch.object(P, 'parallel_ok', return_value=False), \
             patch.object(P, 'live_status', return_value={'hold': False}), \
             patch.object(P, 'load_config', return_value={'parallel_separation': False}):
            with G._gate(None):
                self.assertTrue(lock.locked())
            self.assertFalse(lock.locked())
            with patch.object(P, 'load_config', return_value={'parallel_separation': True}):
                with G._gate(None):
                    self.assertFalse(lock.locked())

    def test_streaming_uses_cpu_even_when_standard_quality_is_selected(self):
        with patch.object(P, 'live_status', return_value={'hold': True}):
            cfg = P.live_light_cfg(dict(P.DEFAULT_CONFIG, vocal_quality='standard', karaoke_quality='standard'))
        self.assertTrue(cfg['_cpu'])
        self.assertEqual(cfg['vocal_quality'], 'standard')

    def test_separation_stall_retries_standard_cpu_and_marks_later_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            P.write_meta(d, dict(id='song', steps={}, notes=[]))
            configs = []
            def separate(folder, cfg, report):
                configs.append(cfg)
                if len(configs) == 1:
                    raise G.GpuStalled('fixture stall')
            with patch.object(P, 'module_status', return_value={'uvr': True}), \
                 patch.object(P, 'separate_uvr', side_effect=separate), \
                 patch.object(P, 'is_acapella', return_value=False), patch.object(P, 'separate_dsp') as dsp:
                P.step_separate(d, dict(P.DEFAULT_CONFIG), Mock())
            self.assertEqual(len(configs), 2)
            self.assertTrue(configs[1]['_cpu'])
            self.assertEqual(configs[1]['vocal_quality'], 'standard')
            self.assertTrue(P.read_meta(d)['live_light'])
            self.assertEqual(P.read_meta(d)['separation'], 'uvr')
            dsp.assert_not_called()

    def test_pausing_separation_does_not_run_the_dsp_fallback(self):
        with patch.object(P, 'module_status', return_value={'uvr': True}), \
             patch.object(P, 'separate_uvr', side_effect=P.JobDeferred('paused')), \
             patch.object(P, 'separate_dsp') as dsp:
            with self.assertRaises(P.JobDeferred):
                P.step_separate(Path('unused'), dict(P.DEFAULT_CONFIG), Mock())
            dsp.assert_not_called()

    def test_early_search_does_not_overwrite_manual_or_provider_lyrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); lrc = d / 'lyrics.lrc'
            for source in ('manual', 'claude', 'gemini', 'openai', 'forced_alignment'):
                lrc.write_text('[00:01.00]保留自訂歌詞\n')
                meta = dict(id='song', steps={}, notes=[], lyrics_source=source)
                P.write_meta(d, meta)
                fut = Future(); fut.set_result(('song', []))
                candidate = dict(title_match=1, diff=0, voice_fit=1)
                with patch.object(P, 'find_candidates', return_value=('song', [candidate])), \
                     patch.object(P, 'fix_lead_gaps'):
                    self.assertTrue(P._apply_early_lyrics(d, P.DEFAULT_CONFIG, fut, Mock()))
                self.assertEqual(lrc.read_text(), '[00:01.00]保留自訂歌詞\n')
                self.assertEqual(P.read_meta(d)['lyrics_source'], source)

    def test_lead_sweep_waits_for_custom_playlist_work(self):
        with patch.object(P.threading, 'Thread'):
            jobs = P.Jobs()
        jobs.state['playlist'] = dict(kind='playlist', song='song', status='running')
        with patch.object(web, 'jobs', jobs), patch.object(web, '_setlist_read', return_value={'items': []}), \
             patch.object(P, 'list_songs', return_value=[dict(id='song')]), \
             patch.object(P, 'usage_score', return_value=0), patch.object(P, 'lead_fix_needed', return_value=True), \
             patch.object(P, 'live_status', return_value={'hold': False}), patch.object(P, 'read_audio') as read:
            web._lead_fix_scan()
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
