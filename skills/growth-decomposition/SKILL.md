---
name: growth-decomposition
description: >-
  Split a company's historical revenue growth, by segment and consolidated, into market growth,
  M&A (acquired revenue) and share/residual, in both 億円 and pt/yr, and compare the split with a
  reference (McKinsey 2017 growth champions: market 5.4% / M&A 2.5% / share 0.8%). Handles segment
  reorganizations (uses restated comparatives, otherwise splits the period and shows a merged line)
  and acquisitions inside the period. Reads facts/financials.csv, writes
  facts/growth-decomposition.md and appends F- rows to facts/facts.csv. Triggers:
  「この会社、何で伸びてきたの？」「成長の内訳出して」「オーガニックでどれくらい伸びてる？」
  「M&A抜きだと何%？」「市場並みに伸びてるだけ？」
disable-model-invocation: false
verb: interpret
categories:
  - finance
autonomy: review
maturity: provisional
workflows:
  - A
  - D
---

# growth-decomposition

Answer "what has this company grown on?" with numbers: how much came from its markets growing,
how much from acquisitions, and how much is left over (share gain, price, mix, FX). The residual is
not proof of share gain; it is the part that needs other evidence.

Read `references/pitfalls.md` before running. Human-facing guide: `README.md`.

## When to use

- `facts/financials.csv` exists (company-financials) with segment revenue over several years
- Before gap-bridge, to see whether the past growth was market-driven, bought, or won
- In workflow D, to separate acquired revenue from organic growth

Do not use to forecast. The status quo for the future is built in gap-bridge from market growth.

## Inputs to ask for

| Input | Typical source | If missing |
|---|---|---|
| Segment and consolidated revenue by year (IDs) | `facts/financials.csv` | Stop; run company-financials first |
| Period (from / to) | User; default first to last year in the data | Ask which end years are representative (avoid a trough year as an end point without saying so) |
| Historical market growth per segment, %/yr (IDs) | Industry statistics; often not public for the past | Leave — . The script still gives total, M&A and organic growth. If the user wants a number, register it as 仮置き with `replace_by` |
| Acquisitions inside the period: segment, year, revenue contribution (IDs) | 有報 notes (e.g. 子会社株式の取得 and its note) | Ask; never infer acquired revenue from the purchase price |
| Segment reorganizations | Notes in financials.csv; rows `売上高（組み替え後・参考）` | The script detects restated rows; if notes mention a transfer but no restated figures exist, warn and use merged lines |

## Steps

1. Read `facts/financials.csv`. List the segments, years, and any reorganization notes or restated rows.
2. Confirm the period and the acquisition list with the user. Confirm where market growth comes from.
3. Run `scripts/decompose.py` without `--write`. Check:
   - reorganization handling: if the period crosses the reorg and starts before the restated year,
     the script refuses to decompose the affected segments, adds a merged line, and adds two
     sub-periods (before / after the reorg, the latter starting from restated figures)
   - the acquisition assumption: the first-year contribution is held flat to the end of the period;
     later growth of the acquired business lands in organic
4. Run with `--write` to append rows to the ledger.
5. Fill `templates/growth-decomposition.md` into `<case>/facts/growth-decomposition.md` around the script body: a short reading of the split
   versus the reference, and the evidence still needed for the residual.
6. Stop at the gate.

## Gate (STOP)

Hand back to the human:

- whether the chosen period and end years are fair (e.g. FY2020 is a trough year)
- whether the market growth rates used are acceptable, or remain —
- whether the residual should be called "share gain" in later documents (only with other evidence:
  orders, customer counts, price)

Record decisions in `<case>/decisions.md` as `D-xxx`.

## Output

1. **Body** — `<case>/facts/growth-decomposition.md`: one table per period (full period, and
   before/after reorganization when needed), consolidated line, merged line, reference split.
2. **Facts** — the script appends F- rows (推定) for increments, CAGRs, market, M&A, share/residual
   in 億円 and pt, each with a formula over input IDs. The reference split goes in as F- 公開 rows.
3. **前提と未確認事項** — acquisition assumption, reorganization handling, market definition ≠
   segment revenue definition, any — values.

Downstream: gap-bridge (context for the share lever), storyline.

## Script

`scripts/decompose.py` (Python 3.10+, stdlib only). Values as `name=value`, `name=value@ID`,
or `name=@ID`. `--write` refuses market growth or acquisition inputs without IDs.

```bash
python3 skills/growth-decomposition/scripts/decompose.py \
  --financials cases/hokushin/facts/financials.csv --facts cases/hokushin/facts/facts.csv \
  --from FY2016 --to FY2025 \
  --market-growth 自動車部品=@F-210 --market-growth 産業機械部品=@F-211 --market-growth 電子部品=@F-212 \
  --acquisition 産業機械部品:FY2019=@F-206 \
  --write
```

The script prints the body, then the ledger rows. Paste the body (everything above
「台帳に追記する行」) into the template; do not edit its numbers. `--out PATH` saves the body only;
point it outside the case folder (e.g. a scratch dir) so numbers do not appear twice in the case.

Without `--market-growth` the script still reports total CAGR, M&A pt and organic CAGR, leaving
market and share as —. The IDs above are examples; use the IDs in the case ledger.

Formulas (per line, start R0, end R1, n years, market m, acquired revenue MA):
market = R0 × ((1+m)^n − 1); share/residual = (R1 − R0) − market − MA;
total pt = (R1/R0)^(1/n) − 1; organic = ((R1 − MA)/R0)^(1/n) − 1; M&A pt = total − organic;
share pt = organic − m.

## Rules

- Do not compute the split in the conversation. Run the script.
- Never put pre-reorg and post-reorg segment figures in one growth rate.
- Call the residual "シェア・残差" unless there is separate evidence of share gain.
- Cite the reference split with its source (McKinsey 2017); it is a reference, not a target.
