"""Real Japanese dictionary/font checks and isolated model download integrity."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

import app as web
import pipeline as P
import share as SH


class Upstream151Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.song = self.root / 'library' / 'songaa'
        self.song.mkdir(parents=True)
        change = patch.object(P, 'LIB', self.song.parent)
        change.start(); self.addCleanup(change.stop)
        P.write_meta(self.song, {'id': 'songaa', 'steps': {}, 'lyrics_source': 'forced_alignment'})
        self.client = web.app.test_client()

    def test_japanese_lyric_repair_preserves_timing_and_custom_source(self):
        old = '[00:01.25]<00:01.25>明日は來るから\n'
        for name in ['lyrics.lrc', 'lyrics_auto.lrc', 'lyrics_online.lrc']:
            (self.song / name).write_text(old)
        result = self.client.get('/api/songs/songaa/lyrics').json
        for key in ['lrc', 'auto', 'online']:
            self.assertEqual(result[key], old.replace('來', '来'))
        self.assertEqual(result['source'], 'forced_alignment')
        self.assertEqual((self.song / 'lyrics.lrc').read_text(), result['lrc'])
        self.assertEqual(P.to_taiwan('明日は来るから'), '明日は来るから')
        self.assertEqual(P.to_taiwan('亲爱的那不是爱情'), '親愛的那不是愛情')

    def test_real_dictionary_reads_repaired_japanese_and_retains_display_text(self):
        line = '明日は來るから'
        result = self.client.post('/api/furigana', json={'lines': [line, line]})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['state']['state'], 'ready')
        tokens = result.json['ruby'][line]
        self.assertEqual(''.join(base for token in tokens for base, _ in token['p']), line)
        readings = ''.join(reading or base for token in tokens for base, reading in token['p'])
        self.assertIn('くる', readings)
        self.assertTrue(any(token.get('pt') for token in tokens))

    def test_reading_override_is_per_song_and_empty_value_restores_dictionary(self):
        other = self.song.parent / 'songbb'; other.mkdir()
        P.write_meta(other, {'id': 'songbb', 'steps': {}})
        response = self.client.post('/api/songs/songaa/kana', json={'base': '明日', 'reading': 'あした'})
        self.assertEqual(response.json['kana_fix'], {'明日': 'あした'})
        self.assertEqual(self.client.get('/api/songs/songaa/lyrics').json['kana_fix'], {'明日': 'あした'})
        self.assertEqual(self.client.get('/api/songs/songbb/lyrics').json['kana_fix'], {})
        self.assertEqual(self.client.post('/api/songs/songaa/kana', json={'base': '明日', 'reading': ''}).json['kana_fix'], {})

    def test_missing_dictionary_returns_install_status_without_blocking_lyrics(self):
        with patch.object(P, 'kana_ready', return_value=False), patch.object(P, 'start_kana_install') as install:
            response = self.client.post('/api/furigana', json={'lines': ['明日は来るから']})
        install.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertIn('state', response.json)
        self.assertEqual(self.client.get('/api/songs/songaa/lyrics').status_code, 200)

    def test_download_rejects_corrupt_source_then_uses_verified_fallback(self):
        correct = b'verified model bytes'
        target = self.root / 'model.onnx'
        with patch.object(P, '_open', side_effect=[io.BytesIO(b'X' * len(correct)), io.BytesIO(correct)]) as opened:
            P.fetch_file(['https://primary.test/model', 'https://fallback.test/model'], target,
                         len(correct), hashlib.sha256(correct).hexdigest())
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(target.read_bytes(), correct)
        self.assertFalse(target.with_name(target.name + '.part').exists())

    def test_bundled_font_and_export_renderer_work_without_system_font_install(self):
        self.assertTrue(SH.HUNINN.is_file())
        self.addCleanup(SH.set_font_family, 'huninn')
        SH.set_font_family('huninn')
        font = SH._font(40, True)
        self.assertEqual(font._path, SH.HUNINN)
        self.assertIn(ord('歌'), SH._cmap(SH.HUNINN))
        image = Image.new('RGB', (300, 100))
        SH._Draw(ImageDraw.Draw(image)).text((10, 10), '練唱歌詞', font=font, fill='white')
        self.assertIsNotNone(image.getbbox())


if __name__ == '__main__':
    unittest.main()
