---
name: scenario-sensitivity
description: >-
  Run base / upside / downside scenarios and a tornado-style one-at-a-time sensitivity on the
  business-case model, with a separate, evidence-backed range per variable (market growth from
  forecast revisions, initiative realisation from share-gain base rates, ramp delay in years,
  margins from peers, M&A go / no-go) — never one uniform ±10%. Every range carries a source tag.
  A stdlib-only script re-runs the same calculation as business-case-model from model/inputs.csv
  and 05-initiatives.csv, writes model/sensitivity.md, and registers upside/downside results in
  facts/facts.csv. Triggers: 「感応度見て」「上振れ下振れのシナリオ作って」「どの前提が一番効く？」
  「トルネード出して」「下振れたらいくらになる？」「M&A がなかったら？」
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
---

# scenario-sensitivity

Show which assumptions move the answer, by how much, and on what evidence. The output is two
things: a scenario table (base / upside / downside) and a tornado table per metric (FY2030
revenue and ROIC by default), each row with its range and source tag.

The rule that carries the skill: **each variable gets its own range, and each range has a
reason.** A uniform ±10% says nothing about which risk is real. The script refuses to run when
three or more variables share the same relative width.

Human-facing guide: `README.md`. Read `references/pitfalls.md` before the first run.

## When to use

- `model/inputs.csv` and `05-initiatives.csv` exist and business-case-model has run
- Someone asks how robust the plan is, what happens if X slips, or which assumption to verify first
- Before kpi-roadmap (gates should watch the variables at the top of the tornado) and storyline

Do not use to build the base case (business-case-model) or to estimate probabilities. Upside and
downside are joint moves of the variables marked `in_scenario`, not confidence intervals.

## Inputs

| Input | File | If missing |
|---|---|---|
| Drivers | `model/inputs.csv` (same file business-case-model reads) | Stop. Run business-case-model first |
| Initiatives | `05-initiatives.csv` | Only driver ranges can be tested |
| Ranges | `model/sensitivity-ranges.csv` from `templates/sensitivity-ranges.csv` | Draft with the user (stop point 1) |
| Revenue target ID | `00-target-spec.md` (`T-`) | Skip the gap-to-target row |
| Confidence filter | Same as the base case decision (D-) | Ask |

`sensitivity-ranges.csv` columns: `key,label,downside,upside,unit,in_scenario,source_tag,source`.
`downside` / `upside` are absolute values in the input's unit (5.0 for 5%), not deltas.
`in_scenario` = `yes` puts the variable into the joint upside/downside. `source_tag` is one of
公開 / クライアント提供 / 推定 / 仮置き; anything but 仮置き needs a `source` (document and
page, or formula with IDs).

Keys: any driver key in `model/inputs.csv`, plus

| Key | Meaning | Base |
|---|---|---|
| `ramp_delay` / `ramp_delay:I-001` | Shift initiative revenue by n years (+1 = one year late). Investment stays on plan. Earlier (−n) keeps the last year flat | 0 |
| `init_scale` / `init_scale:I-001` | Realisation of initiative revenue (investment still spent) | 1.0 |
| `init_go:I-004` | Do the initiative or not: scales revenue and investment (M&A not closed = 0) | 1.0 |

## Where ranges come from

Use evidence in this order, and write it in `source`. Details in `references/method.md`.

| Variable | Evidence for the range | Typical shape |
|---|---|---|
| Status-quo / market growth | Industry forecast and its revision history; sub-segment rates | Asymmetric when forecasts have been cut repeatedly |
| Initiative revenue realisation | Base rates for share-driven growth (average about 0.8pt/yr; few firms sustain 5%+ from share alone), own track record vs past plans | Downside wider than upside |
| Ramp timing | Past slips of the same company (e.g. a launch one year late) | +1 year down, 0 up unless there is evidence of acceleration |
| Margins | Own history, peer margins with matching definitions | Peer range, adjusted for start-up losses |
| M&A | Past deals that failed on price, discipline statements | 0 or 1 via `init_go` |
| Working capital, tax | Own history | Narrow; often not in the scenario |

## Steps

1. Read `model/model-summary.md`, `05-initiatives.md`, `03-gap-bridge.md`, `facts/facts.csv`.
   List the drivers and initiatives that are 仮置き or low confidence.
2. Draft `model/sensitivity-ranges.csv`. One row per variable, each with its own evidence.
   Where no evidence exists, mark 仮置き and say so; do not invent a range.
3. **Stop point 1 (human).** Show the range table. Ask the reviewer to confirm the endpoints and
   which variables go into the joint scenarios. Record as `D-xxx`.
4. Run:

   ```bash
   python3 skills/scenario-sensitivity/scripts/sensitivity.py --case cases/hokushin --target-id T-001
   python3 skills/scenario-sensitivity/scripts/sensitivity.py --case cases/hokushin --target-id T-001 --exclude-confidence 低
   ```

   Use the same `--exclude-confidence` as the base case. The script warns if its base FY2030
   revenue differs from `model/model.csv`.
5. Read the tornado: the top two or three rows are the assumptions to verify first and the
   candidates for gates in kpi-roadmap. A row with zero swing on revenue may still matter for ROIC.
6. Register the scenario results:

   ```bash
   python3 skills/scenario-sensitivity/scripts/sensitivity.py --case cases/hokushin --target-id T-001 --ledger-write
   ```

   Upside and downside results become `F-` / `推定` rows (upserted by definition and period).
   The base column reuses the IDs business-case-model registered. With `--target-id`, the gap between
   FY2030 revenue and the target is also registered for base / upside / downside, so a deck can say
   "x 億円 short of the target" with an ID. Pass `--today` (the case date).
7. Write `<case>/model/scenarios.md` from `templates/scenarios.md`: link `model/sensitivity.md`,
   state in words what drives the downside, and fill 前提と未確認事項.
8. **Stop point 2 (human).** If the downside misses the target by a wide margin or breaks the
   financial discipline, report it; the choice of lane (stay with the plan / look outside it)
   belongs to the manager. Do not soften the ranges to make the downside look better.

## Output (the three common parts)

1. **Body** — `model/sensitivity.md` (scenario table, range table with tags, tornado tables) and
   `model/scenarios.md` from the template
2. **Facts** — upside/downside headline results in `facts/facts.csv`; IDs written next to values in
   the scenario table (`2,975.4 [F-035]`). Ranges cite their evidence IDs in `source`
3. **前提と未確認事項** — 仮置き ranges, joint-move caveat, what the model cannot vary (segment-level
   growth, goodwill, financing), variables left out and why

## Files

| Reads | Writes |
|---|---|
| `model/inputs.csv`, `05-initiatives.csv`, `model/sensitivity-ranges.csv`, `model/model.csv` (check only), `facts/facts.csv` | `model/sensitivity-ranges.csv`, `model/sensitivity.md`, `model/scenarios.md`, `facts/facts.csv` (rows), `decisions.md` (D-) |

## Why the model is re-implemented

The script needs to re-run the calculation with changed drivers, so reading `model/model.csv`
is not enough. The block between `# ==== モデルの定義と計算` and `# ==== ここまで` in
`scripts/sensitivity.py` is a verbatim copy of business-case-model's `build_model.py`, so this
skill runs on its own. Do not edit the copy here; change build_model.py and copy the block. The
diff command is in business-case-model's SKILL.md.

## Responsibility boundary

- business-case-model — holds the base case and the xlsx
- kpi-roadmap — turns the top tornado variables into gate metrics
- capital-capacity — decides how a downside funding gap would be met
