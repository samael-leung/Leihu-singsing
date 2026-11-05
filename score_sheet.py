"""1.7：旋律譜匯出。

把練唱畫面的旋律＋歌詞畫成一頁頁的 PNG，只能開圖片的地方（手機相簿、平板、印出來）也能對著練。
每句歌詞一列（太長自動換列）：
  * 上半是旋律：音符方塊照時間排，高低就是音高，方塊上標音名（C4）或簡譜（1～7，上下加點表示高低八度）
  * 下半是歌詞：每個字放在它開始唱的位置
  * 男女對唱的歌，依聲部上色，列首標「男／女／合」
不做節拍量化：旋律是從原唱分析出來的，沒有可靠的拍子資訊，所以用時間位置排版（跟練唱畫面一樣）。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

import pipeline as P
import share as SH

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DEG = {0: "1", 1: "#1", 2: "2", 3: "#2", 4: "3", 5: "4", 6: "#4", 7: "5", 8: "#5", 9: "6", 10: "#6", 11: "7"}

LAYOUTS = {   # 寬、高、邊界、基本字級
    "phone": (1080, 1920, 56, 34),
    "a4": (1654, 2339, 96, 34),
}
INK, MUTED, LINE, LANE, BG = "#1d232b", "#6b7685", "#d9dee5", "#f3f5f8", "#ffffff"
PART_COLOR = {"m": "#2f78c4", "f": "#d0457f", "b": "#7b4fc9", "": "#c06a14"}

# Krumhansl–Kessler 大調音階輪廓：估計這首歌的調（簡譜的「1」）
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def note_name(m: float) -> str:
    r = int(round(m))
    return f"{NAMES[r % 12]}{r // 12 - 1}"


def guess_tonic(notes: list) -> int:
    """依音符長度統計各音的分布，找最像的大調或小調；小調換成關係大調（簡譜通常用大調的 1）。"""
    h = np.zeros(12)
    for s, e, m in notes:
        h[int(round(m)) % 12] += max(0.05, e - s)
    if h.sum() <= 0:
        return 0
    best, tonic = -2.0, 0
    for k in range(12):
        for prof, rel in ((_MAJOR, 0), (_MINOR, 3)):
            c = float(np.corrcoef(h, np.roll(prof, k))[0, 1])
            if c > best:
                best, tonic = c, (k + rel) % 12
    return tonic


def jianpu(m: float, tonic_midi: int) -> tuple[str, int]:
    """簡譜：回傳（數字，八度：0＝中音、+1＝上面一點、-1＝下面一點）。"""
    r = int(round(m)) - tonic_midi
    return DEG[r % 12], r // 12


def _font(size: int, bold: bool = False):
    return SH._font(size, bold)


def _chunks(line: dict, notes: list, max_chars: int, max_span: float) -> list[dict]:
    """一句太長就從中間最大的空隙切開，直到每段的字數和長度都放得下。"""
    t0, t1 = line["t"], line["end"]
    # 逐字時間略早於句首或晚於句尾時（手動調整過時間常見），算進第一段／最後一段，字才不會不見
    chars = [dict(c, t=min(max(c["t"], t0), t1 - 0.01)) for c in line["chars"] if c["c"].strip()]
    segs = [(t0, t1)]
    out = []
    while segs:
        a, b = segs.pop(0)
        cs = [c for c in chars if a - 1e-3 <= c["t"] < b - 1e-3] if chars else []
        if (len(cs) <= max_chars and b - a <= max_span) or b - a < 1.0:
            out.append((a, b))
            continue
        # 候選切點：字與字之間（沒有逐字時間就用音符之間）
        cuts = [c["t"] for c in cs[1:]] or [n[0] for n in notes if a + 0.5 < n[0] < b - 0.5]
        if not cuts:
            out.append((a, b))
            continue
        mid = (a + b) / 2

        def gap_before(t):
            prev = [n[1] for n in notes if n[1] <= t + 0.02]
            return t - max(prev) if prev else 0.0
        cut = max(cuts, key=lambda t: gap_before(t) * 2 - abs(t - mid) / max(0.5, b - a))
        segs[:0] = [(a, cut), (cut, b)]
    return [{"t": a, "end": b, "chars": [c for c in chars if a - 1e-3 <= c["t"] < b - 1e-3] if chars else [],
             "text": line["text"] if len(out) == 1 else "", "part": line.get("part", "")} for a, b in out]


def render(d: Path, data: dict, out_dir: Path) -> tuple[list[Path], str]:
    from PIL import Image, ImageDraw

    layout = data.get("layout") if data.get("layout") in LAYOUTS else "phone"
    W, H, M, fs = LAYOUTS[layout]
    notation = data.get("notation") if data.get("notation") in ("name", "jianpu", "both") else "jianpu"
    key = int(data.get("key") or 0)
    show_parts = bool(data.get("parts"))
    names = data.get("names") or {"m": "男聲", "f": "女聲"}
    _midi, raw = P.load_pitch(d)
    notes = [(float(s), float(e), float(m) + key) for s, e, m in raw if e - s >= 0.05]
    if not notes:
        raise P.UserError("這首歌還沒有旋律可以匯出")
    tonic_pc = data.get("tonic")
    tonic_pc = (guess_tonic([(s, e, m - key) for s, e, m in notes]) + key) % 12 if tonic_pc in (None, "", "auto") \
        else int(tonic_pc) % 12
    med = float(np.median([m for _s, _e, m in notes]))
    # 中音區（不加點）放在音最多的那個八度
    ms = np.array([m for _s, _e, m in notes])
    cands = [tonic_pc + 12 * k for k in range(1, 10)]
    tonic_midi = max(cands, key=lambda T: (int(((ms >= T - 0.5) & (ms < T + 11.5)).sum()), -abs(T + 6 - med)))

    # 句子：前端送來的（含逐字時間、聲部）；沒有歌詞就用旋律的樂句
    lines = []
    for l in data.get("lines") or []:
        try:
            t, end = float(l["t"]), float(l.get("end") or l["t"] + 3)
        except (KeyError, TypeError, ValueError):
            continue
        chars = [{"c": str(c.get("c", "")), "t": float(c["t"])} for c in (l.get("chars") or [])
                 if c.get("t") is not None and str(c.get("c", "")).strip()]
        lines.append({"t": t, "end": max(end, t + 0.3), "text": str(l.get("text") or ""), "chars": chars,
                      "part": l.get("p") or ""})
    if not lines:
        ph = []
        for s, e, _m in notes:
            if ph and s - ph[-1][1] < 0.6:
                ph[-1][1] = e
            else:
                ph.append([s, e])
        lines = [{"t": a, "end": b, "text": "", "chars": [], "part": ""} for a, b in ph]

    f_title, f_sub, f_small = _font(int(fs * 1.5), True), _font(int(fs * 0.8)), _font(int(fs * 0.62))
    f_lyr = _font(fs)
    f_lbl = _font(int(fs * 0.62), True)
    f_tag = _font(int(fs * 0.72))   # 列首的聲部字（不用粗體：小字加粗會糊成一團）
    tag_w = int(fs * 1.5) if show_parts else 0
    row_x0, row_x1 = M + tag_w, W - M
    row_w = row_x1 - row_x0
    max_chars = max(6, int(row_w / (fs * 1.08)))
    rows = []
    for l in lines:
        for c in _chunks(l, notes, max_chars, 9.0 if layout == "phone" else 12.0):
            rows.append(c)

    pages: list = []

    def new_page(first: bool):
        img = Image.new("RGB", (W, H), BG)
        dr = SH._Draw(ImageDraw.Draw(img, "RGBA"))
        y = M
        if first:
            title = str(data.get("title") or "")
            while title and f_title.getlength(title) > W - 2 * M:
                title = title[:-2] + "…" if len(title) > 2 else ""
            dr.text((M, y), title, font=f_title, fill=INK)
            y += int(fs * 1.5) + 14
            sub = []
            if data.get("artist"):
                sub.append(str(data["artist"]))
            sub.append(f"KEY {key:+d}" if key else "原調")
            if notation in ("jianpu", "both"):
                sub.append(f"1 = {NAMES[tonic_pc]}")
            dr.text((M, y), "　".join(sub), font=f_sub, fill=MUTED)
            y += int(fs * 0.8) + 10
            legend = "方塊位置越高音越高，橫向是時間；"
            legend += "數字是簡譜，上面加點高八度、下面加點低八度" if notation == "jianpu" else \
                "方塊上是音名（C4＝中央 C）" if notation == "name" else "上排簡譜、下排音名"
            dr.text((M, y), legend, font=f_small, fill=MUTED)
            y += int(fs * 0.62) + 8
            if show_parts:
                x = M
                for k, lab in (("m", names.get("m", "男聲")), ("f", names.get("f", "女聲")), ("b", "一起唱")):
                    dr.rounded_rectangle((x, y + 4, x + 22, y + 4 + int(fs * 0.55)), 4, fill=PART_COLOR[k])
                    dr.text((x + 30, y), lab, font=f_small, fill=INK)
                    x += 30 + int(f_small.getlength(lab)) + 28
                y += int(fs * 0.62) + 8
            y += 10
            dr.line((M, y, W - M, y), fill=LINE, width=2)
            y += 18
        pages.append(img)
        return img, dr, y

    img, dr, y = new_page(True)
    unit = max(9, int(fs * 0.36))            # 一個半音的高度
    lbl_h = int(fs * 0.62) + 6
    for row in rows:
        ns = [n for n in notes if n[1] > row["t"] - 0.05 and n[0] < row["end"] + 0.05]
        if ns:
            lo, hi = min(n[2] for n in ns), max(n[2] for n in ns)
        else:
            lo = hi = med
        lo, hi = int(np.floor(lo)), int(np.ceil(hi))
        if hi - lo < 5:
            c = (hi + lo) / 2
            lo, hi = int(np.floor(c - 2.5)), int(np.floor(c - 2.5)) + 5
        lbl_rows = 2 if notation == "both" else 1
        mel_h = (hi - lo + 1) * unit + lbl_rows * lbl_h + 6
        row_h = mel_h + int(fs * 1.35) + 22
        if y + row_h > H - M - fs:
            img, dr, y = new_page(False)
        t0 = min([row["t"]] + [n[0] for n in ns if n[0] >= row["t"] - 0.3])
        t1 = max([row["end"]] + [n[1] for n in ns])
        span = max(1.5, t1 - t0)
        px = row_w / span

        def X(t):
            return row_x0 + (t - t0) * px
        top = y + lbl_rows * lbl_h
        def Y(m):
            return top + (hi - m) * unit
        color = PART_COLOR.get(row["part"] if show_parts else "", PART_COLOR[""])
        # 背景：黑鍵的列淡淡上色，中央 C 畫一條線
        for m in range(lo, hi + 1):
            if m % 12 in (1, 3, 6, 8, 10):
                dr.rectangle((row_x0, Y(m), row_x1, Y(m) + unit), fill=LANE)
            if m % 12 == 0:
                dr.line((row_x0, Y(m) + unit, row_x1, Y(m) + unit), fill=LINE, width=1)
        if show_parts and row["part"]:
            dr.rounded_rectangle((M, top, M + 8, top + (hi - lo + 1) * unit), 4, fill=color)
            dr.text((M + 16, top), {"m": names.get("m", "男聲")[:1], "f": names.get("f", "女聲")[:1], "b": "合"}
                    [row["part"]], font=f_tag, fill=color)
        dr.text((row_x1, y - 2), SH_time(row["t"]), font=f_small, fill=MUTED, anchor="ra")
        # 音符方塊與標記（擋到前一個標記就不畫，免得擠成一團）
        last_lbl = -1e9
        for s, e, m in ns:
            x0, x1 = max(row_x0, X(s)), min(row_x1, X(e))
            if x1 - x0 < 2:
                continue
            ym = Y(m)
            dr.rounded_rectangle((x0, ym + 1, max(x0 + 3, x1 - 2), ym + unit - 1), 3, fill=color)
            labels = []
            if notation in ("jianpu", "both"):
                labels.append("jp")
            if notation in ("name", "both"):
                labels.append("nm")
            w_need = max(f_lbl.getlength(note_name(m)) if "nm" in labels else 0, fs * 0.6)
            if x0 >= last_lbl + 4:
                for i, kind in enumerate(labels):
                    ly = ym - (len(labels) - i) * lbl_h
                    if kind == "nm":
                        dr.text((x0, ly), note_name(m), font=f_lbl, fill=MUTED)
                    else:
                        digit, octv = jianpu(m, tonic_midi)
                        dr.text((x0, ly), digit, font=f_lbl, fill=INK)
                        dw = f_lbl.getlength(digit)
                        cx = x0 + dw - f_lbl.getlength(digit[-1]) / 2
                        for k in range(abs(octv)):
                            dy = ly - 5 - 7 * k if octv > 0 else ly + lbl_h - 3 + 7 * k
                            dr.ellipse((cx - 3, dy - 3, cx + 3, dy + 3), fill=INK)
                last_lbl = x0 + w_need
        # 歌詞：每個字放在開始唱的位置，擠在一起就往右推
        ly = top + (hi - lo + 1) * unit + 10
        if row["chars"]:
            xpos = row_x0 - 1e9
            for c in row["chars"]:
                x = max(X(c["t"]), xpos, row_x0)
                cw = f_lyr.getlength(c["c"])
                if x + cw > row_x1 + fs * 0.5:
                    x = row_x1 - cw
                dr.text((x, ly), c["c"], font=f_lyr, fill=INK)
                xpos = x + cw + 1
        elif row["text"]:
            dr.text((row_x0, ly), row["text"], font=f_lyr, fill=INK)
        y += row_h

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink(missing_ok=True)
    files = []
    total = len(pages)
    brand = f"{P.APP_NAME} 旋律譜"
    for i, im in enumerate(pages):
        dr = SH._Draw(ImageDraw.Draw(im, "RGBA"))
        dr.text((W / 2, H - M / 2), f"{brand}　{i + 1}／{total}", font=f_small, fill=MUTED, anchor="mm")
        p = out_dir / f"{i + 1:02d}.png"
        im.save(p, optimize=True)
        files.append(p)
    return files, NAMES[tonic_pc]


def SH_time(t: float) -> str:
    m = int(t // 60)
    return f"{m}:{int(t - m * 60):02d}"


def safe_name(s: str) -> str:
    return (re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", s).strip(" .") or "旋律譜")[:60]
