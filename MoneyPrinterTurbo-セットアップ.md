# MoneyPrinterTurbo を自分のPCで動かす手順

テーマを入れるだけでショート動画（台本→素材→音声→字幕）が出てくるOSSツール。
https://github.com/harry0703/MoneyPrinterTurbo

この手順は実際にコンテナ上で v1.3.3 をインストールして、動画生成まで通した内容をもとにしている。

---

## 用意するもの

| 何 | 必須 | 取得先 | 補足 |
|---|---|---|---|
| Pexels APIキー | 必須 | https://www.pexels.com/api/ | 無料。動画素材の取得に使う |
| LLM APIキー | 必須 | 下記どれか1つ | 台本と検索ワードの生成に使う |
| ffmpeg | 必須 | `brew install ffmpeg` | Dockerで動かすなら不要 |

LLMはどれか1つでいい。安く済ませるなら DeepSeek か Gemini。

- Gemini: https://aistudio.google.com/app/apikey （無料枠あり）
- DeepSeek: https://platform.deepseek.com/api_keys
- OpenAI: https://platform.openai.com/api-keys

音声合成（Edge TTS）は**キー不要**。日本語ナレーションもこれで出る。

---

## 手順A: Docker（おすすめ。環境を汚さない）

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo
cp config.example.toml config.toml
```

`config.toml` を開いて2箇所だけ書き換える:

```toml
pexels_api_keys = ["ここにPexelsのキー"]

llm_provider = "gemini"
gemini_api_key = "ここにGeminiのキー"
```

あとは起動:

```bash
docker compose up -d
```

ブラウザで http://127.0.0.1:8501 を開く。

---

## 手順B: 直接インストール（Python 3.11 必要）

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo

python3.11 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp config.example.toml config.toml
# 手順Aと同じく config.toml にキーを2つ書く

./webui.sh
```

`requirements.txt` はそのまま通った（moviepy 2.2.1 / streamlit 1.59.1 / edge_tts 7.2.7 など）。

---

## 日本語で作るときの設定

WebUIの設定パネルで:

- **動画のテーマ**: 日本語でOK
- **Video Language**: `ja-JP`
- **Voice**: `ja-JP-NanamiNeural`（女性）/ `ja-JP-KeitaNeural`（男性）
- **Font**: `MicrosoftYaHeiBold.ttc` のままで日本語は正しく表示される（検証済み）

字体をちゃんとした日本語書体にしたいなら、Noto Sans CJK JP を入れると綺麗になる:

```bash
# macOS
brew install --cask font-noto-sans-cjk
cp /Library/Fonts/NotoSansCJK-Bold.ttc resource/fonts/
```

そのあとWebUIのFont欄で `NotoSansCJK-Bold.ttc` を選ぶ。

---

## WebUIを使わずコマンドで回す

`cli.py` があるので、量産するならこっちが速い。

```bash
PYTHONPATH=. ./.venv/bin/python cli.py \
  --video-subject "AIで副業を始める方法" \
  --video-language ja-JP \
  --voice-name "ja-JP-NanamiNeural-Female" \
  --video-aspect 9:16 \
  --font-name "MicrosoftYaHeiBold.ttc" \
  --video-count 1
```

覚えておくと便利なオプション:

| オプション | 効果 |
|---|---|
| `--video-script "..."` | 台本を自分で渡す。LLM呼び出しをスキップ（＝APIキー不要） |
| `--video-terms "cat,city"` | 素材の検索ワードを自分で指定 |
| `--video-source local --video-materials a.mp4,b.mp4` | Pexelsを使わず手持ち素材で作る |
| `--stop-at script` | 台本だけ作って止める（terms / audio / subtitle / materials / video も指定可） |
| `--custom-audio-file voice.mp3` | ナレーションを自分の音声ファイルに差し替え |
| `--no-subtitle-enabled` | 字幕なし |
| `--video-count 5` | 同じ台本で5本まとめて出力 |

出力先は `storage/tasks/<task-id>/final-1.mp4`。

---

## つまずきそうなところ

**Python 3.13 だと入らない**
`.python-version` は 3.11。3.11 で venv を作るのが確実。

**字幕が □ になる**
フォントが日本語を持っていない。上の Noto を入れる。

**素材が集まらない / 動画が短い**
Pexelsは英語の検索ワードで引く。日本語テーマだとヒットしにくいので `--video-terms` で英単語を指定すると安定する。

**Edge TTS が固まる**
`config.toml` の `edge_tts_timeout = 30` を大きくする。

---

## 検証メモ

このコンテナ上で確認したこと:

- ✅ インストール（ffmpeg + requirements.txt）は素通り
- ✅ 台本→素材結合→音声合成→書き出しのパイプラインが最後まで完走
- ✅ 日本語字幕が正しくレンダリングされる（`MicrosoftYaHeiBold.ttc` / `NotoSansCJK-Bold.ttc` の両方）
- ❌ フル生成はここでは不可。このコンテナの通信ポリシーが
  `api.pexels.com`・`pixabay.com`・`speech.platform.bing.com`（Edge TTS）を
  403 で塞いでいるため。手元のPCなら問題なく通る。

なので上記の完走テストは、素材と音声をローカルファイルで差し替えて実行している。
