# キャラクターシート【確定版】— ふうか

> これは「設計図」です。全ての画像・動画はこの仕様に**厳密に**従って生成します。
> 目的は「1枚の完璧な写真」ではなく「100枚の一貫した写真」。

## 基本プロフィール（確定）

| 項目 | 設定 |
|------|------|
| 名前 | **ふうか**（ひらがな表記で統一。「風花」の連想＝信州の冬・透明感） |
| 年齢 | **26歳** |
| 職業設定 | 諏訪の会社で働く事務職。一人暮らし5年目 |
| 住まい設定 | **諏訪市**（上諏訪の古いアパート、窓から諏訪湖がちらっと見える） |
| 一言キャッチ | 「湖のある街で、朝弱いなりの"ちょっと丁寧な暮らし"」 |
| アカウント名案 | `fuuka_kurashi` / `fuuka.suwa` / `fuuka_asayowai` |

## なぜこの組み合わせが強いか
- **諏訪×等身大**：東京系ライフスタイル垢との差別化が一発で決まる。諏訪湖・朝もや・御神渡り・温泉街という"無料の絶景素材"が背景になる。長野市より地名の解像度が高く「その街に住んでる感」が強い
- **26歳・一人暮らし5年目**：暮らしの完成度に説得力が出る年次。「丁寧な暮らし」に憧れる20代前半と、共感する20代後半の両方を取れる
- **ふうか（風花）**：信州の冬の風物詩「風花（かざはな）」と重なり、名前自体が世界観の一部になる

## 外見の固定仕様（Face Anchor）

顔がブレると信頼が崩れます。以下を**毎回同じ値**で固定してください。

- **顔立ち**：ナチュラルで親しみやすい日本人女性。派手すぎない、隣にいそうな可愛さ。26歳らしい落ち着き
- **髪**：肩下5cmのゆるふわセミロング／暗めのミルクティーブラウン／**右6:左4の分け目**
- **瞳**：ダークブラウン、少しだけ丸め
- **肌**：血色感のあるナチュラルメイク、チークは控えめ
- **体型**：中肉・平均身長158cm設定、健康的
- **🔑 唯一無二のディテール（必ず固定）**：**左の口元下に小さなほくろ1つ**
  - ↑ これが「ふうか」を"どこかで見た誰か"ではなく"このキャラ"にする決め手

## スタイル / 世界観（諏訪仕様）

- **ファッション**：古着MIXのカジュアル、ベージュ〜アイボリー〜くすみカラー。冬はニット・マフラーの比重高め（諏訪の冬は氷点下10度＝冬服が映える）
- **小物**：フィルムカメラ、トートバッグ、ラテ、湯たんぽ・ブランケット（冬の暮らし感）
- **撮影トーン**：自然光、ややアンバー寄り、フィルム風の粒状感。湖の朝もや・冬の青白い光も◎
- **背景ロケ地**：
  - 部屋（諏訪湖がちらっと見える窓、古いアパートの温かみ）
  - 諏訪湖畔の遊歩道（朝もや・夕暮れ・冬の御神渡り）
  - 上諏訪駅の足湯、片倉館のレトロ建築
  - 甲州街道の酒蔵通り、レトロな喫茶店
  - 諏訪大社の参道、霧ヶ峰・高ボッチ高原（週末ネタ）
  - ローカルなパン屋・自家焙煎コーヒー店
  - 松本の中町通り・古着屋（電車で30分＝古着買い出し回）

## 画像生成プロンプト（テンプレ・確定版）

生成AI（Flux / GPT Image / Ideogram など）に貼るベースプロンプト。
`[シーン]` だけ差し替えて量産します。

```
A natural-looking 26-year-old Japanese woman, friendly approachable face,
milk-tea brown wavy semi-long hair with a 6:4 right side part,
dark brown slightly round eyes, natural blush light makeup,
small mole below the left corner of her mouth,   ← 固定ディテール
wearing casual vintage-mix outfit in beige/ivory tones with a cozy knit,
[シーン: in her small apartment room with Lake Suwa glimpsed through the window, morning light],
soft natural light, warm amber tone, subtle film grain,
candid lifestyle photo, shot on 35mm film, photorealistic, 4k,
Suwa Nagano Japan lakeside onsen town atmosphere
```

### シーン差し替え例（諏訪ロケ）
- `walking along the Lake Suwa lakeside promenade with morning mist, holding takeaway coffee`
- `soaking feet in the footbath at Kamisuwa station, relaxed`
- `in a retro kissaten (Japanese cafe) in an old onsen town street, reading`
- `strolling the historic sake brewery street with old wooden buildings`
- `browsing a vintage clothing shop in Matsumoto Nakamachi street`（松本遠征回）
- `wrapped in a blanket by the window overlooking the lake, snowy morning, holding a mug`
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
- [ ] 背景が「諏訪の空気」か（湖・温泉街・山。都会的すぎないか）
- [ ] 顔が別人になっていないか（face drift チェック）

> ズレた生成物は**捨てる**。妥協して投稿すると一貫性が崩れます。

---

## 生成ログ（顔候補）

### 2026-08-29 第1回生成（Higgsfield soul_2 / 16:9 / 2K / スプリットシート構成）
確定プロンプト同一・シード違いの3候補。**採用が決まったらここに「✅採用」と記録し、そのジョブIDを以後のimage-to-video・追加生成のリファレンスに使う。**

| 候補 | seed | job_id |
|---|---|---|
| A | 852006 | `19983293-990e-4de0-939f-f983096e192d` |
| B | 161996 | `c62c424f-3f2b-49af-808d-5b7c64975a5c` |
| C | 649554 | `48bab860-6dac-4d2e-893f-466f8bc9e742` |

採用：**✅ 候補A（seed 852006 / job `19983293-990e-4de0-939f-f983096e192d`）を「正解の顔」として確定（2026-08-29）**
→ 以後の全生成（追加写真・image-to-video）はこのジョブIDをリファレンスに使うこと。

### 2026-08-29 第2回生成（候補Aをリファレンス／「可愛い」方向に調整）
変更点：目を大きめ丸め＋涙袋、輪郭を丸みのあるソフトに、シースルーバング追加、
やわらかい微笑み。ほくろ・右6:4分け・ミルクティーブラウン・古着コーデは維持。

| 候補 | seed | job_id |
|---|---|---|
| D | 816963 | `8c026c04-f6c4-4286-96ef-ce719f8a4655` |
| E | 321442 | `6f8c781b-e9dc-4928-a6f0-55d558d61c7f` |
| F | 353504 | `c38837e2-abd0-41d8-9e2c-ba913b1ac130` |

採用：見送り（比較の結果、Aを採用）
