"""CTC paths, real CPU model plumbing, atomic saves and Flask job contracts."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import soundfile as sf
import app as web
import pipeline as P
import forced_alignment as F
import alignment_worker as W


class CtcTests(unittest.TestCase):
    def test_windows_parent_monitor_never_calls_os_kill(self):
        import ctypes
        kernel = MagicMock()
        kernel.OpenProcess.return_value = 123
        kernel.WaitForSingleObject.return_value = 0
        with patch.object(W.sys, 'platform', 'win32'), patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), patch.object(W.os, 'kill') as kill, patch.object(W.os, '_exit') as stop:
            W.watch_parent(456)
        kill.assert_not_called()
        kernel.OpenProcess.assert_called_once_with(0x00100000, False, 456)
        kernel.CloseHandle.assert_called_once_with(123)
        stop.assert_called_once_with(1)
    def test_timestamps_follow_audio_emissions_not_even_spacing(self):
        logits = np.full((12, 3), .001)
        logits[:, 0] = .998
        logits[2:4] = [.001, .998, .001]
        logits[9:11] = [.001, .001, .998]
        spans = F.ctc_path(np.log(logits), [1, 2], 0)
        self.assertEqual([(s, e) for s, e, _ in spans], [(2, 4), (9, 11)])
        self.assertTrue(all(score > .99 for _, _, score in spans))

    def test_repeated_characters_require_a_blank_between_them(self):
        logits = np.array([[.01, .99], [.99, .01], [.01, .99]])
        spans = F.ctc_path(np.log(logits), [1, 1], 0)
        self.assertEqual([(s, e) for s, e, _ in spans], [(0, 1), (2, 3)])
        with self.assertRaises(P.UserError):
            F.ctc_path(np.log(logits[:2]), [1, 1], 0)

    def test_traditional_display_is_preserved_and_simplified_for_model(self):
        lines, labels, owners = F.transcript('愛你，\n愛我', {'爱': 1, '你': 2, '我': 3}, 'zh')
        self.assertEqual(labels, [1, 2, 1, 3])
        out = F.aligned_lines(lines, owners, [(1, 2, .9), (3, 4, .9), (6, 7, .9), (8, 9, .9)], np.arange(11) / 10, 1)
        lrc = F.enhanced_lrc(out)
        self.assertIn('<00:00.10>愛<00:00.30>你', lrc)
        self.assertIn('，', lrc)
        self.assertEqual(P.parse_lrc(lrc)[0]['text'], '愛你，')

    def test_chinese_model_covers_reported_lyric_characters(self):
        self.assertEqual(F.MODELS['zh'], 'ydshieh/wav2vec2-large-xlsr-53-chinese-zh-cn-gpt')
        # IDs from this model's published vocab.json; these are absent in the old model.
        vocab = {'眠': 4697, '徘': 2534, '徊': 2525, '爱': 4263, '[PAD]': 0}
        lines, labels, owners = F.transcript('愛眠徘徊', vocab, 'zh')
        self.assertEqual(labels, [4263, 4697, 2534, 2525])
        self.assertEqual(owners, [(0, i) for i in range(4)])
        out = F.aligned_lines(lines, owners, [(1, 2, .9), (3, 4, .9), (5, 6, .9), (7, 8, .9)], np.arange(11) / 10, 1)
        self.assertEqual(P.parse_lrc(F.enhanced_lrc(out))[0]['text'], '愛眠徘徊')

    def test_original_traditional_glyph_is_used_when_normalized_glyph_is_missing(self):
        lines, labels, owners = F.transcript('愛臺灣鬱體', {'愛': 2695, '臺': 5637, '灣': 4124, '鬱': 7786, '體': 7768}, 'zh')
        self.assertEqual(labels, [2695, 5637, 4124, 7786, 7768])
        self.assertEqual(lines[0]['text'], '愛臺灣鬱體')

    def test_missing_chinese_character_is_not_misreported_as_a_number(self):
        with self.assertRaises(P.UserError) as error:
            F.transcript('愛龘', {'爱': 1}, 'zh')
        self.assertIn('模型字典仍未涵蓋', str(error.exception))
        self.assertNotIn('數字請改', str(error.exception))

    def test_unsupported_characters_are_not_silently_omitted(self):
        with self.assertRaisesRegex(P.UserError, '不支援'):
            F.transcript('愛你5', {'爱': 1, '你': 2}, 'zh')

    def test_low_confidence_does_not_produce_plausible_fake_timestamps(self):
        lines, labels, owners = F.transcript('AB', {'A': 1, 'B': 2}, 'en')
        with self.assertRaisesRegex(P.UserError, '信心偏低'):
            F.aligned_lines(lines, owners, [(0, 1, .0001), (2, 3, .0001)], np.arange(5), 4)

    def test_real_transformers_cpu_inference_with_local_test_model(self):
        from transformers import Wav2Vec2Config, Wav2Vec2ForCTC, Wav2Vec2CTCTokenizer, Wav2Vec2FeatureExtractor, Wav2Vec2Processor
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'vocab.json').write_text(json.dumps({'[PAD]': 0, 'A': 1, 'B': 2, '|': 3, '[UNK]': 4}))
            tokenizer = Wav2Vec2CTCTokenizer(str(root / 'vocab.json'), unk_token='[UNK]', pad_token='[PAD]', word_delimiter_token='|')
            processor = Wav2Vec2Processor(Wav2Vec2FeatureExtractor(feature_size=1, sampling_rate=16000, padding_value=0, do_normalize=True, return_attention_mask=True), tokenizer)
            processor.save_pretrained(root)
            model = Wav2Vec2ForCTC(Wav2Vec2Config(vocab_size=len(tokenizer), hidden_size=16, num_hidden_layers=1,
                num_attention_heads=2, intermediate_size=32, conv_dim=(8,8,8), conv_stride=(5,2,2), conv_kernel=(10,3,3),
                num_conv_pos_embedding_groups=2, mask_time_prob=0, pad_token_id=0))
            model.save_pretrained(root)
            sf.write(root / 'lead.wav', np.sin(np.arange(16000) * .1).astype(np.float32), 16000)
            with patch.dict(F.MODELS, {'en': str(root)}):
                result = W.align({'language': 'en', 'audio': str(root / 'lead.wav'), 'text': 'AB', 'cache': str(root)})
            self.assertEqual(result[0]['text'], 'AB')
            self.assertTrue(0 <= result[0]['t'] < result[0]['end'] <= 1.01)
            # Random weights validate inference plumbing, not acoustic accuracy.


class SaveAndEndpointTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.song = self.root / 'library/abcdef'
        self.song.mkdir(parents=True)
        (self.song / 'lyrics.lrc').write_text('[00:00.00]原本歌詞\n')
        sf.write(self.song / 'lead.wav', np.zeros(16000), 16000)
        P.write_meta(self.song, {'steps': {}, 'duration': 1})
        for change in (patch.object(P, 'ROOT', self.root), patch.object(P, 'LIB', self.root / 'library')):
            change.start(); self.addCleanup(change.stop)
        self.client = web.app.test_client()

    def worker(self, source):
        (self.root / 'alignment_worker.py').write_text(source)

    def result_worker(self):
        self.worker("""import sys,json
