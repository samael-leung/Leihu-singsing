"""CPU Wav2Vec2/CTC worker for original-vocal lyric timestamps."""
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pipeline as P
import forced_alignment as F


def watch_parent(pid):
    if sys.platform == 'win32':
        # os.kill(pid, 0) is not a harmless existence probe on Windows.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return os._exit(1)
        status = kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
        kernel.CloseHandle(handle)
        if status == 0:
            return os._exit(1)
        return
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return os._exit(1)
        time.sleep(1)


def report(step, progress):
    print('LEIHU_ALIGN_PROGRESS ' + json.dumps({'step': step, 'progress': progress}), flush=True)


def align(payload):
    import torch
    try:
        from transformers import AutoModelForCTC, AutoProcessor
    except ImportError as error:
        raise P.UserError('請先更新套件：重新執行 Mac 安裝腳本，或安裝新版 Windows 安裝檔。') from error
    language = payload['language']
    report('載入強制對齊模型（第一次需連網下載）', .05)
    model_name = payload.get('model') or F.MODELS[language]
    processor = AutoProcessor.from_pretrained(model_name, cache_dir=payload['cache'])
    model = AutoModelForCTC.from_pretrained(model_name, cache_dir=payload['cache']).to('cpu').eval()
    lines, labels, owners = F.transcript(payload['text'], processor.tokenizer.get_vocab(), language,
                                        processor.tokenizer.word_delimiter_token or '|')
    blank = model.config.pad_token_id
    unique = sorted(set(labels) | {blank})
    reduced = {token: index for index, token in enumerate(unique)}
    audio = P.read_audio(Path(payload['audio']), sr=16000, mono=True)
    duration = len(audio) / 16000
    emissions, frame_times = [], []
    # Bounded inference with overlap avoids full-song transformer memory use.
    for start in range(0, len(audio), 20 * 16000):
        end = min(len(audio), start + 20 * 16000)
        left, right = max(0, start - 16000), min(len(audio), end + 16000)
        values = processor(audio[left:right], sampling_rate=16000, return_tensors='pt').input_values
        with torch.inference_mode():
            logits = model(values).logits[0]
            probabilities = logits.log_softmax(-1)[:, unique].cpu().numpy()
        boundaries = np.linspace(left / 16000, right / 16000, len(probabilities) + 1)
        centers = (boundaries[:-1] + boundaries[1:]) / 2
        keep = (centers >= start / 16000) & (centers < end / 16000)
        emissions.append(probabilities[keep]); frame_times.extend(boundaries[:-1][keep])
        report('分析主唱音訊', .1 + .65 * end / len(audio))
    report('依正確歌詞搜尋逐字音訊時間', .8)
    probabilities = np.concatenate(emissions)
    frame_times = np.array(frame_times + [duration])
    spans = F.ctc_path(probabilities, [reduced[token] for token in labels], reduced[blank])
    return F.aligned_lines(lines, owners, spans, frame_times, duration)


def main():
    payload = json.loads(sys.stdin.readline())
    threading.Thread(target=watch_parent, args=(payload['parent_pid'],), daemon=True).start()
    try:
        result = {'lines': align(payload)}
    except P.UserError as error:
        result = {'error': str(error)}
    Path(payload['result']).write_text(json.dumps(result, ensure_ascii=False), 'utf-8')


if __name__ == '__main__':
    main()
