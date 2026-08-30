---
name: line-stamp-36
description: |
  ChatGPT（GPT-Image-2）で36コマのLINEスタンプシートを作り、
  36個の個別PNG＋ZIP（背景あり／背景透過）に仕上げるスキル。

  以下のような言葉が出たら必ずこのスキルを使うこと：
  - 「LINEスタンプを作りたい」「スタンプ36個」「スタンプを量産して」
  - 「スタンプ用のプロンプトを作って」「スタンプのセリフを変えて」
  - 「スタンプシートを分割してZIPにして」「LINE申請用に整えて」

  シート画像がすでに手元にある場合の分割・透過・ZIP化にも使う。
---

# LINEスタンプ36個 自動生成

`line-stamp-36/` の資材を使う。詳しい手順は `line-stamp-36/README.md`。

## 判断フロー

```
まだ画像がない
  └─ プロンプトを渡す（下記ステップ1）→ ユーザーがChatGPTで4枚生成 → ステップ2へ
シート画像がすでにある
  └─ ステップ2（make_stamps.py）だけ実行する
```

## ステップ1：プロンプトを渡す

そのまま貼れるものが `line-stamp-36/prompts/prompt-2char.txt` にある。これを提示する。

セリフ・キャラ数を変える依頼なら、`prompts/panels.yaml`（またはビジネス版
`prompts/panels-business.yaml`）を編集してから組み立て直す。

```bash
python3 line-stamp-36/scripts/build_prompt.py --characters 1
python3 line-stamp-36/scripts/build_prompt.py --panels line-stamp-36/prompts/panels-business.yaml
```

キャラ画像2枚を添付してChatGPT（GPT-Image-2）に貼るよう伝える。3×3のシートが4枚返る。

## ステップ2：36個に切って透過してZIPにする

```bash
pip install -r line-stamp-36/requirements.txt   # 初回のみ
python3 line-stamp-36/scripts/make_stamps.py <シート画像...> -o out
```

`out/transparent/`（申請用）、`out/with_bg/`（確認用）、それぞれのZIPができる。
370×320px・main.png(240×240)・tab.png(96×74)・1MB以内まで自動で満たす。

よく使うオプション: `--select 1-32` / `--main-index N` / `--tolerance 60` / `--equal-split`

## 必ず伝えること

**LINEに申請できるスタンプ個数は 8 / 16 / 24 / 32 / 40 個。36個は申請できない。**
`--select 1-32` で32個に絞るか、コマを4つ足して40個にする必要がある。
ユーザーが36個のまま進めようとしていたら、この点を先に伝える。

## 仕上がりが悪いとき

| 症状 | 対処 |
|---|---|
| 白フチが残る | `--tolerance` を上げる（60〜80） |
| キャラの一部が透明になった | `--tolerance` を下げる（20〜30） |
| コマの切り位置がズレる | `--equal-split` を付ける |
| 文字が崩れている | そのコマだけChatGPTで「構図はそのまま文字だけ描き直して」 |
