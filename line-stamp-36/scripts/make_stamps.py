#!/usr/bin/env python3
"""GPT-Image-2 が出力した 3×3 スタンプシートを、LINE申請用の個別PNG＋ZIPに変換する。

ChatGPTに切り抜きを頼むと、コマの位置ズレ・サイズ不揃い・白フチ残りが起きることがある。
このスクリプトは同じ工程をローカルで決定的に実行する（毎回まったく同じ結果になる）。

    python3 scripts/make_stamps.py sheets/*.png -o out

やっていること:
  1. シートを 3×3 に分割（余白の白帯を見て境界を微調整）
  2. 外周につながった背景色だけを透明化（キャラ内部の白は残す）
  3. 余白を詰めて 370×320px の透明キャンバスに中央配置
  4. main.png(240×240) / tab.png(96×74) を生成
  5. 背景ありZIPと背景透過ZIPを書き出し

注意: LINE Creators Market のスタンプ個数は 8/16/24/32/40 個のいずれか。
36個はそのままでは申請できないので --select で32個に絞るか、4コマ足して40個にする。
"""

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

STAMP_SIZE = (370, 320)
MAIN_SIZE = (240, 240)
TAB_SIZE = (96, 74)
MAX_BYTES = 1_000_000  # LINEの1ファイル上限（1MB）
VALID_COUNTS = (8, 16, 24, 32, 40)
FILL_MARK = (255, 0, 255)  # 背景検出用の一時色（マゼンタ）


# ---------------------------------------------------------------- 背景まわり

def guess_bg_color(img: Image.Image) -> tuple:
    """外周1pxで最頻の色を背景色とみなす。"""
    arr = np.array(img.convert("RGB"))
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    colors, counts = np.unique(border.reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in colors[counts.argmax()])


def background_mask(img: Image.Image, bg_color: tuple, tolerance: int) -> np.ndarray:
    """外周からつながっている背景ピクセルだけ True を返す。

    単純な色しきい値だと目のハイライトや白い服まで抜けてしまうため、
    画像の外側2pxを背景色で囲ってから1回だけ塗りつぶし判定する。
    """
    pad = 2
    w, h = img.size
    canvas = Image.new("RGB", (w + pad * 2, h + pad * 2), bg_color)
    canvas.paste(img.convert("RGB"), (pad, pad))
    ImageDraw.floodfill(canvas, (0, 0), FILL_MARK, thresh=tolerance)
    filled = np.array(canvas)[pad:pad + h, pad:pad + w]
    return np.all(filled == np.array(FILL_MARK, dtype=np.uint8), axis=-1)


def cut_out(cell: Image.Image, bg_color: tuple, tolerance: int, feather: float) -> Image.Image:
    """背景を透明にした RGBA を返す。"""
    mask = background_mask(cell, bg_color, tolerance)
    rgba = np.array(cell.convert("RGBA"))
    alpha = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))

    if feather > 0:
        # 境界を1px内側へ寄せてからぼかす。背景色の白フチが残るのを防ぐため。
        alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(feather))

    rgba[:, :, 3] = np.array(alpha)
    return Image.fromarray(rgba, "RGBA")


# ---------------------------------------------------------------- 分割

def detect_boundaries(ink: np.ndarray, divisions: int, length: int, search: float) -> list:
    """等分位置の近くで、いちばん背景が多い（インクの少ない）位置を境界にする。"""
    bounds = [0]
    for i in range(1, divisions):
        center = round(i * length / divisions)
        window = max(4, int(length / divisions * search))
        lo, hi = max(0, center - window), min(length, center + window + 1)
        seg = ink[lo:hi]
        if len(seg) == 0:
            bounds.append(center)
            continue
        best = min(range(len(seg)), key=lambda j: (seg[j], abs(lo + j - center)))
        bounds.append(lo + best)
    bounds.append(length)
    return bounds


def split_sheet(img: Image.Image, rows: int, cols: int, bg_color: tuple,
                tolerance: int, auto_grid: bool) -> list:
    w, h = img.size
    if not auto_grid:
        col_b = [round(i * w / cols) for i in range(cols + 1)]
        row_b = [round(i * h / rows) for i in range(rows + 1)]
    else:
        mask = background_mask(img, bg_color, tolerance)
        ink = ~mask
        col_b = detect_boundaries(ink.mean(axis=0), cols, w, 0.12)
        row_b = detect_boundaries(ink.mean(axis=1), rows, h, 0.12)

    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append(img.crop((col_b[c], row_b[r], col_b[c + 1], row_b[r + 1])))
    return cells


# ---------------------------------------------------------------- 仕上げ

