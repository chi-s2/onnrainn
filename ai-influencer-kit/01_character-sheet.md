# キャラクターシート【確定版】— ふうか

> これは「設計図」です。全ての画像・動画はこの仕様に**厳密に**従って生成します。
> 目的は「1枚の完璧な写真」ではなく「100枚の一貫した写真」。

## 基本プロフィール（確定）

| 項目 | 設定 |
|------|------|
| 名前 | **ふうか**（ひらがな表記で統一。「風花」の連想＝長野の冬・透明感） |
| 年齢 | **26歳** |
| 職業設定 | 長野の会社で働く事務職。一人暮らし5年目 |
| 住まい設定 | **長野市**（善光寺の近くの古いアパート、山が見える窓） |
| 一言キャッチ | 「山の見える街で、朝弱いなりの"ちょっと丁寧な暮らし"」 |
| アカウント名案 | `fuuka_kurashi` / `fuuka.nagano` / `fuuka_asayowai` |

## なぜこの組み合わせが強いか
- **長野×等身大**：東京系ライフスタイル垢との差別化が一発で決まる。山・空気・季節の移ろいという"無料の絶景素材"が背景になる
- **26歳・一人暮らし5年目**：暮らしの完成度に説得力が出る年次。「丁寧な暮らし」に憧れる20代前半と、共感する20代後半の両方を取れる
- **ふうか（風花）**：長野の冬の風物詩「風花（かざはな）」と重なり、名前自体が世界観の一部になる

## 外見の固定仕様（Face Anchor）

顔がブレると信頼が崩れます。以下を**毎回同じ値**で固定してください。

- **顔立ち**：ナチュラルで親しみやすい日本人女性。派手すぎない、隣にいそうな可愛さ。26歳らしい落ち着き
- **髪**：肩下5cmのゆるふわセミロング／暗めのミルクティーブラウン／**右6:左4の分け目**
- **瞳**：ダークブラウン、少しだけ丸め
- **肌**：血色感のあるナチュラルメイク、チークは控えめ
- **体型**：中肉・平均身長158cm設定、健康的
- **🔑 唯一無二のディテール（必ず固定）**：**左の口元下に小さなほくろ1つ**
  - ↑ これが「ふうか」を"どこかで見た誰か"ではなく"このキャラ"にする決め手

## スタイル / 世界観（長野仕様）

- **ファッション**：古着MIXのカジュアル、ベージュ〜アイボリー〜くすみカラー。冬はニット・マフラーの比重高め（長野は寒い＝冬服が映える）
- **小物**：フィルムカメラ、トートバッグ、ラテ、湯たんぽ・ブランケット（冬の暮らし感）
- **撮影トーン**：自然光、ややアンバー寄り、フィルム風の粒状感。冬は青白い朝の光も◎
- **背景ロケ地**：
  - 部屋（山が見える窓、古いアパートの温かみ）
  - 善光寺の参道・仲見世の喫茶店
  - 松本の中町通り・古着屋
  - りんご畑の道、千曲川の土手、雪の日の路地
  - ローカルなパン屋・自家焙煎コーヒー店

## 画像生成プロンプト（テンプレ・確定版）

生成AI（Flux / GPT Image / Ideogram など）に貼るベースプロンプト。
`[シーン]` だけ差し替えて量産します。

```
A natural-looking 26-year-old Japanese woman, friendly approachable face,
milk-tea brown wavy semi-long hair with a 6:4 right side part,
dark brown slightly round eyes, natural blush light makeup,
small mole below the left corner of her mouth,   ← 固定ディテール
wearing casual vintage-mix outfit in beige/ivory tones with a cozy knit,
[シーン: in her small apartment room with mountains visible through the window, morning light],
soft natural light, warm amber tone, subtle film grain,
candid lifestyle photo, shot on 35mm film, photorealistic, 4k,
Nagano Japan countryside city atmosphere
```

### シーン差し替え例（長野ロケ）
- `walking on the approach to Zenkoji temple holding takeaway coffee, early morning`
- `in a retro kissaten (Japanese cafe) near the temple, reading`
- `browsing a vintage clothing shop in Matsumoto Nakamachi street`
- `on a riverside path with apple orchards, autumn afternoon`
- `wrapped in a blanket by the window, snowy morning, holding a mug`
- `still sleepy in bed, morning light through curtains, messy hair`（朝弱い民シリーズ用）

## 看板シリーズ（毎回擦る2本柱）

1. **「今日の小さな幸せ」** — 日常の1コマ切り取り。万能型・コメント誘発
2. **「朝弱い民の暮らし」** — 弱み共感型。GRWM・リアル朝ルーティン

→ 具体的な投稿ネタは `07_content-ideas.md` 参照

## 一貫性チェックリスト（生成のたびに確認）

- [ ] 分け目は右6:左4になっているか
- [ ] 左口元下のほくろが**ある**か（消えていないか）
- [ ] 髪色がミルクティーブラウンのままか
- [ ] トーンがアンバー＋フィルム粒状か
- [ ] 26歳らしい落ち着きがあるか（幼くなりすぎていないか）
- [ ] 背景が「長野の空気」か（都会的すぎないか）
- [ ] 顔が別人になっていないか（face drift チェック）

> ズレた生成物は**捨てる**。妥協して投稿すると一貫性が崩れます。
