---
name: competitor-benchmark
description: >-
  Build a comparison table of the target company and its peers covering financials (revenue,
  operating profit, OP margin, net income, ROE, revenue CAGR over a common window) and strategy /
  KPI columns (overseas sales ratio, cumulative M&A investment, main segment). Flags definition
  mismatches (IFRS 事業利益 vs Japanese-GAAP 営業利益, 売上収益 vs 売上高, equity definitions,
  different periods, cash-flow M&A vs deal value) and refuses to put them in the same column
  without a note. Writes facts/competitor-benchmark.md and appends F- rows to facts/facts.csv.
  Triggers: 「競合と比べて」「同業比較の表作って」「ベンチマークして」「競合の利益率並べて」
  「競合 C はなんで伸びてるの？」「うちの ROE って同業と比べて低い？」
disable-model-invocation: false
verb: interpret
categories:
  - business
  - finance
autonomy: solo
maturity: formal
workflows:
  - A
  - B
  - C
  - D
---

# competitor-benchmark

Put the target company and its peers side by side so that every column means the same thing for
every company, or carries a note saying how it differs. The table is used to read *how* peers grew
(organic vs M&A, which segments, which regions), not to rank them.

The most common failure is a clean-looking table that mixes definitions. The script blocks that.

Human-facing guide: `README.md`. Detailed guidance in `references/`:

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: what to ask for |
| `references/method.md` | Steps and why in this order |
| `references/pitfalls.md` | Before writing the reading; definition traps with good/bad examples |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |

## When to use

- In the "current state" step of a case, alongside company-financials and growth-decomposition
- When someone asks how the client compares with peers, or how a peer reached its size
- Workflow B (capital efficiency peers), C (incumbents in a new market), D (acquirers and targets)

Do not use to recommend a stock or judge a valuation.

## Inputs to ask for

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| Target company figures | `facts/financials.csv` (company-financials) | Stop; run company-financials first |
| Peer list (3–5) and why each is a peer | User / manager | Ask. Write the reason in the table header |
| Peer figures in long form (`company,fiscal_year,item,value,unit,basis,source,note[,id]`) | Peers' 有報, 統合報告書 | Collect; leave missing values out (they show as —) |
| Comparison year, CAGR length | User; default latest common year, 5 years | Script aligns to a common window and says so |
| Target's strategy/KPI rows not in financials (e.g. 海外売上比率) | 中計, 統合報告書 → an extra CSV with `id` | Shows — |

## Steps

1. Read `references/intake.md`. Confirm peers and the reason each is a peer.
2. Collect peer figures into a long CSV. Keep the exact item names and accounting basis from the
   source (売上収益 stays 売上収益; do not rename to 売上高). Put caveats from the source in `note`.
3. Put the target's extra rows (overseas ratio etc.) in an extra CSV, reusing ledger IDs in `id`.
4. Run `scripts/benchmark.py` without `--write`. Read every ※ note and every line in
   「前提と未確認事項」. If the script printed 「置かなかった値」, either add a definition note to
   the script's `NOTES` table with a source-backed explanation, or leave it as —. Never rename an
   item to make it fit. The script exits 1 while any value is refused.
5. Run with `--write` to append rows to the ledger.
6. Fill `templates/competitor-benchmark.md` into `<case>/facts/competitor-benchmark.md` around the script body: peer selection, the reading
   (2–4 lines per peer: how it grew, with IDs), and what is still unknown. Follow
   `references/method.md` for the reading.
7. Hand the result back (see "Where the human decides").

## Where the human decides

This skill is solo (◎): it does not need a decision to finish. It stops and asks only when:

- the peer set is unclear or the user's peers do not match the stated reason
- a definition mismatch has no note the skill can back with a source (choose: leave —, or use a
  different item); for IFRS peers, which item sits in the operating-profit column (`--ifrs-op`)

Record such choices in `<case>/decisions.md` as `D-xxx`.

## Output

1. **Body** — `<case>/facts/competitor-benchmark.md`: financial table, strategy/KPI table,
   numbered ※ notes for every definition or period difference, and the reading.
2. **Facts** — every number has an ID. Peer figures are registered as F- 公開 rows (source from the
   CSV); ratios (OP margin, ROE, CAGR, segment share, target's M&A sum) as F- 推定 rows with formulas.
   Rows that already carry an `id` are reused, not duplicated.
3. **前提と未確認事項** — ROE on period-end equity, fiscal year-end months not checked, overseas
   definition, CAGR window, the other IFRS profit line, M&A outside the window, refused values.

Downstream: financial-analysis (peer ratios), gap-bridge and option-longlist (how peers grew:
e.g. a peer that bought a US company), storyline.

## Script

`scripts/benchmark.py` (Python 3.10+, stdlib only).

```bash
python3 skills/competitor-benchmark/scripts/benchmark.py \
  --competitors case/sources/competitors.csv \
  --financials case/facts/financials.csv --target 対象会社 \
  --extra case/facts/benchmark-extra.csv \
  --year FY2025 --cagr-years 5 \
  --facts case/facts/facts.csv \
  --write
```

The script prints the body, then the ledger rows. Paste the body (everything above
「台帳に追記する行」) into the template; do not edit its numbers. `--out PATH` saves the body only;
point it outside the case folder (e.g. a scratch dir) so numbers do not appear twice in the case.

- `--ifrs-op 事業利益|営業利益`: which IFRS line goes in the operating-profit column (default
  事業利益, the one closer to Japanese-GAAP 営業利益; the other is printed with its ID in the notes)
- Exit code 1 when any value was refused for an unexplained definition mismatch
- The target's M&A sum is derived from 子会社株式の取得による支出 over the peers' M&A window, with
  a note that it is a cash-flow amount, not a deal value; acquisitions outside the window are listed

## Rules

- Never put two definitions in one column without a ※ note. Never rename items to make them match.
- Label CAGR by its real window (FY2021→FY2025 is 4 years, not 5).
- Do not compute ratios in the conversation. Run the script.
- Quote paid reports and media only as short summaries with the source.
- Do not fill PEST/SWOT/3C here; those live in the `pest`, `swot` and `three-c` skills. The table answers a question from the issue tree.