def fit_canvas(src: Image.Image, size: tuple, margin: int, bg=None) -> Image.Image:
    """透明部分を詰めてから、指定サイズの中央に配置する。"""
    trimmed = src.crop(src.getbbox()) if src.getbbox() else src
    box = (max(1, size[0] - margin * 2), max(1, size[1] - margin * 2))
    work = trimmed.copy()
    work.thumbnail(box, Image.LANCZOS)

    canvas = Image.new("RGBA", size, bg if bg else (0, 0, 0, 0))
    canvas.paste(work, ((size[0] - work.width) // 2, (size[1] - work.height) // 2), work)
    return canvas


def save_png(img: Image.Image, path: Path) -> int:
    """1MB以内に収めて保存し、バイト数を返す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    if path.stat().st_size > MAX_BYTES:
        # 減色して再保存（見た目の劣化は最小限に抑える）
        img.convert("RGBA").quantize(colors=256, method=Image.MEDIANCUT).save(path, "PNG", optimize=True)
    return path.stat().st_size


def parse_select(spec: str, total: int) -> list:
    """"1-32" や "1,3,5-8" を 0始まりのindexリストにする。"""
    picked = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            picked.extend(range(int(a), int(b) + 1))
        else:
            picked.append(int(chunk))
    for n in picked:
        if not 1 <= n <= total:
            sys.exit(f"--select の {n} はコマ番号の範囲外です（1〜{total}）")
    return [n - 1 for n in picked]


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(src_dir.glob("*.png")):
            zf.write(f, f.name)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="+", help="シート画像（生成順に並べる）")
    ap.add_argument("-o", "--output", default="out", help="出力ディレクトリ")
    ap.add_argument("--grid", default="3x3", help="1シートの分割（既定 3x3）")
    ap.add_argument("--bg", default="auto", help="背景色 auto / white / R,G,B")
    ap.add_argument("--tolerance", type=int, default=40, help="背景色の許容差（大きいほど強く抜く）")
    ap.add_argument("--feather", type=float, default=0.8, help="フチのぼかし量px（0で無効）")
    ap.add_argument("--margin", type=int, default=10, help="スタンプ枠内の余白px")
    ap.add_argument("--equal-split", action="store_true", help="白帯検出をやめて完全な等分割にする")
    ap.add_argument("--select", help="申請に使うコマ番号（例: 1-32）")
    ap.add_argument("--main-index", type=int, default=1, help="メイン画像に使うコマ番号")
    args = ap.parse_args()

    try:
        cols, rows = (int(v) for v in args.grid.lower().split("x"))
    except ValueError:
        sys.exit("--grid は 3x3 の形式で指定してください")

    paths = [Path(p) for p in args.sheets]
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit("見つからないファイル: " + ", ".join(str(p) for p in missing))

    cells = []
    for path in paths:
        sheet = Image.open(path).convert("RGB")
        if args.bg == "auto":
            bg_color = guess_bg_color(sheet)
        elif args.bg == "white":
            bg_color = (255, 255, 255)
        else:
            bg_color = tuple(int(v) for v in args.bg.split(","))
        print(f"読み込み: {path.name} {sheet.size} 背景色={bg_color}")
        for cell in split_sheet(sheet, rows, cols, bg_color,
                                args.tolerance, not args.equal_split):
            cells.append((cell, bg_color))  # シートごとに背景色が違っても崩れないよう一緒に持つ

    total = len(cells)
    indexes = parse_select(args.select, total) if args.select else list(range(total))
    count = len(indexes)

    out = Path(args.output)
    dir_bg = out / "with_bg"
    dir_tr = out / "transparent"
    for d in (dir_bg, dir_tr):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()

    cut_cache = {}
    for n, idx in enumerate(indexes, start=1):
        cell, bg_color = cells[idx]
        cut = cut_out(cell, bg_color, args.tolerance, args.feather)
        cut_cache[idx] = cut

        opaque = fit_canvas(cut, STAMP_SIZE, args.margin, bg=bg_color + (255,))
        clear = fit_canvas(cut, STAMP_SIZE, args.margin)
        size_bg = save_png(opaque, dir_bg / f"{n:02d}.png")
        size_tr = save_png(clear, dir_tr / f"{n:02d}.png")
        print(f"  {n:02d}.png  元コマ#{idx + 1}  背景あり {size_bg // 1024}KB / 透過 {size_tr // 1024}KB")

    main_idx = args.main_index - 1
    if main_idx not in cut_cache:
        main_idx = indexes[0]
    save_png(fit_canvas(cut_cache[main_idx], MAIN_SIZE, 8), dir_tr / "main.png")
    save_png(fit_canvas(cut_cache[main_idx], TAB_SIZE, 4), dir_tr / "tab.png")
    print(f"  main.png / tab.png ← 元コマ#{main_idx + 1}")

    zip_dir(dir_bg, out / "stamps_with_bg.zip")
    zip_dir(dir_tr, out / "stamps_transparent.zip")

    print(f"\n完了: {count}個 → {out / 'stamps_transparent.zip'}（申請用）")
    print(f"      {out / 'stamps_with_bg.zip'}（確認用・背景あり）")
    if count not in VALID_COUNTS:
        print(f"\n⚠ LINEに申請できるスタンプ個数は {VALID_COUNTS} 個のいずれかです。")
        print(f"  いまは {count} 個なので、例えば `--select 1-32` で32個に絞ってください。")


if __name__ == "__main__":
    main()
