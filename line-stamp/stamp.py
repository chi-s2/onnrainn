#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINEアニメーションスタンプ制作パイプライン（自分用）

サブコマンド:
  convert   グリーンバック動画 → 透過APNG候補を一括生成（工程4）
  preview   候補を一覧できる確認用HTMLを生成（工程5）
  package   選定した8/16/24個から申請用zipを作成（工程6）
  validate  APNG/zipがLINE規格を満たすかチェック

LINEアニメーションスタンプ規格:
  - APNG形式（拡張子 .png）
  - 最大 320x270px（偶数サイズ推奨）
  - 5〜20フレーム
  - 再生時間はループ込みで 1/2/3/4 秒ぴったり
  - 1ファイル 300KB 以下
  - 背景透過（キャラ内部に透過穴があると審査リジェクト）
  - 申請zip: main.png(240x240 APNG) / tab.png(96x74 静止PNG) / 01.png〜
"""

import argparse
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import deque
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("必要ライブラリがありません。先に `pip install pillow numpy imageio-ffmpeg` を実行してください。")

MAX_W, MAX_H = 320, 270
MAIN_SIZE = (240, 240)
TAB_SIZE = (96, 74)
MAX_BYTES = 300 * 1024
MIN_FRAMES, MAX_FRAMES = 5, 20
VALID_TOTALS_MS = (1000, 2000, 3000, 4000)
VALID_SET_COUNTS = (8, 16, 24)


# ---------------------------------------------------------------- ffmpeg

def ffmpeg_exe():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg が見つかりません。`pip install imageio-ffmpeg` を実行してください。")


def video_duration(video):
    out = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(video)],
        capture_output=True, text=True,
    ).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not m:
        sys.exit(f"動画の長さを取得できませんでした: {video}")
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def extract_frames(video, start, dur, n):
    """動画の [start, start+dur] 区間から n フレームを均等に取り出す。"""
    tmp = Path(tempfile.mkdtemp(prefix="stamp_frames_"))
    fps = n / dur
    cmd = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
        "-vf", f"fps={fps:.6f}",
        "-frames:v", str(n),
        str(tmp / "f%03d.png"),
    ]
    subprocess.run(cmd, check=True)
    files = sorted(tmp.glob("f*.png"))
    frames = [np.array(Image.open(f).convert("RGB")) for f in files]
    shutil.rmtree(tmp, ignore_errors=True)
    if not frames:
        return None
    while len(frames) < n:
        frames.append(frames[-1].copy())
    return frames[:n]


# ------------------------------------------------------- クロマキー処理

def estimate_key_color(arr):
    """フレーム外周1pxの中央値を背景色とみなす。"""
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0).astype(np.float32)


def chroma_key(arr, key, t0, t1):
    """背景色との距離でアルファを決める。t0以下=完全透過、t1以上=完全不透明。"""
    f = arr.astype(np.float32)
    dist = np.sqrt(((f - key) ** 2).sum(axis=-1))
    a = np.clip((dist - t0) / max(t1 - t0, 1.0), 0.0, 1.0)
    a = a * a * (3 - 2 * a)  # smoothstep
    alpha = np.round(a * 255).astype(np.uint8)
    rgb = arr.copy()
    if key[1] > key[0] and key[1] > key[2]:
        # グリーンバック: 輪郭の半透明帯に残る緑かぶりを抑える
        edge = (alpha > 0) & (alpha < 255)
        g_cap = np.maximum(rgb[..., 0], rgb[..., 2])
        rgb[..., 1] = np.where(edge & (rgb[..., 1] > g_cap), g_cap, rgb[..., 1])
    return np.dstack([rgb, alpha])


def flood_exterior(mask):
    """外周につながる True 領域だけを残す（ベクトル化flood fill）。"""
    ext = np.zeros_like(mask)
    ext[0, :] = mask[0, :]
    ext[-1, :] = mask[-1, :]
    ext[:, 0] = mask[:, 0]
    ext[:, -1] = mask[:, -1]
    while True:
        grown = ext.copy()
        grown[1:, :] |= ext[:-1, :]
        grown[:-1, :] |= ext[1:, :]
        grown[:, 1:] |= ext[:, :-1]
        grown[:, :-1] |= ext[:, 1:]
        grown &= mask
        if (grown == ext).all():
            return ext
        ext = grown


def fill_holes(rgba):
    """キャラ内部の透過穴を塞ぐ（審査リジェクト対策）。塞いだ画素数を返す。"""
    alpha = rgba[..., 3]
    transparent = alpha < 16
    exterior = flood_exterior(transparent)
    interior_soft = (alpha < 250) & ~exterior
    if not interior_soft.any():
        return rgba, 0
    out = rgba.copy()
    out[..., 3] = np.where(interior_soft, 255, out[..., 3])
    # 穴とその縁は背景色が残っているため、周囲の不透明色で塗り直す
    out[..., :3] = _inpaint(out[..., :3], interior_soft)
    return out, int(interior_soft.sum())


def _inpaint(rgb, need):
    """need画素を近傍の既知色で反復的に埋める。"""
    rgb = rgb.astype(np.float32)
    need = need.copy()
    for _ in range(128):
        if not need.any():
            break
        known = (~need).astype(np.float32)
        acc = np.zeros_like(rgb)
        cnt = np.zeros(need.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1))
            v = np.roll(rgb, (dy, dx), (0, 1))
            acc += v * k[..., None]
            cnt += k
        fill = need & (cnt > 0)
        if not fill.any():
            break
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        need[fill] = False
    return np.clip(rgb, 0, 255).astype(np.uint8)


def harden_interior(frames):
    """PILフレーム列に fill_holes を適用（縮小リサンプルで生じる内部半透明も除去）。"""
    out = []
    for f in frames:
        arr, _ = fill_holes(np.array(f.convert("RGBA")))
        out.append(Image.fromarray(arr))
    return out


def remove_specks(frames_rgba, min_area=40):
    """全フレーム合成マスク上で、面積が小さい浮きゴミ成分を除去する。"""
    union = np.zeros(frames_rgba[0].shape[:2], bool)
    for f in frames_rgba:
        union |= f[..., 3] > 16
    h, w = union.shape
    seen = np.zeros_like(union)
    removed = np.zeros_like(union)
    for y0, x0 in np.argwhere(union & ~seen):
        if seen[y0, x0]:
            continue
        comp = []
        dq = deque([(y0, x0)])
        seen[y0, x0] = True
        while dq:
            y, x = dq.popleft()
            comp.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and union[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    dq.append((ny, nx))
        if len(comp) < min_area:
            ys, xs = zip(*comp)
            removed[list(ys), list(xs)] = True
    if removed.any():
        for f in frames_rgba:
            f[..., 3][removed] = 0
    return frames_rgba, int(removed.sum())


# ------------------------------------------------------- APNG 書き出し

def _even_floor(v):
    return max(2, v - (v % 2))


def crop_and_fit(frames_rgba, max_w=MAX_W, max_h=MAX_H, margin=6):
    """全フレーム共通のバウンディングボックスで切り出し、規格サイズに収める。"""
    union = np.zeros(frames_rgba[0].shape[:2], bool)
    for f in frames_rgba:
        union |= f[..., 3] > 0
    if not union.any():
        return None
    ys, xs = np.where(union)
    y0, y1 = max(0, ys.min() - margin), min(union.shape[0], ys.max() + 1 + margin)
    x0, x1 = max(0, xs.min() - margin), min(union.shape[1], xs.max() + 1 + margin)
    imgs = [Image.fromarray(f[y0:y1, x0:x1]) for f in frames_rgba]
    w, h = imgs[0].size
    scale = min(max_w / w, max_h / h)
    nw, nh = _even_floor(int(w * scale)), _even_floor(int(h * scale))
    return [im.resize((nw, nh), Image.LANCZOS) for im in imgs]


def _durations_ms(n, content_ms):
    base = content_ms // n
    rem = content_ms - base * n
    return [base + (1 if i < rem else 0) for i in range(n)]


def _encode_apng(frames, total_ms, loops):
    content_ms = total_ms // loops
    buf = io.BytesIO()
    frames[0].save(
        buf, format="PNG", save_all=True, append_images=frames[1:],
        duration=_durations_ms(len(frames), content_ms),
        loop=loops, disposal=1, blend=0, optimize=True,
    )
    return buf.getvalue()


def _quantize(frames, colors):
    """全フレーム共通パレットで減色する。失敗したら None。"""
    try:
        w, h = frames[0].size
        sheet = Image.new("RGBA", (w * len(frames), h))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * w, 0))
        pal = sheet.quantize(colors=colors, method=Image.FASTOCTREE)
        return [f.quantize(colors=colors, palette=pal, dither=Image.Dither.NONE)
                for f in frames]
    except Exception:
        return None


def encode_under_limit(frames, total_ms, loops):
    """300KB以下になるまで 減色 → 縮小 → フレーム間引き の順で圧縮する。"""
    def attempt(fs):
        data = _encode_apng(fs, total_ms, loops)
        return data if len(data) <= MAX_BYTES else None

    data = attempt(frames)
    if data:
        return data, ""

    for colors in (256, 128, 64):
        q = _quantize(frames, colors)
        if q and (data := attempt(q)):
            return data, f"減色{colors}色"

    for ratio in (0.9, 0.8, 0.7, 0.6):
        w, h = frames[0].size
        nw, nh = _even_floor(int(w * ratio)), _even_floor(int(h * ratio))
        scaled = [f.resize((nw, nh), Image.LANCZOS) for f in frames]
        for fs, note in ((_quantize(scaled, 128), f"縮小{int(ratio*100)}%+減色128色"),
                         (scaled, f"縮小{int(ratio*100)}%")):
            if fs and (data := attempt(fs)):
                return data, note

    n = len(frames)
    for target_n in (10, 8, 6, 5):
        if target_n >= n:
            continue
        idx = [round(i * (n - 1) / (target_n - 1)) for i in range(target_n)]
        thin = [frames[i] for i in idx]
        for colors in (128, 64):
            q = _quantize(thin, colors) or thin
            if data := attempt(q):
                return data, f"{target_n}フレーム+減色{colors}色"

    return None, "300KB以下にできませんでした"


# ------------------------------------------------------- validate

def read_apng_info(path):
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    durations = []
    for i in range(n):
        im.seek(i)
        durations.append(int(im.info.get("duration", 0)))
    loops = im.info.get("loop", 1)
    return {
        "size": im.size,
        "frames": n,
        "durations_ms": durations,
        "content_ms": sum(durations),
        "loops": loops,
        "bytes": Path(path).stat().st_size,
    }


def check_holes(path):
    """全フレームを走査してキャラ内部の透過画素数を数える。"""
    im = Image.open(path)
    worst = 0
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        rgba = np.array(im.convert("RGBA"))
        alpha = rgba[..., 3]
        transparent = alpha < 16
        exterior = flood_exterior(transparent)
        holes = int(((alpha < 200) & ~exterior).sum())
        worst = max(worst, holes)
    return worst


def validate_apng(path, size=(MAX_W, MAX_H), exact=False, animated=True, deep=False):
    info = read_apng_info(path)
    errors, warnings = [], []
    w, h = info["size"]
    if exact:
        if (w, h) != size:
            errors.append(f"サイズが {w}x{h}（要 {size[0]}x{size[1]}ぴったり）")
    else:
        if w > size[0] or h > size[1]:
            errors.append(f"サイズが {w}x{h}（最大 {size[0]}x{size[1]}）")
        if w % 2 or h % 2:
            warnings.append(f"サイズ {w}x{h} が奇数（偶数推奨）")
    if info["bytes"] > MAX_BYTES:
        errors.append(f"{info['bytes']//1024}KB（最大300KB）")
    if animated:
        if not MIN_FRAMES <= info["frames"] <= MAX_FRAMES:
            errors.append(f"{info['frames']}フレーム（5〜20の範囲外）")
        loops = info["loops"]
        if loops == 0:
            errors.append("ループ回数が無限（1〜4回にする）")
            loops = 1
        total = info["content_ms"] * loops
        if total not in VALID_TOTALS_MS:
            errors.append(f"再生時間がループ込み {total/1000:.2f}秒（1/2/3/4秒ぴったりにする）")
    else:
        if info["frames"] > 1:
            errors.append("静止画のはずがアニメーションになっている")
    if deep:
        holes = check_holes(path)
        if holes > 0:
            errors.append(f"キャラ内部に透過画素が {holes}px（審査リジェクト要因）")
    return info, errors, warnings


# ------------------------------------------------------- convert

def parse_segments(spec):
    segs = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([\d.]+)\s*[-:]\s*([\d.]+)$", part)
        if not m:
            sys.exit(f"セグメント指定が不正です: {part}（例: 0-1.5,1.6-3.0）")
        a, b = float(m.group(1)), float(m.group(2))
        if b <= a:
            sys.exit(f"セグメント指定が不正です: {part}")
        segs.append((a, b))
    return segs


def next_index(outdir, prefix):
    mx = 0
    for f in outdir.glob(f"{prefix}*.png"):
        m = re.match(rf"^{re.escape(prefix)}(\d+)$", f.stem)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def cmd_convert(args):
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    idx = args.start_index or next_index(outdir, args.prefix)
    results = []

    for video in args.videos:
        video = Path(video)
        if not video.exists():
            sys.exit(f"動画が見つかりません: {video}")
        vdur = video_duration(video)
        if args.segments:
            segs = parse_segments(args.segments)
        else:
            step = args.every
            segs = []
            t = 0.0
            while t < vdur - 0.2:
                segs.append((t, min(t + step, vdur)))
                t += step
        print(f"▶ {video.name}（{vdur:.1f}秒）→ {len(segs)}セグメント")

        for (start, end) in segs:
            seg_dur = end - start
            total_s = args.duration or max(1, min(4, round(seg_dur)))
            total_ms = total_s * 1000
            name = f"{args.prefix}{idx:02d}"
            idx += 1

            raw = extract_frames(video, start, seg_dur, args.frames)
            if raw is None:
                print(f"  ✗ {name}: フレーム抽出に失敗（スキップ）")
                continue

            key = estimate_key_color(raw[0])
            keyed = [chroma_key(f, key, args.key_low, args.key_high) for f in raw]
            keyed, speck_px = remove_specks(keyed, args.min_speck)
            hole_px = 0
            fixed = []
            for f in keyed:
                g, n_holes = fill_holes(f)
                hole_px = max(hole_px, n_holes)
                fixed.append(g)

            frames = crop_and_fit(fixed)
            if frames is None:
                print(f"  ✗ {name}: キャラが検出できません（全面透過）→ スキップ")
                continue
            frames = harden_interior(frames)
            coverage = np.array(frames[0])[..., 3].mean() / 255
            data, note = encode_under_limit(frames, total_ms, args.loops)
            if data is None:
                print(f"  ✗ {name}: {note}（スキップ）")
                continue

            path = outdir / f"{name}.png"
            path.write_bytes(data)
            thumb = Image.open(io.BytesIO(data))
            thumb.seek(0)
            thumb.convert("RGBA").save(outdir / f"{name}_thumb.png")

            info = read_apng_info(path)
            notes = [n for n in (note,
                                 f"内部穴{hole_px}px修復" if hole_px else "",
                                 f"ゴミ{speck_px}px除去" if speck_px else "") if n]
            results.append({
                "name": name, "video": video.name,
                "segment": f"{start:.1f}-{end:.1f}s",
                "size": list(info["size"]), "frames": info["frames"],
                "total_s": total_s, "kb": info["bytes"] // 1024,
                "coverage": round(float(coverage), 3),
                "notes": notes,
            })
            print(f"  ✓ {name}: {info['size'][0]}x{info['size'][1]} "
                  f"{info['frames']}f {total_s}s {info['bytes']//1024}KB"
                  + (f"（{'、'.join(notes)}）" if notes else ""))

    manifest_path = outdir / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    old = [r for r in old if r["name"] not in {x["name"] for x in results}]
    manifest_path.write_text(
        json.dumps(old + results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n候補 {len(results)}個 を {outdir}/ に生成しました。"
          f"次: python stamp.py preview --dir {outdir}")


# ------------------------------------------------------- preview

PREVIEW_HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>スタンプ選定</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
         background: #f0f2f5; color: #333; padding: 16px; }
  h1 { font-size: 18px; margin-bottom: 4px; }
  .hint { font-size: 12px; color: #888; margin-bottom: 12px; }
  .bar { position: sticky; top: 0; background: #fff; border-radius: 10px;
         padding: 10px 14px; margin-bottom: 14px; box-shadow: 0 1px 6px rgba(0,0,0,.08);
         display: flex; gap: 10px; align-items: center; flex-wrap: wrap; z-index: 10; }
  .bar b { font-size: 15px; }
  .bar button { padding: 6px 14px; border: none; border-radius: 6px;
                background: #06c755; color: #fff; font-weight: 700; cursor: pointer; }
  .bar button.sub { background: #999; }
  #cmd { width: 100%; font-size: 11px; font-family: monospace; background: #f6f6f6;
         border: 1px solid #ddd; border-radius: 6px; padding: 6px; display: none; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
  .card { background: #fff; border-radius: 10px; padding: 10px;
          box-shadow: 0 1px 4px rgba(0,0,0,.07); position: relative; }
  .card.sel { outline: 3px solid #06c755; }
  .imgwrap { background: repeating-conic-gradient(#eee 0% 25%, #fff 0% 50%) 0 0/16px 16px;
             border-radius: 6px; display: flex; justify-content: center;
             align-items: center; height: 150px; cursor: pointer; overflow: hidden; }
  .imgwrap img { max-width: 100%; max-height: 100%; }
  .play { position: absolute; top: 14px; left: 14px; width: 26px; height: 26px;
          border-radius: 50%; background: rgba(0,0,0,.55); color: #fff;
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; pointer-events: none; }
  .meta { font-size: 11px; color: #777; margin-top: 6px; line-height: 1.5; }
  .meta b { color: #333; font-size: 13px; }
  .order { position: absolute; top: 8px; right: 8px; min-width: 26px; height: 26px;
           border-radius: 13px; background: #06c755; color: #fff; font-weight: 700;
           display: none; align-items: center; justify-content: center; font-size: 13px;
           padding: 0 6px; }
  .card.sel .order { display: flex; }
  .selbtn { margin-top: 6px; width: 100%; padding: 5px; border: 1px solid #06c755;
            background: #fff; color: #06c755; border-radius: 6px; font-weight: 700;
            cursor: pointer; }
  .card.sel .selbtn { background: #06c755; color: #fff; }
</style></head><body>
<h1>スタンプ選定ページ</h1>
<div class="hint">▶をクリックで再生／「選択」で採用（クリック順＝並び順）。1個目がセットの顔。</div>
<div class="bar">
  <b><span id="count">0</span> / <span id="target">24</span> 個選択中</b>
  <button onclick="genCmd()">packageコマンドを表示</button>
  <button class="sub" onclick="clearSel()">選択をリセット</button>
  <textarea id="cmd" rows="3" readonly onclick="this.select()"></textarea>
</div>
<div class="grid" id="grid"></div>
<script>
const ITEMS = __ITEMS__;
const KEY = "stamp-sel:" + location.pathname;
let sel = JSON.parse(localStorage.getItem(KEY) || "[]").filter(n => ITEMS.some(i => i.name === n));

const grid = document.getElementById("grid");
for (const it of ITEMS) {
  const card = document.createElement("div");
  card.className = "card"; card.dataset.name = it.name;
  card.innerHTML = `
    <div class="imgwrap"><img src="${it.name}_thumb.png" data-state="still"></div>
    <div class="play">▶</div>
    <div class="order"></div>
    <div class="meta"><b>${it.name}</b><br>${it.segment || ""} ${it.video || ""}<br>
      ${it.size[0]}x${it.size[1]} / ${it.frames}f / ${it.total_s}s / ${it.kb}KB
      ${it.notes && it.notes.length ? "<br>⚙ " + it.notes.join("、") : ""}</div>
    <button class="selbtn">選択</button>`;
  const img = card.querySelector("img");
  card.querySelector(".imgwrap").onclick = () => {
    const playing = img.dataset.state === "anim";
    img.src = playing ? `${it.name}_thumb.png` : `${it.name}.png?t=${Date.now()}`;
    img.dataset.state = playing ? "still" : "anim";
    card.querySelector(".play").textContent = playing ? "▶" : "⏸";
  };
  card.querySelector(".selbtn").onclick = () => {
    const i = sel.indexOf(it.name);
    if (i >= 0) sel.splice(i, 1); else sel.push(it.name);
    save(); render();
  };
  grid.appendChild(card);
}
function save() { localStorage.setItem(KEY, JSON.stringify(sel)); }
function render() {
  document.getElementById("count").textContent = sel.length;
  for (const card of grid.children) {
    const i = sel.indexOf(card.dataset.name);
    card.classList.toggle("sel", i >= 0);
    card.querySelector(".order").textContent = i + 1;
    card.querySelector(".selbtn").textContent = i >= 0 ? `選択中（${i + 1}番目）` : "選択";
  }
}
function clearSel() { sel = []; save(); render(); }
function genCmd() {
  const ta = document.getElementById("cmd");
  ta.style.display = "block";
  if (![8, 16, 24].includes(sel.length)) {
    ta.value = `※ 選択数は 8 / 16 / 24 個にしてください（現在 ${sel.length} 個）`;
    return;
  }
  ta.value = `python stamp.py package --dir ${"__DIR__"} --list "${sel.join(",")}"`;
  ta.select();
  try { document.execCommand("copy"); } catch (e) {}
}
render();
</script></body></html>
"""


