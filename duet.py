"""1.7：男女對唱分聲部。

男女合唱的歌有兩種唱法，分開處理：
  * 輪流唱（男一句、女一句）：依每句的音高判斷是誰唱的（男聲通常比女聲低好幾個半音）。
  * 同時唱（副歌一起唱、和聲）：用男女聲分離模型把主唱拆成「男聲」「女聲」兩軌。
    模型（Sucial 的 Chorus Male-Female BS Roformer，CC BY-NC-SA 4.0）只擅長分開同時唱的聲音，
    一個人獨唱的句子它常分錯，所以獨唱的句子不靠它，只在判斷「這句是不是兩人一起唱」時參考。

每句標成 m（男）、f（女）、b（一起唱）。結果存在歌曲資料夾的 parts.json，可以在練唱畫面手動修改。
播放時「我唱男聲」：男聲的句子把主唱關掉，一起唱的句子改播分離出來的女聲軌。
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

import numpy as np

import pipeline as P

MF_MODEL = "model_chorus_bs_roformer_ep_267_sdr_24.1275.ckpt"
MF_YAML = "config_chorus_male_female_bs_roformer.yaml"
# 作者在 Hugging Face 的原檔放第一個（GitHub 的備份常回 504 逾時）。兩邊是同一個檔案（SHA-256 相同），
# 分段下載混用來源也沒關係，下載完會核對大小和檢查碼
_HF_MF = "https://huggingface.co/Sucial/Chorus_Male_Female_BS_Roformer/resolve/main/"
P.MODEL_FILES.setdefault(MF_MODEL, (527121477, "123c00786bdbc6bd462dddb35cd21fd6ae99ab8319f93f63a8abc1012e593d94",
                                    [_HF_MF + MF_MODEL, P._GH_AS + MF_MODEL]))
P.MODEL_FILES.setdefault(MF_YAML, (None, None, [_HF_MF + MF_YAML, P._GH_AS + MF_YAML]))
PART_STEMS = ("male", "female")
PARTS_VER = 1
DEFAULT_NAMES = {"m": "男聲", "f": "女聲"}


def parts_path(d: Path) -> Path:
    return d / "parts.json"


def load_parts(d: Path) -> dict | None:
    try:
        return json.loads(parts_path(d).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def save_parts(d: Path, data: dict) -> None:
    P.atomic_write_text(parts_path(d), json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def stems_ready(d: Path) -> bool:
    return all(P.stem_path(d, s).exists() for s in PART_STEMS)


def drop_stems(d: Path) -> None:
    """重新分軌後，舊的男女聲軌就對不上了：刪掉（句子的標記保留）。"""
    for base in [d, *d.glob("v2_*")]:
        for s in PART_STEMS:
            for ext in (".flac", ".wav"):
                (base / f"{s}{ext}").unlink(missing_ok=True)
    data = load_parts(d)
    if data and data.get("stems"):
        data["stems"] = False
        save_parts(d, data)


def model_ready() -> bool:
    p = P.MODELS / "uvr" / MF_MODEL
    return p.exists() and p.stat().st_size == P.MODEL_FILES[MF_MODEL][0]


# ---------------------------------------------------------------- 男女聲分離

def _kind(name: str) -> str | None:
    marks = re.findall(r"\((male|female)\)", name.lower())
    return marks[-1] if marks else None


def separate_parts(d: Path, report) -> None:
    """把主唱（合唱模式時是主唱＋合音）分成男聲、女聲兩軌。"""
    try:
        import torch  # noqa: F401
    except Exception:
        pass
    from audio_separator.separator import Separator

    src_names = ["lead", "back"] if P.read_meta(d).get("vocal_mode") == "all" else ["lead"]
    report("下載男女聲分離模型", 0.03)
    P.ensure_model(MF_YAML)
    P.ensure_model(MF_MODEL, P._dl_report(report, "男女聲分離模型", 0.03))
    tmp = d / "_mf"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        ys = [P.read_audio(P.stem_path(d, s)) for s in src_names]
        n = min(y.shape[1] for y in ys)
        vocal = sum(y[:, :n] for y in ys)
        src = tmp / "vocal.wav"
        P.write_wav(src, vocal)
        sep = Separator(output_dir=str(tmp), model_file_dir=str(P.MODELS / "uvr"), output_format="WAV",
                        sample_rate=P.SR, use_autocast=P._autocast_ok(),
                        mdxc_params={"segment_size": 256, "override_model_segment_size": False, "batch_size": None,
                                     "overlap": 2, "pitch_shift": 0})
        report("載入男女聲分離模型", 0.1)
        sep.load_model(model_filename=MF_MODEL)
        with P._sep_progress("分開男聲與女聲", report, 0.12, 0.7):
            outs = [p for p in P._outputs(sep.separate(str(src)), tmp) if p != src]
        got = {_kind(p.name): p for p in outs}
        if not all(k in got for k in PART_STEMS):
            raise RuntimeError(f"分離結果裡找不到男聲／女聲：{[p.name for p in outs]}")
        full = P.sf.info(str(P.stem_path(d, "lead"))).frames
        for k in PART_STEMS:
            P.save_stem(d, k, P.fit_length(P.read_audio(got[k]), full))
        for v in d.glob("v2_*"):          # 舊的移調版本沒有這兩軌，換 KEY 時會補做
            for k in PART_STEMS:
                for ext in (".flac", ".wav"):
                    (v / f"{k}{ext}").unlink(missing_ok=True)
        del sep
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        P.free_gpu()


# ---------------------------------------------------------------- 每句是誰唱

def line_windows(d: Path, notes: list) -> list[dict]:
    """有時間的歌詞每句的範圍：開始到這句最後一個音結束（不超過下一句開始）。"""
    lines = [l for l in P.lyric_lines(d) if (l.get("text") or "").strip()]
    out = []
    for i, l in enumerate(lines):
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else l["t"] + 6
        end = l["t"]
        for s, e, _m in notes:
            if l["t"] - 0.1 <= s < nxt:
                end = max(end, e)
        end = end if end > l["t"] + 0.3 else min(nxt, l["t"] + 4)
        out.append({"t": round(l["t"], 2), "end": round(min(end, nxt + 0.3), 2), "text": l["text"]})
    return out


def _median_pitch(midi: np.ndarray, a: float, b: float) -> float | None:
    i0, i1 = max(0, int(a / P.HOP_S)), min(len(midi), int(b / P.HOP_S) + 1)
    v = midi[i0:i1]
    v = v[~np.isnan(v)]
    return float(np.median(v)) if v.size >= 8 else None


def two_means(vals: list[float]) -> tuple[float, float] | None:
    """一維 2-means：回傳（低群中心, 高群中心）。"""
    v = np.sort(np.array(vals, dtype=float))
    if v.size < 4:
        return None
    best = None
    for k in range(2, v.size - 1):        # 每群至少 2 句
        lo, hi = v[:k], v[k:]
        cost = float(((lo - lo.mean()) ** 2).sum() + ((hi - hi.mean()) ** 2).sum())
        if best is None or cost < best[0]:
            best = (cost, float(lo.mean()), float(hi.mean()))
    return (best[1], best[2]) if best else None


def _rms(y: np.ndarray, a: float, b: float) -> float:
    i0, i1 = max(0, int(a * P.PITCH_SR)), min(len(y), int(b * P.PITCH_SR))
    return float(np.sqrt(np.mean(y[i0:i1] ** 2))) if i1 > i0 else 0.0


BOTH_RATIO = 0.55   # 小聲那軌至少是大聲那軌的 55%，才算兩人一起唱
SPLIT_MIN = 3.5     # 兩群音高至少差這麼多半音，才用音高分男女


def tag_lines(d: Path) -> dict:
    midi, notes = P.load_pitch(d)
    wins = line_windows(d, notes)
    meds = [_median_pitch(midi, w["t"], w["end"]) for w in wins]
    cl = two_means([m for m in meds if m is not None])
    split = None
    if cl and cl[1] - cl[0] >= SPLIT_MIN:
        split = (cl[0] + cl[1]) / 2
    has_stems = stems_ready(d)
    if has_stems:
        ym = P.read_audio(P.stem_path(d, "male"), sr=P.PITCH_SR, mono=True)
        yf = P.read_audio(P.stem_path(d, "female"), sr=P.PITCH_SR, mono=True)
    out = []
    for w, med in zip(wins, meds):
        p, conf = None, 0.0
        both_hint = None
        if has_stems:
            em, ef = _rms(ym, w["t"], w["end"]), _rms(yf, w["t"], w["end"])
            if max(em, ef) > 1e-4:
                ratio = min(em, ef) / max(em, ef)
                both_hint = ratio
                if ratio >= BOTH_RATIO:
                    p, conf = "b", min(1.0, ratio)
                elif split is None:      # 音高分不出來（例如同性別合唱）：參考哪一軌比較大聲
                    p, conf = ("m" if em > ef else "f"), 1 - ratio
        if p is None and med is not None and split is not None:
            p = "m" if med < split else "f"
            conf = min(1.0, abs(med - split) / 3)
            if both_hint is not None and both_hint >= 0.35:
                conf *= 0.6               # 另一個聲音也不小：可能是一起唱，信心打折
        out.append({"t": w["t"], "end": w["end"], "text": w["text"], "p": p or "", "auto": True,
                    "conf": round(conf, 2)})
    return {"lines": out, "split": None if split is None else round(split, 2),
            "centers": None if not cl else [round(cl[0], 2), round(cl[1], 2)]}


def analyze(d: Path, use_model: bool, report) -> dict:
    """分聲部：（可選）男女聲分離 → 每句自動標記。之前手動改過的句子保留。"""
    if use_model:
        separate_parts(d, report)
    report("判斷每句是誰唱", 0.9)
    res = tag_lines(d)
    old = load_parts(d) or {}
    manual = [l for l in old.get("lines", []) if not l.get("auto")]
    for l in res["lines"]:
        hit = min(manual, key=lambda m: abs(m["t"] - l["t"]), default=None)
        if hit and abs(hit["t"] - l["t"]) <= 0.6:
            l.update(p=hit["p"], auto=False, conf=1.0)
    data = {"ver": PARTS_VER, "at": time.time(), "names": old.get("names") or dict(DEFAULT_NAMES),
            "stems": stems_ready(d), "src": "lead+back" if P.read_meta(d).get("vocal_mode") == "all" else "lead",
            **res}
    save_parts(d, data)
    P.update_meta(d, parts=True, parts_stems=data["stems"])
    report("完成", 1.0)
    return data


def save_manual(d: Path, lines: list, names: dict | None) -> dict:
    data = load_parts(d) or {"ver": PARTS_VER, "names": dict(DEFAULT_NAMES), "stems": stems_ready(d),
                             "src": "lead", "split": None, "centers": None}
    clean = []
    for l in lines[:2000]:
        try:
            t = round(float(l.get("t")), 2)
        except (TypeError, ValueError):
            continue
        p = l.get("p") if l.get("p") in ("m", "f", "b", "") else ""
        clean.append({"t": t, "end": round(float(l.get("end") or t + 3), 2), "text": str(l.get("text") or "")[:200],
                      "p": p, "auto": bool(l.get("auto")), "conf": float(l.get("conf") or (0 if l.get("auto") else 1))})
    data["lines"] = sorted(clean, key=lambda l: l["t"])
    if isinstance(names, dict):
        data["names"] = {k: (str(names.get(k) or DEFAULT_NAMES[k]).strip()[:12] or DEFAULT_NAMES[k]) for k in ("m", "f")}
    data["at"] = time.time()
    save_parts(d, data)
    P.update_meta(d, parts=True)
    return data


def job(song_id: str, use_model: bool):
    def run(report):
        analyze(P.song_dir(song_id), use_model, report)
    return run
