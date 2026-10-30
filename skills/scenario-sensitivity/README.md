# scenario-sensitivity

## 概要

business-case-model と同じ入力（`model/inputs.csv` と `05-initiatives.csv`）と、変数ごとの幅（`model/sensitivity-ranges.csv`）を渡すと、ベース・上振れ・下振れのシナリオ表と、FY2030 の売上と ROIC のトルネード表が返る。幅は変数ごとに根拠を持ち、出典タグが付く。すべての変数を同じ ±10% で振ることはしない。計算はスクリプト `scripts/sensitivity.py` が行い、`model/sensitivity.md` を書く。

## 利用メリット

- どの前提が答えを一番動かすかが、根拠つきで一枚に並ぶ。
- 「下振れたらいくら？」に、どの変数をどこまで動かした値かを添えて答えられる。
- トルネードの上位が、そのまま KPI ロードマップのゲートの指標の候補になる。
- 上振れ・下振れの値が台帳に載るので、ストーリーで ID 付きで使える。

## 利用シーン

- ベースケースのモデルが出たあと
- 「この計画、どこが一番危ない？」と聞かれたとき
- ゲートと撤退基準を決める前（kpi-roadmap の前）

依頼の例: 「感応度見て」「上振れ下振れのシナリオ作って」「どの前提が一番効く？」「トルネード出して」「M&A がなかったら？」

## 使い方

**いつ使うか:** お題A では 8 段目（KPI とモデル）。前は business-case-model、後は kpi-roadmap。

1. `templates/sensitivity-ranges.csv` を `cases/<案件>/model/sensitivity-ranges.csv` に写す。変数ごとに、下振れと上振れの値と根拠を書く。値は差ではなく、入力と同じ単位の値（5% なら 5.0）で書く。
2. 幅とシナリオに入れる変数を、レビュー役と決める（下の「人が決めること」）。
3. スクリプトを回す。確度の除外はベースケースと同じにする。

   ```bash
   python3 skills/scenario-sensitivity/scripts/sensitivity.py --case cases/hokushin --target-id T-001
   ```

4. トルネードの上位 2〜3 個を読み、先に確かめる前提として書き出す。
5. 数字に納得したら、台帳に書く。

   ```bash
   python3 skills/scenario-sensitivity/scripts/sensitivity.py --case cases/hokushin --target-id T-001 --ledger-write
   ```

6. `templates/scenarios.md` を `model/scenarios.md` に写し、一言の結論と前提を書く。

### 特別な変数

| key | 意味 |
|-----|------|
| `ramp_delay` | 施策売上の立ち上がりを何年ずらすか。投資は計画どおり出る |
| `init_scale` | 施策売上の実現率（1.0 が計画どおり）。投資は出る |
| `init_go:I-xxx` | 施策を実行するか（売上と投資の両方に掛かる。M&A 不成立なら 0） |

`:I-xxx` を付けると、その施策だけを動かす。

### 幅の根拠の例

| 変数 | 根拠 |
|------|------|
| 市場成長 | 業界見通しと、その改定の履歴。下方修正が続いていれば下側を厚くとる |
| 施策の実現率 | シェア獲得のベースレート（平均で年 0.8pt 前後）と、自社の中計の達成の実績 |
| 立ち上がり | 自社の過去の遅れ。前倒しの根拠がなければ上側は 0 年 |
| 利益率 | 自社の過去と、定義をそろえた競合の利益率 |
| M&A | 過去の見送りと、価格規律の発言 |

## 人が決めること

- 変数ごとの幅（下振れと上振れの値）と、シナリオに入れる変数
- 下振れが目標に大きく届かない、財務規律を超える、というときに、どちらのレーン（中計に則る / 中計の外側）を前に出すか

スクリプトは幅を決めない。決めたことは `decisions.md` に `D-` で残す。

## よく外す点

- すべての変数を同じ幅で振る。±10% を一律に掛けると、どのリスクが本物か分からない。スクリプトは、3 つ以上の変数が同じ相対幅のとき止まる。
- 幅に根拠と出典タグがない。
- 上振れ・下振れを、確率の区間のように説明する。実際は、シナリオに入れた変数を同時に動かした値である。
- 下振れを見て、幅を狭めて見栄えをよくする。

詳しくは [references/pitfalls.md](references/pitfalls.md)。

## 具体例

| 指標 | ベース | 下振れ |
|---|---:|---:|
| 連結売上高（FY2030） | 3,809.2 億円 [F-468] | 3,177.8 億円 [F-485] |
| 目標との差 | 1,190.8 億円 [F-491] 不足 | 1,822.2 億円 [F-493] 不足 |

売上を最も動かすのは施策売上の実現率と I-006 の買収の実行で、これをゲートの指標にした。全体は [cases/hokushin/model/scenarios.md](../../cases/hokushin/model/scenarios.md)。

## 先輩が聞くとよい問い

[references/questions.md](references/questions.md) に 5 問ある。例: 「市場成長の下振れの値は、どの資料のどの数字から決めた？」

## 構成

```text
scenario-sensitivity/
├── SKILL.md
├── README.md
├── references/
│   ├── intake.md
│   ├── method.md
│   ├── pitfalls.md
│   ├── questions.md
│   ├── eval-scenarios.md
│   └── eval-rubric.md
├── templates/
│   ├── sensitivity-ranges.csv   # model/sensitivity-ranges.csv の型
│   └── scenarios.md             # model/scenarios.md の型
└── scripts/
    └── sensitivity.py           # シナリオとトルネード（モデルの計算は business-case-model の写し）
```
