"""New upstream audio/job behavior alongside the existing integration features."""
import hashlib
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
import app as web
import pipeline as P


class UpstreamMergeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.song = self.root / 'library' / 'sample01'
        self.song.mkdir(parents=True)
        for name, value in [('LIB', self.song.parent), ('MODELS', self.root / 'models'),
                            ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)

    def tone(self, amplitude=0.1):
        y = amplitude * np.sin(2 * np.pi * 1000 * np.arange(P.SR) / P.SR)
        return np.stack([y, y])

    def test_loudness_tracks_amplitude_silence_and_safe_gain_limits(self):
        loud = P.integrated_loudness(self.tone(), P.SR)
        quiet = P.integrated_loudness(self.tone(0.05), P.SR)
        self.assertAlmostEqual(loud - quiet, 6.02, delta=0.03)
        self.assertIsNone(P.integrated_loudness(np.zeros((2, P.SR)), P.SR))
        self.assertIsNone(P.integrated_loudness(np.zeros((2, 100)), P.SR))
        self.assertEqual(P.norm_gain_db({'lufs': -60}), 10)
        self.assertEqual(P.norm_gain_db({'lufs': 0}), -15)
        self.assertEqual(P.norm_gain_db({}), 0)

    def test_old_song_loudness_is_measured_once_without_changing_audio(self):
        P.write_meta(self.song, {'id': 'sample01', 'title': 'Legacy song', 'steps': {'import': True}})
        sf.write(str(self.song / 'mix.wav'), self.tone().T, P.SR)
        original = hashlib.sha256((self.song / 'mix.wav').read_bytes()).hexdigest()
        client = web.app.test_client()
        response = client.get('/api/songs/sample01')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json['lufs'])
        self.assertEqual(response.json['norm_gain_db'], P.norm_gain_db(response.json))
        with patch.object(P, 'measure_loudness', side_effect=AssertionError('must use cached measurement')):
            self.assertEqual(client.get('/api/songs/sample01').status_code, 200)
        self.assertEqual(hashlib.sha256((self.song / 'mix.wav').read_bytes()).hexdigest(), original)

    def test_quality_selection_and_saved_api_provider_coexist(self):
        cfg = dict(P.DEFAULT_CONFIG)
        with patch.object(P, 'cuda_ok', return_value=False):
            self.assertEqual(P.karaoke_model(cfg), cfg['karaoke_model'])
            self.assertEqual(P.karaoke_model(dict(cfg, karaoke_quality='high')), P.HQ_KARAOKE)
        with patch.object(P, 'cuda_ok', return_value=True):
            self.assertEqual(P.karaoke_model(cfg), P.HQ_KARAOKE)
            self.assertEqual(P.karaoke_model(dict(cfg, karaoke_quality='standard')), cfg['karaoke_model'])
        P.save_config(dict(cfg, ai_mode='api', api_provider='gemini', gemini_api_key='local-test-key',
                           ollama_auto_model=False))
        client = web.app.test_client()
        response = client.post('/api/config', json={'karaoke_quality': 'standard'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['karaoke_quality'], 'standard')
        self.assertEqual(response.json['api_provider'], 'gemini')
        self.assertNotIn('local-test-key', response.get_data(as_text=True))

    def test_hq_failure_falls_back_to_standard_and_writes_all_stems(self):
        P.write_meta(self.song, {'id': 'sample01', 'steps': {'import': True}})
        sf.write(str(self.song / 'mix.wav'), self.tone().T, P.SR)
        # Load native audio modules before patch.dict restores its module snapshot.
        P.read_audio(self.song / 'mix.wav')
        loaded = []
        class Separator:
            def __init__(inner, **kwargs):
                inner.folder = Path(kwargs['output_dir'])
            def load_model(inner, model_filename):
                loaded.append(model_filename)
                if model_filename == P.HQ_KARAOKE:
                    raise RuntimeError('simulated GPU memory failure')
            def separate(inner, source):
                prefix = 'first' if Path(source).name == 'mix.wav' else 'second'
                names = [f'{prefix}_(Vocals).wav', f'{prefix}_(Instrumental).wav']
                for name in names:
                    sf.write(str(inner.folder / name), self.tone().T, P.SR)
                return names
        fake = types.ModuleType('audio_separator.separator'); fake.Separator = Separator
        with patch.dict(sys.modules, {'audio_separator': types.ModuleType('audio_separator'),
                                      'audio_separator.separator': fake}):
            P.separate_uvr(self.song, dict(P.DEFAULT_CONFIG, karaoke_quality='high'), lambda *args: None)
        self.assertIn(P.HQ_KARAOKE, loaded)
        self.assertEqual(loaded[-1], P.DEFAULT_CONFIG['karaoke_model'])
        self.assertEqual(P.read_meta(self.song)['karaoke'], P.DEFAULT_CONFIG['karaoke_model'])
        for stem in P.STEMS:
            self.assertEqual(sf.info(str(self.song / f'{stem}.wav')).frames, P.SR)

    def test_cancel_api_stops_running_job_at_checkpoint_and_never_runs_queued_job(self):
        jobs = P.Jobs()
        started, release, queued_ran = threading.Event(), threading.Event(), threading.Event()
        def running(report):
            started.set()
            release.wait(5)
            report('checkpoint', 0.5)
        with patch.object(web, 'jobs', jobs):
            first = jobs.submit('process', 'sample01', running)
            self.assertTrue(started.wait(2))
            second = jobs.submit('process', 'sample01', lambda report: queued_ran.set())
            client = web.app.test_client()
            try:
                self.assertEqual(client.post(f'/api/jobs/{second}/cancel').status_code, 200)
                self.assertEqual(jobs.get(second)['status'], 'cancelled')
                self.assertEqual(client.post(f'/api/jobs/{first}/cancel').status_code, 200)
            finally:
                release.set()
            limit = time.monotonic() + 3
            while jobs.get(first)['status'] != 'cancelled' and time.monotonic() < limit:
                time.sleep(0.01)
            self.assertEqual(jobs.get(first)['status'], 'cancelled')
            self.assertFalse(queued_ran.is_set())
            self.assertEqual(client.post('/api/jobs/missing/cancel').status_code, 400)

    def test_cancelled_lyrics_preserve_completed_steps_and_do_not_search(self):
        P.write_meta(self.song, {'id': 'sample01', 'steps': {'import': True, 'pitch': True}, 'notes': []})
        with patch.object(P, 'step_lyrics', side_effect=P.JobCancelled()), patch.object(P, 'find_and_store_candidates') as search:
            with self.assertRaises(P.JobCancelled):
                P.process_song('sample01', ['lyrics'])(lambda *args: None)
        meta = P.read_meta(self.song)
        self.assertTrue(meta['steps']['pitch'])
        self.assertTrue(any('已停止' in note for note in meta['notes']))
        search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
