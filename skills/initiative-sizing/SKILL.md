---
name: initiative-sizing
description: >-
  Size each selected option as an initiative card I-xxx: incremental revenue by year from addressable
  market × share gain × ramp-up curve (S-curve or linear over N years from a start year), or acquired
  revenue for acquisitions, plus an investment schedule. Revenue is incremental to the status quo
  (S-xxx), never total. Confidence (高/中/低) is chosen by the human, not the skill. Writes
  05-initiatives.csv and 05-initiatives.md, and registers I-xxx in the fact ledger via scripts/sizing.py.
  「この打ち手、いくらになる？」「施策ごとに売上見積もって」「施策カード作って」
  「立ち上がりも入れて年次で出して」「打ち手を数字にして」
disable-model-invocation: false
verb: estimate
categories:
  - business
  - finance
autonomy: together
maturity: formal
workflows:
  - A
  - B
  - C
---

# initiative-sizing

Put a number on each option that passed the longlist review. Each initiative gets a card: what market,
how much share on top of the status quo, from when, how fast, how much investment, and how confident
we are. The confidence and the key assumptions are set together with a senior (△). All arithmetic is
done by `scripts/sizing.py`.

> Human guide (Japanese): [README.md](README.md)

## When to use

- After option-longlist review: `decisions.md` has a D-xxx listing which O-xxx go to sizing
- Before capital-capacity (needs the investment schedule) and option-evaluation (needs impact)
- Workflows A, B, C

Do NOT use for: listing options (option-longlist), checking funding (capital-capacity),
building the full PL/CF model (business-case-model).

## Inputs

| File | What you need |
|------|---------------|
| `04-options.md` + `decisions.md` | O-xxx sent to sizing |
| `03-gap-bridge.md` | S-xxx (status quo) and G-xxx. Sizing is incremental to S |
| `facts/facts.csv` | Market sizes, growth rates, share gains, acquisition revenue, investment totals — all as ledger rows |
| `facts/market-sizing.md` | Definition of each market (must match the company's revenue definition, or the gap is noted) |

Intake questions: [references/intake.md](references/intake.md).

## Steps

1. **One card per option.** For each O-xxx sent to sizing, assign I-xxx (next free number in the
   ledger). One option may become several cards if it spans markets; never merge two options.
2. **Register every input in the ledger first.** Market size, market growth, share gain (pt, on top
   of status quo), acquired revenue, investment total. Public values with page, estimates with formula
   and input IDs, placeholders as `仮置き` with `replace_by`. Unknown → `—` (the script carries `—`).
3. **Write the input CSV** (`<case>/05-initiative-inputs.csv`). Columns:
   `id,initiative,option_id,method,market_ref,growth_ref,share_gain_ref,acq_revenue_ref,base_year,start_year,ramp_years,curve,investment_ref,invest_from,invest_to,invest_weights,confidence`.
   The CSV holds IDs, not values. `method` = `market_share` or `acquisition`. `curve` = `s` (default),
   `linear`, or `step` (full from year 1 — warned except for acquisitions). Leave `confidence` as `—`.
4. **STOP — agree assumptions with the senior (△).** Show, per card: market and its definition,
   share gain and why it is plausible (compare with the McKinsey base rate: share gain averages
   0.8pt of growth a year), start year, ramp years, investment. Change only what they agree to.
5. **Run the script.**
   ```bash
   python3 skills/initiative-sizing/scripts/sizing.py \
       --ledger <case>/facts/facts.csv --inputs <case>/05-initiative-inputs.csv \
       --from FY2026 --to FY2030 \
       --out-csv <case>/05-initiatives.csv --out-md <case>/05-initiatives.tables.md \
       --append-ledger --today YYYY-MM-DD
   ```
   It writes `05-initiatives.csv`, Markdown tables (cards, yearly revenue, yearly investment,
   formulas, open items) and one ledger row per I-xxx (final-year incremental revenue, `推定`, formula
   citing input IDs). Re-running updates the same I-xxx rows; it does not duplicate them.
   Exit code 2 = input error (missing ID, wrong unit); fix the ledger, do not bypass.
6. **STOP — the human sets confidence.** Ask the senior/manager to choose 高/中/低 per card, with a
   one-line reason. Write it into the input CSV and re-run. Record as D-xxx in `decisions.md`.
   Never pick confidence yourself.
7. **Assemble `05-initiatives.md`** from `templates/initiatives.md`, pasting the script's tables.
   Compare the total incremental revenue (the script's 計 row, tagged with its F-xxx) with G-xxx;
   do not add numbers by hand.

Method and rationale: [references/method.md](references/method.md).

## Output (common 3 parts)

1. **Body** — `05-initiatives.md` (cards + yearly tables) and `05-initiatives.csv`.
2. **Facts** — I-xxx rows in `facts/facts.csv` (value = incremental revenue in the `--to` year,
   億円), plus one F-xxx row for the total across cards (upserted by definition; cite it when
   comparing with G-xxx). Input rows (F-xxx) are registered before running. Dropping a card leaves
   its old I-xxx row in the ledger; mark it in 前提と未確認事項 rather than reusing the ID.
3. **前提と未確認事項** — the script lists placeholders with deadlines and warnings (step curve,
   ramp ≤ 1 year, share gain > 5pt, missing investment, confidence `—`). Add what the script cannot
   know (market definition mismatches, overlap between cards).

## Hand-off

| File | Shape | Read by |
|------|-------|---------|
| `05-initiatives.csv` | `id,initiative,year,revenue,investment,unit,confidence`; one row per initiative per year; `year` = `FY2027`; `unit` = `億円`; `—` for unknown | capital-capacity, business-case-model, kpi-tree |
| `05-initiatives.md` | cards with `[I-xxx]` | option-evaluation, storyline |

## Pitfalls

See [references/pitfalls.md](references/pitfalls.md). Most common: full revenue from year 1;
total share instead of share gain (double counts market growth already in S); revenue with no
investment; confidence chosen by the analyst; market definitions that do not match revenue.

## Rules

- No arithmetic in conversation. Totals and growth come from the script.
- Every value in the CSV traces to a ledger ID through the I-xxx formula.
- Seed questions for the senior: [references/questions.md](references/questions.md).
