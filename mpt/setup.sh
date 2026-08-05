#!/usr/bin/env bash
# MoneyPrinterTurbo を日本語設定でセットアップする。
#
# 使い方:
#   export PEXELS_API_KEY="xxxx"
#   export GEMINI_API_KEY="yyyy"        # または OPENAI_API_KEY / DEEPSEEK_API_KEY
#   ./mpt/setup.sh
#
# 置き場所は既定で ~/MoneyPrinterTurbo。MPT_DIR で変えられる。

set -euo pipefail

MPT_DIR="${MPT_DIR:-$HOME/MoneyPrinterTurbo}"
REPO="https://github.com/harry0703/MoneyPrinterTurbo.git"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mエラー:\033[0m %s\n' "$*" >&2; exit 1; }

# --- 前提チェック ---------------------------------------------------------

command -v git >/dev/null || die "git がありません。"

if command -v ffmpeg >/dev/null; then
  say "ffmpeg: $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"
else
  die "ffmpeg がありません。先に 'brew install ffmpeg' を実行してください。"
fi

PY=""
for c in python3.11 python3.12 python3; do
  if command -v "$c" >/dev/null; then
    v="$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    case "$v" in
      3.11|3.12) PY="$c"; break ;;
    esac
  fi
done
[ -n "$PY" ] || die "Python 3.11 か 3.12 が必要です（3.13 だと依存が入りません）。'brew install python@3.11' を実行してください。"
say "Python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

# --- キーの確認 -----------------------------------------------------------

[ -n "${PEXELS_API_KEY:-}" ] || die "PEXELS_API_KEY が未設定です。https://www.pexels.com/api/ で無料取得できます。"

LLM_PROVIDER=""
LLM_KEY=""
if   [ -n "${GEMINI_API_KEY:-}" ];   then LLM_PROVIDER="gemini";   LLM_KEY="$GEMINI_API_KEY"
elif [ -n "${OPENAI_API_KEY:-}" ];   then LLM_PROVIDER="openai";   LLM_KEY="$OPENAI_API_KEY"
elif [ -n "${DEEPSEEK_API_KEY:-}" ]; then LLM_PROVIDER="deepseek"; LLM_KEY="$DEEPSEEK_API_KEY"
else
  die "LLM のキーが未設定です。GEMINI_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY のどれか1つを設定してください。"
fi
say "LLM プロバイダ: $LLM_PROVIDER"

# --- 取得 -----------------------------------------------------------------

if [ -d "$MPT_DIR/.git" ]; then
  say "既存のクローンを更新: $MPT_DIR"
  git -C "$MPT_DIR" pull --ff-only
else
  say "クローン中: $MPT_DIR"
  git clone --depth 1 "$REPO" "$MPT_DIR"
fi

# --- 依存 -----------------------------------------------------------------

if [ ! -x "$MPT_DIR/.venv/bin/python" ]; then
  say "venv を作成中"
  "$PY" -m venv "$MPT_DIR/.venv"
fi

say "依存をインストール中（数分かかります）"
"$MPT_DIR/.venv/bin/pip" install -q --upgrade pip
"$MPT_DIR/.venv/bin/pip" install -q -r "$MPT_DIR/requirements.txt"

# --- 設定 -----------------------------------------------------------------

[ -f "$MPT_DIR/config.toml" ] || cp "$MPT_DIR/config.example.toml" "$MPT_DIR/config.toml"

say "config.toml にキーを書き込み中"
MPT_CONFIG="$MPT_DIR/config.toml" \
MPT_PEXELS="$PEXELS_API_KEY" \
MPT_PROVIDER="$LLM_PROVIDER" \
MPT_LLM_KEY="$LLM_KEY" \
"$MPT_DIR/.venv/bin/python" - <<'PY'
import os
import re

path = os.environ["MPT_CONFIG"]
pexels = os.environ["MPT_PEXELS"]
provider = os.environ["MPT_PROVIDER"]
llm_key = os.environ["MPT_LLM_KEY"]

with open(path, encoding="utf-8") as f:
    text = f.read()


def set_key(text, key, value):
    """トップレベルの key = ... を value で置き換える。"""
    pattern = re.compile(rf'^(\s*){re.escape(key)}\s*=.*$', re.MULTILINE)
    replacement = rf'\g<1>{key} = {value}'
    new_text, n = pattern.subn(replacement, text, count=1)
    if n == 0:
        raise SystemExit(f"config.toml に {key} が見つかりませんでした")
    return new_text


text = set_key(text, "pexels_api_keys", f'["{pexels}"]')
text = set_key(text, "llm_provider", f'"{provider}"')
text = set_key(text, f"{provider}_api_key", f'"{llm_key}"')

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print(f"  pexels_api_keys / llm_provider={provider} / {provider}_api_key を設定しました")
PY

# --- 日本語フォント（任意） ------------------------------------------------

for cand in \
  "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc" \
  "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" \
  "/Library/Fonts/NotoSansCJK-Bold.ttc"
do
  if [ -f "$cand" ]; then
    cp "$cand" "$MPT_DIR/resource/fonts/" 2>/dev/null && \
      say "日本語フォントを追加: $(basename "$cand")"
    break
  fi
done

# --- 完了 -----------------------------------------------------------------

cat <<EOF

セットアップ完了。

  WebUI で使う:
    cd "$MPT_DIR" && ./webui.sh
    → http://127.0.0.1:8501

  コマンドで1本作る:
    ./mpt/make-video.sh "AIで副業を始める方法"

EOF
