"""
動くLINEスタンプ用の描画エンジン。

Pillow だけで完結するベクター風の描画キット。
猫キャラをパラメータ（ポーズ）で描き分け、フレームを並べて APNG にする。

座標系:
    キャンバスは 320x270 (LINE アニメーションスタンプの最大サイズ)。
    猫はローカル座標で組み立てる。原点は「猫の足元の中心」、上が -y。
    描画は SS 倍に拡大してから縮小する（アンチエイリアス目的）。
"""

import math
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 基本設定

W, H = 320, 270          # スタンプ画像サイズ
SS = 3                   # スーパーサンプリング倍率
STROKE = 3.0             # 輪郭線の太さ（縮小後の px）

OUTLINE = (126, 96, 84, 255)      # 輪郭のこげ茶
FUR     = (255, 252, 248, 255)    # 体のベース（ほぼ白）
SHADE   = (244, 233, 225, 255)    # 体の影
PINK    = (247, 180, 196, 255)    # 耳の内側など
PINK_D  = (231, 137, 161, 255)    # 濃いピンク
BLUSH   = (250, 178, 188, 190)    # ほっぺ
EYE     = (94, 70, 62, 255)       # 目
WHITE   = (255, 255, 255, 255)
CREAM   = (255, 247, 240, 255)

FONT_PATH = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"


# ---------------------------------------------------------------- 幾何ユーティリティ

def ellipse_pts(cx, cy, rx, ry, n=48, rot=0.0):
    """楕円を点列で返す。rot は度数。"""
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


def catmull(pts, samples=12, closed=True):
    """Catmull-Rom スプラインで点列をなめらかにする。"""
    n = len(pts)
    out = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        if closed:
            p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        else:
            p0 = pts[max(i - 1, 0)]; p1 = pts[i]
            p2 = pts[min(i + 1, n - 1)]; p3 = pts[min(i + 2, n - 1)]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    return out


