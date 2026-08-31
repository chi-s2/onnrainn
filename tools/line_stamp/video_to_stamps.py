#!/usr/bin/env python3
"""動画1本から、スタンプ候補のAPNGをまとめて書き出す（工程4）。

グリーンバックで撮った生成動画を渡すと、

  1. フレームを取り出す
  2. カットに分ける（既定は1.5秒ごと。自動検出も可）
  3. 緑背景を透過させる
  4. キャラ内部に残った透過の穴を埋める（審査でリジェクトされた原因への対策）
  5. 中身に合わせて余白を切る
  6. 決めポーズ（最終コマ）を1コマ目に移す
  7. LINE規格に整えて APNG で書き出す

までを一度にやる。1本15秒・1.5秒刻みなら候補が10個できる。

使い方:
    python3 video_to_stamps.py movie.mp4 -o cand/
    python3 video_to_stamps.py movie.mp4 -o cand/ --cut-seconds 1.5
    python3 video_to_stamps.py movie.mp4 -o cand/ --detect      # カット自動検出
    python3 video_to_stamps.py frames/  -o cand/ --no-green     # 透過済み素材から
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow と numpy が必要です:  pip install Pillow numpy scipy")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chroma
from last_frame_first import (
    ALLOWED_LOOPS, MAX_BYTES, MAX_H, MAX_W, Clip,
    build_stamp, ffmpeg_exe, report, save_apng,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


# ---- フレームの取り出し -----------------------------------------------------
def extract_frames(src: Path, fps: float, workdir: Path) -> list:
    if src.is_dir():
        files = sorted(p for p in src.iterdir()
                       if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file())
        if not files:
            raise SystemExit(f"{src} に画像が見つかりません")
        return [Image.open(p).convert("RGBA") for p in files]

    if src.suffix.lower() not in VIDEO_SUFFIXES:
        # GIF / APNG などのアニメ画像
        from PIL import ImageSequence
        return [p.convert("RGBA") for p in ImageSequence.Iterator(Image.open(src))]

    subprocess.run(
        [ffmpeg_exe(), "-loglevel", "error", "-i", str(src),
         "-vf", f"fps={fps}", str(workdir / "%05d.png")],
        check=True,
    )
    files = sorted(workdir.glob("*.png"))
    if not files:
        raise SystemExit(f"{src} からフレームを取り出せませんでした")
    return [Image.open(p).convert("RGBA") for p in files]


# ---- カット分割 -------------------------------------------------------------
def split_fixed(n: int, per_cut: int) -> list:
    """per_cut コマずつの等分割。端数は最後のカットに寄せる。"""
    if per_cut >= n:
        return [(0, n)]
    cuts = [(i, min(i + per_cut, n)) for i in range(0, n, per_cut)]
    if cuts[-1][1] - cuts[-1][0] < per_cut / 2 and len(cuts) > 1:
        cuts[-2] = (cuts[-2][0], cuts[-1][1])   # 短すぎる尻尾は前にくっつける
        cuts.pop()
    return cuts


def split_detected(frames: list, sensitivity: float, min_len: int) -> list:
    """コマ間の差が大きいところをカットの切れ目とみなす。"""
    small = [np.asarray(f.convert("RGB").resize((64, 64)), dtype=np.int16)
             for f in frames]
    diffs = np.array([np.abs(small[i] - small[i - 1]).mean()
                      for i in range(1, len(small))])
    if diffs.size == 0 or diffs.max() == 0:
        return [(0, len(frames))]

    threshold = diffs.max() * sensitivity
    bounds = [0]
    for i, d in enumerate(diffs, start=1):
        if d >= threshold and i - bounds[-1] >= min_len:
            bounds.append(i)
    bounds.append(len(frames))
    cuts = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    return [c for c in cuts if c[1] - c[0] >= min_len] or [(0, len(frames))]


# ---- 1カットの処理 ----------------------------------------------------------
def process_cut(frames: list, args, per_frame_ms: int) -> tuple:
    stats = {"holes": 0, "hole_px": 0, "soft_px": 0}
    work = []
    for f in frames:
        if not args.no_green:
            f = chroma.remove_green(f, keep=args.green_keep, cut=args.green_cut,
                                    despill=not args.no_despill)
        if not args.no_clean:
            f, st = chroma.clean(f, max_area=args.max_hole, margin=args.edge_margin)
            for k in stats:
                stats[k] += st[k]
        work.append(f)

    if not args.no_trim:
        box = chroma.union_bbox(work, pad=args.trim_pad)
        if box and box[2] > box[0] and box[3] > box[1]:
            work = [f.crop(box) for f in work]

    clip = Clip(work, [per_frame_ms] * len(work))
    clip, loop, played = build_stamp(
        clip, mode=args.mode, pose=args.pose_frame,
        loop=args.loop, seconds=args.seconds, size=args.size,
    )

    # 縮小すると穴と半透明がまた出るので、仕上げにもう一度かける。ここが最終形。
    if not args.no_clean:
        frames = []
        for f in clip.frames:
            if not args.no_green and not args.no_despill:
                f = chroma.despill_visible(f)
            f, st = chroma.clean(f, max_area=args.max_hole, margin=args.edge_margin)
            stats["holes"] += st["holes"]
            stats["hole_px"] += st["hole_px"]
            stats["soft_px"] += st["soft_px"]
            frames.append(f)
        clip = Clip(frames, clip.durations)
    return clip, loop, played, stats


# ---- CLI --------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="動画1本からスタンプ候補のAPNGをまとめて書き出す",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", type=Path, help="動画 / GIF / APNG / 連番PNGのフォルダ")
    ap.add_argument("-o", "--outdir", type=Path, default=Path("stamps"),
                    help="書き出し先フォルダ（既定 stamps/）")
    ap.add_argument("--fps", type=float, default=12.0, help="切り出すfps（既定12）")

    g = ap.add_argument_group("カット分割")
    g.add_argument("--cut-seconds", type=float, default=1.5,
                   help="1カットの長さ（秒）。既定1.5")
    g.add_argument("--cuts", type=int, help="カット数を指定して等分割する")
    g.add_argument("--detect", action="store_true", help="コマ間の差からカットを自動検出")
    g.add_argument("--sensitivity", type=float, default=0.35,
                   help="--detect の閾値。小さいほど細かく切る（既定0.35）")

    g = ap.add_argument_group("透過処理")
    g.add_argument("--no-green", action="store_true", help="グリーンバック除去をしない")
    g.add_argument("--green-keep", type=int, default=25,
                   help="これ以下の緑らしさは残す（既定25）")
    g.add_argument("--green-cut", type=int, default=60,
                   help="これ以上の緑らしさは透過（既定60）")
    g.add_argument("--no-despill", action="store_true", help="輪郭の緑かぶり抑制をしない")
    g.add_argument("--no-clean", action="store_true", help="内部の透過穴の処理をしない")
    g.add_argument("--max-hole", type=float, default=0.02,
                   help="埋める穴の上限（画像に対する面積比。0ですべて埋める）")
    g.add_argument("--edge-margin", type=int, default=2,
                   help="輪郭から何画素内側をベタ塗りするか（既定2）")
    g.add_argument("--no-trim", action="store_true", help="余白のトリミングをしない")
    g.add_argument("--trim-pad", type=int, default=2, help="トリミング時に残す余白（既定2）")

    g = ap.add_argument_group("スタンプの整形")
    g.add_argument("--mode", choices=("rotate", "duplicate", "none"), default="rotate",
                   help="決めポーズの1コマ目への入れ方（既定rotate）")
    g.add_argument("--pose-frame", type=int, default=-1,
                   help="決めポーズのコマ番号。1始まり、負数で末尾から（既定-1=最終コマ）")
    g.add_argument("--loop", type=int, choices=ALLOWED_LOOPS, help="ループ回数1〜4")
    g.add_argument("--seconds", type=int, choices=(1, 2, 3, 4),
                   help="ループ込みの再生時間（秒）")
    g.add_argument("--size", default=f"{MAX_W}x{MAX_H}", help="最大サイズ WxH（既定320x270）")
    g.add_argument("--max-bytes", type=int, default=MAX_BYTES, help="上限バイト数")
    g.add_argument("--start", type=int, default=1, help="連番の開始番号（既定1）")
    ap.add_argument("--verbose", action="store_true", help="1カットずつ規格チェックを表示")
    args = ap.parse_args(argv)

    if not args.input.exists():
        return print(f"入力が見つかりません: {args.input}") or 1
    if args.pose_frame > 0:
        args.pose_frame -= 1          # 1始まり → 0始まり

    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(args.input, args.fps, Path(tmp))
    n = len(frames)
    per_frame_ms = max(1, round(1000 / args.fps))

    if args.detect:
        min_len = max(2, int(args.fps * 0.4))
        cuts = split_detected(frames, args.sensitivity, min_len)
        how = f"自動検出（感度{args.sensitivity}）"
    elif args.cuts:
        per = max(1, -(-n // args.cuts))
        cuts = split_fixed(n, per)
        how = f"{args.cuts}分割の指定"
    else:
        per = max(1, round(args.fps * args.cut_seconds))
        cuts = split_fixed(n, per)
        how = f"{args.cut_seconds}秒ごと"

    print(f"入力      {args.input}  →  {n}コマ ({args.fps}fps, {n / args.fps:.1f}秒)")
    print(f"カット    {len(cuts)}個  [{how}]")
    print(f"透過      {'なし' if args.no_green else f'グリーンバック除去 keep={args.green_keep} cut={args.green_cut}'}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    total_holes = ng = 0
    for i, (a, b) in enumerate(cuts):
        out = args.outdir / f"{args.start + i:02d}.png"
        clip, loop, played, stats = process_cut(frames[a:b], args, per_frame_ms)
        size, method, clip = save_apng(clip, out, loop, args.max_bytes,
                                       clean=not args.no_clean)
        total_holes += stats["holes"]
        ok = size <= args.max_bytes
        ng += 0 if ok else 1
        w, h = clip.frames[0].size
        print(f"  {'OK' if ok else 'NG'}  {out.name}  "
              f"コマ{b - a}→{len(clip.frames)}  {w}x{h}  "
              f"{clip.total_ms / 1000:.2f}秒x{loop}={played / 1000:g}秒  "
              f"{size / 1024:.0f}KB  穴{stats['holes']}  [{method}]")
        if args.verbose:
            report(out)

    print(f"\n書き出し  {args.outdir}/  に {len(cuts)}個")
    if total_holes:
        print(f"内部の透過穴を {total_holes}箇所 埋めました（審査対策）")
    if ng:
        print(f"※ {ng}個が300KBに収まりませんでした。--fps を下げるか素材を見直してください。")
    print("次は候補を見比べて24個を選ぶ工程です。")
    return 1 if ng else 0


if __name__ == "__main__":
    raise SystemExit(main())
