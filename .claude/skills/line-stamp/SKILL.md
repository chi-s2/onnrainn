---
name: line-stamp
description: >-
  動くLINEスタンプ（アニメーションスタンプ）の制作を支援するスキル。
  「LINEスタンプを作って」「スタンプの申請用ファイルを作って」「動画をAPNGにして」
  「グリーンバック動画を透過して」「スタンプの確認ページを作って」「申請用zipを作って」
  「スタンプがリジェクトされた」などと言われたら必ずこのスキルを使うこと。
  グリーンバック動画→透過APNG変換、24個選定用の確認ページ生成、
  main.png/tab.png/zip の申請パッケージ作成、LINE規格チェックのすべてに対応する。
---

# 動くLINEスタンプ制作スキル

`line-stamp/` ディレクトリにある `stamp.py` が制作パイプラインの本体。
必ず `line-stamp/README.md` を読んでから作業すること。プロンプト類は `line-stamp/prompts.md`。

## コマンド早見表

```bash
pip install -r line-stamp/requirements.txt   # 初回のみ

# 工程4: グリーンバック動画 → 透過APNG候補（1.5秒ごとにカット）
python line-stamp/stamp.py convert 動画.mp4 --every 1.5 --out work/candidates

# 工程5: 選定用の確認ページを生成（ブラウザで開いて24個選ぶ）
python line-stamp/stamp.py preview --dir work/candidates

# 工程6: 申請用zip（main.png / tab.png / 01〜24.png）
python line-stamp/stamp.py package --dir work/candidates --list "cand_03,cand_11,..."

# 規格チェック（リジェクト時の原因調査もこれ）
python line-stamp/stamp.py validate submit/stamps.zip
```

## 対応方針

- ユーザーが動画ファイルを渡してきたら convert → preview まで進めて、
  確認ページのパスを伝えて選定を依頼する。
- 選定結果（順番付きリスト）を受け取ったら package を実行し、
  規格チェックの結果と zip のパスを報告する。
- 「リジェクトされた」と言われたら validate で原因を特定し、
  convert のかけ直し（穴修復は自動）か該当オプションの調整で修正する。
- 並び順の相談を受けたら: 1個目はセットの顔 / 前半に高頻度の動き（挨拶・OK・ありがとう系）/
  似た絵柄・動きを隣接させない、の3原則で提案する。
- 規格値（320×270 / 5〜20フレーム / 1〜4秒ぴったり / 300KB / 8・16・24個）は
  stamp.py が自動適合とチェックを行うので、手計算で加工しない。
