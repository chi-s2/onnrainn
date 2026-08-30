"""
スタンプ8種類のアニメーション定義。

各シーンは frame(t) を持つ。t は 0.0〜1.0 未満の再生位置で、
t=0 と t=1 がつながるように作ってあるのでループしても飛ばない。
"""

import math
from PIL import ImageDraw

import stickerkit as k
from stickerkit import pose, text, new_frame, finish, draw_cat

GROUND = 246.0          # 猫の足元の y
TEXT_Y = 30.0           # セリフの中心 y


def _osc(t, cycles=1, phase=0.0):
    return math.sin(2 * math.pi * (t * cycles + phase))


# ---------------------------------------------------------------- 01 おはよう

def ohayou(t):
    img = new_frame()
    w = _osc(t, 2)                       # 手を振る
    bob = -3 - 3 * abs(_osc(t, 2))
    p = pose(y=GROUND, bob=bob, tilt=-5 + 3 * w, ear=5 * w,
             paw_r=(60 + 6 * w, -116 - 6 * abs(w)),
             eyes="happy" if abs(w) < 0.85 else "blink",
             mouth="smile", tail=6 * _osc(t, 2, 0.25))
    draw_cat(img, p)
    text(img, "おはよう", 160, TEXT_Y, 34, fill=(214, 132, 96, 255))
    return finish(img)


# ---------------------------------------------------------------- 02 ありがとう

def arigatou(t):
    img = new_frame()
    # 0.15〜0.55 でおじぎ、そのあと戻る
    if t < 0.15:
        b = 0.0
    elif t < 0.45:
        b = k.ease((t - 0.15) / 0.30)
    elif t < 0.70:
        b = 1.0
    else:
        b = 1.0 - k.ease(min((t - 0.70) / 0.30, 1.0))
    p = pose(y=GROUND, head_dy=30 * b, bob=6 * b,
             squash=1 - 0.20 * b, ear=-30 * b, tilt=-3 * b,
             paw_l=(-40, -52 + 6 * b), paw_r=(40, -52 + 6 * b),
             eyes="happy", mouth="smile" if b < 0.5 else "omega")
    draw_cat(img, p)
    d = ImageDraw.Draw(img)
    for i, (sx, sy) in enumerate(((78, 96), (243, 88), (66, 150))):
        s = 5 + 4 * abs(_osc(t, 2, i * 0.33))
        k.sparkle(d, sx, sy, s, (255, 206, 122, 255))
    text(img, "ありがとう", 160, TEXT_Y, 32, fill=(232, 142, 128, 255))
    return finish(img)


# ---------------------------------------------------------------- 03 だいすき

def daisuki(t):
    img = new_frame()
    pulse = 0.5 + 0.5 * _osc(t, 2)
    bob = -4 * pulse
    hx, hy = 0, -74 - 6 * pulse            # ハートの位置（ローカル）
    p = pose(y=GROUND, bob=bob, tilt=3 * _osc(t, 1),
             paw_l=(-25, hy + 12), paw_r=(25, hy + 12),
             eyes="sparkle", mouth="omega", ear=4 * pulse)

    def front(d, T, pp):
        cx, cy = T([(hx, hy)])[0]
        k.heart(d, cx, cy, 27 + 4 * pulse, (247, 156, 178, 255))

    draw_cat(img, p, item_front=front)
    d = ImageDraw.Draw(img)
    for i, (sx, sy) in enumerate(((72, 108), (250, 118), (238, 178))):
        ph = (t + i / 3.0) % 1.0
        k.heart(d, sx, sy - 18 * ph, 7 + 4 * (1 - ph),
                (250, 178, 196, int(255 * (1 - ph))), None, 0)
    text(img, "だいすき", 160, TEXT_Y, 34, fill=(230, 108, 142, 255))
    return finish(img)


# ---------------------------------------------------------------- 04 ごめんね

def gomen(t):
    img = new_frame()
    sh = _osc(t, 4) * 2.2                  # しょんぼり震え
    p = pose(x=160 + sh, y=GROUND, tilt=6 + 2 * _osc(t, 2), ear=-24,
             head_dy=6, squash=0.94, eyes="sad", mouth="wave",
             paw_l=(-30, -60), paw_r=(30, -60), tail=-8)
    draw_cat(img, p)
    d = ImageDraw.Draw(img)
    tp = (t * 2) % 1.0                     # 涙が2回落ちる
    if tp < 0.75:
        k.teardrop(d, 160 + sh + 42, 132 + 46 * k.ease(tp / 0.75), 7 * (1 - tp * 0.4))
    text(img, "ごめんね", 160, TEXT_Y, 34, fill=(140, 150, 200, 255))
    return finish(img)


# ---------------------------------------------------------------- 05 OK!