def cmd_preview(args):
    outdir = Path(args.dir)
    manifest_path = outdir / "manifest.json"
    items = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    known = {i["name"] for i in items}
    for f in sorted(outdir.glob("*.png")):
        if f.stem.endswith("_thumb") or f.stem in known:
            continue
        try:
            info = read_apng_info(f)
        except Exception:
            continue
        thumb = outdir / f"{f.stem}_thumb.png"
        if not thumb.exists():
            im = Image.open(f)
            im.seek(0)
            im.convert("RGBA").save(thumb)
        items.append({
            "name": f.stem, "video": "", "segment": "",
            "size": list(info["size"]), "frames": info["frames"],
            "total_s": info["content_ms"] * max(info["loops"], 1) / 1000,
            "kb": info["bytes"] // 1024, "notes": [],
        })
    if not items:
        sys.exit(f"{outdir}/ に候補APNGがありません。先に convert を実行してください。")
    html = PREVIEW_HTML.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__DIR__", str(outdir))
    out = outdir / "preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"確認ページを生成しました: {out}\nブラウザで開いて24個（または8/16個）選んでください。")


# ------------------------------------------------------- package

def _fit_on_canvas(frames, canvas_size):
    """frames をアスペクト維持で縮小し、透明キャンバス中央に配置する。"""
    cw, ch = canvas_size
    w, h = frames[0].size
    scale = min(cw / w, ch / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    out = []
    for f in frames:
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(f.resize((nw, nh), Image.LANCZOS), ((cw - nw) // 2, (ch - nh) // 2))
        out.append(canvas)
    return out


def load_apng_frames(path):
    im = Image.open(path)
    frames, durations = [], []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        frames.append(im.convert("RGBA").copy())
        durations.append(int(im.info.get("duration", 100)))
    loops = im.info.get("loop", 1)
    return frames, durations, loops


def cmd_package(args):
    srcdir = Path(args.dir)
    if args.json:
        names = json.loads(Path(args.json).read_text())
    else:
        names = [n.strip() for n in args.list.split(",") if n.strip()]
    if len(names) not in VALID_SET_COUNTS:
        sys.exit(f"選択数が {len(names)} 個です。8 / 16 / 24 個にしてください。")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    ok = True

    for i, name in enumerate(names, 1):
        src = srcdir / f"{name}.png"
        if not src.exists():
            sys.exit(f"候補が見つかりません: {src}")
        dst = outdir / f"{i:02d}.png"
        shutil.copyfile(src, dst)

    # main.png: 240x240 の APNG（デフォルトは1個目のスタンプから生成）
    main_src = srcdir / f"{args.main or names[0]}.png"
    frames, durations, loops = load_apng_frames(main_src)
    total_ms = sum(durations) * max(loops, 1)
    if total_ms not in VALID_TOTALS_MS:
        total_ms = min(VALID_TOTALS_MS, key=lambda t: abs(t - total_ms))
    main_frames = harden_interior(_fit_on_canvas(frames, MAIN_SIZE))
    data, note = encode_under_limit(main_frames, total_ms, max(loops, 1))
    if data is None:
        sys.exit(f"main.png を300KB以下にできませんでした（{main_src}）")
    (outdir / "main.png").write_bytes(data)

    # tab.png: 96x74 の静止透過PNG（1フレーム目から生成）
    tab = harden_interior(_fit_on_canvas([frames[0]], TAB_SIZE))[0]
    tab.save(outdir / "tab.png", format="PNG", optimize=True)

    print("── 規格チェック ──")
    targets = [("main.png", MAIN_SIZE, True, True), ("tab.png", TAB_SIZE, True, False)]
    targets += [(f"{i:02d}.png", (MAX_W, MAX_H), False, True) for i in range(1, len(names) + 1)]
    for fname, size, exact, animated in targets:
        info, errors, warnings = validate_apng(
            outdir / fname, size=size, exact=exact, animated=animated, deep=True)
        mark = "✗" if errors else ("△" if warnings else "✓")
        if errors:
            ok = False
        line = f" {mark} {fname}: {info['size'][0]}x{info['size'][1]} " \
               f"{info['frames']}f {info['bytes']//1024}KB"
        for e in errors:
            line += f"\n     ✗ {e}"
        for w in warnings:
            line += f"\n     △ {w}"
        print(line)

    if not ok:
        sys.exit("\n規格エラーがあるため zip は作成しませんでした。修正して再実行してください。")

    zip_path = outdir / args.zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        z.write(outdir / "main.png", "main.png")
        z.write(outdir / "tab.png", "tab.png")
        for i in range(1, len(names) + 1):
            z.write(outdir / f"{i:02d}.png", f"{i:02d}.png")
    print(f"\n申請用zipを作成しました: {zip_path}（{zip_path.stat().st_size//1024}KB）")
    print("LINE Creators Market → 新規登録 → アニメーションスタンプ でアップロードしてください。")


# ------------------------------------------------------- validate cmd

def cmd_validate(args):
    ok = True
    for target in args.paths:
        target = Path(target)
        if target.suffix == ".zip":
            with zipfile.ZipFile(target) as z, tempfile.TemporaryDirectory() as td:
                z.extractall(td)
                names = sorted(z.namelist())
                stamps = [n for n in names if re.match(r"^\d\d\.png$", n)]
                print(f"■ {target.name}: {len(names)}ファイル（スタンプ{len(stamps)}個）")
                if "main.png" not in names or "tab.png" not in names:
                    print("  ✗ main.png / tab.png が不足")
                    ok = False
                if len(stamps) not in VALID_SET_COUNTS:
                    print(f"  ✗ スタンプ数 {len(stamps)}（8/16/24個にする）")
                    ok = False
                for n in names:
                    p = Path(td) / n
                    if n == "main.png":
                        size, exact, animated = MAIN_SIZE, True, True
                    elif n == "tab.png":
                        size, exact, animated = TAB_SIZE, True, False
                    else:
                        size, exact, animated = (MAX_W, MAX_H), False, True
                    info, errors, warnings = validate_apng(
                        p, size=size, exact=exact, animated=animated, deep=True)
                    mark = "✗" if errors else ("△" if warnings else "✓")
                    if errors:
                        ok = False
                    print(f"  {mark} {n}: {info['size'][0]}x{info['size'][1]} "
                          f"{info['frames']}f {info['bytes']//1024}KB")
                    for e in errors:
                        print(f"      ✗ {e}")
                    for w in warnings:
                        print(f"      △ {w}")
        else:
            info, errors, warnings = validate_apng(target, deep=True)
            mark = "✗" if errors else ("△" if warnings else "✓")
            if errors:
                ok = False
            total = info["content_ms"] * max(info["loops"], 1)
            print(f"{mark} {target}: {info['size'][0]}x{info['size'][1]} "
                  f"{info['frames']}f 再生{total/1000:.2f}s(ループ{info['loops']}) "
                  f"{info['bytes']//1024}KB")
            for e in errors:
                print(f"    ✗ {e}")
            for w in warnings:
                print(f"    △ {w}")
    sys.exit(0 if ok else 1)


# ------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="LINEアニメーションスタンプ制作パイプライン")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("convert", help="グリーンバック動画→透過APNG候補")
    p.add_argument("videos", nargs="+", help="動画ファイル（複数可）")
    p.add_argument("--out", default="work/candidates", help="出力先（既定: work/candidates）")
    p.add_argument("--every", type=float, default=1.5, help="等間隔カットの秒数（既定: 1.5）")
    p.add_argument("--segments", help='手動カット指定 例: "0-1.5,1.6-3.2"')
    p.add_argument("--duration", type=int, choices=(1, 2, 3, 4),
                   help="再生秒数を固定（省略時はカット長から自動選択）")
    p.add_argument("--frames", type=int, default=10, help="フレーム数 5〜20（既定: 10）")
    p.add_argument("--loops", type=int, default=1, choices=(1, 2, 3, 4),
                   help="ループ回数（既定: 1）")
    p.add_argument("--prefix", default="cand_", help="候補名の接頭辞（既定: cand_）")
    p.add_argument("--start-index", type=int, help="連番の開始番号（省略時は続きから）")
    p.add_argument("--key-low", type=float, default=55, help="キー距離: 完全透過しきい値")
    p.add_argument("--key-high", type=float, default=130, help="キー距離: 完全不透明しきい値")
    p.add_argument("--min-speck", type=int, default=40, help="除去する浮きゴミの最大面積px")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("preview", help="候補一覧の確認用HTMLを生成")
    p.add_argument("--dir", default="work/candidates")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("package", help="選定した候補から申請用zipを作成")
    p.add_argument("--dir", default="work/candidates", help="候補ディレクトリ")
    p.add_argument("--list", help='採用する候補名を順番に 例: "cand_03,cand_11,..."')
    p.add_argument("--json", help="採用リストのJSONファイル")
    p.add_argument("--main", help="main.png の元にする候補名（既定: 1個目）")
    p.add_argument("--out", default="submit", help="出力先（既定: submit）")
    p.add_argument("--zip-name", default="stamps.zip")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("validate", help="APNG/zipの規格チェック")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    if args.cmd == "package" and not (args.list or args.json):
        ap.error("--list か --json で採用リストを指定してください")
    args.func(args)


if __name__ == "__main__":
    main()
