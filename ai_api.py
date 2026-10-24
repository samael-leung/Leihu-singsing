"""練唱台 AI 呼叫、結構化歌詞時間與用量紀錄。"""
from __future__ import annotations

import json
import math
import os
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import pipeline as P

_lock = threading.Lock()
SESSION_START = time.time()


def _load():
    try:
        return json.loads(USAGE_PATH.read_text('utf-8'))
    except (OSError, ValueError):
        return {'calls': []}


def record(model, tin, tout, purpose, song, active_provider=None):
    cfg = P.load_config()
    active = active_provider or provider(cfg)
    cost = 0.0 if active == 'ollama' else None
    if active != 'ollama' and cfg.get('ai_price_provider') == active and cfg.get('ai_price_model') == model:
        pin, pout = cfg.get('ai_input_price'), cfg.get('ai_output_price')
        if pin is not None and pout is not None:
            cost = round((tin * float(pin) + tout * float(pout)) / 1_000_000, 6)
    entry = {'time': time.time(), 'provider': active, 'model': model,
             'purpose': purpose, 'song': song, 'input_tokens': tin,
             'output_tokens': tout, 'cost_usd': cost}
    with _lock:
        data = _load()
        data['calls'] = (data['calls'] + [entry])[-2000:]
        P.atomic_write_text(USAGE_PATH, json.dumps(data, ensure_ascii=False, indent=1))
    return entry


def _sum(calls):
    unpriced = sum(c['cost_usd'] is None for c in calls)
    return {'calls': len(calls), 'input_tokens': sum(c['input_tokens'] for c in calls),
            'output_tokens': sum(c['output_tokens'] for c in calls),
            'cost_usd': None if unpriced else round(sum(c['cost_usd'] for c in calls), 6),
            'unpriced': unpriced}


def summary():
    cfg = P.load_config()
    calls = [c for c in _load()['calls'] if c.get('provider') == provider(cfg)]
    result = {'last': calls[-1] if calls else None,
              'session': _sum([c for c in calls if c['time'] >= SESSION_START]),
              'total': _sum(calls), 'recent': calls[-8:][::-1], 'balance': None}
    bal, since = cfg.get('balance_usd'), cfg.get('balance_set_at')
    if provider(cfg) != 'ollama' and cfg.get('balance_provider') == provider(cfg) and bal is not None and since:
        spent = _sum([c for c in calls if c['time'] >= since])['cost_usd']
        result['balance'] = {'entered_usd': float(bal), 'entered_at': since,
                             'spent_since_usd': spent,
                             'estimated_usd': None if spent is None else round(float(bal)-spent, 4)}
    return result


def _request(url, body=None, key=None, timeout=300, extra_headers=None):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    headers.update(extra_headers or {})
    req = Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as e:
        # Do not echo request headers, credentials, or upstream response bodies.
        if e.code in (401, 403):
            raise P.UserError('AI 服務拒絕存取，請確認金鑰與存取權限。') from e
        if e.code == 404:
            raise P.UserError('找不到 AI 模型或服務網址；本機模型請先執行 ollama pull。') from e
        if e.code == 429:
            raise P.UserError('AI 服務額度不足或請求過於頻繁，請檢查帳戶後稍後再試。') from e
        raise P.UserError(f'AI 服務回應錯誤（HTTP {e.code}）。') from e
    except (URLError, TimeoutError, socket.timeout) as e:
        raise P.UserError('連不上 AI 服務或等待逾時，請確認服務已啟動及網路設定。') from e
    except (ValueError, UnicodeError) as e:
        raise P.UserError('AI 服務回傳了無法解析的 JSON。') from e
    if not isinstance(result, dict):
        raise P.UserError('AI 服務回傳格式不正確。')
    return result


