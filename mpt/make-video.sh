#!/usr/bin/env bash
# MoneyPrinterTurbo で日本語ショート動画を1本作る。
#
# 使い方:
#   ./mpt/make-video.sh "AIで副業を始める方法"
#   ./mpt/make-video.sh "猫の睡眠" --terms "cat sleeping,cozy home" --count 3
#
# オプション:
#   --terms  "a,b"   Pexels の検索ワード（英語推奨）。省略すると LLM が作る
#   --count  N       出力本数（既定 1）
#   --voice  male    ナレーションを男性声に（既定 female）
#   --aspect 16:9    16:9 / 1:1 / 9:16（既定 9:16）
#   --script "..."   台本を自分で渡す。LLM を呼ばない
#   --dry            台本だけ作って止める

set -euo pipefail

MPT_DIR="${MPT_DIR:-$HOME/MoneyPrinterTurbo}"

die() { printf '\033[1;31mエラー:\033[0m %s\n' "$*" >&2; exit 1; }

[ -x "$MPT_DIR/.venv/bin/python" ] || die "$MPT_DIR が未セットアップです。先に ./mpt/setup.sh を実行してください。"
[ $# -ge 1 ] || die "テーマを渡してください。例: ./mpt/make-video.sh \"AIで副業を始める方法\""

SUBJECT="$1"; shift

TERMS=""
COUNT="1"
VOICE="ja-JP-NanamiNeural-Female"
ASPECT="9:16"
SCRIPT=""
STOP_AT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --terms)  TERMS="${2:?--terms に値が必要です}"; shift 2 ;;
    --count)  COUNT="${2:?--count に値が必要です}"; shift 2 ;;
    --aspect) ASPECT="${2:?--aspect に値が必要です}"; shift 2 ;;
    --script) SCRIPT="${2:?--script に値が必要です}"; shift 2 ;;
    --voice)
      case "${2:-}" in
        male|Male)     VOICE="ja-JP-KeitaNeural-Male" ;;
        female|Female) VOICE="ja-JP-NanamiNeural-Female" ;;
        *) die "--voice は male か female です" ;;
      esac
      shift 2 ;;
    --dry) STOP_AT="script"; shift ;;
    *) die "不明なオプション: $1" ;;
  esac
done

# 日本語フォントは、入っていればそれを使う。無ければ同梱フォント
# （MicrosoftYaHeiBold.ttc）でも日本語は正しく表示される。
FONT="MicrosoftYaHeiBold.ttc"
for f in "NotoSansCJK-Bold.ttc" "ヒラギノ角ゴシック W6.ttc"; do
  if [ -f "$MPT_DIR/resource/fonts/$f" ]; then FONT="$f"; break; fi
done

set -- \
  --video-subject "$SUBJECT" \
  --video-language "ja-JP" \
  --voice-name "$VOICE" \
  --video-aspect "$ASPECT" \
  --font-name "$FONT" \
  --video-count "$COUNT" \
  --subtitle-enabled

[ -n "$TERMS" ]   && set -- "$@" --video-terms "$TERMS"
[ -n "$SCRIPT" ]  && set -- "$@" --video-script "$SCRIPT"
[ -n "$STOP_AT" ] && set -- "$@" --stop-at "$STOP_AT"

printf '\033[1;36m==>\033[0m テーマ: %s\n' "$SUBJECT"
printf '\033[1;36m==>\033[0m 声: %s / フォント: %s / 比率: %s\n' "$VOICE" "$FONT" "$ASPECT"

cd "$MPT_DIR"
PYTHONPATH="$MPT_DIR" exec "$MPT_DIR/.venv/bin/python" cli.py "$@"
