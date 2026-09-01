# 諏訪ロケ撮影用プロンプト集（ストック量産用）

> **使い方**：各プロンプトに「正解の顔」（候補A / job `19983293-990e-4de0-939f-f983096e192d`）を
> 参照画像として添付して生成する。Higgsfield soul_2 / 9:16（TikTok縦型）。
> ChatGPT等の他ツールで生成する場合も、Aの画像を添付して同じプロンプトを使えばOK。

## 共通の識別ブロック（全プロンプトの先頭に入っている）

```
same original Japanese woman as the reference image, 26 years old,
friendly approachable face, milk-tea brown wavy semi-long hair with a relaxed
6:4 right side part, small beauty mark just below the left corner of her mouth,
natural light makeup
```

## 共通の仕上げブロック（全プロンプトの末尾）

```
candid lifestyle photo, shot on 35mm film with subtle grain, warm amber tone,
photorealistic, natural unretouched skin, no beauty filter, single subject,
no text, no watermark
```

## シーン一覧（第1弾・6シーン）

| # | シーン | 状態 |
|---|--------|------|
| 0 | 諏訪湖畔の朝もや＋テイクアウトコーヒー | ⏸ クレジット切れで未生成 |
| 1 | レトロ喫茶店で読書＋ラテ | ⏸ クレジット切れで未生成 |
| 2 | 部屋の窓辺・ブランケット＋マグ（諏訪湖ちら見え） | ⏸ クレジット切れで未生成 |
| 3 | 酒蔵通り散歩＋フィルムカメラ | ⚠️ 生成済みだが要確認（job `8b455091-d8cf-4bb3-b405-735ef89a0fc2`）|
| 4 | 上諏訪駅の足湯 | ⏸ クレジット切れで未生成 |
| 5 | 朝弱い民・ベッドで寝起き | ⏸ クレジット切れで未生成 |

### シーン0：湖畔の朝もや
```
[識別ブロック], walking along the Lake Suwa lakeside promenade in early morning
mist, holding a takeaway coffee cup, wearing an oversized ivory chunky-knit
cardigan over a cream tee and beige corduroy trousers, soft hazy morning light
over the lake, mountains faintly visible across the water, [仕上げブロック]
```

### シーン1：レトロ喫茶店
```
[識別ブロック], sitting in a retro Japanese kissaten cafe with dark wood
interior and warm pendant lights, reading a paperback with a latte on the
table, wearing a cozy ivory knit and beige corduroy trousers, soft window
light, [仕上げブロック]
```

### シーン2：部屋の窓辺
```
[識別ブロック], wrapped in a beige blanket by the window of her small old
apartment with Lake Suwa glimpsed through the window, holding a warm mug with
both hands, cozy morning light, gentle sleepy smile, [仕上げブロック]
```

### シーン3：酒蔵通り
```
[識別ブロック], strolling a historic Japanese sake brewery street with old
wooden buildings and white storehouse walls, holding a compact film camera,
wearing an oversized ivory knit cardigan and beige corduroy trousers with a
tote bag, late afternoon golden light, [仕上げブロック]
```

### シーン4：駅の足湯
```
[識別ブロック], sitting at an outdoor public footbath at a Japanese onsen town
train station, bare feet soaking in the steaming water, trousers rolled up,
relaxed happy expression, wearing a cozy ivory knit cardigan, soft evening
light with gentle steam, [仕上げブロック]
```

### シーン5：朝弱い民（すっぴん設定）
```
same original Japanese woman as the reference image, 26 years old, friendly
approachable face, milk-tea brown wavy semi-long hair slightly messy, relaxed
6:4 right side part, small beauty mark just below the left corner of her mouth,
no makeup natural bare face, still sleepy in bed under a cream duvet, morning
light through thin curtains, rubbing one eye, cozy relatable morning-hater
mood, candid lifestyle photo, shot on 35mm film with subtle grain, warm soft
tone, photorealistic, natural unretouched skin, no beauty filter, single
subject, no text, no watermark
```

## 第2弾以降のシーン候補（冬になったら）
- 雪の湖畔・白い息＋マフラー
- こたつ or ストーブ前で湯たんぽ
- 御神渡りを見に行く朝（起きられた奇跡の日）
- 片倉館のレトロ建築前
- 霧ヶ峰ドライブ（週末回）
