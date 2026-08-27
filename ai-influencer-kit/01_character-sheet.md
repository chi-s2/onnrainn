# キャラクターシート（顔と世界観の固定仕様）

> これは「設計図」です。全ての画像・動画はこの仕様に**厳密に**従って生成します。
> 目的は「1枚の完璧な写真」ではなく「100枚の一貫した写真」。

## 基本プロフィール（仮案 — 書き換え可）

| 項目 | 設定 |
|------|------|
| 名前（仮） | 環／めい／あかり などから選ぶ ※ここでは仮に **「あかり」** |
| 年齢感 | 22〜24歳 |
| 職業設定 | カフェ巡りが好きな会社員／週末は古着とカメラ |
| 住まい設定 | 東京・下北沢〜中目黒あたりの雰囲気 |
| 一言キャッチ | 「等身大の"ちょっと丁寧な暮らし"」 |

## 外見の固定仕様（Face Anchor）

顔がブレると信頼が崩れます。以下を**毎回同じ値**で固定してください。

- **顔立ち**：ナチュラルで親しみやすい日本人女性。派手すぎない、隣にいそうな可愛さ
- **髪**：肩下5cmのゆるふわセミロング／暗めのミルクティーブラウン／центру分けではなく **右6:左4の分け目**
- **瞳**：ダークブラウン、少しだけ丸め
- **肌**：血色感のあるナチュラルメイク、チークは控えめ
- **体型**：中肉・平均身長158cm設定、健康的
- **🔑 唯一無二のディテール（必ず固定）**：**左の口元下に小さなほくろ1つ**
  - ↑ これが「あかり」を"どこかで見た誰か"ではなく"このキャラ"にする決め手

## スタイル / 世界観

- **ファッション**：古着MIXのカジュアル、ベージュ〜アイボリー〜くすみカラー中心
- **小物**：フィルムカメラ、トートバッグ、ラテ
- **撮影トーン**：自然光、ややアンバー寄り、フィルム風の粒状感
- **背景**：カフェ、路面店、公園、部屋（生活感を残す）

## 画像生成プロンプト（テンプレ）

生成AI（Flux / GPT Image / Ideogram など）に貼るベースプロンプト。
`[シーン]` だけ差し替えて量産します。

```
A natural-looking 23-year-old Japanese woman, friendly approachable face,
milk-tea brown wavy semi-long hair with a 6:4 right side part,
dark brown slightly round eyes, natural blush light makeup,
small mole below the left corner of her mouth,   ← 固定ディテール
wearing casual vintage-mix beige/ivory outfit,
[シーン: sitting in a cozy Tokyo cafe holding a latte],
soft natural window light, warm amber tone, subtle film grain,
candid lifestyle photo, shot on 35mm film, photorealistic, 4k
```

### シーン差し替え例
- `walking in Shimokitazawa street with a film camera`
- `at home by the window reading, morning light`
- `trying on clothes in a vintage shop, mirror selfie`
- `park bench in autumn, holding takeaway coffee`

## 一貫性チェックリスト（生成のたびに確認）

- [ ] 分け目は右6:左4になっているか
- [ ] 左口元下のほくろが**ある**か（消えていないか）
- [ ] 髪色がミルクティーブラウンのままか
- [ ] トーンがアンバー＋フィルム粒状か
- [ ] 顔が別人になっていないか（face drift チェック）

> ズレた生成物は**捨てる**。妥協して投稿すると一貫性が崩れます。