def rot_pts(pts, cx, cy, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa,
             cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def scale_pts(pts, cx, cy, sx, sy):
    return [(cx + (x - cx) * sx, cy + (y - cy) * sy) for x, y in pts]


def move_pts(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    """イーズインアウト。"""
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 描画プリミティブ

def poly(pts, fill=None):
    return {"kind": "poly", "pts": pts, "fill": fill}


def path(pts, w, fill=None):
    return {"kind": "path", "pts": pts, "w": w, "fill": fill}


def _sc(pts):
    return [(x * SS, y * SS) for x, y in pts]


def _cap(d, p, r, col):
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)


def draw_group(d, parts, fill=FUR, outline=OUTLINE, sw=STROKE):
    """
    パーツ群を「1つのシルエット＋外周だけの輪郭線」として描く。

    先に全パーツを太い線＋塗りで輪郭色に描き、そのあと同じ形を
    細い線＋塗りで本体色に重ねる。こうすると重なった部分の
    内側の線が消えて、外周だけに輪郭が残る。
    """
    for stage in (0, 1):
        for p in parts:
            pts = _sc(p["pts"])
            col = outline if stage == 0 else (p.get("fill") or fill)
            pad = sw * SS if stage == 0 else 0.0
            if p["kind"] == "poly":
                d.polygon(pts, fill=col)
                lw = max(1, int(round(2 * pad))) if stage == 0 else 0
                if lw:
                    d.line(pts + [pts[0]], fill=col, width=lw, joint="curve")
            else:
                lw = max(1, int(round(p["w"] * SS + 2 * pad)))
                d.line(pts, fill=col, width=lw, joint="curve")
                _cap(d, pts[0], lw / 2, col)
                _cap(d, pts[-1], lw / 2, col)


def ell(d, cx, cy, rx, ry, fill, rot=0.0):
    d.polygon(_sc(ellipse_pts(cx, cy, rx, ry, 40, rot)), fill=fill)


def line(d, pts, w, col, cap=True):
    p = _sc(pts)
    lw = max(1, int(round(w * SS)))
    d.line(p, fill=col, width=lw, joint="curve")
    if cap:
        _cap(d, p[0], lw / 2, col)
        _cap(d, p[-1], lw / 2, col)


# ---------------------------------------------------------------- 猫キャラ

DEFAULT_POSE = dict(
    x=160.0, y=248.0,     # 足元の位置
    scale=1.0,
    bob=0.0,              # 上下の弾み（体と頭）
    squash=1.0,           # つぶれ具合（1.0 で標準、<1 でしゃがむ）
    lean=0.0,             # 体の左右傾き（度）
    tilt=0.0,             # 首の傾き（度）
    head_dx=0.0, head_dy=0.0,
    paw_l=None, paw_r=None,   # 手先の位置（ローカル座標）。None で自然に下ろす
    ear=0.0,              # 耳のぱたぱた（度）
    tail=0.0,             # しっぽの振り
    eyes="open",          # open / blink / happy / sleepy / sparkle / wide / sad
    mouth="x",            # x / omega / smile / open / wave / flat
    blush=True,
    look=(0.0, 0.0),      # 黒目のオフセット
    pattern=None,         # None / "spots"
)


def pose(**kw):
    p = dict(DEFAULT_POSE)
    p.update(kw)
    return p


def _cat_geometry(p):
    """ポーズから猫のパーツ（ローカル座標）を組み立てる。

    背面グループ（胴体・頭・しっぽ）と前面グループ（手足）を分けて返す。
    グループごとに輪郭を引くので、手足が体の上でちゃんと形として見える。
    """
    bob = p["bob"]
    sq = p["squash"]

    # --- 胴体：卵形のブロブ
    body_ctrl = [(0, -98), (42, -74), (52, -34), (32, -6), (0, -2),
                 (-32, -6), (-52, -34), (-42, -74)]
    body = catmull(body_ctrl, 10)
    body = scale_pts(body, 0, -2, 1 + (1 - sq) * 0.35, sq)
    body = move_pts(body, 0, bob * 0.5)

    # --- しっぽ
    tw = p["tail"]
    tail = catmull([(44, -32 + bob * 0.5), (72, -36 + tw * 0.4 + bob * 0.5),
                    (88, -56 + tw + bob * 0.5), (80, -84 + tw * 1.6 + bob * 0.5)],
                   10, closed=False)

    # --- 頭（耳を含む）
    hx = p["head_dx"]
    hy = -118 + bob + p["head_dy"] - (1 - sq) * 16
    head = ellipse_pts(hx, hy, 57, 51, 56)

    def ear(side):
        e = catmull([(hx + 20 * side, hy - 42),
                     (hx + 33 * side, hy - 74),
                     (hx + 52 * side, hy - 40),
                     (hx + 44 * side, hy - 28)], 9)
        return rot_pts(e, hx + 30 * side, hy - 40, p["ear"] * side)

    head_parts = [ear(-1), ear(1), head]
    if p["tilt"]:
        head_parts = [rot_pts(q, hx, hy, p["tilt"]) for q in head_parts]

    back = [path(tail, 13), poly(body)] + [poly(q) for q in head_parts]

    # --- 前足（体の手前に置いて輪郭で分離する）
    front = []
    for side in (-1, 1):
        foot = ellipse_pts(24 * side, -13, 18, 12.5, 30, rot=8 * side)
        front.append(poly(foot))

    # --- 腕：肩から手先（paw）までのカプセル。手先の座標を直接指定できる。
    def arm(side, target):
        sx, sy = 36 * side, -76 + bob * 0.7
        if target is None:
            target = (50 * side, -44 + bob * 0.5)
        mx = (sx + target[0]) / 2 + 5 * side
        my = (sy + target[1]) / 2 + 2
        return path(catmull([(sx, sy), (mx, my), target], 9, closed=False), 16)

    front.append(arm(-1, p["paw_l"]))
    front.append(arm(1, p["paw_r"]))

    if p["lean"]:
        back = [dict(q, pts=rot_pts(q["pts"], 0, -20, p["lean"])) for q in back]
        front = [dict(q, pts=rot_pts(q["pts"], 0, -20, p["lean"])) for q in front]

    return back, front, (hx, hy)


def _make_T(p):
    """ローカル座標 → キャンバス座標の変換を作る。"""
    s, ox, oy, lean = p["scale"], p["x"], p["y"], p["lean"]

    def T(pts, cx=None, cy=None, tilt=0.0, leaned=False):
        q = rot_pts(pts, cx, cy, tilt) if tilt else pts
        if lean and not leaned:
            q = rot_pts(q, 0, -20, lean)
        return move_pts(scale_pts(q, 0, 0, s, s), ox, oy)

    return T


def _face(d, p, hx, hy, T):
    """顔まわりのディテール。hx,hy は頭の中心（ローカル座標）。"""
    tilt = p["tilt"]
    s = p["scale"]

    def F(pts):
        return T(pts, hx, hy, tilt)

    # 耳の内側
    for side in (-1, 1):
        inner = catmull([(hx + 27 * side, hy - 42),
                         (hx + 34 * side, hy - 63),
                         (hx + 45 * side, hy - 41),
                         (hx + 40 * side, hy - 34)], 8)
        inner = rot_pts(inner, hx + 30 * side, hy - 40, p["ear"] * side)
        d.polygon(_sc(F(inner)), fill=PINK)

    # ほっぺ
    if p["blush"]:
        for side in (-1, 1):
            d.polygon(_sc(F(ellipse_pts(hx + 37 * side, hy + 9, 13, 8.5, 28))), fill=BLUSH)

    # 目
    lx, ly = p["look"]
    eyes = p["eyes"]
    for side in (-1, 1):
        ex, ey = hx + 21 * side + lx, hy - 5 + ly
        if eyes == "blink":
            line(d, F([(ex - 8, ey), (ex, ey + 2.5), (ex + 8, ey)]), 3.4 * s, EYE)
        elif eyes == "happy":
            arc = [(ex - 9, ey + 4), (ex - 4, ey - 5), (ex + 4, ey - 5), (ex + 9, ey + 4)]
            line(d, F(catmull(arc, 8, closed=False)), 3.6 * s, EYE)
        elif eyes == "sad":
            arc = [(ex - 9, ey - 4), (ex - 4, ey + 4), (ex + 4, ey + 4), (ex + 9, ey - 4)]
            line(d, F(catmull(arc, 8, closed=False)), 3.4 * s, EYE)
        elif eyes == "sleepy":
            line(d, F([(ex - 8, ey - 1), (ex, ey + 3), (ex + 8, ey - 1)]), 3.4 * s, EYE)
        elif eyes == "wide":
            d.polygon(_sc(F(ellipse_pts(ex, ey, 9.5, 11.5, 30))), fill=EYE)
            d.polygon(_sc(F(ellipse_pts(ex - 3, ey - 4, 3.4, 4, 20))), fill=WHITE)
        elif eyes == "sparkle":
            d.polygon(_sc(F(ellipse_pts(ex, ey, 8.5, 10.5, 30))), fill=EYE)
            d.polygon(_sc(F(ellipse_pts(ex - 2.6, ey - 3.6, 3.2, 3.8, 20))), fill=WHITE)
            d.polygon(_sc(F(ellipse_pts(ex + 2.4, ey + 3.2, 1.8, 2.0, 16))), fill=WHITE)
        else:  # open
            d.polygon(_sc(F(ellipse_pts(ex, ey, 7.6, 9.6, 30))), fill=EYE)

    # 口
    m = p["mouth"]
    mx, my = hx, hy + 8
    if m == "x":
        line(d, F([(mx - 6, my - 5), (mx + 6, my + 5)]), 3.0 * s, EYE)
        line(d, F([(mx + 6, my - 5), (mx - 6, my + 5)]), 3.0 * s, EYE)
    elif m == "omega":
        line(d, F(catmull([(mx - 9, my - 3), (mx - 4.5, my + 4), (mx, my - 2)], 8, False)), 3.0 * s, EYE)
        line(d, F(catmull([(mx, my - 2), (mx + 4.5, my + 4), (mx + 9, my - 3)], 8, False)), 3.0 * s, EYE)
    elif m == "smile":
        line(d, F(catmull([(mx - 8, my - 3), (mx, my + 5), (mx + 8, my - 3)], 9, False)), 3.0 * s, EYE)
    elif m == "open":
        d.polygon(_sc(F(ellipse_pts(mx, my + 2, 7, 8.5, 26))), fill=EYE)
        d.polygon(_sc(F(ellipse_pts(mx, my + 5, 4, 4.5, 20))), fill=PINK_D)
    elif m == "wave":
        line(d, F(catmull([(mx - 9, my), (mx - 3, my + 4), (mx + 3, my - 1), (mx + 9, my + 3)], 8, False)), 2.8 * s, EYE)
    elif m == "flat":
        line(d, F([(mx - 6, my + 1), (mx + 6, my + 1)]), 2.8 * s, EYE)


def draw_cat(img, p, item_back=None, item_front=None):
    """
    猫を1匹描く。

    item_back / item_front は callable(draw, T, pose)。
    体の後ろ／手の前に小物を描きたいときに渡す。
    """
    d = ImageDraw.Draw(img)
    back, front, (hx, hy) = _cat_geometry(p)
    T = _make_T(p)
    s = p["scale"]

    def place(group):
        out = []
        for q in group:
            r = {"kind": q["kind"], "pts": T(q["pts"], leaned=True), "fill": q.get("fill")}
            if q["kind"] == "path":
                r["w"] = q["w"] * s
            out.append(r)
        return out

    if item_back:
        item_back(d, T, p)
    draw_group(d, place(back), FUR, OUTLINE, STROKE * s)
    _face(d, p, hx, hy, T)
    draw_group(d, place(front), FUR, OUTLINE, STROKE * s)
    if item_front:
        item_front(d, T, p)


# ---------------------------------------------------------------- 小物

def heart(d, cx, cy, r, fill=PINK, outline=OUTLINE, sw=2.6, rot=0.0):
    pts = []
    for i in range(60):
        t = 2 * math.pi * i / 60
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 16, cy + y * r / 16))
    if rot:
        pts = rot_pts(pts, cx, cy, rot)
    draw_group(d, [poly(pts)], fill, outline, sw)


