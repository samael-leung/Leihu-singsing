"""Audio-based CTC lyric alignment; no generative-model/API timestamps."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pipeline as P

MODELS = {'zh': 'ydshieh/wav2vec2-large-xlsr-53-chinese-zh-cn-gpt',
          'en': 'facebook/wav2vec2-base-960h'}
UNITS = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]|[^\s\u3400-\u9fff\uf900-\ufaff]+')


def transcript(text, vocab, language, delimiter='|'):
    """Keep original display units while normalizing model labels."""
    converter = None
    if language == 'zh':
        from opencc import OpenCC
        converter = OpenCC('t2s')
    lines, labels, owners, missing = [], [], [], []
    for line in [s.strip() for s in text.splitlines() if s.strip()]:
        units = []
        row = len(lines)
        for match in UNITS.finditer(line):
            index = len(units)
            unit = {'c': match.group(), 'sp': bool(re.match(r'\s', line[match.end():]))}
            units.append(unit)
            for character in unit['c']:
                if not character.isalnum():
                    continue
                normalized = converter.convert(character) if converter else character
                # Training text uses simplified Chinese; keep traditional display and
                # try the original glyph if its normalized form is absent.
                candidates = (normalized, normalized.upper(), normalized.lower(), character)
                label = next((vocab[c] for c in candidates if c in vocab), None)
                if label is None:
                    missing.append(character)
                else:
                    labels.append(label)
                    owners.append((row, index))
            if language == 'en' and unit['sp'] and delimiter in vocab:
                labels.append(vocab[delimiter]); owners.append(None)
        if not any(owner and owner[0] == row for owner in owners):
            raise P.UserError('每行歌詞都必須包含可對齊的文字。')
        lines.append({'text': line, 'chars': units})
        if language == 'en' and delimiter in vocab:
            labels.append(vocab[delimiter]); owners.append(None)
    while owners and owners[-1] is None:
        labels.pop(); owners.pop()
    if missing:
        characters = ''.join(dict.fromkeys(missing))[:30]
        advice = ('數字請改成實際唱出的文字。' if any(c.isdigit() for c in missing) else '')
        advice += '請確認所選語言；若是正確的中文歌詞，表示模型字典仍未涵蓋這些字，不需要改寫原歌詞。' if language == 'zh' else '請確認所選語言；中文歌詞請選中文普通話。'
        raise P.UserError('對齊模型不支援這些字元：' + characters + '。' + advice)
    return lines, labels, owners


def ctc_path(log_probs, labels, blank):
    """Viterbi CTC path with blank states and repeated-label constraints."""
    frames = len(log_probs)
    needed = len(labels) + sum(a == b for a, b in zip(labels, labels[1:]))
    if not labels or frames < needed or frames * (2 * len(labels) + 1) > 120_000_000:
        raise P.UserError('歌詞或音訊太長／字數不適合整段對齊，請先使用較短的歌曲與完整歌詞。')
    states = np.full(2 * len(labels) + 1, blank, dtype=np.int32)
    states[1::2] = labels
    skip = np.zeros(len(states), dtype=bool)
    skip[2:] = (states[2:] != blank) & (states[2:] != states[:-2])
    previous = np.full(len(states), -np.inf, dtype=np.float32)
    previous[0] = 0
    trace = np.empty((frames, len(states)), dtype=np.uint8)
    for frame in range(frames):
        one = np.concatenate(([-np.inf], previous[:-1]))
        two = np.concatenate(([-np.inf, -np.inf], previous[:-2]))
        two[~skip] = -np.inf
        choices = np.stack((previous, one, two))
        trace[frame] = choices.argmax(axis=0)
        previous = choices.max(axis=0) + log_probs[frame, states]
    state = len(states) - 1 if previous[-1] >= previous[-2] else len(states) - 2
    if not math.isfinite(float(previous[state])):
        raise P.UserError('找不到完整的歌詞對齊路徑。')
    spans = [[] for _ in labels]
    for frame in range(frames - 1, -1, -1):
        if state % 2:
            spans[state // 2].append(frame)
        state -= int(trace[frame, state])
    if any(not span for span in spans):
        raise P.UserError('部分歌詞沒有可對齊的音訊。')
    return [(min(span), max(span) + 1,
             float(np.exp(log_probs[span, token]).mean())) for token, span in zip(labels, spans)]


def aligned_lines(lines, owners, spans, frame_times, duration):
    scores = []
    for owner, (start, end, score) in zip(owners, spans):
        if owner is None:
            continue
        scores.append(score)
        unit = lines[owner[0]]['chars'][owner[1]]
        unit['t'] = min(unit.get('t', duration), float(frame_times[start]))
        unit['end'] = max(unit.get('end', 0), float(frame_times[end]))
        unit['score'] = min(unit.get('score', 1), score)
    if not scores or sum(score < .01 for score in scores) / len(scores) > .25:
        raise P.UserError('太多歌詞與音訊的對齊信心偏低；請確認歌詞完整、順序正確、語言與演唱版本一致。原歌詞未更動。')
    previous = -1
    for line in lines:
        timed = [unit for unit in line['chars'] if 't' in unit]
        line['t'], line['end'] = timed[0]['t'], timed[-1]['end']
        if not 0 <= line['t'] < line['end'] <= duration + .01 or round(line['t'], 2) <= previous:
            raise P.UserError('對齊結果的句子時間不合理；原歌詞未更動。')
        previous = round(line['t'], 2)
        for index, unit in enumerate(line['chars']):
            if 't' not in unit:
                earlier = [u for u in line['chars'][:index] if 'end' in u]
                unit['t'] = earlier[-1]['end'] if earlier else line['t']
    return lines


def enhanced_lrc(lines):
    return '\n'.join('[' + P.fmt_lrc_time(line['t']) + ']' + ''.join(
        '<' + P.fmt_lrc_time(unit['t']) + '>' + unit['c'] + (' ' if unit['sp'] else '')
        for unit in line['chars']) for line in lines) + '\n'


def revision(d):
    path = d / 'lyrics.lrc'
    return hashlib.sha256(path.read_bytes() if path.exists() else b'').hexdigest()


def run(d, text, language, original_revision, report):
    """Native/model work is isolated; commit only a complete, current result."""
    if language not in MODELS:
        raise P.UserError('強制對齊目前支援中文普通話與英文。')
    if not P.stem_path(d, 'lead').is_file():
        raise P.UserError('請先完成分軌，強制對齊需要主唱音訊。')
    (P.ROOT / 'logs').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='alignment-', dir=d) as temporary:
        result_file = Path(temporary) / 'result.json'
        payload = {'audio': str(P.stem_path(d, 'lead').resolve()), 'text': text, 'language': language, 'model': MODELS[language],
                   'cache': str((P.MODELS / 'alignment').resolve()), 'result': str(result_file.resolve()),
                   'parent_pid': os.getpid()}
        process = subprocess.Popen([sys.executable, '-u', str(P.ROOT / 'alignment_worker.py')],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace',
                                   env=dict(os.environ, PYTHONFAULTHANDLER='1',
                                            HF_HOME=payload['cache'], HF_XET_CACHE=str(Path(payload['cache']) / 'xet')))
        try:
            process.stdin.write(json.dumps(payload) + '\n'); process.stdin.close()
            with open(P.ROOT / 'logs/alignment-worker.log', 'a', encoding='utf-8') as log:
                for line in process.stdout:
                    log.write(line); log.flush()
                    if line.startswith('LEIHU_ALIGN_PROGRESS '):
                        event = json.loads(line[len('LEIHU_ALIGN_PROGRESS '):])
                        report(event['step'], event['progress'])
            code = process.wait()
            if code or not result_file.is_file():
                raise P.UserError('強制對齊未完成；首次需連網下載模型。詳情見 logs/alignment-worker.log，原歌詞未更動。')
            result = json.loads(result_file.read_text('utf-8'))
            if result.get('error'):
                raise P.UserError(result['error'])
            with P._META_LOCK:
                if revision(d) != original_revision:
                    raise P.UserError('對齊期間歌詞已被修改，沒有覆蓋較新的歌詞；請重試。')
                lrc = enhanced_lrc(result['lines'])
                target = d / 'lyrics.lrc'
                staged = Path(temporary) / 'lyrics.lrc'
                staged.write_text(lrc, 'utf-8'); staged.replace(target)
                meta = P.read_meta(d)
                meta.setdefault('steps', {})['lyrics'] = True
                meta['lyrics_source'] = 'forced_alignment'
                meta['alignment_model'] = MODELS[language]
                P.write_meta(d, meta)
            report('音訊強制對齊完成，逐字時間已儲存', 1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            process.stdout.close()
            if not process.stdin.closed:
                process.stdin.close()
