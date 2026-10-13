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


def record(model, tin, tout, purpose, song):
    cfg = P.load_config()
    cost = 0.0 if PROVIDER == 'ollama' else None
    if PROVIDER == 'openai' and cfg.get('ai_price_model') == model:
        pin, pout = cfg.get('ai_input_price'), cfg.get('ai_output_price')
        if pin is not None and pout is not None:
            cost = round((tin * float(pin) + tout * float(pout)) / 1_000_000, 6)
    entry = {'time': time.time(), 'provider': PROVIDER, 'model': model,
             'purpose': purpose, 'song': song, 'input_tokens': tin,
             'output_tokens': tout, 'cost_usd': cost}
    with _lock:
        data = _load()
        data['calls'] = (data['calls'] + [entry])[-2000:]
        USAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), 'utf-8')
    return entry


def _sum(calls):
    unpriced = sum(c['cost_usd'] is None for c in calls)
    return {'calls': len(calls), 'input_tokens': sum(c['input_tokens'] for c in calls),
            'output_tokens': sum(c['output_tokens'] for c in calls),
            'cost_usd': None if unpriced else round(sum(c['cost_usd'] for c in calls), 6),
            'unpriced': unpriced}


def summary():
    cfg = P.load_config()
    calls = _load()['calls']
    result = {'last': calls[-1] if calls else None,
              'session': _sum([c for c in calls if c['time'] >= SESSION_START]),
              'total': _sum(calls), 'recent': calls[-8:][::-1], 'balance': None}
    bal, since = cfg.get('balance_usd'), cfg.get('balance_set_at')
    if PROVIDER == 'openai' and bal is not None and since:
        spent = _sum([c for c in calls if c['time'] >= since])['cost_usd']
        result['balance'] = {'entered_usd': float(bal), 'entered_at': since,
                             'spent_since_usd': spent,
                             'estimated_usd': None if spent is None else round(float(bal)-spent, 4)}
    return result


def _request(url, body=None, key=None, timeout=300):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
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
    try:
        return _call(prompt, max_tokens, purpose, song)
    except ResponseTruncated as first:
        # Match upstream's single bounded retry and retain both requests' usage.
        text, second = _call(prompt, max_tokens * 4, purpose, song)
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

PROVIDER = 'ollama'
USAGE_PATH = P.ROOT / 'usage-local.json'


def _settings():
    cfg = P.load_config()
    base = (cfg.get('ollama_url') or 'http://127.0.0.1:11434').rstrip('/')
    parts = urlsplit(base)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise P.UserError('Ollama 網址必須是有效的 HTTP／HTTPS 網址，不可包含帳密或查詢參數。')
    return base, cfg.get('ollama_model') or 'qwen2.5:14b'


def ready():
    try:
        base, model = _settings()
        result = _request(base + '/api/tags', timeout=2)
        return any(m.get('name') == model or m.get('model') == model for m in result.get('models', []))
    except P.UserError:
        return False


def _call(prompt, max_tokens, purpose, song, schema=None):
    base, model = _settings()
    body = {'model': model, 'stream': False, 'keep_alive': 0,
            'messages': [{'role': 'system', 'content': '請使用台灣繁體中文。若指定 JSON 格式，只回傳符合結構的 JSON。'},
                         {'role': 'user', 'content': prompt}],
            'options': {'temperature': 0, 'num_predict': max_tokens, 'num_ctx': 16384}}
    if schema:
        body['format'] = schema
    result = _request(base + '/api/chat', body, timeout=600)
    if result.get('error'):
        raise P.UserError('Ollama 無法執行模型，請檢查本機服務紀錄與可用記憶體。')
    text = result.get('message', {}).get('content')
    usage = record(model, int(result.get('prompt_eval_count') or 0), int(result.get('eval_count') or 0), purpose, song)
    if result.get('done_reason') == 'length':
        raise ResponseTruncated(usage)
    if not result.get('done') or not isinstance(text, str) or not text.strip():
        raise P.UserError('本機模型沒有完成有效回覆，請再試一次。')
    return text.strip(), usage
