# 共通の決まり（Phase 0）

すべてのスキルと案件フォルダが従う決まり。スキルを作る人と、成果物を読む人の両方に向けて書く。

## 1. 共通の出力（設計原則1）

どのスキルも、次の 3 点だけを必ず返す。「示唆」「次の問い」の欄は設けない（示唆は先輩質問タイムで人が問う）。

1. **本体** — 表や図。スキルごとの templates/ の型に従う
2. **ファクト** — 本体に出てくる数字はすべて ID 付きで `facts/facts.csv` に登録する
3. **前提と未確認事項** — 置いた前提、確かめられなかったこと、— で残した値

## 2. ファクト台帳 `facts/facts.csv`

案件のすべての数字は、この台帳に 1 行ずつ登録する。ほかの成果物は値を書くときに必ず ID を添える。

```csv
id,value,unit,definition,period,source_tag,source,retrieved_at,confidentiality,replace_by
F-012,200000,百万円,連結売上高（架空の北辰工業）,FY2025,公開,有価証券報告書 FY2025 p.45,2026-10-20,公開,
F-031,5.0,%,対象市場の年成長率,FY2025-FY2030,仮置き,—,2026-10-22,公開,2026-11-05
```

| 列 | 内容 |
|----|------|
| `id` | 接頭辞 + 3 桁以上の連番（下表）。一度振った ID は使い回さない |
| `value` | 数値。分からない値は `—`（エムダッシュ）のまま残す |
| `unit` | `百万円` `億円` `%` `pt` `倍` `年` `人` など |
| `definition` | 何の数字か。連結/単体、オーガニック/M&A込み など定義の違いが分かるように書く |
| `period` | `FY2025`、`FY2025-FY2030` など |
| `source_tag` | `公開` / `クライアント提供` / `推定` / `仮置き` の 4 種のみ |
| `source` | 公開・クライアント提供は資料名とページ。推定は計算式と入力 ID（例: `F-012 × (1+F-031)^5`）。仮置きは `—` |
| `retrieved_at` | 取得・作成日 `YYYY-MM-DD` |
| `confidentiality` | `公開` / `社外秘`。クライアント提供の値は `社外秘` |
| `replace_by` | 仮置きのときだけ必須。差し替え期限 `YYYY-MM-DD` |

### ID の接頭辞（企画書 5 章のはしご）

| 接頭辞 | 段 | 例 |
|--------|----|----|
| `T-` | 目標仕様 | T-001 売上目標 5000 億円 |
| `Q-` / `A-` | 論点 / 仮説 | Q-003, A-003 |
| `F-` | ファクト（公開・提供・推定・仮置きすべて） | F-012 |
| `S-` | 成り行き（status quo） | S-001 FY2030 成り行き売上 |
| `G-` | ギャップ | G-002 自動車部品のギャップ |
| `O-` | 打ち手候補 | O-007 |
| `I-` | 施策カード（見積もり済みの打ち手） | I-003 |
| `C-` | 資本（投資額・調達余力） | C-004 |
| `K-` | KPI | K-010 |
| `D-` | 意思決定 | D-002 |

数字は台帳では `F-` に限らない。S・G・I・C・K の数字も、その ID で台帳に登録する（`source_tag` は多くの場合 `推定`、`source` に計算式）。

### 出典タグの使い分け（設計原則4）

| タグ | 使う場面 | 必須の情報 |
|------|---------|-----------|
| 公開 | 有報・短信・中計・統計など公開情報から取った値 | 資料名とページ |
| クライアント提供 | 社内資料から取った値（インサイドアウト） | 資料名、`confidentiality=社外秘` |
| 推定 | 根拠と計算式が示せる値 | 計算式と入力 ID |
| 仮置き | 議論のために置いた根拠のない値 | `replace_by`（差し替え期限） |

もっともらしい推定で埋めるより、`—` で残すことを優先する。

## 3. 形式ごとの ID の持たせ方

| 形式 | 書き方 |
|------|--------|
| Markdown | 数字の直後に `[F-012]`。例: `連結売上 2,000 億円 [F-012]` |
| CSV（中間データ） | `id` 列を持たせる。値の列と台帳が一致すること |
| Excel / モデル | `inputs` シートに `id,label,value,unit,source_tag` の列。計算シートは inputs のセルだけを参照し、数値を直打ちしない |
| スライド | 各ページの注記に ID と出典を並べる（スライドは本リポジトリの対象外。ID を落とさずに渡す） |

