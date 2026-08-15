#!/usr/bin/env bash
# Higgsfield で生成した素材を使って、MoneyPrinterTurbo でサンプル動画を1本組む。
#
# 背景:
#   素材（画像3枚）と日本語ナレーションは Higgsfield 側で生成済み。
#   ただし作業コンテナからは Higgsfield の CDN が 403 で塞がれていて
#   ダウンロードできなかったため、この組み立てだけ手元で実行する。
#
# 使い方:
#   1. Higgsfield のライブラリからナレーション音声を mp3 で落として、
#      このディレクトリに voice.mp3 という名前で置く
#   2. ./mpt/sample/build-sample.sh
#
# なぜ2段階か:
#   cli.py には SRT を渡すオプションが無く、字幕は Edge TTS か Whisper から
#   しか作れない。ここでは自前の音声を使うので、まず字幕なしで映像を組み、
#   そのあと自作の SRT を焼き込む。

set -euo pipefail

MPT_DIR="${MPT_DIR:-$HOME/MoneyPrinterTurbo}"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/sample.mp4"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mエラー:\033[0m %s\n' "$*" >&2; exit 1; }

[ -x "$MPT_DIR/.venv/bin/python" ] || die "$MPT_DIR が未セットアップです。先に ./mpt/setup.sh を実行してください。"
command -v ffprobe >/dev/null || die "ffmpeg/ffprobe がありません。'brew install ffmpeg' を実行してください。"

PY="$MPT_DIR/.venv/bin/python"

# --- 素材の取得 -----------------------------------------------------------

IMG_BASE="https://d8j0ntlcm91z4.cloudfront.net/user_3FVKEnuSRou9ZWUmzk5Lt8LXzKy"
IMG_1="$IMG_BASE/hf_20260815_090222_3b172927-a8b0-4d2f-b16b-161ca2252ebd.png"
IMG_2="$IMG_BASE/hf_20260815_090222_e57b552e-786d-416b-9957-4c68eb76fe88.png"
IMG_3="$IMG_BASE/hf_20260815_090222_9965aa60-deee-42e7-8e46-512327869ea2.png"

i=1
for url in "$IMG_1" "$IMG_2" "$IMG_3"; do
  if [ ! -f "$HERE/img$i.png" ]; then
    say "素材 $i をダウンロード中"
    curl -fsSL -o "$HERE/img$i.png" "$url" \
      || die "素材 $i の取得に失敗。Higgsfield のライブラリから手動で落として $HERE/img$i.png に置いてください。"
  fi
  i=$((i + 1))
done

[ -f "$HERE/voice.mp3" ] \
  || die "$HERE/voice.mp3 がありません。Higgsfield のライブラリからナレーション音声を mp3 で落として置いてください。"

# --- 字幕をナレーションの長さに合わせて作る --------------------------------

say "音声の長さを測って字幕を生成中"
DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$HERE/voice.mp3")"

SRT_DURATION="$DURATION" "$PY" - "$HERE/sample.srt" <<'PY'
import os
import sys

# 台本。ナレーション音声とこの並びは一致している。
lines = [
    "AIで副業、何から始めればいいか分からない。",
    "まずは、自分が普段やっている作業を書き出してみてください。",
    "そこがAIの出番です。",
    "次に、その作業をAIに任せて、浮いた時間を売る。",
    "最後に、結果を発信する。",
    "仕事は、発信した人のところに来ます。",
]

total = float(os.environ["SRT_DURATION"])

# 話す長さは文字数にだいたい比例するので、その比で割り振る。
weights = [len(line) for line in lines]
total_weight = sum(weights)


def timestamp(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


cursor = 0.0
blocks = []
for i, (line, weight) in enumerate(zip(lines, weights), start=1):
    span = total * weight / total_weight
    start, end = cursor, cursor + span
    cursor = end
    blocks.append(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{line}\n")

with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("\n".join(blocks))

print(f"  {len(lines)} 行 / 合計 {total:.1f} 秒")
PY

# --- 1段目: 映像を組む（字幕なし） -----------------------------------------

say "素材とナレーションを結合中"

cd "$MPT_DIR"
RESULT_JSON="$(PYTHONPATH="$MPT_DIR" "$PY" cli.py \
  --video-script "AIで副業を始める3ステップ" \
  --video-terms "startup" \
  --video-source local \
  --video-materials "$HERE/img1.png,$HERE/img2.png,$HERE/img3.png" \
  --custom-audio-file "$HERE/voice.mp3" \
  --video-aspect 9:16 \
  --bgm-type none \
  --no-subtitle-enabled \
  --video-count 1 | tail -1)"

COMBINED="$(printf '%s' "$RESULT_JSON" | "$PY" -c '
import json, sys
data = json.load(sys.stdin)
paths = data.get("result", {}).get("combined_videos") or []
if not paths:
    sys.exit("cli.py の出力に combined_videos がありませんでした")
print(paths[0])
')"

say "結合済み: $COMBINED"

# --- 2段目: 日本語字幕を焼き込む -------------------------------------------

say "日本語字幕を焼き込み中"

MPT_COMBINED="$COMBINED" \
MPT_AUDIO="$HERE/voice.mp3" \
MPT_SRT="$HERE/sample.srt" \
MPT_OUT="$OUT" \
PYTHONPATH="$MPT_DIR" "$PY" - <<'PY'
import os

from app.models.schema import VideoAspect, VideoParams
from app.services import video

# 同梱の MicrosoftYaHeiBold.ttc でも日本語は正しく出る。
# Noto かヒラギノが入っていればそちらを優先する。
font = "MicrosoftYaHeiBold.ttc"
for candidate in ("NotoSansCJK-Bold.ttc", "ヒラギノ角ゴシック W6.ttc"):
    if os.path.isfile(os.path.join("resource", "fonts", candidate)):
        font = candidate
        break

params = VideoParams(video_subject="AIで副業を始める3ステップ")
params.video_aspect = VideoAspect.portrait
params.subtitle_enabled = True
params.font_name = font
params.font_size = 60
params.text_fore_color = "#FFFFFF"
params.stroke_color = "#000000"
params.stroke_width = 1.5
params.subtitle_position = "bottom"
params.bgm_type = "none"
params.voice_volume = 1.0

ok = video.generate_video(
    video_path=os.environ["MPT_COMBINED"],
    audio_path=os.environ["MPT_AUDIO"],
    subtitle_path=os.environ["MPT_SRT"],
    output_file=os.environ["MPT_OUT"],
    params=params,
)
if not ok:
    raise SystemExit("字幕の焼き込みに失敗しました")
print(f"  フォント: {font}")
PY

cat <<EOF

完成: $OUT

字幕を直したいときは $HERE/sample.srt を編集して、
このスクリプトをもう一度実行してください（素材は再ダウンロードされません）。
EOF
