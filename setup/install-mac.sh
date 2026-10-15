#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
    echo "此安裝腳本需在 macOS 執行。" >&2
    exit 1
fi
if [[ "$(uname -m)" != arm64 ]]; then
    echo "目前支援 Apple Silicon 原生 arm64。Apple Silicon 請勿以 Rosetta 執行；本腳本不支援 Intel Mac。" >&2
    exit 1
fi
mac_version=$(sw_vers -productVersion)
if (( ${mac_version%%.*} < 14 )); then
    echo "請先更新至 macOS 14 或更新版本。" >&2
    exit 1
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v brew >/dev/null; then
    echo "請先從 https://brew.sh 安裝 Homebrew，再重新執行。" >&2
    exit 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
    echo "請先執行 xcode-select --install，完成 Command Line Tools 安裝後再重新執行。" >&2
    exit 1
fi
brew install python@3.11 ffmpeg cmake pkg-config libsndfile
PYTHON="$(brew --prefix python@3.11)/bin/python3.11"
if [[ -d .venv ]]; then
    .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 11), "請先移走現有非 Python 3.11 的 .venv"'
else
    "$PYTHON" -m venv .venv
fi
.venv/bin/python -c 'import platform; assert platform.machine() == "arm64", "現有 .venv 非 arm64，請移走後重建"'
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-mac.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'import flask, numpy, soundfile, librosa, pedalboard, torch, torchcrepe, faster_whisper, webview; from audio_separator.separator import Separator; from PIL import Image; from transformers import AutoProcessor, AutoModelForCTC; print("Mac 相依套件載入成功")'
echo "安裝完成。執行 bash setup/start-mac.sh，首次啟動選擇本機模型或 API；選本機模式後儲存設定才會下載語言模型。"
