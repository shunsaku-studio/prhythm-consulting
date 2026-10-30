---
name: financial-analysis
description: >-
  Read facts/financials.csv and analyze profitability, efficiency and safety;
  decompose ROE (DuPont: net margin x asset turnover x leverage) and compute ROIC
  with stated definitions; split changes between two years into drivers (ROE
  contributions, segment mix vs segment margin) and compare with peers. Pushes
  every ratio change to a driver and a document that confirms it, instead of
  stopping at the ratio. Writes facts/financial-analysis.md and ledger rows.
  「この会社の財務、ざっと見て」「ROE を分解して」「ROIC 出して」
  「利益率が上がった理由は？」「同業と比べて収益性どう？」「財務分析して」
disable-model-invocation: false
verb: interpret
categories:
  - finance
autonomy: solo
maturity: formal
workflows:
  - A
  - B
  - D
---

# financial-analysis

Turn a financial time series into ratios and, more importantly, into the drivers behind their changes.
A ratio table without drivers is not a finished output of this skill.

Human guide (Japanese): [README.md](README.md)

## When to use

- Workflow A step 3 (現状と成長の内訳), after company-financials
- Workflow B (ROE 5% → 8%): the ROE decomposition is the starting point
- Workflow D: segment margins and capital before portfolio options
- Before capital-capacity (it uses net debt, FCF and ROIC from here)

Do NOT use for: building the time series (company-financials), splitting revenue growth into market / share / M&A (growth-decomposition), a full competitor table across KPIs and strategy (competitor-benchmark), valuation or investment advice.

## Intake

Details: [references/intake.md](references/intake.md).

| Input | Default | Ask when |
|-------|---------|----------|
| `facts/financials.csv` | — | Missing → run company-financials first |
| Two years to compare | first and last year | The window crosses a discontinuity listed in `facts/financials.md` (suggest a window after it) |
| Tax rate for NOPAT | 30% (仮置き) | Always say it is 仮置き; replace with the 法定実効税率 from the 有報 |
| Operating cash need (months of sales) | not used (invested capital subtracts all cash) | Only with `--cash-months` for the excess-cash variant; then say it is 仮置き |
| Balances | average of opening and closing | The client's own disclosure uses period-end (e.g. ROE in the 資本コスト disclosure) |
| Peers CSV | none | competitor data is available (`company,fiscal_year,item,value,unit,basis,source,note`) |

## Steps

Method and reasons: [references/method.md](references/method.md).

1. **Check the input.** Read `facts/financials.md` (discontinuities). Choose a comparison window that does not cross a segment reorganization or accounting change, or state that it does.
2. **Run `scripts/ratios.py`** (below). Do not compute ratios in conversation.
3. **Read the level.** Profitability (operating margin, net margin, ROE, ROA, ROIC), efficiency (asset turnover), safety (equity ratio, net debt, net D/E), CF (FCF, capex/depreciation, payout). Compare with the company's own targets and disclosed guardrails (e.g. net D/E within 0.5x, cost of equity 7.5%) with their source IDs.
4. **Decompose the change.** Use the script's ROE contribution table and the operating-margin mix/rate table. Name which factor moved most.
5. **Push to drivers.** For every factor that moved, write a driver hypothesis (price, volume, cost, FX, M&A, reorganization, one-off) and the document that would confirm it (MD&A in the 有報, 決算説明会資料). Label each as 確認済み (with source) or 未確認. Do not write a driver as fact without a source.
6. **Compare with peers** if peer data exists, only after checking definitions (IFRS 事業利益 ≠ 日本基準 営業利益; IFRS equity excludes non-controlling interests). Put definition differences in the table.
7. **Hand off.** No gate (autonomy: solo). ROIC vs WACC, net D/E headroom and FCF go to capital-capacity; segment margins go to growth-decomposition and gap-bridge.

## Output (always these three parts)

Write `facts/financial-analysis.md` using [templates/financial-analysis.md](templates/financial-analysis.md).

1. **Body** — ratio tables (script output), decomposition tables, the driver table (step 5), peer comparison with definition notes
2. **Facts** — every number the body shows carries `[F-xxx]` in the same cell. The script registers ratios as `推定` with formulas that reference the financials IDs, and tax rate / cash months as `仮置き` with `replace_by`. By default only the two comparison years are registered; use `--register all` (or a list of years) for any year you put in the body with a number
3. **前提と未確認事項** — ratio definitions (average vs period-end, 純資産 vs 株主資本), 仮置き values, unconfirmed drivers, ratios left as — (e.g. segment ROIC when segment assets are not disclosed)

No 示唆 or next-question sections.

## Script

`scripts/ratios.py` (Python 3.10+, standard library only).

```bash
python3 skills/financial-analysis/scripts/ratios.py <case>/facts/financials.csv \
  --company 北辰工業 --compare FY2021,FY2025 \
  --peers cases/hokushin/sources/competitors.csv \
  --ledger <case>/facts/facts.csv --append --out <case>/facts/financial-analysis.md
```

Definitions the script uses (state them in the output):

- ROE = net income ÷ average 純資産 (`--balance end` for period-end). DuPont = net margin × asset turnover × leverage with the same balances, so the product equals ROE
- ROIC = NOPAT ÷ average invested capital; NOPAT = operating income × (1 − tax rate); invested capital = 純資産 + interest-bearing debt − 現金及び預金 (CONVENTIONS 共通の定義, the same as capital-capacity and business-case-model). `--cash-months N` switches to the excess-cash variant (subtract only cash above N months of sales, 仮置き); say so in 前提 and do not set it beside the other skills' ROIC
- The CF table also gives 減価償却費 ÷ 売上高 and 設備投資額 ÷ 売上高 (registered for the `--register` years); business-case-model uses them for `da_rate` and `maint_capex_rate`
- Segment margins and mix (section 6) carry IDs for the `--register` years; numbers without an ID are printed without a unit and are for reading the trend only. Any segment number a later file or deliverable shows must be one with an ID
- Peer rows (`--peers`) are registered with the same definition text as competitor-benchmark (`売上高（日本基準、連結）東亜精工`), and a 推定 row whose formula already exists in the ledger (e.g. target-math's ROE) is reused, so running both skills does not duplicate facts
- ROE change split: each factor's share of ln(ROE1/ROE0), times ΔROE (pt)
- Operating margin change split: mix effect Σ(Δweight × old margin), rate effect Σ(new weight × Δmargin), the rest = 調整額 and rounding
- Item aliases: 売上高/売上収益, 親会社株主に帰属する当期純利益/親会社の所有者に帰属する当期利益, 純資産/親会社の所有者に帰属する持分, 総資産/資産合計. If 有利子負債 is missing, it sums 短期借入金, 長期借入金, 社債 etc.
- Options: `--tax-rate`, `--tax-rate-id`, `--cash-months`, `--equity-item`, `--register`, `--unit`, `--peer-year`; without `--append` nothing is written to the ledger
- Re-running reuses IDs for the same definition, period, unit and value

## Pitfalls

Full list: [references/pitfalls.md](references/pitfalls.md). The main one: listing ratios without going to drivers.

Senior question seeds: [references/questions.md](references/questions.md).
Evaluation: [references/eval-scenarios.md](references/eval-scenarios.md), [references/eval-rubric.md](references/eval-rubric.md).
