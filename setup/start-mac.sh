#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
    echo "此啟動腳本需在 macOS 執行。" >&2
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    echo "請先執行 bash setup/install-mac.sh。" >&2
    exit 1
fi
# Finder 啟動時 PATH 可能不含 Homebrew；優先使用安裝時的 ffmpeg。
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
case "${1:-browser}" in
    browser) exec .venv/bin/python app.py ;;
    desktop) exec .venv/bin/python desktop.py ;;
    *) echo "用法：bash setup/start-mac.sh [browser|desktop]" >&2; exit 2 ;;
esac
