"""グリーンバック除去と、LINE審査で引っかかる「内部の透過穴」の始末。

過去に「イラストの内部が透過されています」でリジェクトされた事例がある。
原因は、透過処理のときにキャラの内側へ目に見えないサイズの穴が残っていたこと。
このモジュールはその穴を検出して埋めるところまでを担当する。
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage


# ---- グリーンバック除去 -----------------------------------------------------
def remove_green(img: Image.Image, keep: int = 25, cut: int = 60,
                 despill: bool = True) -> Image.Image:
    """緑背景を透過させる。

    「緑らしさ」= G - max(R, B) で判定する。
      keep 以下 … 完全に不透明（キャラ本体）
      cut 以上  … 完全に透明（背景）
      その間    … 中間のアルファ（輪郭のアンチエイリアス）

    despill=True なら、輪郭に残る緑かぶりを抑える。
    """
    # int16 だと (cut - greenness) * 255 が桁あふれして、緑から遠い色ほど
    # 透明にされてしまう。int32 で計算する。
    arr = np.array(img.convert("RGBA"), dtype=np.int32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    greenness = g - np.maximum(r, b)

    span = max(1, cut - keep)
    alpha = np.clip((cut - greenness) * 255 // span, 0, 255)
    alpha = np.minimum(alpha, arr[..., 3])          # 元から透明な所は透明のまま

    out = np.dstack([r, g, b, alpha]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    return despill_visible(img) if despill else img


def despill_visible(img: Image.Image, tol: int = 0) -> Image.Image:
    """見えている画素に残った緑かぶりを抑える。

    G が R と B の平均を超えていたら、その平均まで落とす。
    縮小したあとの輪郭にも緑が乗るので、仕上げにもう一度かけると効く。
    """
    arr = np.array(img.convert("RGBA"), dtype=np.int32)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    neutral = (r + b) // 2
    arr[..., 1] = np.where((a > 0) & (g > neutral + tol), neutral, g)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# ---- 内部の透過穴を埋める ---------------------------------------------------
def fill_interior_holes(img: Image.Image, opaque_at: int = 250,
                        max_area: float = 0.02) -> tuple[Image.Image, int, int]:
    """キャラの内側にできた透過の穴を埋める。

    外周とつながっていない透明領域＝内部の穴。面積が小さいものだけ埋める
    （max_area は画像全体に対する比率。0 以下ならすべて埋める）。

    戻り値は (処理後の画像, 埋めた穴の数, 埋めた画素数)。
    """
    arr = np.array(img.convert("RGBA"))
    alpha = arr[..., 3]
    solid = alpha >= opaque_at

    filled = ndimage.binary_fill_holes(solid)
    holes = filled & ~solid
    if not holes.any():
        return img, 0, 0

    labels, n = ndimage.label(holes)
    if max_area > 0:
        limit = arr.shape[0] * arr.shape[1] * max_area
        sizes = ndimage.sum_labels(np.ones_like(labels), labels, range(1, n + 1))
        small = {i + 1 for i, sz in enumerate(sizes) if sz <= limit}
        holes = np.isin(labels, list(small)) if small else np.zeros_like(holes)
        n = len(small)
    if not holes.any():
        return img, 0, 0

    # 穴の色は最寄りの不透明画素から借りる。
    _, (yi, xi) = ndimage.distance_transform_edt(~solid, return_indices=True)
    for c in range(3):
        arr[..., c] = np.where(holes, arr[..., c][yi, xi], arr[..., c])
    arr[..., 3] = np.where(holes, 255, alpha)
    return Image.fromarray(arr, "RGBA"), n, int(holes.sum())


def harden_interior(img: Image.Image, margin: int = 2) -> tuple[Image.Image, int]:
    """輪郭から margin 画素より内側にある半透明を、完全な不透明にする。

    輪郭のアンチエイリアスは残したまま、内側だけをベタにする。
    目に見えない薄い透過が審査で拾われるのを防ぐため。
    """
    arr = np.array(img.convert("RGBA"))
    alpha = arr[..., 3]
    inside = ndimage.binary_erosion(alpha > 0, iterations=max(1, margin))
    target = inside & (alpha < 255)
    if not target.any():
        return img, 0
    arr[..., 3] = np.where(target, 255, alpha)
    return Image.fromarray(arr, "RGBA"), int(target.sum())


def clean(img: Image.Image, opaque_at: int = 250, max_area: float = 0.02,
          margin: int = 2, passes: int = 3) -> tuple[Image.Image, dict]:
    """内側のベタ塗りと穴埋めを、変化がなくなるまで交互にかける。

    ベタ塗りは穴の形を変え、穴埋めはベタ塗りの対象を変えるので、
    片方だけだと1画素の穴が残ることがある。
    """
    total = {"holes": 0, "hole_px": 0, "soft_px": 0}
    for _ in range(max(1, passes)):
        img, soft_px = harden_interior(img, margin)
        img, holes, hole_px = fill_interior_holes(img, opaque_at, max_area)
        total["soft_px"] += soft_px
        total["holes"] += holes
        total["hole_px"] += hole_px
        if soft_px == 0 and holes == 0:
            break
    return img, total


def audit(img: Image.Image, opaque_at: int = 250, margin: int = 2) -> dict:
    """埋めずに、内部の穴・半透明がどれだけ残っているかだけ数える。"""
    arr = np.array(img.convert("RGBA"))
    alpha = arr[..., 3]
    solid = alpha >= opaque_at
    holes = ndimage.binary_fill_holes(solid) & ~solid
    _, n = ndimage.label(holes)
    inside = ndimage.binary_erosion(alpha > 0, iterations=max(1, margin))
    return {"holes": n, "hole_px": int(holes.sum()),
            "soft_px": int((inside & (alpha < 255)).sum())}


# ---- 余白のトリミング -------------------------------------------------------
def union_bbox(frames: list, pad: int = 2) -> tuple[int, int, int, int] | None:
    """全コマを通して中身が入っている範囲。コマ間で位置がずれないよう共通で切る。"""
    box = None
    for f in frames:
        bb = f.getbbox()
        if bb is None:
            continue
        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                      max(box[2], bb[2]), max(box[3], bb[3]))
    if box is None:
        return None
    w, h = frames[0].size
    return (max(0, box[0] - pad), max(0, box[1] - pad),
            min(w, box[2] + pad), min(h, box[3] + pad))
