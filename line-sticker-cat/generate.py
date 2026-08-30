#!/usr/bin/env python3
"""
動くLINEスタンプ（APNG）を書き出す。

    python3 generate.py            # out/ に全部書き出す
    python3 generate.py --sheet    # 確認用のコンタクトシートも作る

LINE クリエイターズスタンプ「アニメーションスタンプ」の規定に合わせてある:
    スタンプ画像   APNG / 最大 320x270px（幅か高さの一方は 270px 以上）/ 8・16・24 個
    フレーム数     5〜20
    再生時間       1・2・3・4 秒のいずれか
    ループ回数     1〜4 回。ただし 再生時間 x ループ回数 <= 4 秒
    ファイルサイズ 1個 300KB 以下
    メイン画像     APNG / 240x240px / 300KB 以下
    タブ画像       PNG（静止画）/ 96x74px
    ZIP           全部まとめて 20MB 以下
"""

import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageChops

import stickerkit as k
from scenes import SCENES, main_image, tab_image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

FRAMES = 12          # 5〜20 の範囲
SECONDS = 2.0        # 1・2・3・4 秒のいずれか
LOOPS = 2            # 再生時間 x ループ回数 が 4 秒を超えないこと（2s x 2 = 4s）

LIMIT_STICKER = 300 * 1024
LIMIT_MAIN = 300 * 1024
LIMIT_TAB = 50 * 1024
LIMIT_ZIP = 20 * 1024 * 1024


def render(fn, frames=FRAMES):
    return [fn(i / frames) for i in range(frames)]


# 色数を減らすほど軽くなる。見た目が保てる範囲でいちばん多い色数を選ぶ。
PALETTES = [96, 72, 56, 44, 36, 32, 24, 16]


def _quantize(frames, colors):
    """RGBA のまま色数だけ落とす。透明のフチも含めて減色する。"""
    return [f.quantize(colors=colors, method=Image.FASTOCTREE).convert("RGBA")
            for f in frames]


def _write(frames, path, dur, loops):
    # disposal=0 / blend=0 にすると Pillow がフレーム間の差分だけを
    # 書き出せるようになり、ファイルがかなり小さくなる。
    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        format="PNG", duration=dur, loop=loops,
        disposal=0, blend=0, default_image=False, optimize=True,
    )


def save_apng(frames, path, seconds=SECONDS, loops=LOOPS, limit=None):
    """上限に収まる中でいちばん色数の多いパレットを選んで APNG を書き出す。"""
    dur = int(round(seconds * 1000 / len(frames)))
    target = int(limit * 0.92) if limit else None
    chosen, used = frames, None
    for colors in PALETTES:
        q = _quantize(frames, colors)
        _write(q, path, dur, loops)
        chosen, used = q, colors
        if target is None or os.path.getsize(path) <= target:
            break
    return dur, used, chosen


