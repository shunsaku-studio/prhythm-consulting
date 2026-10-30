---
name: gap-bridge
description: >-
  Compute the status-quo revenue (S: base revenue grown at market rates only) and the gap (G) to a
  revenue target, by segment and in total, then test how the gap could be allocated to levers
  (share gain, new markets, M&A, price). For the share lever it computes the implied share-driven
  growth in pt/yr on top of market growth and raises a red flag above 5pt/yr, citing base rates.
  Writes 03-gap-bridge.md and appends S-/G- rows to facts/facts.csv. Use after the target is
  specified and market-growth assumptions are fixed. Triggers: 「成り行きだといくら？」
  「ギャップどれくらい？」「どこにいくら足りないか出して」「5000億まで何で埋める？」
  「シェアで埋めるのって無理ある？」「ブリッジ作って」
disable-model-invocation: false
verb: estimate
categories:
  - finance
  - business
autonomy: review
maturity: provisional
workflows:
  - A
  - D
---

# gap-bridge

Turn "we want 500 billion yen" into two numbers per segment: what the company reaches if markets
grow and nothing else changes (S), and how much is missing (G). Then show what each lever would
have to deliver per year, so the team can see which allocations are within base rates and which
need a second lane.

Read `references/pitfalls.md` before running. Human-facing guide: `README.md`.

## When to use

- The target is specified (`00-target-spec.md` exists, or the user gives value / year / definition)
- Market growth assumptions per segment are fixed (output of market-sizing, gate 「成り行きの前提を確定」)
- Someone asks "how far short are we, and where?"

Do not use to choose initiatives or size them. This skill sizes the hole, not the plugs.

## Inputs to ask for

Ask only for what is missing. Leave unknowns as — and list them.

| Input | Typical source | If missing |
|---|---|---|
| Base-year revenue by segment (IDs) | `facts/financials.csv` (company-financials) | Use consolidated only; segment G stays — |
| Market growth per segment, %/yr (IDs) | `facts/market-sizing.md` | Stop. Do not invent a rate; ask, or register a 仮置き with `replace_by` |
| Target value, year, definition (ID `T-`) | `00-target-spec.md` | Compute S only; G stays — |
| Segment targets | Only if a human set them | Leave segment G as —. Never pro-rate the total gap |
| Lever allocation (optional) | Draft from the user; registered as 仮置き | Show S and G without levers |

Check that base revenue and the target use the same definition (consolidated vs organic, M&A
included or not). If they differ, stop and ask.

## Steps

1. Read `00-target-spec.md` and `facts/facts.csv`. Collect the IDs for base revenue, market growth and target.
2. Run `scripts/gap_bridge.py` without `--write`. Check the table against the inputs (segment sums,
   base year, horizon).
3. If the user gave a lever allocation, run again with `--lever`. Read the share check:
   - implied share-driven growth > 5pt/yr → 赤旗. Report it with the base rates the script prints
     (average share gain 0.8pt/yr; only 13% of companies exceeded 5% from share over 10 years, McKinsey 2017)
   - also report what the average 0.8pt/yr would deliver
4. Run with `--write` to append rows to the ledger.
5. Fill `templates/03-gap-bridge.md` into `<case>/03-gap-bridge.md`: paste the script body, then
   write the two-lane framing (see below) in plain words, using only IDs from the ledger.
6. Stop at the gate.

The red flag is not a verdict that the target is impossible. It is the reason to open lane 2
(M&A, market re-selection, a different deadline or definition).

## Two lanes

- **レーン1 中計に則る必要量**: take the target as given and state what each lever must deliver.
- **レーン2 中計の外側**: from base rates and the share check, the paths outside the plan
  (larger M&A, moving to faster markets, revisiting the deadline or definition with management).

Write both. Do not choose which one leads; that is the manager's call at the storyline gate.

## Gate (STOP)

This skill decides nothing. After writing the file, stop and hand these to the human:

- whether the market-growth assumptions used for S are the agreed ones (if not, return to market-sizing)
- whether to set segment targets (only then are segment gaps computed)
- the lever allocation is a 仮置き draft; which levers to pursue is decided later (option-longlist onward)

Record any decision made here in `<case>/decisions.md` as `D-xxx` (date, what was decided, options
compared, who decided, evidence IDs in brackets).

## Output

Always three parts:

1. **Body** — `<case>/03-gap-bridge.md` from `templates/03-gap-bridge.md`: S and G table, waterfall,
   share check, two lanes.
2. **Facts** — every number has an ID. The script appends `S-` rows (status quo per segment, total,
   market increment, blended market growth) and `G-` rows (gap, required CAGR, lever allocations,
   implied pt/yr, average-share delivery, unallocated). Base rates go in as `F-` 公開 rows.
3. **前提と未確認事項** — assumptions (share constant in S, market definition ≠ segment revenue
   definition), — values, and 仮置き rows with their `replace_by`.

Downstream: option-longlist, initiative-sizing and storyline read `03-gap-bridge.md`.

## Script

`scripts/gap_bridge.py` (Python 3.10+, stdlib only). Values are passed as `name=value`,
`name=value@ID`, or `name=@ID` (value read from `--facts`). `--write` refuses inputs without IDs.

```bash
# Reproduce the planning example (no ledger): 2000 → 5000 in 5 years, market 5%
python3 skills/gap-bridge/scripts/gap_bridge.py \
  --base 連結=2000 --growth 5 --years 5 --base-year FY2025 --target 5000 --lever シェア=800
# → 成り行き 2,553 / ギャップ 2,447 / 必要年率 20.1% / シェア 800 は年 5.9pt（赤旗）/ 0.8pt なら 99

# Case run: segments, segment market growth, ledger append
python3 skills/gap-bridge/scripts/gap_bridge.py --facts cases/hokushin/facts/facts.csv \
  --base 自動車部品=@F-184 --base 産業機械部品=@F-186 --base 電子部品=@F-188 \
  --growth 自動車部品=@F-202 --growth 産業機械部品=@F-203 --growth 電子部品=@F-204 \
  --years 5 --base-year FY2025 --target @T-001 \
  --lever シェア=800 --lever M&A=1000 --replace-by 2026-11-13 \
  --write
```

The script prints the body, then the ledger rows. Paste the body (everything above
「台帳に追記する行」) into the template; do not edit its numbers. `--out PATH` saves the body only;
point it outside the case folder (e.g. a scratch dir) so numbers do not appear twice in the case.

Options: `--target-seg 名前=値[@ID]` (human-set segment targets), `--lever 名前:セグメント=値`
(lever on one segment), `--share-redflag 5.0`, `--share-avg 0.8`, `--unit 億円`.
The IDs above are examples; use the IDs in the case ledger.

## Rules

- Do not compute S, G or pt in the conversation. Run the script.
- Do not pro-rate the total gap to segments.
- Lever amounts without an ID are 仮置き and need `--replace-by`.
- Show the red flag with the base rate and its source. Do not soften or drop it.