def _validate(data, schema):
    if not isinstance(data, dict) or set(data) != {'times'}:
        raise P.UserError('AI 沒有回傳正確的歌詞時間格式。')
    times = data['times']
    rule = schema['properties']['times']
    if not isinstance(times, list) or not rule.get('minItems', 0) <= len(times) <= rule.get('maxItems', float('inf')):
        raise P.UserError('AI 回傳的時間數量與歌詞行數不符。')
    if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in times):
        raise P.UserError('AI 回傳的歌詞時間必須是有限的非負數字。')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise P.UserError('AI 回傳的歌詞時間沒有遞增，請再試一次。')
    return data


class ResponseTruncated(P.UserError):
    def __init__(self, usage):
        super().__init__('AI 回覆被截斷，請縮短輸入或分段處理。')
        self.usage = usage


def ask_text(prompt, max_tokens, purpose, song=''):
    cfg = P.load_config()
    try:
        return _call(prompt, max_tokens, purpose, song, cfg=cfg)
    except ResponseTruncated as first:
        # Match upstream's single bounded retry and retain both requests' usage.
        text, second = _call(prompt, max_tokens * 4, purpose, song, cfg=cfg)
        usage = dict(second)
        for key in ('input_tokens', 'output_tokens'):
            usage[key] += first.usage[key]
        a, b = first.usage['cost_usd'], second['cost_usd']
        usage['cost_usd'] = None if a is None or b is None else round(a + b, 6)
        return text, usage


def ask_tool(prompt, tool, max_tokens, purpose, song=''):
    schema = dict(tool['input_schema'], additionalProperties=False)
    text, usage = _call(prompt, max_tokens, purpose, song, schema)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise P.UserError('AI 沒有回傳有效的 JSON 歌詞時間，請再試一次。') from e
    return _validate(data, schema), usage

USAGE_PATH = P.ROOT / 'usage-ai-choice.json'
API_PROVIDERS = ('openai', 'claude', 'gemini')
KEYS = {'openai': ('openai_api_key', 'OPENAI_API_KEY'),
        'claude': ('anthropic_api_key', 'ANTHROPIC_API_KEY'),
        'gemini': ('gemini_api_key', 'GEMINI_API_KEY')}
MODELS = {'openai': ('openai_model', 'gpt-4.1-mini'),
          'claude': ('claude_model', 'claude-sonnet-4-6'),
          'gemini': ('gemini_model', 'gemini-2.5-flash')}


def provider(cfg=None):
    cfg = P.load_config() if cfg is None else cfg
    mode = cfg.get('ai_mode', 'local')
    if mode == 'local':
        return 'ollama'
    if mode != 'api' or cfg.get('api_provider') not in API_PROVIDERS:
        raise P.UserError('請在設定選擇本機模型，或有效的 API 供應商。')
    return cfg['api_provider']


def _settings(cfg=None):
    cfg = P.load_config() if cfg is None else cfg
    base = (cfg.get('ollama_url') or 'http://127.0.0.1:11434').rstrip('/')
    parts = urlsplit(base)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise P.UserError('Ollama 網址必須是有效的 HTTP／HTTPS 網址，不可包含帳密或查詢參數。')
    return base, cfg.get('ollama_model') or 'qwen2.5:3b'


def _key(cfg, active):
    field, env = KEYS[active]
    return cfg.get(field) or os.environ.get(env) or ''


def ready(cfg=None):
    cfg = P.load_config() if cfg is None else cfg
    try:
        active = provider(cfg)
        if active != 'ollama':
            return bool(_key(cfg, active))
        base, model = _settings(cfg)
        result = _request(base + '/api/tags', timeout=2)
        names = {model, model if ':' in model else model + ':latest'}
        return any(m.get('name') in names or m.get('model') in names for m in result.get('models', []))
    except P.UserError:
        return False