def verify(path, frames, seconds, loops, limit, size, require_270=False):
    """書き出した APNG を読み直して規定を満たしているか確認する。"""
    problems = []
    n = len(frames)
    if not (5 <= n <= 20):
        problems.append(f"フレーム数 {n} が 5〜20 の外")
    if not (1.0 <= seconds <= 4.0):
        problems.append(f"再生時間 {seconds}s が 1〜4 秒の外")
    if seconds not in (1.0, 2.0, 3.0, 4.0):
        problems.append(f"再生時間 {seconds}s は 1/2/3/4 秒のいずれかにする")
    if not (1 <= loops <= 4):
        problems.append(f"ループ {loops} 回が 1〜4 回の外")
    if seconds * loops > 4.0 + 1e-9:
        problems.append(f"再生時間 x ループ = {seconds*loops}s が 4 秒超過")
    if size[0] % 2 or size[1] % 2:
        problems.append(f"サイズ {size} が偶数でない")
    if require_270 and max(size) < 270:
        # 270px 以上の規定はスタンプ画像のみ。メイン画像は 240x240 固定。
        problems.append(f"サイズ {size} は幅か高さの一方を 270px 以上にする")

    bytes_ = os.path.getsize(path)
    if bytes_ > limit:
        problems.append(f"{bytes_}B が上限 {limit}B 超過")

    with Image.open(path) as im:
        if im.size != size:
            problems.append(f"書き出しサイズ {im.size} != {size}")
        if getattr(im, "n_frames", 1) != n:
            problems.append(f"書き出しフレーム数 {im.n_frames} != {n}")
        total = 0.0
        for i in range(getattr(im, "n_frames", 1)):
            im.seek(i)
            total += im.info.get("duration", 0)
        if abs(total / 1000.0 - seconds) > 0.06:
            problems.append(f"実再生時間 {total/1000:.2f}s != {seconds}s")

        # 差分書き出しが正しく復元できるか、全フレームを読み直して照合する
        for i, want in enumerate(frames):
            im.seek(i)
            got = im.convert("RGBA")
            diff = ImageChops.difference(got, want).getbbox()
            if diff is not None:
                ext = ImageChops.difference(got, want).getextrema()
                worst = max(hi for _, hi in ext)
                if worst > 2:
                    problems.append(f"frame{i} の復元が一致しない (最大差 {worst})")
                    break
    return bytes_, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true", help="確認用シートも書き出す")
    ap.add_argument("--frames", type=int, default=FRAMES)
    ap.add_argument("--seconds", type=float, default=SECONDS)
    ap.add_argument("--loops", type=int, default=LOOPS)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    ok = True
    sheets = []

    for num, label, fn in SCENES:
        frames = render(fn, args.frames)
        path = os.path.join(OUT, f"{num}.png")
        _, colors, written = save_apng(frames, path, args.seconds, args.loops, limit=LIMIT_STICKER)
        size, problems = verify(path, written, args.seconds, args.loops,
                                LIMIT_STICKER, (k.W, k.H), require_270=True)
        flag = "OK " if not problems else "NG "
        print(f"{flag}{num}.png  {label:<7} {len(frames)}f {colors:3d}色 {size/1024:6.1f}KB"
              + ("" if not problems else "  -> " + " / ".join(problems)))
        ok &= not problems
        sheets.append(frames)

    # メイン画像
    frames = render(main_image, args.frames)
    path = os.path.join(OUT, "main.png")
    _, colors, written = save_apng(frames, path, args.seconds, args.loops, limit=LIMIT_MAIN)
    size, problems = verify(path, written, args.seconds, args.loops, LIMIT_MAIN, (240, 240))
    print(f"{'OK ' if not problems else 'NG '}main.png  (240x240) {colors:3d}色 {size/1024:6.1f}KB"
          + ("" if not problems else "  -> " + " / ".join(problems)))
    ok &= not problems

    # タブ画像（静止画）
    tab = tab_image()
    tpath = os.path.join(OUT, "tab.png")
    tab.save(tpath, format="PNG", optimize=True)
    tsize = os.path.getsize(tpath)
    tprob = []
    if tab.size != (96, 74):
        tprob.append(f"サイズ {tab.size} != (96, 74)")
    if tsize > LIMIT_TAB:
        tprob.append(f"{tsize}B が上限 {LIMIT_TAB}B 超過")
    print(f"{'OK ' if not tprob else 'NG '}tab.png   (96x74)   {tsize/1024:6.1f}KB"
          + ("" if not tprob else "  -> " + " / ".join(tprob)))
    ok &= not tprob

    # LINE Creators Market にまとめてアップロードするための ZIP
    names = [f"{num}.png" for num, _, _ in SCENES] + ["main.png", "tab.png"]
    zpath = os.path.join(OUT, "line-sticker-cat.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(os.path.join(OUT, n), n)
    zsize = os.path.getsize(zpath)
    zprob = [] if zsize <= LIMIT_ZIP else [f"{zsize}B が上限 {LIMIT_ZIP}B 超過"]
    print(f"{'OK ' if not zprob else 'NG '}line-sticker-cat.zip  {len(names)}ファイル "
          f"{zsize/1024/1024:.2f}MB" + ("" if not zprob else "  -> " + " / ".join(zprob)))
    ok &= not zprob

    if args.sheet:
        cols = len(sheets)
        rows = min(len(s) for s in sheets)
        sheet = Image.new("RGBA", (k.W * cols, k.H * rows), (255, 255, 255, 255))
        for c, fr in enumerate(sheets):
            for r in range(rows):
                sheet.alpha_composite(fr[r], (k.W * c, k.H * r))
        sp = os.path.join(OUT, "_contact_sheet.png")
        sheet.save(sp)
        print(f"   sheet -> {sp}")

    print(f"\n再生: {args.seconds:.0f}秒 x {args.loops}ループ = "
          f"{args.seconds*args.loops:.0f}秒 / {args.frames}フレーム")
    print("すべて規定内です。" if ok else "規定を外れたファイルがあります。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