from pathlib import Path
data=json.loads(sys.stdin.readline())
Path(data['result']).write_text(json.dumps({'lines':[{'t':.1,'end':.5,'text':'新歌詞','chars':[{'c':'新','t':.1,'sp':False},{'c':'歌','t':.2,'sp':False},{'c':'詞','t':.3,'sp':False}]}]}))
""")

    def test_success_saves_enhanced_lrc_and_metadata(self):
        self.result_worker()
        F.run(self.song, '新歌詞', 'zh', F.revision(self.song), lambda *args: None)
        self.assertIn('<00:00.10>新<00:00.20>歌', (self.song / 'lyrics.lrc').read_text())
        self.assertEqual(P.read_meta(self.song)['lyrics_source'], 'forced_alignment')

    def test_worker_failure_preserves_existing_lyrics(self):
        before = (self.song / 'lyrics.lrc').read_bytes()
        self.worker('import sys\nsys.stdin.readline()\nsys.exit(139)\n')
        with self.assertRaises(P.UserError):
            F.run(self.song, '新歌詞', 'zh', F.revision(self.song), lambda *args: None)
        self.assertEqual((self.song / 'lyrics.lrc').read_bytes(), before)

    def test_newer_edits_are_not_overwritten(self):
        original = F.revision(self.song)
        (self.song / 'lyrics.lrc').write_text('使用者新修改')
        self.result_worker()
        with self.assertRaisesRegex(P.UserError, '已被修改'):
            F.run(self.song, '新歌詞', 'zh', original, lambda *args: None)
        self.assertEqual((self.song / 'lyrics.lrc').read_text(), '使用者新修改')

    def test_endpoint_queues_expensive_work_and_validates_input(self):
        with patch.object(web.jobs, 'find', return_value=None), patch.object(web.jobs, 'submit', return_value='alignment-job') as submit:
            response = self.client.post('/api/songs/abcdef/lyrics/force-align', json={'text': '正確歌詞', 'language': 'zh'})
        self.assertEqual(response.json, {'job': 'alignment-job'})
        self.assertEqual(submit.call_args.args[:2], ('alignment', 'abcdef'))
        with patch.object(web.FA, 'run') as run:
            submit.call_args.args[2](lambda *args: None)
        self.assertEqual(run.call_args.args[1:3], ('正確歌詞', 'zh'))
        for body in ({'text': ''}, {'text': []}, {'text': '歌詞', 'language': 'ja'}):
            self.assertEqual(self.client.post('/api/songs/abcdef/lyrics/force-align', json=body).status_code, 400)


if __name__ == '__main__':
    unittest.main()
