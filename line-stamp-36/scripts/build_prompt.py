#!/usr/bin/env python3
"""panels.yaml から ChatGPT（GPT-Image-2）へ貼り付けるプロンプトを組み立てる。

使い方:
    python3 scripts/build_prompt.py                       # 2キャラ版・36コマ
    python3 scripts/build_prompt.py --characters 1        # 1キャラ版（char2の記述を落とす）
    python3 scripts/build_prompt.py --panels prompts/panels-business.yaml
    python3 scripts/build_prompt.py -o out/prompt.txt     # ファイルに保存
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

HEADER = "添付の画像を元に、以下のプロンプトで合計{sheets}枚の画像を生成して　1:1で"

POSTPROCESS = """各画像は3×3のスタンプシートです。全てスタンプ用に切り取り、1コマ1ファイルにして、\
合計{total}個のファイルをZIPファイルとして納品してください。\
別パターンとしてプロレベルのLINEスタンプに仕上げるよう、背景を除去したバージョンもZIPで納品してください。

※画像は生成せず、加工作業のみ実行"""


def indent_block(text: str, pad: str = "    ") -> str:
    """YAMLのブロックスカラー用に本文をインデントする。"""
    lines = [ln.strip() for ln in text.strip().splitlines()]
    return "\n".join(pad + ln for ln in lines)


def build(data: dict, characters: int, per_sheet: int) -> str:
    chars = data["characters"]
    style = dict(data["style"])
    panels = data["panels"]

    total = len(panels)
    sheets = -(-total // per_sheet)  # 切り上げ

    out = [HEADER.format(sheets=sheets), ""]

    keys = ["character_1"] if characters == 1 else ["character_1", "character_2"]
    for key in keys:
        if key not in chars:
            sys.exit(f"panels.yaml に {key} がありません")
        out.append(f"{key}:")
        out.append(f"  name: {chars[key]['name']}")
        out.append("  description: |")
        out.append(indent_block(chars[key]["description"]))
        out.append("")

    # レイアウト行はコマ数から実際の値を書き直す（YAMLを書き換えたときのズレ防止）
    rows = cols = int(per_sheet ** 0.5)
    style["layout"] = f"{cols}列×{rows}行 × {sheets}セット（全{total}コマ）"

    out.append("style:")
    for k, v in style.items():
        out.append(f"  {k}: {v}")
    out.append("")

    out.append("panels:")
    for panel in panels:
        out.append(f"  - position: {panel['position']}")
        out.append(f"    text: {panel['text']}")
        out.append(f"    text_color: {panel['text_color']}")
        out.append(f"    char1_pose: {panel['char1_pose']}")
        if characters == 2 and panel.get("char2_pose"):
            out.append(f"    char2_pose: {panel['char2_pose']}")
        out.append("")

    out.append("---- ここまでが生成用プロンプト ----")
    out.append("")
    out.append("【生成が終わったら、続けて次を送る】")
    out.append("")
    out.append(POSTPROCESS.format(total=total))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panels", default=str(ROOT / "prompts" / "panels.yaml"), help="コマ定義YAML")
    ap.add_argument("--characters", type=int, choices=(1, 2), default=2, help="登場キャラ数")
    ap.add_argument("--per-sheet", type=int, default=9, help="1シートあたりのコマ数（既定9＝3×3）")
    ap.add_argument("-o", "--output", help="出力先ファイル（省略時は標準出力）")
    args = ap.parse_args()

    data = yaml.safe_load(Path(args.panels).read_text(encoding="utf-8"))
    text = build(data, args.characters, args.per_sheet)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"書き出し: {path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