`[F-012]` のように角括弧で囲んだ ID だけが number-audit の点検対象になる。本文で ID に言及するだけなら括弧を付けない。

Q・A・O・D は数字を持たないので台帳に載せない。本文では括弧なしで書くのが基本である。角括弧で囲んでもよいが、そのときは number-audit が案件内の Markdown にその ID の定義の行（見出し、表の先頭のセル、箇条書きの先頭。例: `decisions.md` の `## D-003`、`04-options.md` の表の `| O-007 |`）を探し、なければエラーにする。`01-issue-tree.md` の A- は表の 4 列目にあり定義の行にならないので、角括弧で囲まない。

## 4. 計算は会話の中でしない（設計原則3）

年率換算、ブリッジ、感応度、資本の対照は、各スキルの `scripts/` の Python スクリプトで計算する。

- Python 3.10 以上、**標準ライブラリだけ**で動かす
- 入力は facts.csv（または CSV/JSON）、出力は Markdown 表と、台帳に追記する行（CSV）
- 実行例を SKILL.md に書く

## 5. 案件フォルダ

```
case/
├── 00-target-spec.md        # T：目標仕様
├── 01-issue-tree.md         # Q・A：論点と仮説
├── 02-workplan.md
├── facts/
│   ├── facts.csv            # F：全ファクトの台帳
│   ├── financials.csv       # company-financials の出力（縦持ち。列は 9 節）
│   ├── midterm-plan.md
│   ├── financials.md        # company-financials の読み取りメモ（不連続の一覧）
│   ├── financial-analysis.md
│   ├── growth-decomposition.md
│   ├── competitor-benchmark.md
│   ├── midterm-plan.md / midterm-plan.csv
│   ├── leadership.md
│   └── market-sizing.md
├── client/                  # インサイドアウトの社内データ。公開データと分ける
├── 03-gap-bridge.md         # S・G
├── 04-options.md            # O（末尾に option-evaluation の評価マトリクス）
├── 05-initiative-inputs.csv # initiative-sizing の入力（ID で参照）
├── 05-initiatives.md / .csv # I
├── 06-capital-inputs.csv    # capital-capacity の入力（ID で参照）
├── 06-capital.md            # C
├── 07-kpi-tree.md           # K
├── model/                   # business-case-model の出力
├── 08-kpi-roadmap.md
├── decisions.md             # D：意思決定ログ
├── reviews/question-time.md # 先輩質問タイムの記録
└── deliverables/storyline.md
```

## 6. スキル 1 本の構成

```
<skill>/
├── SKILL.md            # エージェント向け（英語）。500 行以内
├── README.md           # 人向けの日本語ガイド。ドキュメントサイトの正本
├── references/
│   ├── intake.md       # 何を聞いてから始めるか
│   ├── method.md       # 手順と、なぜその順か
│   ├── pitfalls.md     # よく外す点と、良い例・悪い例
│   ├── questions.md    # 先輩向けの問いの種（3〜5 問）
│   ├── eval-scenarios.md
│   └── eval-rubric.md
├── templates/          # 出力の型（Markdown）
└── scripts/            # 計算が必要なスキルのみ
```

**仮の型**（`maturity: provisional`）は SKILL.md、README.md、`references/pitfalls.md`、`references/questions.md`、`templates/` の 1 枚だけを置く。残りは汎用の LLM と手作業で埋める。計算が要る仮の型は、設計原則3に従って `scripts/` も置く。

### SKILL.md の frontmatter

```yaml
---
name: target-math
description: >-
  英語の説明。最後にジュニアが実際に受け取る依頼の言い方を日本語で並べる
  （「5000億って年何%？」「目標の難易度見て」など）。
disable-model-invocation: false
verb: estimate          # 作業の型
categories:             # 領域
  - finance
autonomy: solo          # 単独度
maturity: formal        # formal（正式）/ provisional（仮の型）
workflows:              # 使うお題
  - A
  - B
  - D
---
```

