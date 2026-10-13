"""Multi-provider, secret handling and hardware-selection contracts."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_api as A
import app as web
import model_setup as M
import pipeline as P

TOOL = {'name': 'set_line_times', 'input_schema': {'type': 'object', 'properties': {
    'times': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2}}, 'required': ['times']}}


def reply(provider, structured=False, truncated=False):
    text = '{"times":[1,3]}' if structured else '先放慢速度練習。'
    if provider == 'ollama':
        return {'message': {'content': text}, 'done': True, 'done_reason': 'length' if truncated else 'stop',
                'prompt_eval_count': 100, 'eval_count': 20}
    if provider == 'openai':
        return {'choices': [{'message': {'content': text}, 'finish_reason': 'length' if truncated else 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}
    if provider == 'claude':
        content = [{'type': 'tool_use', 'name': 'set_line_times', 'input': {'times': [1, 3]}}] if structured else [{'type': 'text', 'text': text}]
        return {'content': content, 'stop_reason': 'max_tokens' if truncated else 'tool_use' if structured else 'end_turn',
                'usage': {'input_tokens': 100, 'output_tokens': 20}}
    return {'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'MAX_TOKENS' if truncated else 'STOP'}],
            'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20, 'thoughtsTokenCount': 5}}


class ProviderChoiceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.client = web.app.test_client()
        for change in (patch.object(P, 'CONFIG_PATH', self.root / 'config.json'),
                       patch.object(P, 'LIB', self.root / 'library'),
                       patch.object(A, 'USAGE_PATH', self.root / 'usage.json'),
                       patch.dict(os.environ, {}, clear=True)):
            change.start()
            self.addCleanup(change.stop)
        self.configure('ollama')

    def configure(self, active):
        cfg = dict(P.DEFAULT_CONFIG, ai_mode='local' if active == 'ollama' else 'api',
                   api_provider=active if active != 'ollama' else 'openai', ollama_auto_model=False)
        for field, _ in A.KEYS.values():
            cfg[field] = 'private-test-key'
        P.save_config(cfg)
        return cfg

    def test_native_authentication_and_response_contracts(self):
        for active in ('ollama', 'openai', 'claude', 'gemini'):
            with self.subTest(active=active):
                self.configure(active)
                with patch.object(A, 'urlopen', return_value=io.BytesIO(json.dumps(reply(active)).encode())) as send:
                    text, usage = A.ask_text('練習建議', 100, 'coach')
                request = send.call_args.args[0]
                self.assertEqual(text, '先放慢速度練習。')
                self.assertEqual(usage['provider'], active)
                self.assertEqual(usage['input_tokens'], 100)
                self.assertEqual(usage['output_tokens'], 25 if active == 'gemini' else 20)
                self.assertNotIn('private-test-key', request.full_url)
                self.assertEqual(request.get_header('Authorization'), 'Bearer private-test-key' if active == 'openai' else None)
                self.assertEqual(request.get_header('X-api-key'), 'private-test-key' if active == 'claude' else None)
                self.assertEqual(request.get_header('X-goog-api-key'), 'private-test-key' if active == 'gemini' else None)
                if active == 'claude':
                    self.assertEqual(request.get_header('Anthropic-version'), '2023-06-01')
                self.assertEqual(usage['cost_usd'], 0 if active == 'ollama' else None)

    def test_each_provider_requests_and_validates_structured_alignment(self):
        for active in ('ollama', 'openai', 'claude', 'gemini'):
            with self.subTest(active=active):
                self.configure(active)
                with patch.object(A, '_request', return_value=reply(active, structured=True)) as send:
                    data, _ = A.ask_tool('對齊歌詞', TOOL, 100, 'align')
                self.assertEqual(data['times'], [1, 3])
                body = send.call_args.args[1]
                if active == 'ollama':
                    schema = body['format']
                elif active == 'openai':
                    self.assertTrue(body['response_format']['json_schema']['strict'])
                    schema = body['response_format']['json_schema']['schema']
                elif active == 'claude':
                    self.assertEqual(body['tool_choice'], {'type': 'tool', 'name': 'set_line_times'})
                    schema = body['tools'][0]['input_schema']
                else:
                    self.assertEqual(body['generationConfig']['responseMimeType'], 'application/json')
                    schema = body['generationConfig']['responseJsonSchema']
                self.assertEqual(schema['properties']['times']['minItems'], 2)
                self.assertFalse(schema['additionalProperties'])

    def test_truncated_advice_retries_once_for_all_providers(self):
        for active in ('ollama', 'openai', 'claude', 'gemini'):
            with self.subTest(active=active):
                self.configure(active)
                with patch.object(A, '_request', side_effect=[reply(active, truncated=True), reply(active)]) as send:
                    _, usage = A.ask_text('建議', 100, 'coach')
                self.assertEqual(send.call_count, 2)
                self.assertEqual(usage['input_tokens'], 200)
                self.assertEqual(usage['output_tokens'], 50 if active == 'gemini' else 40)
                first, second = [call.args[1] for call in send.call_args_list]
                if active == 'ollama':
                    self.assertEqual(second['options']['num_predict'], first['options']['num_predict'] * 4)
                elif active == 'openai':
                    self.assertEqual(second['max_completion_tokens'], first['max_completion_tokens'] * 4)
                elif active == 'claude':
                    self.assertEqual(second['max_tokens'], first['max_tokens'] * 4)
                else:
                    self.assertEqual(second['generationConfig']['maxOutputTokens'], first['generationConfig']['maxOutputTokens'] * 4)
                with patch.object(A, '_request', return_value=reply(active, truncated=True)) as send:
                    with self.assertRaises(A.ResponseTruncated):
                        A.ask_text('建議', 100, 'coach')
                self.assertEqual(send.call_count, 2)

    def test_provider_switch_during_request_does_not_change_retry_provider(self):
        self.configure('openai')
        def request(url, *args, **kwargs):
            self.assertEqual(url, 'https://api.openai.com/v1/chat/completions')
            self.configure('gemini')
            return reply('openai', truncated=send.call_count == 1)
        with patch.object(A, '_request', side_effect=request) as send:
            _, usage = A.ask_text('建議', 100, 'coach')
        self.assertEqual(usage['provider'], 'openai')
        self.assertTrue(all(c['provider'] == 'openai' for c in A._load()['calls']))

    def test_keys_are_private_and_blank_updates_preserve_them(self):
        self.configure('openai')
        result = self.client.get('/api/config')
        self.assertNotIn('private-test-key', result.get_data(as_text=True))
        for field, _ in A.KEYS.values():
            self.assertNotIn(field, result.json)
            self.client.post('/api/config', json={field: ''})
            self.assertEqual(P.load_config()[field], 'private-test-key')
        self.client.post('/api/config', json={'clear_api_key': 'gemini'})
        self.assertEqual(P.load_config()['gemini_api_key'], '')
        self.assertEqual(P.load_config()['openai_api_key'], 'private-test-key')

    def test_environment_keys_and_missing_keys_for_all_api_providers(self):
        for active in A.API_PROVIDERS:
            with self.subTest(active=active):
                cfg = self.configure(active)
                field, env = A.KEYS[active]
                cfg[field] = ''
                P.save_config(cfg)
                self.assertFalse(A.ready())
                with self.assertRaises(P.UserError):
                    A.ask_text('建議', 10, 'coach')
                with patch.dict(os.environ, {env: 'environment-test-key'}):
                    self.assertTrue(A.ready())
                    self.assertTrue(self.client.get('/api/config').json['has_keys'][active])

    def test_api_mode_never_prepares_local_models(self):
        self.configure('openai')
        with patch.object(web.MS, 'prepare') as prepare, patch.object(web.jobs, 'submit') as submit:
            self.assertEqual(self.client.post('/api/ai/prepare', json={}).status_code, 400)
        prepare.assert_not_called()
        submit.assert_not_called()

    def test_auto_local_choice_and_job_snapshot(self):
        recommendation = {'model': 'qwen2.5:14b', 'num_ctx': 16384}
        with patch.object(web.MS, 'recommend', return_value=recommendation):
            response = self.client.post('/api/config', json={'ai_mode': 'local', 'ollama_auto_model': True})
        self.assertEqual(response.json['ollama_model'], 'qwen2.5:14b')
        with patch.object(web.jobs, 'find', return_value=None), patch.object(web.jobs, 'submit', return_value='test-job') as submit:
            self.assertEqual(self.client.post('/api/ai/prepare', json={}).json['job'], 'test-job')
        worker = submit.call_args.args[2]
        self.configure('openai')
        with patch.object(web.MS, 'prepare') as prepare:
            worker(lambda *args: None)
        self.assertEqual(prepare.call_args.args[0]['ai_mode'], 'local')
        self.assertEqual(prepare.call_args.args[0]['ollama_model'], 'qwen2.5:14b')

    def test_invalid_configuration_is_rejected_atomically(self):
        before = P.CONFIG_PATH.read_text()
        for body in ({'ai_mode': 'bad'}, {'api_provider': 'bad'}, {'ollama_auto_model': 'yes'},
                     {'ollama_num_ctx': 0}, {'ai_input_price': 'NaN'}, {'ai_output_price': -1}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/config', json=body).status_code, 400)
                self.assertEqual(P.CONFIG_PATH.read_text(), before)

    def test_ledger_is_separated_by_selected_provider(self):
        for active in A.API_PROVIDERS:
            self.configure(active)
            with patch.object(A, '_request', return_value=reply(active)):
                A.ask_text('建議', 10, 'coach')
        self.assertEqual(len(A._load()['calls']), 3)
        for active in A.API_PROVIDERS:
            self.configure(active)
            self.assertEqual(A.summary()['total']['calls'], 1)
            self.assertEqual(A.summary()['last']['provider'], active)

    def test_gemini_unsafe_model_name_does_not_make_a_request(self):
        cfg = self.configure('gemini')
        cfg['gemini_model'] = 'x?key=bad'
        P.save_config(cfg)
        with patch.object(A, '_request') as send:
            with self.assertRaises(P.UserError):
                A.ask_text('建議', 10, 'coach')
        send.assert_not_called()

    def test_structured_truncation_is_never_retried_for_any_provider(self):
        for active in ('ollama', 'openai', 'claude', 'gemini'):
            with self.subTest(active=active):
                self.configure(active)
                with patch.object(A, '_request', return_value=reply(active, structured=True, truncated=True)) as send:
                    with self.assertRaises(A.ResponseTruncated):
                        A.ask_tool('對齊歌詞', TOOL, 100, 'align')
                send.assert_called_once()

    def test_api_estimates_require_provider_and_model_price_match(self):
        cfg = self.configure('openai')
        cfg.update(ai_price_provider='openai', ai_price_model='gpt-4.1-mini', ai_input_price=.4, ai_output_price=1.6)
        P.save_config(cfg)
        with patch.object(A, '_request', return_value=reply('openai')):
            _, usage = A.ask_text('建議', 100, 'coach')
        self.assertEqual(usage['cost_usd'], .000072)
        cfg['ai_price_provider'] = 'claude'
        P.save_config(cfg)
        with patch.object(A, '_request', return_value=reply('openai')):
            _, usage = A.ask_text('建議', 100, 'coach')
        self.assertIsNone(usage['cost_usd'])

    def test_api_startup_does_not_start_ollama(self):
        cfg = self.configure('openai')
        cfg['ai_setup_complete'] = True
        P.save_config(cfg)
        with patch.object(web.sys, 'platform', 'win32'), patch.object(web.sys, 'argv', ['app.py', '--no-browser']), patch.object(web, 'watch_parent'), patch.object(web.app, 'run'), patch.object(M.O, 'ensure_service') as ensure:
            web.main()
        ensure.assert_not_called()

    def test_mac_local_bootstrap_installs_ollama_only_when_needed(self):
        cfg = self.configure('ollama')
        with patch.object(M.sys, 'platform', 'darwin'), patch.object(P, 'ROOT', self.root), patch.object(M.O, 'service_ready', return_value=False), patch.object(M.O, 'find_ollama', return_value=None), patch.object(M.shutil, 'which', return_value='/opt/homebrew/bin/brew'), patch.object(M.subprocess, 'run') as install, patch.object(M.O, 'ensure_service') as ensure, patch.object(M.O, 'prepare_model') as download:
            install.return_value.returncode = 0
            M.prepare(cfg, lambda *args: None)
        self.assertEqual(install.call_args.args[0], ['/opt/homebrew/bin/brew', 'install', 'ollama'])
        ensure.assert_called_once_with(cfg['ollama_url'], self.root / 'logs')
        self.assertEqual(download.call_args.args[:2], (cfg['ollama_url'], cfg['ollama_model']))

    def test_mac_existing_ollama_is_reused(self):
        cfg = self.configure('ollama')
        with patch.object(M.sys, 'platform', 'darwin'), patch.object(M.O, 'service_ready', return_value=True), patch.object(M.subprocess, 'run') as install, patch.object(M.O, 'ensure_service'), patch.object(M.O, 'prepare_model'):
            M.prepare(cfg, lambda *args: None)
        install.assert_not_called()


class HardwareChoiceTests(unittest.TestCase):
    def info(self, ram=32, platform='win32', free=None):
        return {'platform': platform, 'arch': 'arm64' if platform == 'darwin' else 'AMD64', 'ram_gb': ram,
                'gpus': [] if free is None else [{'name': 'RTX test', 'total_gb': 24, 'free_gb': free}]}

    def test_m2_pro_32gb_selects_7b(self):
        result = M.recommend(self.info(platform='darwin'))
        self.assertEqual(result['model'], 'qwen2.5:7b')
        self.assertEqual(result['num_ctx'], 8192)

    def test_24gb_gpu_and_96gb_ram_selects_14b(self):
        self.assertEqual(M.recommend(self.info(ram=96, free=24))['model'], 'qwen2.5:14b')

    def test_available_vram_limits_recommendation(self):
        for free, size in ((12, '7b'), (6, '3b'), (2, '1.5b')):
            self.assertEqual(M.recommend(self.info(free=free))['model'], 'qwen2.5:' + size)

    def test_cpu_and_unknown_hardware_use_small_model(self):
        self.assertEqual(M.recommend(self.info())['model'], 'qwen2.5:3b')
        self.assertEqual(M.recommend(self.info(ram=0))['model'], 'qwen2.5:1.5b')

    def test_mac_detection_reads_memory_without_nvidia(self):
        with patch.object(M.sys, 'platform', 'darwin'), patch.object(M.platform, 'machine', return_value='arm64'), patch.object(M.subprocess, 'check_output', return_value=str(32 * 1024**3)), patch.object(M.shutil, 'which', return_value=None):
            self.assertEqual(M.recommend()['model'], 'qwen2.5:7b')


if __name__ == '__main__':
    unittest.main()
