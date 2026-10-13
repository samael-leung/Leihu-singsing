"""Ollama discovery, service startup and resumable model preparation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def find_ollama() -> Path | None:
    candidates = [shutil.which("ollama")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Programs" / "Ollama" / "ollama.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def api(base: str, path: str, body: dict | None = None, timeout: int = 10):
    request = Request(base.rstrip("/") + path,
                      data=None if body is None else json.dumps(body).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def service_ready(base: str) -> bool:
    try:
        data = api(base, "/api/version", timeout=2)
        return isinstance(data, dict) and isinstance(data.get("version"), str) and bool(data["version"])
    except (OSError, ValueError):
        return False


def is_local(base: str) -> bool:
    parts = urlsplit(base)
    return (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1")
            and not parts.username and not parts.password and not parts.query
            and not parts.fragment and parts.path in ("", "/"))


def ensure_service(base: str, logs: Path) -> None:
    if service_ready(base):
        return
    executable = find_ollama()
    if not is_local(base) or executable is None:
        raise RuntimeError("Ollama 服務未啟動，請確認服務網址與 Ollama 安裝。")
    logs.mkdir(parents=True, exist_ok=True)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    # Preserve the user's OLLAMA_MODELS setting and default shared model cache.
    env = dict(os.environ, OLLAMA_HOST=urlsplit(base).netloc)
    with open(logs / "ollama-server.log", "ab") as log:
        process = subprocess.Popen([str(executable), "serve"], env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=flags)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if service_ready(base):
            return
        if process.poll() is not None:
            raise RuntimeError("Ollama 啟動失敗，請查看 logs/ollama-server.log。")
        time.sleep(0.5)
    raise RuntimeError("Ollama 啟動逾時，請查看 logs/ollama-server.log。")


def model_present(base: str, model: str) -> bool:
    name = model if ":" in model else model + ":latest"
    return any(item.get("name") in (model, name) or item.get("model") in (model, name)
               for item in api(base, "/api/tags").get("models", []))


def pull_model(base: str, model: str, report) -> None:
    request = Request(base.rstrip("/") + "/api/pull",
                      data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    success = False
    # Ollama handles content-addressed blobs, checksum verification and partial downloads.
    with urlopen(request, timeout=120) as response:
        for line in response:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError("Ollama 模型下載失敗：" + str(data["error"]))
            total, completed = data.get("total", 0), data.get("completed", 0)
            fraction = min(0.95, completed / total * 0.95) if total else 0.0
            status = data.get("status", "下載模型")
            if total:
                status += f" {completed / 1e9:.2f}/{total / 1e9:.2f} GB"
            report(fraction, status)
            if data.get("status") == "success":
                success = True
    if not success:
        raise RuntimeError("Ollama 模型下載未完成；重新執行安裝即可續傳。")


def prepare_model(base: str, model: str, report) -> None:
    if not model_present(base, model):
        last = None
        for attempt in range(3):
            try:
                pull_model(base, model, report)
                break
            except (OSError, ValueError, RuntimeError) as error:
                last = error
                if attempt == 2:
                    raise RuntimeError(f"模型 {model} 下載失敗，請重新執行修復與更新以續傳。") from last
                report(0, f"下載中斷，重試 {attempt + 2}/3")
                time.sleep(2)
    if not model_present(base, model):
        raise RuntimeError(f"下載後找不到模型 {model}，請重新執行修復與更新。")
    report(0.96, "檢查本機模型載入")
    result = api(base, "/api/generate", {"model": model, "prompt": "Reply OK.",
                 "stream": False, "keep_alive": 0,
                 "options": {"num_predict": 8, "num_ctx": 2048, "temperature": 0}}, timeout=600)
    if result.get("error") or not result.get("done") or not result.get("response"):
        raise RuntimeError(f"模型 {model} 無法載入，請檢查 Ollama 紀錄與可用記憶體。")
    report(1, "本機模型已準備好")
