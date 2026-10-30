# Prhythm for Consulting

**抽象的な依頼を、ジュニアでも組み立てられ、自分の言葉で説明できるビジネスケースへ。**
[Agent Skills](https://agentskills.io) オープンスタンダード準拠。

```bash
gh skill install shunsaku-studio/prhythm-consulting --all
```

📚 **[ドキュメントサイト](https://shunsaku-studio.github.io/prhythm-consulting/)** — スキル一覧、ワークフロー、見本案件

> プロトタイプ（v0.1）。お題A（売上成長）を最後まで通した段階。会社・人物・数値の見本はすべて架空。

---

## What — 何か

顧客の抽象的な依頼（「売上を 2,000 億円から 5,000 億円にしたい」など）を、目標・論点・事実・ギャップ・打ち手・資本・KPI の順に一段ずつ具体化するスキル集と、その成果物をジュニアが自分の言葉で説明できるかを先輩が確かめる「先輩質問タイム」という運用でできている。

- **スキル**は作業を速く、数字を正確にするために使う。数字はすべて出典タグ付きの台帳（`facts/facts.csv`）に載せ、計算はスクリプトに任せる
- **理解の確認**はスキルの中に置かない。質問タイムを通っていない成果物はマネージャーのレビューに出さない、という人と人の約束にする

## Why — なぜ作るのか

抽象的な依頼を受けたジュニアがつまずく場所は、だいたい決まっている。多くは型と手順を知らないことから起きるので、道具で手当てできる。

| 詰まる場所 | 手当て |
|-----------|--------|
| 何を問われているか分からない | 依頼を目標仕様に翻訳する [target-math](skills/target-math/)、[midterm-plan-reader](skills/midterm-plan-reader/) を最初に置く |
| 数字に根拠がない | 出典タグを必須にし、計算はスクリプトに任せ、[number-audit](skills/number-audit/) で突き合わせる |
| 顧客の文脈を踏まえない | 中計と経営者の言葉を起点にする（[midterm-plan-reader](skills/midterm-plan-reader/)、[leadership-lens](skills/leadership-lens/)） |
| 資本の制約を見ない | [capital-capacity](skills/capital-capacity/) で、打ち手の投資総額と調達余力を突き合わせる |
| 枠を埋めて終わる / AI が作ったものを説明できない | 先輩質問タイムで「だから何が言えるか」「この数字はどこから来たか」を口頭で問う |

成果物が AI で作れるほど、作った本人が中身を理解しているかを確かめる仕組みの価値は上がる。

## Who — 誰のためか

入社 1〜3 年目のアナリストとコンサルタント。質問タイムの質問役として、2〜5 年目の先輩とマネージャー。

## How — はしごを一段ずつ下りる

```mermaid
flowchart LR
  T["目標 T"] --> Q["論点・仮説 Q/A"] --> F["事実 F"] --> G["ギャップ S/G"] --> O["打ち手 O/I"] --> C["資本 C"] --> K["KPI とゲート K"] --> D["意思決定 D"] --> S["ストーリー"]
```

段と段の間には人が判断するゲートがあり、主要なゲートの前に先輩質問タイムを置く。依頼の種類ごとの経路は [workflows/](workflows/) に、お題A を最後まで通した成果物は [cases/hokushin/](cases/hokushin/) にある。

### スキル

| 作業の型 | スキル |
|---------|--------|
| 調べる | [company-financials](skills/company-financials/)、[midterm-plan-reader](skills/midterm-plan-reader/)、[leadership-lens](skills/leadership-lens/) |
| 分ける | [issue-tree](skills/issue-tree/)、[workplan](skills/workplan/)、[kpi-tree](skills/kpi-tree/) |
| 読み解く | [financial-analysis](skills/financial-analysis/)、[growth-decomposition](skills/growth-decomposition/)、[competitor-benchmark](skills/competitor-benchmark/) |
| 見積もる | [target-math](skills/target-math/)、[market-sizing](skills/market-sizing/)、[gap-bridge](skills/gap-bridge/)、[initiative-sizing](skills/initiative-sizing/)、[capital-capacity](skills/capital-capacity/)、[business-case-model](skills/business-case-model/)、[scenario-sensitivity](skills/scenario-sensitivity/) |
| 判断材料にする | [option-longlist](skills/option-longlist/)、[option-evaluation](skills/option-evaluation/) |
| 計画にする | [kpi-roadmap](skills/kpi-roadmap/) |
| 伝える | [storyline](skills/storyline/) |
| 点検する | [number-audit](skills/number-audit/) |

## リポジトリの構成

```
skills/          # スキル本体（SKILL.md は英語、README.md は日本語）
workflows/       # お題ごとのワークフロー
cases/hokushin/  # 見本案件（お題A、架空）
docs-site/       # ドキュメントサイト（VitePress。ページは skills/ などから生成）
CONVENTIONS.md   # 台帳、ID、出典タグ、フォルダ構成の決まり
```

ドキュメントサイトをローカルで見る:

```bash
npm run docs:dev
```

スクリプトは Python 3.10 以上の標準ライブラリだけで動く。