def star(d, cx, cy, r, fill=(255, 224, 130, 255), n=4, sw=0.0):
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else r * 0.28
        t = math.pi * i / n - math.pi / 2
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    d.polygon(_sc(catmull(pts, 5)), fill=fill)


def sparkle(d, cx, cy, r, col=(255, 214, 120, 255)):
    line(d, [(cx - r, cy), (cx + r, cy)], 2.4, col)
    line(d, [(cx, cy - r), (cx, cy + r)], 2.4, col)


def fish(d, cx, cy, r, rot=0.0):
    body = ellipse_pts(cx, cy, r, r * 0.60, 36, rot)
    tail = catmull(rot_pts([(cx - r * 0.85, cy),
                            (cx - r * 1.75, cy - r * 0.60),
                            (cx - r * 1.45, cy),
                            (cx - r * 1.75, cy + r * 0.60)], cx, cy, rot), 8)
    draw_group(d, [poly(tail), poly(body)], (178, 214, 238, 255), OUTLINE, 2.4)
    ex, ey = rot_pts([(cx + r * 0.42, cy - r * 0.12)], cx, cy, rot)[0]
    d.polygon(_sc(ellipse_pts(ex, ey, r * 0.11, r * 0.13, 16)), fill=EYE)


def teardrop(d, cx, cy, r):
    pts = catmull([(cx, cy - r * 1.5), (cx + r * 0.75, cy + r * 0.2),
                   (cx, cy + r), (cx - r * 0.75, cy + r * 0.2)], 10)
    draw_group(d, [poly(pts)], (168, 214, 240, 235), (108, 158, 198, 255), 1.8)


