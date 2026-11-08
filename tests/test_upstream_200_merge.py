"""Live controls and sheet exports preserve custom state and source lyrics."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import app as web
import hotkeys as HK
import pipeline as P
import score_sheet as SS

_cwd = Path.cwd()
with patch.object(sys, 'stdout'), patch.object(sys, 'stderr'):
    import desktop
os.chdir(_cwd)


class LiveFeatureTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        for change in (patch.object(P, 'LIB', self.song.parent),
                       patch.object(P, 'CONFIG_PATH', self.root / 'config.json'),
                       patch.object(P, 'MODELS', self.root / 'models'),
                       patch.object(web, 'SETLIST_PATH', self.root / 'setlist.json')):
            change.start(); self.addCleanup(change.stop)
        P.MODELS.mkdir()
        P.write_meta(self.song, {'id': 'songaa', 'title': '測試/旋律譜', 'artist': '歌手',
                                'steps': {'pitch': True}, 'duration': 24, 'notes': []})
        pitch = {'hop': .02, 'midi': [60] * 1200,
                 'notes': [[i * 2, i * 2 + 1, 60 + i % 5] for i in range(12)]}
        (self.song / 'pitch.json').write_text(json.dumps(pitch))
        (self.song / 'lyrics.lrc').write_text('[00:01.00]<00:01.00>保<00:02.00>留\n')
        P.save_config(dict(P.DEFAULT_CONFIG, ai_mode='api', api_provider='gemini',
                           gemini_api_key='fixture-private-key', ai_setup_complete=True))
        self.client = web.app.test_client()

    def test_hotkey_parser_accepts_macro_keys_and_rejects_unmodified_typing_keys(self):
        self.assertEqual(HK.parse('Ctrl+Alt+Space'), (3, 32))
        self.assertEqual(HK.parse('F13'), (0, 0x7C))
        for invalid in ('A', 'Space', 'F1', 'Ctrl+Ctrl+A', 'Unknown+A', 'Ctrl+NoSuchKey'):
            with self.subTest(combo=invalid): self.assertIsNone(HK.parse(invalid))

    def test_hotkey_save_survives_reload_and_preserves_provider_secrets(self):
        result = self.client.post('/api/hotkeys', json={'combos': {'play': 'F13', 'now': '', 'unknown': 'bad'}})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['current']['play'], 'F13')
        self.assertEqual(result.json['current']['now'], '')
        saved = P.load_config()
        self.assertEqual(saved['api_provider'], 'gemini')
        self.assertEqual(saved['gemini_api_key'], 'fixture-private-key')
        self.assertEqual(self.client.get('/api/hotkeys').json['current']['play'], 'F13')
        self.assertNotIn('fixture-private-key', self.client.get('/api/hotkeys').text)

    def test_hotkeys_reject_equivalent_duplicates_and_invalid_input_without_saving(self):
        original = P.CONFIG_PATH.read_bytes()
        for combos in ({'now': 'Alt+Ctrl+Space'}, {'now': 'A'}, ['play']):
            with self.subTest(combos=combos):
                result = self.client.post('/api/hotkeys', json={'combos': combos})
                self.assertEqual(result.status_code, 400)
                self.assertEqual(P.CONFIG_PATH.read_bytes(), original)

    def test_hotkey_capture_pause_writes_only_the_app_pause_marker(self):
        with patch.object(P, 'ROOT', self.root):
            self.assertEqual(self.client.post('/api/hotkeys/pause', json={'on': True}).status_code, 200)
            self.assertTrue((self.root / '.hotkeys_pause').exists())
            self.client.post('/api/hotkeys/pause', json={'on': False})
            self.assertFalse((self.root / '.hotkeys_pause').exists())

    def test_setlist_persists_deduplicates_and_starts_a_new_session_after_six_hours(self):
        song = {'id': 'songaa', 'title': 'Title', 'artist': 'Artist', 'key': -2}
        with patch.object(web.time, 'time', return_value=1000):
            self.assertEqual(self.client.post('/api/setlist/add', json=song).status_code, 200)
        with patch.object(web.time, 'time', return_value=1200):
            self.client.post('/api/setlist/add', json=song)
        self.assertEqual(len(self.client.get('/api/setlist').json['items']), 1)
        self.assertEqual(json.loads(web.SETLIST_PATH.read_text())['items'][0]['key'], -2)
        with patch.object(web.time, 'time', return_value=1000 + web.SETLIST_GAP + 1):
            self.client.post('/api/setlist/add', json=dict(song, id='songbb'))
        self.assertEqual([s['id'] for s in web.app.test_client().get('/api/setlist').json['items']], ['songbb'])
        self.client.post('/api/setlist/clear', json={})
        self.assertEqual(self.client.get('/api/setlist').json, {'started': None, 'items': []})

    def test_overlay_reports_artist_and_key_without_losing_lyrics_on_metadata_only_reads(self):
        before = dict(web.OVERLAY)
        self.addCleanup(lambda: web.OVERLAY.update(before))
        self.client.post('/api/overlay', json={'sid': 'songaa', 'title': 'Title', 'artist': 'Artist',
            'key': -2, 'lines': [{'t': 1, 'text': '保留'}], 'playing': False})
        first = self.client.get('/api/overlay').json
        self.assertEqual((first['artist'], first['key']), ('Artist', -2))
        self.assertEqual(first['lines'][0]['text'], '保留')
        again = self.client.get('/api/overlay?ver=' + str(first['ver'])).json
        self.assertNotIn('lines', again)
        self.assertEqual(again['key'], -2)

    def test_real_png_export_in_both_layouts_leaves_enhanced_lyrics_and_metadata_untouched(self):
        original = {p.name: p.read_bytes() for p in self.song.iterdir()}
        for layout, size in [('phone', (1080, 1920)), ('a4', (1654, 2339))]:
            with self.subTest(layout=layout), patch.object(P, 'downloads_dir', return_value=self.root / 'exports'):
                response = self.client.post('/api/songs/songaa/sheet', json={
                    'layout': layout, 'notation': 'both', 'key': -2,
                    'lines': [{'t': 1, 'end': 4, 'text': '保留', 'chars': [{'c': '保', 't': .5}, {'c': '留', 't': 5}]}]})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json['files'])
                self.assertIn('測試 旋律譜', response.json['folder'])
                with Image.open(response.json['files'][0]) as image:
                    self.assertEqual(image.size, size)
                    self.assertEqual(image.format, 'PNG')
                    self.assertTrue(any(low < high for low, high in image.getextrema()))
        self.assertEqual({p.name: p.read_bytes() for p in self.song.iterdir()}, original)

    def test_sheet_handles_clamped_duplicate_times_and_preserves_leading_and_trailing_characters(self):
        line = {'t': 1, 'end': 4, 'text': '邊界', 'chars': [{'c': '前', 't': 0},
                *[{'c': '同', 't': 1} for _ in range(30)], {'c': '後', 't': 10}]}
        chunks = SS._chunks(line, [], 8, 2)
        self.assertEqual(''.join(c['c'] for row in chunks for c in row['chars']), '前' + '同' * 30 + '後')
        self.assertTrue(all(row['end'] > row['t'] for row in chunks))

    def test_sheet_without_pitch_returns_a_user_error_and_does_not_make_an_image(self):
        (self.song / 'pitch.json').write_text(json.dumps({'midi': [], 'notes': []}))
        with patch.object(P, 'downloads_dir', return_value=self.root / 'exports'):
            result = self.client.post('/api/songs/songaa/sheet', json={})
        self.assertEqual(result.status_code, 400)
        self.assertFalse(list((self.root / 'exports').rglob('*.png')))

    def test_duet_cleanup_preserves_current_stems_settings_and_lyrics(self):
        for name in ('male.flac', 'female.wav', 'parts.json', 'lead.flac', 'back.flac', 'inst.flac', 'mix.flac'):
            (self.song / name).write_bytes(b'fixture audio or metadata')
        model = P.MODELS / 'model_chorus_bs_roformer_ep_267_sdr_24.1275.ckpt'
        model.write_bytes(b'obsolete model')
        P.update_meta(self.song, parts_stems=True)
        original = (self.song / 'lyrics.lrc').read_bytes()
        web.remove_duet_leftovers()
        self.assertFalse(model.exists())
        for name in ('male.flac', 'female.wav', 'parts.json'): self.assertFalse((self.song / name).exists())
        for name in ('lead.flac', 'back.flac', 'inst.flac', 'mix.flac'): self.assertTrue((self.song / name).exists())
        self.assertEqual((self.song / 'lyrics.lrc').read_bytes(), original)
        self.assertNotIn('parts_stems', P.read_meta(self.song))
        self.assertTrue(P.CONFIG_PATH.exists())

    def test_windows_hotkey_registration_and_dispatch_using_native_api_contract(self):
        import ctypes
        user32, window = Mock(), Mock()
        user32.RegisterHotKey.return_value = True
        count = 0
        def peek(pointer, *args):
            nonlocal count
            count += 1
            if count == 2:
                pointer._obj.message, pointer._obj.wParam = 0x0312, 1
                return 1
            return 0
        user32.PeekMessageW.side_effect = peek
        with patch.object(desktop, 'ROOT', self.root), \
             patch.object(desktop, 'HOTKEY_STATUS', self.root / 'hotkeys_status.json'), \
             patch.object(desktop, 'HOTKEY_PAUSE', self.root / '.hotkeys_pause'), \
             patch.object(ctypes, 'windll', Mock(user32=user32), create=True), \
             patch.object(desktop.time, 'time', return_value=100), \
             patch.object(desktop.time, 'sleep', side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt): desktop.global_hotkeys(window)
        self.assertEqual(user32.RegisterHotKey.call_count, len(HK.ACTIONS))
        window.evaluate_js.assert_called_once_with("window.liveHotkey && window.liveHotkey('play')")
        self.assertEqual(len(json.loads((self.root / 'hotkeys_status.json').read_text())['ok']), len(HK.ACTIONS))
