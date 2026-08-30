#!/usr/bin/env python3
"""動くLINEスタンプの「最後のコマを1コマ目に」変換ツール。

動くスタンプは再生が終わったあと、トークに残り続けるのが 1コマ目。
そのため決めポーズ（生成動画ではたいてい最終コマ）を 1コマ目に持ってくると、
送ったあとの見栄えが一段よくなる。

このスクリプトは GIF / APNG / WebP / 連番PNG / 動画 を受け取り、
  1. 決めポーズのコマを先頭へ移動（デフォルトは最終コマ）
  2. LINE のアニメーションスタンプ規格に合わせて整形
     （320x270 以内・偶数サイズ / 5〜20コマ / 再生1〜4秒 / 300KB以内）
  3. APNG として書き出す
までをまとめて行う。

使い方:
    python3 last_frame_first.py input.gif -o stamp01.png
    python3 last_frame_first.py frames/ --fps 12 -o stamp01.png
    python3 last_frame_first.py movie.mp4 --fps 10 -o stamp01.png   # ffmpeg が必要
    python3 last_frame_first.py stamp01.png --check                 # 規格チェックのみ
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ImportError:  # pragma: no cover
    sys.exit("Pillow が必要です:  pip install Pillow")


# ---- LINE アニメーションスタンプの規格 -------------------------------------
MAX_W, MAX_H = 320, 270
MIN_FRAMES, MAX_FRAMES = 5, 20
MIN_TOTAL_MS, MAX_TOTAL_MS = 1000, 4000
MAX_BYTES = 300 * 1024
MIN_FRAME_MS = 20  # ブラウザ/端末が無視しない下限

IMAGE_SUFFIXES = {".png", ".gif", ".webp", ".apng", ".jpg", ".jpeg", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


@dataclass
class Clip:
    """コマ画像（RGBA）と各コマの表示時間（ms）の組。"""

    frames: list
    durations: list

    def __post_init__(self):
        if len(self.frames) != len(self.durations):
            raise ValueError("frames と durations の数が一致しません")

    @property
    def total_ms(self) -> int:
        return sum(self.durations)


# ---- 読み込み ---------------------------------------------------------------
def load_clip(src: Path, fps: float | None) -> Clip:
    if src.is_dir():
        return _load_from_dir(src, fps or 12.0)
    if src.suffix.lower() in VIDEO_SUFFIXES:
        return _load_from_video(src, fps or 10.0)
    return _load_from_animation(src, fps)


def _load_from_dir(src: Path, fps: float) -> Clip:
    files = sorted(
        p for p in src.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file()
    )
    if not files:
        raise SystemExit(f"{src} に画像が見つかりません")
    frames = [Image.open(p).convert("RGBA") for p in files]
    per = max(MIN_FRAME_MS, round(1000 / fps))
    return Clip(frames, [per] * len(frames))


def _load_from_animation(src: Path, fps: float | None) -> Clip:
    im = Image.open(src)
    frames, durations = [], []
    for page in ImageSequence.Iterator(im):
        frames.append(page.convert("RGBA"))
        durations.append(int(page.info.get("duration", 0) or 0))
    if not frames:
        raise SystemExit(f"{src} からコマを読み取れませんでした")
    if fps or not any(durations):
        per = max(MIN_FRAME_MS, round(1000 / (fps or 12.0)))
        durations = [per] * len(frames)
    else:
        fallback = max(d for d in durations)
        durations = [max(MIN_FRAME_MS, d or fallback) for d in durations]
    return Clip(frames, durations)


def _load_from_video(src: Path, fps: float) -> Clip:
    if not shutil.which("ffmpeg"):
        raise SystemExit(
            "動画の読み込みには ffmpeg が必要です。\n"
            "先に GIF / APNG / 連番PNG に書き出してから渡してください。"
        )
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["ffmpeg", "-loglevel", "error", "-i", str(src),
               "-vf", f"fps={fps}", os.path.join(tmp, "%04d.png")]
        subprocess.run(cmd, check=True)
        clip = _load_from_dir(Path(tmp), fps)
    print("※ 動画から読み込んだため背景は透過していません。"
          "透過が必要なら透過つきの素材を渡してください。")
    return clip


# ---- 変換ステップ -----------------------------------------------------------
def move_pose_to_front(clip: Clip, mode: str, pose: int) -> Clip:
    """決めポーズのコマを 1コマ目に持ってくる。

    mode="rotate"    : 順序を回転させる（コマ数は変わらない。ループ再生なら見た目は同じ）
    mode="duplicate" : 決めポーズの複製を先頭に足す（コマ数 +1）
    mode="none"      : 並べ替えない
    """
    n = len(clip.frames)
    idx = pose if pose >= 0 else n + pose
    if not 0 <= idx < n:
        raise SystemExit(f"--pose-frame が範囲外です（1〜{n} で指定してください）")

    if mode == "none" or (mode == "rotate" and idx == 0):
        return clip
    if mode == "rotate":
        return Clip(clip.frames[idx:] + clip.frames[:idx],
                    clip.durations[idx:] + clip.durations[:idx])
    if mode == "duplicate":
        return Clip([clip.frames[idx].copy()] + clip.frames,
                    [clip.durations[idx]] + clip.durations)
    raise SystemExit(f"未知の mode: {mode}")


def fit_frame_count(clip: Clip, lo: int = MIN_FRAMES, hi: int = MAX_FRAMES) -> Clip:
    """コマ数を 5〜20 に収める。総再生時間と 1コマ目は保つ。"""
    clip = _thin_frames(clip, hi)
    return _pad_frames(clip, lo)


def _thin_frames(clip: Clip, hi: int) -> Clip:
    n = len(clip.frames)
    if n <= hi:
        return clip
    # 1コマ目（決めポーズ）は必ず残し、残りを等間隔で間引く。
    keep = sorted({0} | {round(i * (n - 1) / (hi - 1)) for i in range(hi)})
    frames = [clip.frames[i] for i in keep]
    # 捨てたコマの表示時間は直前の残ったコマへ寄せる（総時間を維持）。
    durations, bucket = [], 0
    keep_set = set(keep)
    for i in range(n):
        bucket += clip.durations[i]
        if i + 1 in keep_set or i == n - 1:
            durations.append(bucket)
            bucket = 0
    return Clip(frames, durations[: len(frames)])


def _pad_frames(clip: Clip, lo: int) -> Clip:
    frames, durations = list(clip.frames), list(clip.durations)
    # 表示時間が最も長いコマを2つに割って増やす（見た目も総時間も変わらない）。
    while len(frames) < lo:
        i = max(range(len(durations)), key=lambda k: durations[k])
        half = durations[i] / 2
        durations[i : i + 1] = [math.ceil(half), math.floor(half)]
        frames[i : i + 1] = [frames[i], frames[i].copy()]
    return Clip(frames, [max(1, int(d)) for d in durations])


def fit_duration(clip: Clip) -> Clip:
    """総再生時間を 1〜4 秒に収める。"""
    total = clip.total_ms
    n = len(clip.durations)
    floor_total = MIN_FRAME_MS * n
    target = min(max(total, MIN_TOTAL_MS, floor_total), MAX_TOTAL_MS)
    if target < floor_total:  # コマ数が多すぎて 4 秒に収まらないケースは起きない
        target = floor_total
    if total == target:
        return clip
    scale = target / total if total else 1
    scaled = [max(MIN_FRAME_MS, round(d * scale)) for d in clip.durations]
    # 丸め誤差を最長コマで吸収する。
    diff = target - sum(scaled)
    if diff:
        i = max(range(n), key=lambda k: scaled[k])
        scaled[i] = max(MIN_FRAME_MS, scaled[i] + diff)
    return Clip(clip.frames, scaled)


def fit_size(clip: Clip, max_w: int = MAX_W, max_h: int = MAX_H) -> Clip:
    """320x270 以内・幅高さとも偶数にする（拡大はしない）。"""
    w, h = clip.frames[0].size
    scale = min(max_w / w, max_h / h, 1.0)
    nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
    nw, nh = nw - (nw % 2), nh - (nh % 2)
    if (nw, nh) == (w, h):
        return clip
    frames = [f.resize((nw, nh), Image.LANCZOS) for f in clip.frames]
    return Clip(frames, clip.durations)


# ---- 書き出し ---------------------------------------------------------------
def _write(clip: Clip, out: Path, loop: int) -> int:
    clip.frames[0].save(
        out,
        format="PNG",
        save_all=True,
        append_images=clip.frames[1:],
        duration=clip.durations,
        loop=loop,
        disposal=2,   # APNG_DISPOSE_OP_BACKGROUND: 毎コマ消してから描く
        blend=0,      # APNG_BLEND_OP_SOURCE: 前のコマと混ぜない
        default_image=False,
        optimize=True,
    )
    return out.stat().st_size


def save_apng(clip: Clip, out: Path, loop: int, max_bytes: int) -> tuple[int, str]:
    """300KB に収まるまで減色 → 縮小の順に落としていく。"""
    size = _write(clip, out, loop)
    if size <= max_bytes:
        return size, "無加工（フルカラー）"

    for colors in (256, 192, 128, 96, 64, 48, 32):
        reduced = Clip(
            [f.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
             for f in clip.frames],
            clip.durations,
        )
        size = _write(reduced, out, loop)
        if size <= max_bytes:
            return size, f"{colors}色に減色"

    work = clip
    for ratio in (0.9, 0.8, 0.7, 0.6, 0.5):
        w, h = clip.frames[0].size
        nw, nh = max(2, int(w * ratio)) & ~1, max(2, int(h * ratio)) & ~1
        work = Clip(
            [f.resize((nw, nh), Image.LANCZOS)
              .quantize(colors=64, method=Image.Quantize.FASTOCTREE)
              .convert("RGBA") for f in clip.frames],
            clip.durations,
        )
        size = _write(work, out, loop)
        if size <= max_bytes:
            return size, f"64色 + {nw}x{nh} に縮小"

    return size, "圧縮しきれず（要素材の見直し）"


# ---- レポート ---------------------------------------------------------------
def report(path: Path) -> None:
    im = Image.open(path)
    frames = [p.copy() for p in ImageSequence.Iterator(im)]
    durations = [int(p.info.get("duration", 0) or 0) for p in frames]
    w, h = frames[0].size
    size = path.stat().st_size

    def mark(ok: bool) -> str:
        return "OK  " if ok else "NG  "

    print(f"\n■ {path}")
    print(f"  {mark(w <= MAX_W and h <= MAX_H and w % 2 == 0 and h % 2 == 0)}"
          f"サイズ      {w}x{h}  (320x270以内・偶数)")
    print(f"  {mark(MIN_FRAMES <= len(frames) <= MAX_FRAMES)}"
          f"コマ数      {len(frames)}コマ  (5〜20)")
    print(f"  {mark(MIN_TOTAL_MS <= sum(durations) <= MAX_TOTAL_MS)}"
          f"再生時間    {sum(durations) / 1000:.2f}秒  (1〜4秒)")
    print(f"  {mark(size <= MAX_BYTES)}"
          f"ファイル    {size / 1024:.1f}KB  (300KB以内)")
    print("      1コマ目    = トーク画面に残り続けるコマ（決めポーズか確認）")


# ---- CLI --------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="動くLINEスタンプの決めポーズを1コマ目に移してAPNGで書き出す",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", type=Path,
                    help="GIF / APNG / WebP / 連番PNGのフォルダ / 動画")
    ap.add_argument("-o", "--output", type=Path, help="書き出し先の .png (APNG)")
    ap.add_argument("--mode", choices=("rotate", "duplicate", "none"), default="rotate",
                    help="rotate=順序を回す(既定) / duplicate=複製を先頭に足す / none=並べ替えない")
    ap.add_argument("--pose-frame", type=int, default=-1,
                    help="決めポーズのコマ番号。1始まり、負数で末尾から。既定は最終コマ(-1)")
    ap.add_argument("--fps", type=float,
                    help="連番PNG・動画のfps。アニメ画像に指定すると表示時間を上書き")
    ap.add_argument("--loop", type=int, default=4, help="ループ回数 1〜4（既定4）")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES, help="上限バイト数（既定307200）")
    ap.add_argument("--size", default=f"{MAX_W}x{MAX_H}",
                    help="収める最大サイズ WxH（既定320x270。メイン画像なら240x240）")
    ap.add_argument("--keep-size", action="store_true", help="リサイズをしない")
    ap.add_argument("--keep-timing", action="store_true", help="コマ数・再生時間の調整をしない")
    ap.add_argument("--check", action="store_true", help="変換せず規格チェックだけ行う")
    args = ap.parse_args(argv)

    if not args.input.exists():
        return print(f"入力が見つかりません: {args.input}") or 1
    if args.check:
        report(args.input)
        return 0

    out = args.output or args.input.with_name(args.input.stem + "_stamp.png")
    if out.suffix.lower() != ".png":
        print("※ LINEのアニメーションスタンプは APNG(.png) です。拡張子を .png にします。")
        out = out.with_suffix(".png")

    clip = load_clip(args.input, args.fps)
    before = len(clip.frames)

    pose = args.pose_frame - 1 if args.pose_frame > 0 else args.pose_frame
    clip = move_pose_to_front(clip, args.mode, pose)
    if not args.keep_timing:
        clip = fit_frame_count(clip)
        clip = fit_duration(clip)
    if not args.keep_size:
        try:
            max_w, max_h = (int(v) for v in args.size.lower().split("x"))
        except ValueError:
            return print(f"--size は 320x270 の形式で指定してください: {args.size}") or 1
        clip = fit_size(clip, max_w, max_h)

    out.parent.mkdir(parents=True, exist_ok=True)
    size, how = save_apng(clip, out, max(1, min(4, args.loop)), args.max_bytes)

    print(f"読み込み  {args.input}  ({before}コマ)")
    label = "最終コマ" if args.pose_frame == -1 else f"{args.pose_frame}コマ目"
    print(f"1コマ目   元の{label}（mode={args.mode}）")
    print(f"書き出し  {out}  [{how}]")
    report(out)
    return 0 if size <= args.max_bytes else 1


if __name__ == "__main__":
    raise SystemExit(main())
