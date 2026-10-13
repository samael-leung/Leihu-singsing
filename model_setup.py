"""Hardware recommendations and optional Ollama setup shared by both platforms."""
from __future__ import annotations

import csv
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import ollama_setup as O
import pipeline as P


def hardware() -> dict:
    info = {'platform': sys.platform, 'arch': platform.machine(), 'ram_gb': 0, 'gpus': []}
    try:
        if sys.platform == 'darwin':
            ram = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True, timeout=10))
        elif sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            class Memory(ctypes.Structure):
                _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
            data = Memory()
            data.length = ctypes.sizeof(data)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data)):
                raise OSError('memory query failed')
            ram = data.total
        else:
            ram = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        info['ram_gb'] = round(ram / 1024**3, 1)
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        pass
    executable = shutil.which('nvidia-smi')
    if not executable and sys.platform == 'win32':
        candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/nvidia-smi.exe',
                      Path(os.environ.get('ProgramW6432', 'C:/Program Files')) / 'NVIDIA Corporation/NVSMI/nvidia-smi.exe']
        executable = next((str(p) for p in candidates if p.is_file()), None)
    if executable and sys.platform != 'darwin':
        try:
            output = subprocess.check_output([executable, '--query-gpu=name,memory.total,memory.free',
                                              '--format=csv,noheader,nounits'], text=True, timeout=10)
            for name, total, free in csv.reader(output.splitlines()):
                info['gpus'].append({'name': name.strip(), 'total_gb': round(float(total) / 1024, 1),
                                     'free_gb': round(float(free) / 1024, 1)})
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return info


def recommend(info=None) -> dict:
    info = hardware() if info is None else info
    ram = info['ram_gb']
    if info['platform'] == 'darwin' and info['arch'] == 'arm64':
        size, ctx = ('14b', 8192) if ram >= 48 else ('7b', 8192) if ram >= 16 else ('3b', 4096)
        reason = f'Apple Silicon，共享記憶體 {ram:g} GB；保留空間給 macOS 與音訊處理'
    elif info['gpus']:
        gpu = max(info['gpus'], key=lambda g: g['free_gb'])
        free = gpu['free_gb']
        if free >= 20 and ram >= 16:
            size, ctx = '14b', 16384
        elif free >= 10 and ram >= 12:
            size, ctx = '7b', 8192
        elif free >= 5:
            size, ctx = '3b', 4096
        else:
            size, ctx = '1.5b', 4096
        reason = f"{gpu['name']}，目前可用顯示記憶體 {free:g}/{gpu['total_gb']:g} GB，RAM {ram:g} GB"
    else:
        size, ctx = ('3b', 4096) if ram >= 16 else ('1.5b', 4096)
        reason = f'未偵測到 NVIDIA 顯示卡，RAM {ram:g} GB；選用較小模型以減少 CPU 等待'
    return dict(model='qwen2.5:' + size, num_ctx=ctx, reason=reason, hardware=info)


def prepare(cfg, report):
    """Install/download only after the user selects local mode."""
    if cfg['ai_mode'] != 'local':
        raise P.UserError('請先選擇本機模型模式。')
    base = cfg['ollama_url']
    if sys.platform == 'win32':
        import installer
        if not installer.prepare_ollama(cfg=cfg, report=lambda fraction, text: report(text, fraction)):
            raise P.UserError('本機模型準備失敗；請查看 logs/install.log，重新儲存設定可續傳。')
        return
    if not O.service_ready(base) and O.find_ollama() is None:
        if not O.is_local(base):
            raise P.UserError('遠端 Ollama 未啟動；請先啟動指定服務。')
        if sys.platform != 'darwin':
            raise P.UserError('請先安裝 Ollama，再重試本機模型準備。')
        brew = shutil.which('brew')
        if not brew:
            raise P.UserError('請先安裝 Homebrew，再重新準備本機模型。')
        report('安裝 Ollama', 0.02)
        (P.ROOT / 'logs').mkdir(exist_ok=True)
        with open(P.ROOT / 'logs/ollama-install.log', 'ab') as log:
            result = subprocess.run([brew, 'install', 'ollama'], stdout=log, stderr=log, timeout=1800)
        if result.returncode:
            raise P.UserError('Homebrew 安裝 Ollama 失敗，請查看 logs/ollama-install.log。')
    try:
        O.ensure_service(base, P.ROOT / 'logs')
        O.prepare_model(base, cfg['ollama_model'], lambda fraction, text: report(text, fraction))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise P.UserError(f'本機模型未準備完成：{error}') from error
