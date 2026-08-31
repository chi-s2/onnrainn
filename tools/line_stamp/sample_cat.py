#!/usr/bin/env python3
"""パイプライン確認用の、猫のグリーンバック動画を作る。

生成AIの動画が手元にないときでも、工程4（video_to_stamps.py）を
一通り試せるようにするためのサンプル素材ジェネレータ。
「1つの動きあたり1.5秒 × 10カット = 15秒」という構成を再現する。

    python3 sample_cat.py -o cat.mp4
    python3 video_to_stamps.py cat.mp4 -o cand/
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from last_frame_first import ffmpeg_exe

GREEN = (0, 177, 64)
W, H = 720, 600
SS = 2                      # 2倍で描いて縮小（輪郭をなめらかに）

FUR = (247, 206, 156)
FUR_DARK = (226, 172, 112)
BELLY = (255, 243, 227)
INNER_EAR = (245, 176, 176)
LINE = (92, 64, 48)
BLUSH = (247, 176, 168)


# ---- 猫を1枚描く ------------------------------------------------------------
def _bezier(p0, p1, p2, n):
    """2次ベジェ曲線上の点を n 個返す（しっぽ用）。"""
    for i in range(n):
        t = i / (n - 1)
        u = 1 - t
        yield (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
               u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def draw_cat(arms=(0.0, 0.0), tail=0.0, eyes="open", mouth="smile",
             squash=0.0, dy=0.0, blush=False) -> Image.Image:
    """猫を透過画像で1枚描く。

    arms   : 左右の手の上がり具合 0.0〜1.0
    tail   : しっぽの振れ -1.0〜1.0
    eyes   : open / closed / happy / wide
    mouth  : smile / open / small
    squash : つぶれ具合（伸縮）-0.3〜0.3
    dy     : 上下の移動（ジャンプ）-1.0〜1.0
    """
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = SS
    cx = W * s // 2
    cy = int((400 - dy * 60) * s)

    bw = int(112 * s * (1 + squash))     # 胴の幅
    bh = int(102 * s * (1 - squash))     # 胴の高さ

    # しっぽ（胴の右下から出て、右へ回って上に立つ）
    p0 = (cx + bw * 0.75, cy + bh * 0.45)
    p1 = (cx + bw * 0.75 + (150 + tail * 40) * s, cy + bh * 0.55)
    p2 = (cx + bw * 0.75 + (110 + tail * 70) * s, cy - bh * (0.9 + tail * 0.35))
    pts = list(_bezier(p0, p1, p2, 26))
    for i, (tx, ty) in enumerate(pts):
        r = (17 - 9 * i / (len(pts) - 1)) * s
        d.ellipse([tx - r, ty - r, tx + r, ty + r], fill=FUR_DARK)

    # 後ろ足
    for sx in (-1, 1):
        fx = cx + sx * int(bw * 0.60)
        d.ellipse([fx - 30 * s, cy + bh - 34 * s, fx + 30 * s, cy + bh + 20 * s], fill=FUR)

    # 胴
    d.ellipse([cx - bw, cy - bh, cx + bw, cy + bh], fill=FUR)
    d.ellipse([cx - int(bw * 0.60), cy - int(bh * 0.30),
               cx + int(bw * 0.60), cy + int(bh * 0.86)], fill=BELLY)

    # 手（付け根から先へ1本の腕として描く）
    hy = cy - int(bh * 0.12)
    for sx, up in ((-1, arms[0]), (1, arms[1])):
        root = (cx + sx * int(bw * 0.62), hy)
        ax = root[0] + sx * int((26 + up * 18) * s)
        ay = hy - int(up * 118 * s) + int((1 - up) * 34 * s)
        d.line([root, (ax, ay)], fill=FUR, width=int(34 * s))
        d.ellipse([ax - 24 * s, ay - 24 * s, ax + 24 * s, ay + 24 * s], fill=FUR)

    # 頭
    hx = cx
    hcy = cy - bh - int(66 * s * (1 - squash * 0.6))
    hr = int(86 * s)
    for sx in (-1, 1):                                   # 耳
        ex = hx + sx * int(hr * 0.60)
        d.polygon([(ex - 36 * s, hcy - hr * 0.48), (ex + sx * 26 * s, hcy - hr * 1.34),
                   (ex + 36 * s, hcy - hr * 0.48)], fill=FUR)
        d.polygon([(ex - 18 * s, hcy - hr * 0.58), (ex + sx * 14 * s, hcy - hr * 1.10),
                   (ex + 18 * s, hcy - hr * 0.58)], fill=INNER_EAR)
    d.ellipse([hx - hr, hcy - hr, hx + hr, hcy + hr], fill=FUR)

    # 目
    ey = hcy - int(hr * 0.06)
    for sx in (-1, 1):
        ex = hx + sx * int(hr * 0.40)
        if eyes == "closed":
            d.arc([ex - 22 * s, ey - 18 * s, ex + 22 * s, ey + 22 * s],
                  200, 340, fill=LINE, width=int(7 * s))
        elif eyes == "happy":
            d.arc([ex - 22 * s, ey - 4 * s, ex + 22 * s, ey + 36 * s],
                  190, 350, fill=LINE, width=int(8 * s))
        else:
            r = 26 * s if eyes == "wide" else 20 * s
            d.ellipse([ex - r * 0.80, ey - r, ex + r * 0.80, ey + r], fill=LINE)
            d.ellipse([ex - r * 0.32, ey - r * 0.60, ex + r * 0.14, ey - r * 0.10],
                      fill=(255, 255, 255))

    # 鼻と口
    ny = ey + int(hr * 0.36)
    d.polygon([(hx - 11 * s, ny - 5 * s), (hx + 11 * s, ny - 5 * s), (hx, ny + 8 * s)],
              fill=(226, 138, 138))
    if mouth == "open":
        d.ellipse([hx - 18 * s, ny + 6 * s, hx + 18 * s, ny + 38 * s], fill=(196, 108, 108))
    else:
        w = 17 * s if mouth == "smile" else 10 * s
        for sx in (-1, 1):
            d.arc([hx + sx * w - w, ny + 2 * s, hx + sx * w + w, ny + 26 * s],
                  0, 180, fill=LINE, width=int(6 * s))

    # ひげ
    for sx in (-1, 1):
        for k in (-1, 0, 1):
            x0 = hx + sx * int(hr * 0.40)
            d.line([(x0, ny + k * 11 * s - 3 * s),
                    (x0 + sx * int(hr * 0.98), ny + k * 19 * s - 13 * s)],
                   fill=LINE, width=int(4 * s))

    if blush:
        for sx in (-1, 1):
            bx = hx + sx * int(hr * 0.70)
            d.ellipse([bx - 19 * s, ny - 12 * s, bx + 19 * s, ny + 10 * s], fill=BLUSH)

    return im


# ---- 10個の動き -------------------------------------------------------------
def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, t)))


def motion(name: str, t: float, last: bool) -> dict:
    """t=0〜1 の途中の姿。last=True のコマが決めポーズ。"""
    w = math.sin(t * math.pi * 3)
    if name == "wave":                 # 手をふる → 決め: 両手を上げてにっこり
        return dict(arms=(0.1, 0.7 + 0.3 * w), eyes="open", mouth="smile") if not last \
            else dict(arms=(1.0, 1.0), eyes="happy", mouth="open")
    if name == "bow":                  # おじぎ
        return dict(arms=(0.1, 0.1), squash=0.12 * ease(t), eyes="open") if not last \
            else dict(arms=(0.2, 0.2), squash=0.26, eyes="closed", mouth="small")
    if name == "jump":                 # ジャンプ
        return dict(arms=(0.4 + 0.4 * w, 0.4 + 0.4 * w), squash=-0.10 * w,
                    dy=0.7 * max(0.0, w), eyes="wide") \
            if not last else dict(arms=(1.0, 1.0), squash=-0.20, dy=1.0,
                                  eyes="happy", mouth="open")
    if name == "tilt":                 # 首をかしげる
        return dict(tail=w, eyes="open", mouth="small") if not last \
            else dict(tail=0.9, eyes="happy", mouth="smile", blush=True)
    if name == "sleep":                # ごろん → 寝る
        return dict(squash=0.2 * ease(t), eyes="open", mouth="small") if not last \
            else dict(squash=0.3, eyes="closed", mouth="small")
    if name == "surprise":             # びっくり
        return dict(arms=(0.6 * abs(w), 0.6 * abs(w)), eyes="wide", mouth="open") if not last \
            else dict(arms=(0.9, 0.9), eyes="wide", mouth="open", squash=-0.12)
    if name == "clap":                 # 拍手
        return dict(arms=(0.55 + 0.2 * w, 0.55 - 0.2 * w), eyes="open", mouth="smile") \
            if not last else dict(arms=(0.75, 0.75), eyes="happy", mouth="open")
    if name == "nod":                  # うなずく
        return dict(squash=0.1 * abs(w), eyes="open", mouth="small") if not last \
            else dict(squash=0.16, eyes="closed", mouth="smile")
    if name == "stretch":              # のび
        return dict(arms=(0.5 * ease(t), 0.5 * ease(t)), squash=-0.1 * ease(t),
                    eyes="closed", mouth="open") if not last \
            else dict(arms=(1.0, 1.0), squash=-0.24, eyes="closed", mouth="open")
    if name == "love":                 # てれる
        return dict(arms=(0.5, 0.5 + 0.15 * w), eyes="open", mouth="smile", blush=True) \
            if not last else dict(arms=(0.72, 0.72), eyes="happy", mouth="smile", blush=True)
    return dict()


MOTIONS = ["wave", "bow", "jump", "tilt", "sleep",
           "surprise", "clap", "nod", "stretch", "love"]


def render(outdir: Path, fps: float, seconds: float) -> int:
    per = max(2, round(fps * seconds))
    idx = 0
    for name in MOTIONS:
        for k in range(per):
            last = k == per - 1
            layer = draw_cat(**motion(name, k / (per - 1), last))
            frame = Image.new("RGBA", (W * SS, H * SS), GREEN + (255,))
            frame.alpha_composite(layer)
            frame.convert("RGB").resize((W, H), Image.LANCZOS).save(outdir / f"{idx:05d}.png")
            idx += 1
    return idx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="パイプライン確認用の猫グリーンバック動画を作る")
    ap.add_argument("-o", "--output", type=Path, default=Path("cat.mp4"),
                    help="書き出し先。.mp4 ならffmpegで動画化、フォルダなら連番PNG")
    ap.add_argument("--fps", type=float, default=12.0, help="fps（既定12）")
    ap.add_argument("--seconds", type=float, default=1.5, help="1カットの長さ（既定1.5秒）")
    args = ap.parse_args(argv)

    if args.output.suffix.lower() == ".mp4":
        with tempfile.TemporaryDirectory() as tmp:
            n = render(Path(tmp), args.fps, args.seconds)
            subprocess.run(
                [ffmpeg_exe(), "-y", "-loglevel", "error", "-framerate", str(args.fps),
                 "-i", f"{tmp}/%05d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 str(args.output)],
                check=True,
            )
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        n = render(args.output, args.fps, args.seconds)

    print(f"{len(MOTIONS)}カット x {round(args.fps * args.seconds)}コマ = {n}コマ "
          f"({n / args.fps:.1f}秒)  →  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
