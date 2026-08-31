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

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PIL import Image, ImageSequence
except ImportError:  # pragma: no cover
    sys.exit("Pillow が必要です:  pip install Pillow")


# ---- LINE アニメーションスタンプの規格 -------------------------------------
MAX_W, MAX_H = 320, 270
MIN_FRAMES, MAX_FRAMES = 5, 20
# 再生時間は「ループ込みで 1/2/3/4 秒ぴったり」。
# つまり  1ループの長さ × ループ回数 = 1000/2000/3000/4000ms  でなければならない。
ALLOWED_TOTAL_MS = (1000, 2000, 3000, 4000)
ALLOWED_LOOPS = (1, 2, 3, 4)
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


def ffmpeg_exe() -> str:
    """ffmpeg の実行ファイルを探す。無ければ pip の imageio-ffmpeg 同梱版を使う。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit(
            "動画の読み込みには ffmpeg が必要です。\n"
            "  pip install imageio-ffmpeg   （または ffmpeg 本体をインストール）"
        )


def _load_from_video(src: Path, fps: float) -> Clip:
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [ffmpeg_exe(), "-loglevel", "error", "-i", str(src),
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


def choose_timing(natural_ms: int, n_frames: int,
                  loop: int | None, seconds: int | None) -> tuple[int, int]:
    """(ループ込みの総秒数, ループ回数) を決める。

    LINE は「1ループの長さ × ループ回数」が 1/2/3/4 秒ぴったりであることを求める。
    元素材の速さ（1ループの長さ）にいちばん近い組み合わせを選ぶ。
    """
    floor_ms = MIN_FRAME_MS * n_frames
    cands = [
        (total, lp)
        for total in ALLOWED_TOTAL_MS
        for lp in ALLOWED_LOOPS
        if (seconds is None or total == seconds * 1000)
        and (loop is None or lp == loop)
        and total / lp >= floor_ms
    ]
    if not cands:
        raise SystemExit(
            f"{n_frames}コマだと指定の再生時間・ループ回数に収まりません。"
            "コマ数を減らすか、--seconds / --loop を見直してください。"
        )
    # 1ループの長さが元素材に近いものを優先。同点ならループ回数が多いほうを選ぶ。
    total, lp = min(cands, key=lambda c: (abs(c[0] / c[1] - natural_ms), -c[1]))
    return total, lp


def _rescale_exact(durations: list, target: int) -> list:
    """各コマの比率を保ったまま、合計をちょうど target ms にする。"""
    total = sum(durations) or 1
    raw = [d * target / total for d in durations]
    out = [max(MIN_FRAME_MS, int(r)) for r in raw]
    diff = target - sum(out)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - int(raw[i]), reverse=True)
    i = 0
    while diff > 0:                      # 端数を小数部が大きいコマから配る
        out[order[i % len(order)]] += 1
        diff -= 1
        i += 1
    while diff < 0:                      # 超過分は長いコマから削る
        j = max(range(len(out)), key=lambda k: out[k])
        if out[j] <= MIN_FRAME_MS:
            break
        out[j] -= 1
        diff += 1
    return out


def fit_duration(clip: Clip, loop: int | None, seconds: int | None) -> tuple[Clip, int, int]:
    """ループ込みの再生時間を 1/2/3/4 秒ぴったりに合わせる。"""
    total, lp = choose_timing(clip.total_ms, len(clip.frames), loop, seconds)
    per_loop = round(total / lp)
    return Clip(clip.frames, _rescale_exact(clip.durations, per_loop)), lp, total


def resize_rgba(img: Image.Image, size: tuple) -> Image.Image:
    """アルファを掛けてから縮小し、あとで戻す。

    そのまま縮小すると、完全に透明な画素が持っている色（グリーンバックなら緑）が
    輪郭に混ざってしまう。numpy があれば乗算アルファで正しく縮小する。
    """
    try:
        import numpy as np
    except ImportError:
        return img.resize(size, Image.LANCZOS)

    src = np.asarray(img.convert("RGBA"), dtype=np.float32)
    a = src[..., 3:4] / 255.0
    pre = np.concatenate([src[..., :3] * a, src[..., 3:4]], axis=2)
    small = np.asarray(
        Image.fromarray(pre.astype(np.uint8), "RGBA").resize(size, Image.LANCZOS),
        dtype=np.float32,
    )
    na = small[..., 3:4] / 255.0
    rgb = np.clip(small[..., :3] / np.where(na == 0, 1.0, na), 0, 255)
    out = np.concatenate([rgb, small[..., 3:4]], axis=2).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def fit_size(clip: Clip, max_w: int = MAX_W, max_h: int = MAX_H) -> Clip:
    """320x270 以内・幅高さとも偶数にする（拡大はしない）。"""
    w, h = clip.frames[0].size
    scale = min(max_w / w, max_h / h, 1.0)
    nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
    nw, nh = nw - (nw % 2), nh - (nh % 2)
    if (nw, nh) == (w, h):
        return clip
    return Clip([resize_rgba(f, (nw, nh)) for f in clip.frames], clip.durations)


# ---- 書き出し ---------------------------------------------------------------
def _write(clip: Clip, out: Path, loop: int) -> int:
    clip.frames[0].save(
        out,
        format="PNG",
        save_all=True,
        append_images=clip.frames[1:],
        duration=clip.durations,
        loop=loop,
        # APNGのdispose_opは 0=そのまま 1=背景で消す 2=前のコマに戻す。
        # 透過キャラは毎コマ消してから描き直す必要があるので 1。
        # 2 にすると再生時にコマが欠けた壊れたAPNGになる。
        disposal=1,
        blend=0,      # blend_op 0 = OP_SOURCE（前のコマと混ぜず置き換える）
        default_image=False,
        optimize=True,
    )
    return out.stat().st_size


def quantize_keep_alpha(img: Image.Image, colors: int) -> Image.Image:
    """色だけ減色し、アルファはそのまま残す。

    RGBA のまま quantize するとアルファまで palette に丸められ、キャラの内側に
    半透明と穴が大量にできる（「イラストの内部が透過されています」の原因）。
    減らしたいのは色数なので、RGB だけ減色してアルファは元のまま戻す。
    """
    rgb = img.convert("RGB").quantize(
        colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGB")
    return Image.merge("RGBA", (*rgb.split(), img.convert("RGBA").getchannel("A")))


def _quantized(clip: Clip, colors: int) -> Clip:
    return Clip([quantize_keep_alpha(f, colors) for f in clip.frames], clip.durations)


def _scaled(clip: Clip, ratio: float, clean: bool) -> Clip:
    w, h = clip.frames[0].size
    nw, nh = max(2, int(w * ratio)) & ~1, max(2, int(h * ratio)) & ~1
    out = Clip([resize_rgba(f, (nw, nh)) for f in clip.frames], clip.durations)
    return clean_clip(out)[0] if clean else out     # 縮小で穴が復活するため


def _candidates(clip: Clip, clean: bool):
    """300KBに収まるまで試す順。画の劣化が小さいものから並べる。

    減色 → コマ間引き → 縮小。スタンプは絵の粗さのほうが目立つので、
    コマを減らすほうが縮小より先。
    """
    yield "無加工（フルカラー）", clip
    for colors in (256, 128, 64, 32):
        yield f"{colors}色に減色", _quantized(clip, colors)

    for nf in (15, 12, 10, 8, MIN_FRAMES):
        if nf >= len(clip.frames):
            continue
        thinned = fit_frame_count(clip, nf, nf)
        yield f"{nf}コマに間引き", thinned
        for colors in (128, 64, 32):
            yield f"{nf}コマ + {colors}色", _quantized(thinned, colors)

    for ratio in (0.9, 0.8, 0.7, 0.6, 0.5):
        small = _scaled(clip, ratio, clean)
        w, h = small.frames[0].size
        yield f"{w}x{h} に縮小 + 64色", _quantized(small, 64)


def save_apng(clip: Clip, out: Path, loop: int, max_bytes: int,
              clean: bool = False) -> tuple:
    """収まるまで落としながら書き出す。戻り値は (バイト数, 手法, 実際に書いたClip)。"""
    size, label, used = 0, "", clip
    for label, cand in _candidates(clip, clean):
        size = _write(cand, out, loop)
        used = cand
        if size <= max_bytes:
            return size, label, used
    return size, f"{label}（それでも収まらず）", used


# ---- レポート ---------------------------------------------------------------
def report(path: Path) -> None:
    im = Image.open(path)
    loop = int(im.info.get("loop", 1) or 1)
    frames = [p.copy() for p in ImageSequence.Iterator(im)]
    durations = [int(p.info.get("duration", 0) or 0) for p in frames]
    w, h = frames[0].size
    size = path.stat().st_size
    per_loop = sum(durations)
    played = per_loop * loop

    def mark(ok: bool) -> str:
        return "OK  " if ok else "NG  "

    print(f"\n■ {path}")
    print(f"  {mark(w <= MAX_W and h <= MAX_H and w % 2 == 0 and h % 2 == 0)}"
          f"サイズ      {w}x{h}  (320x270以内・偶数)")
    print(f"  {mark(MIN_FRAMES <= len(frames) <= MAX_FRAMES)}"
          f"コマ数      {len(frames)}コマ  (5〜20)")
    print(f"  {mark(loop in ALLOWED_LOOPS)}"
          f"ループ      {loop}回  (1〜4回)")
    print(f"  {mark(played in ALLOWED_TOTAL_MS)}"
          f"再生時間    {per_loop / 1000:.3f}秒 x {loop}回 = {played / 1000:g}秒"
          f"  (ループ込みで1/2/3/4秒ぴったり)")
    print(f"  {mark(size <= MAX_BYTES)}"
          f"ファイル    {size / 1024:.1f}KB  (300KB以内)")
    print("      1コマ目    = トーク画面に残り続けるコマ（決めポーズか確認）")


# ---- CLI --------------------------------------------------------------------
def clean_clip(clip: Clip, max_area: float = 0.02, margin: int = 2) -> tuple[Clip, int]:
    """全コマの内部の透過穴を埋め、輪郭より内側の半透明をベタにする。

    リサイズや減色のあとにもう一度かけるのが効く（縮小で穴が復活するため）。
    """
    try:
        import chroma
    except ImportError:
        raise SystemExit("この処理には numpy と scipy が必要です:  pip install numpy scipy")
    frames, holes = [], 0
    for f in clip.frames:
        f, st = chroma.clean(f, max_area=max_area, margin=margin)
        holes += st["holes"]
        frames.append(f)
    return Clip(frames, clip.durations), holes


def build_stamp(clip: Clip, *, mode: str = "rotate", pose: int = -1,
                loop: int | None = None, seconds: int | None = None,
                size: str = f"{MAX_W}x{MAX_H}",
                keep_size: bool = False, keep_timing: bool = False):
    """決めポーズの移動 → コマ数 → 再生時間 → サイズ、をまとめて適用する。

    戻り値は (整形後のClip, ループ回数, ループ込みの再生時間ms または None)。
    """
    clip = move_pose_to_front(clip, mode, pose)
    lp, played = max(ALLOWED_LOOPS), None
    if not keep_timing:
        clip = fit_frame_count(clip)
        clip, lp, played = fit_duration(clip, loop, seconds)
    elif loop:
        lp = loop
    if not keep_size:
        try:
            max_w, max_h = (int(v) for v in size.lower().split("x"))
        except ValueError:
            raise SystemExit(f"サイズは 320x270 の形式で指定してください: {size}")
        clip = fit_size(clip, max_w, max_h)
    return clip, lp, played


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
    ap.add_argument("--loop", type=int, choices=ALLOWED_LOOPS,
                    help="ループ回数 1〜4。未指定なら元素材の速さに近い組み合わせを自動選択")
    ap.add_argument("--seconds", type=int, choices=(1, 2, 3, 4),
                    help="ループ込みの再生時間（秒）。未指定なら自動選択")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES, help="上限バイト数（既定307200）")
    ap.add_argument("--size", default=f"{MAX_W}x{MAX_H}",
                    help="収める最大サイズ WxH（既定320x270。メイン画像なら240x240）")
    ap.add_argument("--keep-size", action="store_true", help="リサイズをしない")
    ap.add_argument("--keep-timing", action="store_true", help="コマ数・再生時間の調整をしない")
    ap.add_argument("--clean", action="store_true",
                    help="仕上げに内部の透過穴を埋め、内側の半透明をベタにする（要 numpy/scipy）")
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
    clip, loop, played = build_stamp(
        clip, mode=args.mode, pose=pose, loop=args.loop, seconds=args.seconds,
        size=args.size, keep_size=args.keep_size, keep_timing=args.keep_timing,
    )

    holes = 0
    if args.clean:
        clip, holes = clean_clip(clip)

    out.parent.mkdir(parents=True, exist_ok=True)
    size, how, clip = save_apng(clip, out, loop, args.max_bytes, clean=args.clean)

    print(f"読み込み  {args.input}  ({before}コマ)")
    label = "最終コマ" if args.pose_frame == -1 else f"{args.pose_frame}コマ目"
    print(f"1コマ目   元の{label}（mode={args.mode}）")
    if played:
        print(f"再生時間  {clip.total_ms / 1000:.3f}秒 x {loop}回 = {played / 1000:g}秒")
    if args.clean:
        print(f"透過整理  内部の穴を{holes}箇所埋めました")
    print(f"書き出し  {out}  [{how}]")
    report(out)
    return 0 if size <= args.max_bytes else 1


if __name__ == "__main__":
    raise SystemExit(main())