def zzz(d, cx, cy, size, alpha=255):
    col = (150, 170, 205, alpha)
    s = size
    line(d, [(cx - s, cy - s), (cx + s, cy - s), (cx - s, cy + s), (cx + s, cy + s)], max(2.0, s * 0.42), col)


# ---------------------------------------------------------------- テキスト

_font_cache = {}


def font(size):
    key = int(size * SS)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_PATH, key)
    return _font_cache[key]


def text(img, s, cx, cy, size=34, fill=(120, 88, 76, 255),
         edge=WHITE, outer=OUTLINE, anchor="mm", spacing=1.0):
    """
    白フチ＋こげ茶フチの二重縁取りテキスト。スタンプらしい可読性を出す。
    """
    d = ImageDraw.Draw(img)
    f = font(size)
    x, y = cx * SS, cy * SS
    o1 = max(2, int(size * SS * 0.20))
    o2 = max(1, int(size * SS * 0.11))
    if outer:
        d.text((x, y), s, font=f, fill=outer, anchor=anchor,
               stroke_width=o1, stroke_fill=outer)
    if edge:
        d.text((x, y), s, font=f, fill=edge, anchor=anchor,
               stroke_width=o2, stroke_fill=edge)
    d.text((x, y), s, font=f, fill=fill, anchor=anchor,
           stroke_width=max(1, int(size * SS * 0.035)), stroke_fill=fill)


# ---------------------------------------------------------------- フレーム生成

def new_frame(w=W, h=H):
    """描画用の（SS 倍に拡大した）透明キャンバスを作る。"""
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def finish(img):
    """スーパーサンプリングを解いて実サイズに落とす。"""
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
