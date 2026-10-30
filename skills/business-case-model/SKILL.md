---
name: business-case-model
description: >-
  Build a yearly business-case model (base year FY2025 + plan years to FY2030) from drivers in
  model/inputs.csv and initiatives in 05-initiatives.csv: status-quo revenue, initiative revenue,
  operating profit and margin, D&A, capex/investment, working capital, tax, NOPAT, FCF, invested
  capital, ROIC vs WACC, approximate ROE, cash and net D/E. A stdlib-only script writes
  model/model.csv and model/business-case.xlsx, whose calc sheet holds only formulas that point at
  the inputs sheet (no hard-coded numbers), and registers headline results in facts/facts.csv.
  Use after initiatives are sized and capital capacity is checked. Triggers: 「モデル組んで」
  「PL と CF を 5 年分回して」「ROIC どうなる？」「施策を全部載せると数字どうなる？」
  「Excel のモデルにして」「ビジネスケース作って」
disable-model-invocation: false
verb: estimate
categories:
  - finance
autonomy: review
maturity: formal
workflows:
  - A
  - B
  - C
  - D
---

# business-case-model

Turn drivers and initiative cards into one yearly model that a manager can open in Excel and
trace back to IDs. The model does not decide anything. It shows what the chosen initiatives do to
revenue, profit, cash and capital efficiency, and where the money runs out.

Two rules carry the skill:

1. **Inputs and calculation are separate.** Every number enters through `model/inputs.csv`
   (one ledger ID per driver) or `05-initiatives.csv`. The calc sheet only holds formulas.
2. **No arithmetic in the conversation.** `scripts/build_model.py` computes; you read and report.

Human-facing guide: `README.md`. Read `references/pitfalls.md` before the first run.

## When to use

- Initiatives are sized (`05-initiatives.csv` from initiative-sizing) and the capital check
  (`06-capital.md`) exists or is in progress
- Someone asks what the plan does to PL, CF, ROIC or ROE
- Before scenario-sensitivity (it re-runs this model) and kpi-roadmap (it takes yearly targets from `model/model.csv`)

Do not use to size initiatives (initiative-sizing) or to judge funding capacity alone
(capital-capacity). Do not use it to forecast the share price or give investment advice.

## Inputs

Ask only for what is missing. See `references/intake.md`.

| Input | File / source | If missing |
|---|---|---|
| Base-year actuals (revenue, OP, equity, debt, cash, D&A) | `facts/financials.csv` → ledger IDs | Stop. Run company-financials first |
| Status-quo growth rate | `03-gap-bridge.md` / `facts/market-sizing.md` (S-, F-) | Stop. Do not invent it |
| Initiative revenue and investment by year | `05-initiatives.csv` | Run with status quo only and say so |
| Margin, tax, NWC, interest, maintenance capex, depreciation life | Ledger; otherwise 仮置き with `replace_by` | Register as 仮置き, list in 前提と未確認事項 |
| WACC, payout ratio, financial discipline (e.g. net D/E cap) | Capital-cost disclosure, briefings | Leave — and skip the comparison |
| Confidence filter | Human decision | Ask (see stop point 1) |

`model/inputs.csv` columns: `id,label,value,unit,source_tag,key`. The first five follow
CONVENTIONS §9. `key` is the machine name the script reads (number-audit ignores extra
columns). Copy `templates/inputs.csv`; the `key` set is fixed:

`base_revenue base_op base_equity base_debt base_cash base_growth base_margin init_margin
da_rate maint_capex_rate dep_life nwc_rate tax_rate interest_rate payout_ratio wacc`

Every row needs a ledger ID whose value equals the row's value. Amounts in 億円; rates in `%`
(5.0, not 0.05). A value of `—` stops the script and lists what is missing.

`05-initiatives.csv` (`id,initiative,year,revenue,investment,unit,confidence`): `year` is
`FY2027` (initiative-sizing writes it that way; a bare `2027` is still read); `unit` 億円 or 百万円; `revenue` is incremental to the status quo;
`investment` is the cash spent in that year (capex or acquisition price).

## Steps

1. Read `facts/facts.csv`, `03-gap-bridge.md`, `05-initiatives.md/.csv`, `06-capital.md`.
   Check definitions match: consolidated vs segment, organic vs M&A, the base year.
2. Fill `model/inputs.csv` from `templates/inputs.csv`. Use existing ledger IDs. For a missing
   assumption, add a 仮置き row to the ledger first (with `replace_by`), then reference it.
3. **Stop point 1 (human).** Show the driver table and the initiative list with confidence.
   Ask which confidence levels go into the base case and whether the base margin stays flat.
   Record the answer as `D-xxx` in `decisions.md`.
4. Dry run (no ledger write):

   ```bash
   python3 skills/business-case-model/scripts/build_model.py --case case
   python3 skills/business-case-model/scripts/build_model.py --case case --exclude-confidence 低
   ```

   `model/facts-rows.csv` has a blank `id` until `--ledger-write`, so number-audit stays clean.
   Read the 基準年の再現チェック lines first. If the derived FY2025 net income / ROE is far from
   the disclosed figures, fix tax or interest before reading any projection.