def _call(prompt, max_tokens, purpose, song, schema=None, cfg=None):
    cfg = P.load_config() if cfg is None else cfg
    active = provider(cfg)
    instruction = '請使用台灣繁體中文。若指定 JSON 格式，只回傳符合結構的 JSON。'
    if active == 'ollama':
        base, model = _settings(cfg)
        body = {'model': model, 'stream': False, 'keep_alive': 0,
                'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': prompt}],
                'options': {'temperature': 0, 'num_predict': max_tokens,
                            'num_ctx': int(cfg.get('ollama_num_ctx') or 4096)}}
        if schema:
            body['format'] = schema
        result = _request(base + '/api/chat', body, timeout=600)
        usage = record(model, int(result.get('prompt_eval_count') or 0), int(result.get('eval_count') or 0), purpose, song, active)
        text = result.get('message', {}).get('content')
        finish = result.get('done_reason')
        complete = result.get('done') and not result.get('error')
    else:
        key = _key(cfg, active)
        if not key:
            raise P.UserError(f'還沒設定 {active} API 金鑰，請到設定輸入。')
        field, default = MODELS[active]
        model = cfg.get(field) or default
        if active == 'openai':
            body = {'model': model, 'max_completion_tokens': max_tokens,
                    'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': prompt}]}
            if schema:
                body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'set_line_times', 'strict': True, 'schema': schema}}
            result = _request('https://api.openai.com/v1/chat/completions', body, key)
            raw = result.get('usage') or {}
            usage = record(model, int(raw.get('prompt_tokens') or 0), int(raw.get('completion_tokens') or 0), purpose, song, active)
            choices = result.get('choices') or []
            choice = choices[0] if choices else {}
            message = choice.get('message') or {}
            if message.get('refusal'):
                raise P.UserError('OpenAI 拒絕這次請求，請調整輸入內容。')
            text, finish = message.get('content'), choice.get('finish_reason')
            complete = finish == 'stop'
        elif active == 'claude':
            body = {'model': model, 'max_tokens': max_tokens, 'system': instruction,
                    'messages': [{'role': 'user', 'content': prompt}]}
            if schema:
                body['tools'] = [{'name': 'set_line_times', 'description': '回傳每行歌詞的開始秒數', 'input_schema': schema}]
                body['tool_choice'] = {'type': 'tool', 'name': 'set_line_times'}
            result = _request('https://api.anthropic.com/v1/messages', body,
                              extra_headers={'x-api-key': key, 'anthropic-version': '2023-06-01'})
            raw = result.get('usage') or {}
            tin = sum(int(raw.get(k) or 0) for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
            usage = record(model, tin, int(raw.get('output_tokens') or 0), purpose, song, active)
            content = result.get('content') or []
            if schema:
                tool = next((b for b in content if b.get('type') == 'tool_use' and b.get('name') == 'set_line_times'), None)
                text = json.dumps(tool['input']) if tool and isinstance(tool.get('input'), dict) else None
            else:
                text = ''.join(b.get('text', '') for b in content if b.get('type') == 'text')
            finish = result.get('stop_reason')
            complete = finish == ('tool_use' if schema else 'end_turn')
        else:
            import re
            model = model.removeprefix('models/')
            if not re.fullmatch(r'[A-Za-z0-9._-]+', model):
                raise P.UserError('Gemini 模型名稱格式不正確。')
            generation = {'maxOutputTokens': max_tokens}
            if schema:
                generation.update(responseMimeType='application/json', responseJsonSchema=schema)
            body = {'systemInstruction': {'parts': [{'text': instruction}]},
                    'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                    'generationConfig': generation}
            result = _request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', body,
                              extra_headers={'x-goog-api-key': key})
            raw = result.get('usageMetadata') or {}
            usage = record(model, int(raw.get('promptTokenCount') or 0),
                           int(raw.get('candidatesTokenCount') or 0) + int(raw.get('thoughtsTokenCount') or 0), purpose, song, active)
            candidates = result.get('candidates') or []
            candidate = candidates[0] if candidates else {}
            text = ''.join(p.get('text', '') for p in (candidate.get('content') or {}).get('parts', []) if not p.get('thought'))
            finish = candidate.get('finishReason')
            complete = finish == 'STOP'
    if finish in ('length', 'max_tokens', 'MAX_TOKENS'):
        raise ResponseTruncated(usage)
    if not complete or not isinstance(text, str) or not text.strip():
        raise P.UserError(f'{active} 沒有完成有效回覆，可能被安全規則拒絕；請調整輸入後再試。')
    return text.strip(), usage
