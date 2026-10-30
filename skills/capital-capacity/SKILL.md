---
name: capital-capacity
description: >-
  Check whether the initiatives can be funded. Reads 05-initiatives.csv and the company's financials,
  and sets total investment against funding capacity by source — operating cash flow after
  maintenance capex and dividends (payout ratio), cash above a minimum balance, borrowing headroom up
  to the net D/E limit (counted together with cash, never twice), and asset sales such as
  cross-shareholdings — year by year, with the surplus or shortfall and the tightest year. Adds the
  ROIC impact (incremental NOPAT / incremental invested capital) against WACC. Writes 06-capital.md
  and C-xxx ledger rows via scripts/capacity.py. If short, it hands the choice back to the human.
  「それ、お金足りるの？」「投資の手当てできる？」「資金繰りの枠見て」「D/E の上限まで借りたらいくら？」
  「ROIC 下がらない？」
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

# capital-capacity

The gate between the revenue options and the money. Revenue initiatives without investment, or
investment without a funding source, do not pass. All arithmetic is in `scripts/capacity.py`.

> Human guide (Japanese): [README.md](README.md)

## When to use

- After initiative-sizing has written `05-initiatives.csv` (with investment by year)
- Before the gate 「追う打ち手を選ぶ」 (question time ② comes before that gate)
- Workflows A, B (capital efficiency), C (new entry), D (M&A)

Do NOT use for: the full PL/BS/CF model (business-case-model), scoring options (option-evaluation),
investment advice or valuation of the company's shares.

## Inputs

| File | What you need |
|------|---------------|
| `05-initiatives.csv` | `id,initiative,year,revenue,investment,unit,confidence`; each I-xxx must be in the ledger |
| `facts/financials.csv` | Latest FY consolidated: 営業活動によるキャッシュ・フロー, 親会社株主に帰属する当期純利益, 売上高, 現金及び預金, 有利子負債, 純資産, 営業利益 (item names overridable with `--fin-map`) |
| `facts/facts.csv` | Policy and assumptions as ledger rows: maintenance capex, payout ratio, minimum cash months, net D/E limit, tax rate, initiative operating margin, WACC, asset sales by year |
| `00-target-spec.md` | Capital-efficiency target (ROE / ROIC) to compare with |

Intake questions: [references/intake.md](references/intake.md).

## Steps

1. **Register policy and assumptions in the ledger.** From the disclosure: payout ratio, net D/E
   limit, WACC, cross-shareholding reduction plan (public, with page). Assumptions without a source —
   maintenance capex (e.g. equal to depreciation), minimum cash (e.g. 1–2 months of sales), tax rate,
   initiative operating margin — go in as `仮置き` with `replace_by`. Unknown → `—`.
2. **Write `<case>/06-capital-inputs.csv`** with columns `key,ref,note` (refs only, no values).
   Keys: `maintenance_capex, payout_ratio, min_cash_months, net_de_limit, tax_rate, op_margin, wacc`
   (required), optional `op_margin.I-001` (per initiative), `asset_sale.FY2027` (one row per year),
   `ocf_growth`, `ni_growth`, `wc_ratio`. Base financials come from `financials.csv`; any key in the
   inputs file overrides it.
3. **Run the script.**
   ```bash
   python3 skills/capital-capacity/scripts/capacity.py \
       --initiatives <case>/05-initiatives.csv --ledger <case>/facts/facts.csv \
       --inputs <case>/06-capital-inputs.csv --financials <case>/facts/financials.csv --fy FY2025 \
       --out-md <scratch>/06-capital.tables.md --append-ledger --today YYYY-MM-DD
   ```
   Output: (a) investment total vs capacity by source with surplus/shortfall, (b) yearly table of
   investment, OCF, dividends, asset sales, net debt, equity, net D/E and breach flag,
   (c) ROIC per initiative and total vs WACC, company ROIC before/after, (d) open items.
   C-xxx rows are upserted by definition + period (re-runs do not duplicate).
   When a shortfall sends you back to the options, run each plan with `--label 初回案` / `--label 見直し案`:
   the plan-dependent rows (investment total, surplus/shortfall, max net D/E, incremental ROIC, ROIC after)
   carry the label in their definition, so the first plan's C- rows survive and decisions.md can cite both.
   Funding-side rows (OCF capacity, cash, borrowing, asset sales, total) do not depend on the plan and stay one row.
   The total and the surplus/shortfall rows write their formula with C- IDs.
   Item names: the script reads the 有報 names company-financials writes (and the IFRS names); override with
   `--fin-map`. Company ROIC uses CONVENTIONS 共通の定義 (純資産 + 有利子負債 − 現金及び預金, period-end).
   `--count-initiative-cf` adds initiatives' after-tax operating profit to OCF; default is off
   (conservative). State which one you used.
4. **Assemble `06-capital.md`** from `templates/capital.md`, pasting the tables. Keep `--out-md` outside the
   case folder (a scratch dir) so the same numbers do not appear twice in the case.
5. **STOP — hand the result to the human (○ review).** Present: surplus/shortfall [C-xxx], the
   tightest year and its net D/E, incremental ROIC vs WACC. If short or if any year breaches the
   limit, list the options without choosing:
   - back to **option-longlist** (other options: partnership instead of acquisition, asset sales,
     exits),
   - back to **initiative-sizing** (re-time investment, phase the acquisition),
   - revisit the **target** (deadline or definition) with the manager and the client,
   - change financial policy (D/E limit, payout ratio, equity issuance) — company policy; only the
     client can change it, and it is a lane-2 discussion point, not an assumption to slip in.
   Record what the human decides as D-xxx in `decisions.md`.

Method and rationale: [references/method.md](references/method.md).

## Output (common 3 parts)

1. **Body** — `06-capital.md`: capacity table, yearly net D/E, ROIC impact.
2. **Facts** — C-xxx rows (推定, formula with input IDs): investment total, OCF capacity, cash
   above minimum, borrowing headroom, asset sales, total capacity, surplus/shortfall, max net D/E,
   incremental ROIC, company ROIC before/after.
3. **前提と未確認事項** — the script lists placeholders and conservative choices; add what it
   cannot know (timing of asset sales, M&A price risk, covenant terms).

## Hand-off

| File | Read by |
|------|---------|
| `06-capital.md` (C-xxx) | business-case-model, option-evaluation (capital need), storyline |

## Pitfalls

See [references/pitfalls.md](references/pitfalls.md). Most common: stacking revenue with no
investment; assuming all cash can be spent; adding cash and borrowing headroom on top of each other
under a net D/E limit; checking only the period total and missing the year the limit is breached;
ignoring dividends or maintenance capex.

## Rules

- Do not decide how to close a shortfall. Lay out the routes; the human chooses.
- Do not change company policy values (D/E limit, payout ratio) as an assumption.
- This is not investment advice and not a share valuation.
- Seed questions for the senior: [references/questions.md](references/questions.md).