5. Check the workbook:

   ```bash
   python3 skills/business-case-model/scripts/check_xlsx.py --case case --soffice
   ```

   It confirms the parts of the xlsx, finds hard-coded numbers in the calc sheet, recomputes every
   formula in Python against `model.csv`, and (with `--soffice`, if LibreOffice is installed)
   recalculates a copy whose cached values are blanked. If soffice is absent, say "表計算ソフトでの
   再計算は未確認" in 前提と未確認事項. Deeper Excel auditing (style rules, circularity, review of
   a hand-edited workbook) is left to external model-audit tools.
6. Write the ledger rows once the numbers look right:

   ```bash
   python3 skills/business-case-model/scripts/build_model.py --case case --ledger-write --today YYYY-MM-DD
   ```

   It upserts headline results as `F-` rows (`推定`, source lists the input IDs), including the peak net
   D/E and the lowest cash balance over the plan years (the flags the template asks IDs for). Re-running
   updates the same IDs; it never mints new ones for the same definition and period. Pass `--today`.
7. Write `<case>/model/model-summary.md` from `templates/model-summary.md`: the body (yearly table with
   IDs), the flags the script printed, and 前提と未確認事項.
8. **Stop point 2 (human).** If cash goes negative, net D/E breaks the discipline, or ROIC stays
   below WACC, do not fix it inside the model. Report it and ask whether to go back to
   capital-capacity / option selection. Record the decision as `D-xxx`.
9. Run number-audit on the case before handing the model to anyone.

## Model logic (fixed in `compute()`)

Plan year t, previous year p:

- 成り行き売上 = p × (1 + base_growth); 施策売上 = Σ initiative revenue; 連結 = sum
- 営業利益 = 成り行き × base_margin + 施策 × init_margin
- 減価償却 = 成り行き × da_rate + Σ initiative investment up to p ÷ dep_life (from the next year)
- 投資 = 成り行き × maint_capex_rate + Σ initiative investment in t
- 運転資本の増加 = (連結売上 t − p) × nwc_rate
- NOPAT = 営業利益 × (1 − tax); FCF = NOPAT + D&A − 投資 − 運転資本の増加
- 投下資本 = p + 投資 − D&A + 運転資本の増加 (FY2025 = 純資産 + 有利子負債 − 現預金)
- ROIC = NOPAT ÷ average invested capital; ROE ≈ (営業利益 − 利息) × (1 − tax) ÷ average equity
- Debt is held flat; cash absorbs FCF, after-tax interest and dividends, so a negative cash line
  is the funding need

Limits to state every time: no goodwill amortisation or impairment split, non-operating items
other than interest ignored, one margin for all initiatives, one status-quo growth rate for the
whole company. If the case needs segment-level growth or margins, say so and keep the gap in
前提と未確認事項 rather than patching numbers by hand.

## Output (the three common parts)

1. **Body** — `model/model.csv` (long format `id,fiscal_year,item,value,unit,note`; only headline
   rows carry an `id`), `model/business-case.xlsx` (`inputs` + `calc`), and `model/model-summary.md`
   from the template
2. **Facts** — headline results upserted to `facts/facts.csv` as `F-` / `推定`; the same rows in
   `model/facts-rows.csv`. In Markdown write `4,282.6 億円 [F-018]` style
3. **前提と未確認事項** — 仮置き drivers and their `replace_by`, excluded initiatives, model
   limits above, xlsx validation status

## Files

| Reads | Writes |
|---|---|
| `facts/facts.csv`, `model/inputs.csv`, `05-initiatives.csv`, `03-gap-bridge.md`, `06-capital.md` | `model/inputs.csv`, `model/model.csv`, `model/business-case.xlsx`, `model/facts-rows.csv`, `model/model-summary.md`, `facts/facts.csv` (rows), `decisions.md` (D-) |

scenario-sensitivity reads `model/inputs.csv` + `05-initiatives.csv` and re-runs the same
calculation. kpi-roadmap and kpi-tree read `model/model.csv`.

## Script maintenance

`compute()` and the driver/item tables between the `# ==== モデルの定義と計算` and `# ==== ここまで`
markers are copied verbatim into `skills/scenario-sensitivity/scripts/sensitivity.py`. After any
change, copy the block and check:

```bash
diff <(sed -n '/^BASE_YEAR = /,/^# ==== ここまで/p' skills/business-case-model/scripts/build_model.py) \
     <(sed -n '/^BASE_YEAR = /,/^# ==== ここまで/p' skills/scenario-sensitivity/scripts/sensitivity.py)
```

## Responsibility boundary

- initiative-sizing — produces the initiative revenue and investment; this skill does not resize
- capital-capacity — judges funding capacity; this skill shows the cash line that results
- scenario-sensitivity — moves the drivers; this skill holds the base case
- number-audit — checks IDs and the xlsx inputs sheet against the ledger