| キー | 値 |
|------|----|
| `verb` | `investigate` 調べる / `split` 分ける / `interpret` 読み解く / `estimate` 見積もる / `decide` 判断材料にする / `plan` 計画にする / `communicate` 伝える / `audit` 点検する |
| `categories` | `business` ビジネス / `finance` 財務 / `delivery` 実行計画 |
| `autonomy` | `solo` ◎ ひとりで完結 / `review` ○ 結果をレビューに出す前提 / `together` △ 上位者と一緒に決める |
| `maturity` | `formal` 正式 / `provisional` 仮の型 |
| `workflows` | `A` 売上成長 / `B` 資本効率 / `C` 新規参入 / `D` M&A とポートフォリオ |

### README.md の型

```markdown
# <skill-name>

## 概要
（1 段落。何を渡すと何が返るか）

## 利用メリット
## 利用シーン
依頼の例: 「…」「…」
## 使い方
**いつ使うか:** …（前後のスキル）
1. …
## 人が決めること
（ゲート。スキルが決めないこと）
## よく外す点
## 具体例
（お題A 北辰工業の出力の抜粋。cases/hokushin/ へのリンク）
## 先輩が聞くとよい問い
```

## 7. 人が決める場所（設計原則5）

目標の解釈、検証する仮説の優先順位、追う打ち手、確度の置き方、どちらのレーンを前に出すか、撤退基準は人が決める。スキルは比較表と論点を揃えたところで **停止してユーザーに判断を求め**、決定は `decisions.md` に `D-` の ID で残す。

```markdown
## D-001 目標の解釈（2026-10-31）
- 決めたこと: 連結売上 5000 億円、FY2030、M&A 込み
- 比べた案: 5 年 / 7 年 / 10 年、オーガニックのみ / M&A 込み
- 決めた人: マネージャー（質問タイム① 通過後）
- 根拠: [T-001] [T-004] [F-120]
```

## 8. 学習の仕組みはスキルに入れない（設計原則7）

スキルに理解度クイズや自己レビューの強制を入れない。先輩向けの問いの種は `references/questions.md` に置くだけで、スキルの手順からは呼ばない。

## 9. スキル間で受け渡す主なファイル

成果物が次のスキルの入力になるよう、受け渡すファイルの形を決めておく。

| ファイル | 作るスキル | 読むスキル | 形 |
|----------|-----------|-----------|----|
| `facts/facts.csv` | すべて | すべて | 2 節 |
| `facts/financials.csv` | company-financials | financial-analysis, growth-decomposition, capital-capacity, business-case-model | `id,fiscal_year,item,segment,value,unit,basis,source,note`。縦持ち。`segment` は `連結` かセグメント名。各行は同じ `id` で台帳にも載せる |
| `00-target-spec.md` | target-math | 以降すべて | 目標値、期限、定義、資本効率の目標、必要年率、ベースレートとの照合 |
| `03-gap-bridge.md` | gap-bridge | option-longlist, initiative-sizing, storyline | セグメント別の成り行き（S）とギャップ（G） |
| `05-initiatives.md` + `05-initiatives.csv` | initiative-sizing | capital-capacity, business-case-model, kpi-tree | 施策ごとの年次売上、投資、確度。CSV は `id,initiative,year,revenue,investment,unit,confidence` |
| `06-capital.md` | capital-capacity | business-case-model, storyline | 投資総額と調達余力の対照（C） |
| `model/` | business-case-model | scenario-sensitivity, kpi-roadmap | `inputs.csv`（`id,label,value,unit,source_tag`）、計算結果の CSV、数式入りの `business-case.xlsx` |

スクリプトが台帳に行を足すときは、接頭辞ごとに使われていない最小の番号から振る。どのスクリプトの出力でもない数字（開示された WACC、工業会の市場規模、議論のための仮置きなど）は、`skills/number-audit/scripts/add_fact.py` で台帳に足す。CSV を手で編集しない。

### 共通の定義

| 用語 | 定義 |
|------|------|
| 投下資本（ROIC の分母） | 純資産 + 有利子負債 − 現金及び預金（ネット）。余剰現金だけを引く定義を使うときは、その旨と必要現金の置き方を前提に書く |
| NOPAT | 営業利益 ×（1 − 実効税率）。実効税率は既定で 30%（仮置き） |
| 年度 | `FY2025` の形。会社の決算期に合わせ、暦年と混ぜない |
