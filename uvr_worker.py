"""Mac UVR isolation worker: CPU ONNX/PyTorch only, progress over stdout."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pipeline as P


def watch_parent(pid):
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return os._exit(1)
        time.sleep(1)


def main():
    payload = json.loads(sys.stdin.readline())
    threading.Thread(target=watch_parent, args=(payload['parent_pid'],), daemon=True).start()
    def report(step, progress):
        print('LEIHU_UVR_PROGRESS ' + json.dumps({'step': step, 'progress': progress}), flush=True)
    P._separate_uvr_direct(Path(payload['song_dir']), payload['models'], report, cpu_only=True)


if __name__ == '__main__':
    main()
