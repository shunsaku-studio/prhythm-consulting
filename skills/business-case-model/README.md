# business-case-model

## 概要

ドライバー（`model/inputs.csv`）と施策（`05-initiatives.csv`）を渡すと、FY2025 実績から FY2030 までの年次モデルが返る。中身は売上（成り行きと施策）、営業利益と利益率、減価償却、投資、運転資本、税、NOPAT、FCF、投下資本、ROIC と WACC の差、ROE の近似、現預金とネット D/E である。計算はスクリプト `scripts/build_model.py` が行い、`model/model.csv` と、数式入りの `model/business-case.xlsx` を書く。xlsx の calc シートは inputs シートのセルを参照する数式だけでできていて、数値の直打ちがない。

## 利用メリット

- 施策を全部載せたとき、売上だけでなく、現預金と ROIC がどうなるかが一枚で見える。
- 入力と計算が分かれているので、仮置きを差し替えたら回し直すだけでよい。
- xlsx の数字はすべて inputs シートの ID までたどれる。マネージャーが Excel で開いて確かめられる。
- 主要な結果は台帳に `推定` で載り、計算式として入力の ID が残る。

## 利用シーン

- 施策の見積もり（initiative-sizing）と資本の対照（capital-capacity）が出たあと
- 「施策を載せると ROIC はどうなる？」と聞かれたとき
- シナリオと感応度（scenario-sensitivity）、KPI ロードマップ（kpi-roadmap）の前

依頼の例: 「モデル組んで」「PL と CF を 5 年分回して」「ROIC どうなる？」「施策を全部載せると数字どうなる？」「Excel のモデルにして」

## 使い方

**いつ使うか:** お題A では 8 段目（KPI とモデル）。前は initiative-sizing と capital-capacity、後は scenario-sensitivity と kpi-roadmap。

1. `templates/inputs.csv` を `cases/<案件>/model/inputs.csv` に写す。各行に台帳の ID を入れ、値を台帳と同じにする。分からない値は先に台帳へ `仮置き`（差し替え期限つき）で載せる。
2. どの確度の施策をベースケースに入れるかを、マネージャーと決める（下の「人が決めること」）。
3. 台帳に書かずに回して、表と旗を読む。最初に「基準年の再現チェック」を見る。FY2025 の純利益と ROE が開示とずれていたら、税率か金利の入力を直す。

   ```bash
   python3 skills/business-case-model/scripts/build_model.py --case cases/hokushin
   ```

4. xlsx を点検する。LibreOffice があれば `--soffice` で再計算まで確かめる。

   ```bash
   python3 skills/business-case-model/scripts/check_xlsx.py --case cases/hokushin --soffice
   ```

5. 数字に納得したら、台帳に書く。同じ定義と期間の行は同じ ID のまま更新される。

   ```bash
   python3 skills/business-case-model/scripts/build_model.py --case cases/hokushin --ledger-write
   ```

6. `templates/model-summary.md` を `model/model-summary.md` に写し、表と旗と前提を埋める。
7. number-audit を回してから上に出す。

### モデルの中身（要点）

| 項目 | 計算 |
|------|------|
| 成り行き売上 | 前年 ×（1 + 成り行き成長率） |
| 営業利益 | 成り行き売上 × 成り行きの利益率 ＋ 施策売上 × 施策の利益率 |
| 減価償却 | 成り行き売上 × 償却率 ＋ 前年までの施策投資 ÷ 償却年数 |
| 投資 | 成り行き売上 × 維持更新投資率 ＋ その年の施策投資 |
| FCF | NOPAT ＋ 減価償却 − 投資 − 運転資本の増加 |
| 投下資本 | 前年 ＋ 投資 − 減価償却 ＋ 運転資本の増加（FY2025 は 純資産 ＋ 有利子負債 − 現預金） |
| 現預金 | 前年 ＋ FCF − 税引後の利息 − 配当。借入は一定に置くので、マイナスが資金の不足分になる |

## 人が決めること

- どの確度の施策をベースケースに入れるか（例: 確度「低」を除く）
- 成り行き事業の利益率を据え置くか、改善を見込むか
- 現預金がマイナスになる、ネット D/E が財務規律を超える、ROIC が WACC を下回る、という旗が立ったとき、資本の段や打ち手の段に戻るかどうか

スクリプトは旗を立てるだけで、モデルの中で数字を合わせにいかない。決めたことは `decisions.md` に `D-` で残す。

## よく外す点

- 数値を直打ちし、入力と計算が混ざる。xlsx を手で直して成長率をセルに打つと、仮置きを差し替えても数字が変わらない。直すのは `inputs.csv` だけにする。
- 投資を置かずに売上だけを積む。M&A は買収価格を投資に入れる。
- 施策の売上を成り行きと二重に数える。施策売上は成り行きへの上乗せ分だけを書く。
- 基準年が開示と合わないまま先へ進む。
- 現預金がマイナスなのに、そのまま「達成できる」と書く。

詳しくは [references/pitfalls.md](references/pitfalls.md)。数式の監査（直打ちの検出の先にある、書式の決まりや循環参照の点検など）は外部のモデル監査ツールに任せる。

## 具体例

<!-- EXAMPLE: お題A の実行結果で埋める -->
お題A（北辰工業）で、施策を載せた FY2030 の売上・ROIC・現預金と、`cases/hokushin/model/` の xlsx を示す。

## 先輩が聞くとよい問い

[references/questions.md](references/questions.md) に 5 問ある。例: 「現預金がマイナスになる年に、何をして資金を手当てする前提？」

## 構成

```text
business-case-model/
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
│   ├── inputs.csv          # model/inputs.csv の型
│   └── model-summary.md    # model/model-summary.md の型
└── scripts/
    ├── build_model.py      # モデルの計算、model.csv と xlsx の書き出し、台帳への登録
    └── check_xlsx.py       # xlsx の部品・直打ち・数式の再計算の点検
```
