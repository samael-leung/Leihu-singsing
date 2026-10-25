"""Stem-aware normalization and import lyrics preserve existing custom edits."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

import pipeline as P


class Upstream165Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        for name, value in [('LIB', self.song.parent), ('CONFIG_PATH', self.root / 'config.json')]:
            change = patch.object(P, name, value)
            change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'songaa', 'title': 'Sample', 'duration': 3, 'steps': {'import': True}, 'notes': []})

    def tone(self, amplitude, frequency):
        signal = amplitude * np.sin(2 * np.pi * frequency * np.arange(P.SR) / P.SR)
        return np.stack([signal, signal])

    def test_stem_combinations_are_measured_cached_and_recomputed_after_changes(self):
        stems = {name: self.tone(amplitude, frequency) for name, amplitude, frequency in
                 [('lead', .4, 220), ('back', .05, 440), ('inst', .08, 880)]}
        for name, signal in {**stems, 'mix': sum(stems.values())}.items():
            sf.write(str(self.song / f'{name}.wav'), signal.T, P.SR, subtype='FLOAT')
        original = (self.song / 'lead.wav').read_bytes()
        result = P.measure_stem_loudness(self.song)
        self.assertEqual(len(result['combo_lufs']), 7)
        self.assertGreater(result['combo_lufs']['111'], result['combo_lufs']['011'])
        with patch.object(P, 'read_audio', side_effect=AssertionError('must reuse cache')):
            self.assertEqual(P.measure_stem_loudness(self.song)['combo_lufs'], result['combo_lufs'])
        sf.write(str(self.song / 'inst.wav'), self.tone(.16, 880).T, P.SR, subtype='FLOAT')
        updated = P.measure_stem_loudness(self.song)
        self.assertNotEqual(updated['combo_lufs_sig'], result['combo_lufs_sig'])
        self.assertAlmostEqual(updated['combo_lufs']['001'] - result['combo_lufs']['001'], 6.02, delta=.05)
        self.assertEqual((self.song / 'lead.wav').read_bytes(), original)

    def test_karaoke_normalization_uses_audible_stems_with_safe_fallback(self):
        meta = {'lufs': -8, 'combo_lufs': {'111': -8, '011': -24}}
        self.assertEqual(P.norm_gain_db(meta, {'lead': 0, 'back': 1, 'inst': 1}), P.TARGET_LUFS + 24)
        self.assertEqual(P.norm_gain_db(meta, {'lead': 1, 'back': 1, 'inst': 1}), P.TARGET_LUFS + 8)
        self.assertEqual(P.norm_gain_db({'lufs': -100}), 12)
        self.assertEqual(P.norm_gain_db({'lufs': 0}), -15)

    def test_import_uses_online_lyrics_by_default_but_explicit_recognition_remains_available(self):
        for automatic, steps, expect_recognition in [(False, ['import', 'lyrics'], False),
                                                       (True, ['import', 'lyrics'], True),
                                                       (False, ['lyrics'], True)]:
            with self.subTest(automatic=automatic, steps=steps), \
                 patch.object(P, 'load_config', return_value=dict(P.DEFAULT_CONFIG, auto_recognize_lyrics=automatic)), \
                 patch.object(P, 'step_import'), patch.object(P, 'step_lyrics') as recognize, \
                 patch.object(P, 'search_lyrics_later') as search:
                P.process_song('songaa', steps)(lambda *args: None)
                self.assertEqual(recognize.called, expect_recognition)
                if not expect_recognition:
                    search.assert_called_once_with(self.song, dict(P.DEFAULT_CONFIG, auto_recognize_lyrics=False), apply_first=True)
                    self.assertFalse(P.read_meta(self.song)['lyrics_recognized'])

    def candidate(self):
        return {'id': 'test', 'track': 'Sample', 'artist': 'Artist', 'plain': 'Online lyrics',
                'synced': '[00:01.00]Online lyrics\n', 'duration': 3, 'similarity': None, 'title_match': 1, 'diff': 0}

    def test_online_first_import_applies_real_candidate_and_saves_separate_lyrics(self):
        P.update_meta(self.song, lyrics_recognized=False)
        with patch.object(P, 'find_candidates', return_value=([], [self.candidate()])):
            P.find_and_store_candidates(self.song, P.DEFAULT_CONFIG, apply_first=True)
        self.assertEqual(P.read_meta(self.song)['lyrics_source'], 'online')
        self.assertIn('Online lyrics', (self.song / 'lyrics.lrc').read_text())
        self.assertEqual((self.song / 'lyrics_online.lrc').read_text(), (self.song / 'lyrics.lrc').read_text())

    def test_background_online_lyrics_do_not_overwrite_forced_alignment(self):
        original = '[00:00.10]<00:00.10>Corrected\n'
        (self.song / 'lyrics.lrc').write_text(original)
        P.update_meta(self.song, lyrics_recognized=False, lyrics_source='forced_alignment')
        with patch.object(P, 'find_candidates', return_value=([], [self.candidate()])), patch.object(P, 'apply_candidate') as apply:
            P.find_and_store_candidates(self.song, P.DEFAULT_CONFIG, apply_first=True)
        apply.assert_not_called()
        self.assertEqual((self.song / 'lyrics.lrc').read_text(), original)
        self.assertEqual(P.read_meta(self.song)['lyrics_source'], 'forced_alignment')
