---
name: market-sizing
description: >-
  Size the markets a company serves, with ranges, from two directions: top-down (industry market
  size × share of it that matches the company's own definition × growth) and bottom-up (product of
  drivers such as units × content per unit), then cross-check them. Defaults the low case to a
  haircut because industry forecasts are often revised down, and reports the company's implied
  share. Writes facts/market-sizing.md and appends F- rows to facts/facts.csv; the agreed growth
  rates become the status-quo assumptions for gap-bridge. Triggers: 「市場はどれだけ伸びる？」
  「市場規模ざっくり出して」「TAM どれくらい？」「この市場、何%成長で置けばいい？」
  「工業会の数字そのまま使っていい？」
disable-model-invocation: false
verb: estimate
categories:
  - business
autonomy: review
maturity: provisional
workflows:
  - A
  - C
---

# market-sizing

Give each market a range, not a point, and say which definition the number uses. The main use in
workflow A is to fix the market growth rates behind the status quo (S) in gap-bridge. In workflow C
it sizes a new market.

Read `references/pitfalls.md` before running. Human-facing guide: `README.md`.

## When to use

- Before gap-bridge, to decide the market growth per segment
- When a market size is quoted from one source with an unclear definition
- To size a new market for an entry option

## Inputs to ask for

| Input | Typical source | If missing |
|---|---|---|
| Market definition per segment: products, regions, customer stage | User + industry report | Ask. Write the definition before any number |
| Industry market size and forecast growth (IDs) | Industry association statistics (`sources/industry-stats.md`) | Leave — ; do not search for a number that fits |
| Forecast revision history | Same report | Ask; default the low case to base − 1.0pt (`--haircut`) |
| Share of the industry market that matches the company's definition (low:base:high) | Judgment; segment notes, product lists | Register as 仮置き with `--replace-by`. Without it the script uses 1 and warns |
| Company revenue in the base year (IDs) | `facts/financials.csv` | Skip the implied share |
| Bottom-up drivers (low/base/high, unit, source) | User, public statistics | Register as 仮置き with `replace_by`; never present top-down alone as final |

## Steps

1. Write the market definition per segment and how it differs from the company's segment revenue.
2. Collect top-down inputs from the ledger. Register missing public facts first (公開, with page).
3. Build the bottom-up CSV (`segment,factor,low,base,high,unit,id,source_tag,source,replace_by`).
   Make the units multiply to the market unit (万台 × 万円 = 億円).
4. Run `scripts/market_sizing.py` without `--write`. Read the cross-check: a gap above
   `--tolerance` (default 30%) or non-overlapping ranges means the definition or a driver is off.
   Fix the inputs or record why they differ; do not tune drivers until the numbers match.
5. Run with `--write`, then fill `templates/market-sizing.md` into `<case>/facts/market-sizing.md`.
6. Stop at the gate.

## Gate (STOP) — 成り行きの前提を確定

Hand back to the human (manager):

- which growth rate per segment (low / base / high) is used for the status quo in gap-bridge
- whether the definition gap (scope ratio) is acceptable
- which 仮置き values must be replaced, and by when

Record the decision in `<case>/decisions.md` as `D-xxx` with the IDs of the chosen rates.
gap-bridge then uses those IDs.

## Output

1. **Body** — `<case>/facts/market-sizing.md` from `templates/market-sizing.md`: definitions,
   top-down table with ranges and implied share, bottom-up table, cross-check.
2. **Facts** — F- rows: low-case growth (推定, haircut), scope ratios (仮置き), target-year market
   low/base/high (推定), implied share (推定), bottom-up drivers and products, cross-check gap.
3. **前提と未確認事項** — definition differences, revision history, — values, 仮置き with `replace_by`.

## Script

`scripts/market_sizing.py` (Python 3.10+, stdlib only). Values as `name=value`, `name=value@ID`,
`name=@ID`; ranges as `name=low:base:high`. `--write` refuses inputs without IDs and 仮置き rows
without `replace_by`.

```bash
python3 skills/market-sizing/scripts/market_sizing.py --facts case/facts/facts.csv \
  --years 5 --base-year FY2025 \
  --size 自動車向け=@F-207 --growth 自動車向け=@F-202 --scope 自動車向け=0.10:0.15:0.20 \
  --company 自動車向け=@F-184 --bottom-up case/facts/market-bottom-up.csv \
  --replace-by 2026-11-06 --write
```

The script prints the body, then the ledger rows. Paste the body (everything above
「台帳に追記する行」) into the template; do not edit its numbers. `--out PATH` saves the body only;
point it outside the case folder (e.g. a scratch dir) so numbers do not appear twice in the case.

Options: `--growth-low` / `--growth-high` to override the defaults (low = base − haircut,
high = base), `--haircut 1.0`, `--tolerance 30`. The IDs above are examples.

## Rules

- Never give a single estimate with an unclear definition. Always definition + range + source.
- The industry definition is not the company's revenue definition. Say how they differ.
- Do not default to symmetric ranges; forecasts in this industry have been revised down.
- Do not compute sizes in the conversation. Run the script.
