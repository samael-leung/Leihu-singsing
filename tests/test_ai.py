"""Provider contracts and user-facing Flask workflows without external credentials."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import ai_api as A
import app as web
import pipeline as P

LOCAL = A.PROVIDER == 'ollama'
MODEL_KEY = 'ollama_model' if LOCAL else 'openai_model'
MODEL = 'qwen2.5:14b' if LOCAL else 'gpt-4.1-mini'
TOOL = {'name': 'set_line_times', 'input_schema': {
    'type': 'object', 'properties': {'times': {
        'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2}},
    'required': ['times']}}


def response(text='練習時先放慢速度。', finish='stop'):
    if LOCAL:
        return {'message': {'content': text}, 'done': True,
                'done_reason': 'length' if finish == 'length' else 'stop',
                'prompt_eval_count': 120, 'eval_count': 30}
    return {'choices': [{'message': {'content': text}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 120, 'completion_tokens': 30}}


class AIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lib = self.root / 'library'
        self.lib.mkdir()
        self.patches = [patch.object(P, 'CONFIG_PATH', self.root / 'config.json'),
                        patch.object(P, 'LIB', self.lib),
                        patch.object(A, 'USAGE_PATH', self.root / 'usage.json'),
                        patch.dict(os.environ, {}, clear=True)]
        for p in self.patches: p.start()
        self.addCleanup(self.tmp.cleanup)
        for p in self.patches: self.addCleanup(p.stop)
        cfg = dict(P.DEFAULT_CONFIG)
        if not LOCAL: cfg['openai_api_key'] = 'sk-private-test-key-123456'
        P.save_config(cfg)
        self.client = web.app.test_client()

    def song(self):
        d = self.lib / 'abcdef'
        d.mkdir()
        P.write_meta(d, {'title': '測試歌曲', 'duration': 10, 'steps': {}, 'notes': []})
        (d / 'lyrics.lrc').write_text('原本歌詞', encoding='utf-8')
        return d

    def test_http_request_payload_and_authorization(self):
        with patch.object(A, 'urlopen', return_value=io.BytesIO(json.dumps(response()).encode())) as send:
            text, usage = A.ask_text('請給建議', 1200, 'coach')
        req = send.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(body['model'], MODEL)
        self.assertIn('台灣繁體中文', body['messages'][0]['content'])
        self.assertEqual(usage['input_tokens'], 120)
        self.assertEqual(text, '練習時先放慢速度。')
        if LOCAL:
            self.assertEqual(req.full_url, 'http://127.0.0.1:11434/api/chat')
            self.assertFalse(body['stream'])
            self.assertEqual(body['keep_alive'], 0)
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(usage['cost_usd'], 0)
        else:
            self.assertEqual(req.full_url, 'https://api.openai.com/v1/chat/completions')
            self.assertEqual(req.get_header('Authorization'), 'Bearer sk-private-test-key-123456')
            self.assertEqual(body['max_completion_tokens'], 1200)
            self.assertIsNone(usage['cost_usd'])

    def test_structured_output_contract(self):
        with patch.object(A, '_request', return_value=response('{"times":[1,3]}')) as send:
            data, _ = A.ask_tool('對齊', TOOL, 8000, 'align')
        self.assertEqual(data, {'times': [1,3]})
        body = send.call_args.args[1]
        schema = body['format'] if LOCAL else body['response_format']['json_schema']['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['times']['minItems'], 2)
        if not LOCAL: self.assertTrue(body['response_format']['json_schema']['strict'])

    def test_invalid_structured_results_are_rejected(self):
        for text in ('{}', '{"times":[1]}', '{"times":[true,3]}',
                     '{"times":[1,NaN]}', '{"times":[-1,3]}',
                     '{"times":[3,1]}', '{"times":[1,1]}',
                     '{"times":["1",3]}', 'not JSON'):
            with self.subTest(text=text), patch.object(A, '_request', return_value=response(text)):
                with self.assertRaises(P.UserError): A.ask_tool('對齊', TOOL, 100, 'align')

    def test_truncated_text_is_not_returned(self):
        with patch.object(A, '_request', return_value=response('partial', 'length')):
            with self.assertRaisesRegex(P.UserError, '截斷'): A.ask_text('建議', 10, 'coach')
        self.assertEqual(A.summary()['total']['calls'], 2)

    def test_truncated_advice_retries_once_and_counts_both_requests(self):
        with patch.object(A, '_request', side_effect=[response('partial', 'length'), response('完整建議')]) as send:
            text, usage = A.ask_text('建議', 3000, 'coach')
        self.assertEqual(text, '完整建議')
        bodies = [call.args[1] for call in send.call_args_list]
        limits = [body['options']['num_predict'] if LOCAL else body['max_completion_tokens'] for body in bodies]
        self.assertEqual(limits, [3000, 12000])
        self.assertEqual(usage['input_tokens'], 240)
        self.assertEqual(usage['output_tokens'], 60)
        self.assertEqual(A.summary()['total']['calls'], 2)

    def test_structured_alignment_does_not_retry_truncated_output(self):
        with patch.object(A, '_request', return_value=response('{"times":', 'length')) as send:
            with self.assertRaises(P.UserError): A.ask_tool('對齊', TOOL, 8000, 'align')
        self.assertEqual(send.call_count, 1)

    @unittest.skipIf(LOCAL, 'OpenAI retry pricing')
    def test_retry_cost_includes_both_billed_requests(self):
        cfg=P.load_config(); cfg.update(ai_price_model=MODEL,ai_input_price=0.4,ai_output_price=1.6); P.save_config(cfg)
        with patch.object(A, '_request', side_effect=[response('partial', 'length'), response('完整建議')]):
            _, usage=A.ask_text('建議',3000,'coach')
        self.assertEqual(usage['cost_usd'],0.000192)
        self.assertEqual(A.summary()['total']['cost_usd'],0.000192)

    def test_empty_output_is_rejected(self):
        with patch.object(A, '_request', return_value=response('')):
            with self.assertRaises(P.UserError): A.ask_text('建議', 10, 'coach')

    def test_http_failures_are_actionable_without_leaking_secrets(self):
        for code in (401,403,404,429,500):
            error = HTTPError('http://example', code, 'secret-upstream-text', {}, None)
            with self.subTest(code=code), patch.object(A, 'urlopen', side_effect=error):
                with self.assertRaises(P.UserError) as caught: A.ask_text('建議', 10, 'coach')
                self.assertNotIn('secret-upstream-text', str(caught.exception))
                self.assertNotIn('sk-private', str(caught.exception))

    def test_connection_failure(self):
        with patch.object(A, 'urlopen', side_effect=URLError('offline')):
            with self.assertRaisesRegex(P.UserError, '連不上'): A.ask_text('建議', 10, 'coach')

    def test_invalid_http_response(self):
        for raw in (b'not JSON', b'[]'):
            with self.subTest(raw=raw), patch.object(A, 'urlopen', return_value=io.BytesIO(raw)):
                with self.assertRaises(P.UserError): A.ask_text('建議', 10, 'coach')

    def test_config_never_exposes_legacy_or_active_key(self):
        cfg=P.load_config(); cfg['anthropic_api_key']='old-private-secret'
        cfg['openai_api_key']='sk-private-test-key-123456'; P.save_config(cfg)
        result=self.client.get('/api/config')
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('old-private-secret', result.get_data(as_text=True))
        self.assertNotIn('sk-private-test-key-123456', result.get_data(as_text=True))
        self.assertEqual(result.json['has_key'], not LOCAL)

    def test_settings_dom_matches_frontend(self):
        import re
        html=(P.ROOT/'static/index.html').read_text('utf-8')
        js=(P.ROOT/'static/app.js').read_text('utf-8')
        ids=set(re.findall(r'id="([^"]+)"',html))
        for selector in re.findall(r'\$\("#(cfg-[^"]+|ai-chip)"\)',js):
            self.assertIn(selector,ids)
        self.assertNotIn('/claude/',js)

    @unittest.skipIf(LOCAL, 'OpenAI key and cost settings')
    def test_key_updates_and_unknown_balance(self):
        saved=P.load_config()['openai_api_key']
        self.assertEqual(self.client.post('/api/config',json={'openai_api_key':''}).status_code,200)
        self.assertEqual(P.load_config()['openai_api_key'],saved)
        masked=self.client.get('/api/config').json['openai_api_key']
        self.client.post('/api/config',json={'openai_api_key':masked})
        self.assertEqual(P.load_config()['openai_api_key'],saved)
        self.client.post('/api/config',json={'balance_usd':10})
        with patch.object(A,'_request',return_value=response()): A.ask_text('建議',10,'coach')
        self.assertIsNone(A.summary()['balance']['estimated_usd'])
        self.client.post('/api/config',json={'openai_api_key':'','clear_key':True})
        self.assertFalse(A.ready())

    def test_alignment_endpoint_writes_validated_lyrics(self):
        d=self.song()
        with patch.object(A, '_request', return_value=response('{"times":[1,3]}')):
            result=self.client.post('/api/songs/abcdef/ai/align', json={'text':'第一句\n第二句'})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertIn('[00:01.00]第一句', result.json['lrc'])
        self.assertEqual(P.read_meta(d)['lyrics_source'], A.PROVIDER)
        self.assertEqual((d/'lyrics.lrc').read_text('utf-8'), result.json['lrc'])

    def test_alignment_failure_preserves_existing_lyrics(self):
        d=self.song()
        for text in ('{"times":[2,1]}', '{"times":[1,20]}', '{"times":[1.001,1.002]}'):
            with self.subTest(text=text), patch.object(A, '_request', return_value=response(text)):
                result=self.client.post('/api/songs/abcdef/ai/align', json={'text':'第一句\n第二句'})
                self.assertEqual(result.status_code,400, result.json)
                self.assertEqual((d/'lyrics.lrc').read_text('utf-8'), '原本歌詞')

    def test_coaching_endpoint_persists_advice(self):
        d=self.song(); (d/'takes').mkdir()
        info={'acc':0.8,'mean':-5,'spread':15,'key':0,'speed':1,'lines':[]}
        take=d/'takes'/'abcdef.json'; take.write_text(json.dumps(info))
        with patch.object(A, '_request', return_value=response()):
            result=self.client.post('/api/songs/abcdef/ai/coach', json={'take':'abcdef'})
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(json.loads(take.read_text())['coach'], '練習時先放慢速度。')

    def test_provider_specific_readiness(self):
        if LOCAL:
            with patch.object(A, '_request', return_value={'models':[{'name':MODEL}]}): self.assertTrue(A.ready())
            with patch.object(A, '_request', return_value={'models':[]}): self.assertFalse(A.ready())
            with patch.object(A, '_request', side_effect=P.UserError('offline')): self.assertFalse(A.ready())
        else:
            self.assertTrue(A.ready())
            cfg=P.load_config(); cfg['openai_api_key']=''; P.save_config(cfg)
            self.assertFalse(A.ready())
            with patch.dict(os.environ, {'OPENAI_API_KEY':'environment-test-key'}):
                self.assertTrue(A.ready())
                with patch.object(A, '_request', return_value=response()) as send: A.ask_text('建議',10,'coach')
                self.assertEqual(send.call_args.args[2], 'environment-test-key')
            with self.assertRaises(P.UserError): A.ask_text('建議',10,'coach')

    def test_provider_specific_configuration(self):
        if LOCAL:
            cfg=P.load_config(); cfg['ollama_url']='http://user:password@localhost'; P.save_config(cfg)
            with self.assertRaises(P.UserError): A.ask_text('建議',10,'coach')
        else:
            cfg=P.load_config(); cfg.update(ai_price_model=MODEL,ai_input_price=0.4,ai_output_price=1.6)
            P.save_config(cfg)
            with patch.object(A, '_request', return_value=response()): _,usage=A.ask_text('建議',10,'coach')
            self.assertEqual(usage['cost_usd'],0.000096)
            cfg[MODEL_KEY]='another-model'; P.save_config(cfg)
            with patch.object(A, '_request', return_value=response()): _,usage=A.ask_text('建議',10,'coach')
            self.assertIsNone(usage['cost_usd'])
            self.assertIsNone(A.summary()['total']['cost_usd'])
            for price in (-1,'NaN','bad'):
                r=self.client.post('/api/config',json={'ai_input_price':price})
                self.assertEqual(r.status_code,400)

    @unittest.skipIf(LOCAL, 'OpenAI refusal contract')
    def test_openai_refusal_is_not_advice(self):
        result=response(); result['choices'][0]['message']['refusal']='refused'
        with patch.object(A, '_request', return_value=result):
            with self.assertRaisesRegex(P.UserError,'拒絕'): A.ask_text('建議',10,'coach')


if __name__ == '__main__': unittest.main()