def ok(t):
    img = new_frame()
    # 前半で沈んでジャンプ、後半で着地
    if t < 0.25:
        s = k.ease(t / 0.25); jump = 0.0; sq = 1 - 0.20 * s
    elif t < 0.65:
        s = (t - 0.25) / 0.40
        jump = math.sin(math.pi * s) * 38
        sq = 1 + 0.10 * math.sin(math.pi * s)
    else:
        s = 1 - k.ease((t - 0.65) / 0.35)
        jump = 0.0; sq = 1 - 0.14 * s
    p = pose(y=GROUND - jump, bob=-jump * 0.25, squash=sq, tilt=-4,
             paw_r=(60, -126 - jump * 0.25), paw_l=(-48, -54),
             eyes="wide" if jump > 2 else "happy", mouth="open" if jump > 2 else "smile",
             ear=12 if jump > 2 else 0, tail=10 * _osc(t, 1))
    draw_cat(img, p)
    ts = 34 + 5 * (jump / 26.0)
    text(img, "OK！", 160, TEXT_Y, ts, fill=(96, 178, 152, 255))
    return finish(img)


# ---------------------------------------------------------------- 06 おやすみ

def oyasumi(t):
    img = new_frame()
    breath = _osc(t, 1)
    p = pose(y=GROUND, bob=1.5 * breath, squash=0.90 + 0.02 * breath,
             tilt=10, head_dx=-4, ear=-10, eyes="blink", mouth="flat",
             paw_l=(-40, -44), paw_r=(40, -44), tail=4 * breath)
    draw_cat(img, p)
    d = ImageDraw.Draw(img)
    for i in range(3):
        ph = (t + i / 3.0) % 1.0
        a = int(235 * min(1.0, (1 - ph) * 2.2))
        k.zzz(d, 236 + 16 * ph, 118 - 54 * ph, 6 + 5 * ph, a)
    text(img, "おやすみ", 160, TEXT_Y, 34, fill=(126, 140, 190, 255))
    return finish(img)


# ---------------------------------------------------------------- 07 がんばれ

def ganbare(t):
    img = new_frame()
    pump = abs(_osc(t, 2))                 # 2回ガッツポーズ
    bob = -8 * pump
    p = pose(y=GROUND, bob=bob, squash=1 - 0.05 * (1 - pump),
             paw_l=(-52, -76 - 40 * pump), paw_r=(52, -76 - 40 * pump),
             eyes="sparkle" if pump > 0.5 else "happy",
             mouth="open" if pump > 0.5 else "smile",
             ear=10 * pump, tilt=2 * _osc(t, 2, 0.25))
    draw_cat(img, p)
    d = ImageDraw.Draw(img)
    for i, sx in enumerate((60, 262)):
        k.sparkle(d, sx, 96 - 10 * pump, 6 + 5 * pump, (255, 196, 110, 255))
    text(img, "がんばれ", 160, TEXT_Y, 34, fill=(238, 138, 92, 255))
    return finish(img)


# ---------------------------------------------------------------- 08 おなかすいた

def onaka(t):
    img = new_frame()
    rumble = _osc(t, 3) * 1.8
    swim = _osc(t, 1)
    p = pose(x=160 + rumble, y=GROUND, tilt=-6 + 3 * _osc(t, 1),
             squash=0.96, head_dy=4, ear=-14 + 4 * _osc(t, 3),
             eyes="sad", mouth="wave", look=(5, 3),
             paw_l=(-34, -46), paw_r=(40, -60), tail=-6 * _osc(t, 1))
    draw_cat(img, p)
    d = ImageDraw.Draw(img)
    # 目の前を魚が泳いでいく（届かない）
    k.fish(d, 258 + 4 * swim, 132 + 6 * swim, 20, rot=-8 * swim)
    text(img, "おなかすいた", 160, TEXT_Y, 28, fill=(198, 140, 96, 255))
    return finish(img)


# ---------------------------------------------------------------- メイン画像／タブ画像

def main_image(t):
    """メイン画像（240x240 APNG）。"""
    img = new_frame(240, 240)
    w = _osc(t, 2)
    p = pose(x=120, y=224, scale=0.88, bob=-3 - 3 * abs(w), tilt=-5 + 3 * w,
             ear=5 * w, paw_r=(60 + 6 * w, -116 - 6 * abs(w)),
             eyes="happy" if abs(w) < 0.85 else "blink", mouth="smile",
             tail=6 * _osc(t, 2, 0.25))
    draw_cat(img, p)
    text(img, "ねこ", 120, 30, 30, fill=(214, 132, 96, 255))
    return finish(img)


def tab_image():
    """タブ画像（96x74 の静止 PNG）。顔だけ。"""
    img = new_frame(96, 74)
    # 顔が画面いっぱいに収まるよう、頭の中心が y=38 に来る位置に置く
    scale = 0.42
    p = pose(x=48, y=38 + 118 * scale, scale=scale, eyes="happy", mouth="omega")
    draw_cat(img, p)
    return finish(img)


SCENES = [
    ("01", "おはよう", ohayou),
    ("02", "ありがとう", arigatou),
    ("03", "だいすき", daisuki),
    ("04", "ごめんね", gomen),
    ("05", "OK！", ok),
    ("06", "おやすみ", oyasumi),
    ("07", "がんばれ", ganbare),
    ("08", "おなかすいた", onaka),
]
