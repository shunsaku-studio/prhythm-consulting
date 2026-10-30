---
name: option-evaluation
description: >-
  Provisional. Lay sized initiatives side by side in an evaluation matrix — impact, feasibility,
  capital need, time to effect, risk, fit with the mid-term plan and the leader's red lines — so the
  human can choose which ones to pursue. Weights are set by the human; scripts/score.py only computes
  weighted totals in input order and flags pairs whose order flips when a weight moves. No automatic
  ranking or selection.
  「打ち手を比べて」「どれを追うか決めたいので材料並べて」「評価マトリクス作って」「優先順位の材料出して」
disable-model-invocation: false
verb: decide
categories:
  - business
autonomy: together
maturity: provisional
workflows:
  - A
  - C
---

# option-evaluation (provisional)

Prepare the comparison for the gate 「追う打ち手を選ぶ」. The skill fills the matrix with evidence;
the human sets the weights and makes the choice. Provisional: one template, pitfalls, questions,
and a small scoring script.

> Human guide (Japanese): [README.md](README.md)

## Inputs

- `05-initiatives.md` / `05-initiatives.csv` — impact (incremental revenue [I-xxx]), time to effect
  (start year, ramp), human-set confidence
- `06-capital.md` — capital need per initiative, incremental ROIC vs WACC [C-xxx]
- `04-options.md` — lane 1 / lane 2
- `facts/midterm-plan.md`, `facts/leadership.md` — fit, red lines (public statements only, labelled)

## Steps

1. Copy `templates/evaluation-matrix.md` into the `## 評価マトリクス` section at the end of
   `<case>/04-options.md` (there is no separate case file for evaluation).
2. For each I-xxx, write the **evidence** per criterion first (with IDs), then a 1–5 score where
   higher is always better (5 = small capital need, fast, low risk). Unknown → `—`.
   Fill `red_line` with ○ / × / — and the statement it refers to.
3. **STOP — ask the human for weights** (manager, after question time ②). Do not propose
   "standard" weights as if they were neutral.
4. Write the scores to `<case>/04-evaluation-matrix.csv`
   (`id,option,impact,feasibility,capital_need,time_to_effect,risk,fit,red_line,note`) and run:
   ```bash
   python3 skills/option-evaluation/scripts/score.py <case>/04-evaluation-matrix.csv \
       --weights impact=30,feasibility=20,capital_need=15,time_to_effect=10,risk=15,fit=10
   ```
   The weights shown are an example format only. The script refuses to run without weights,
   keeps input order, and lists pairs that flip when one weight moves ±10.
5. Paste the output. **STOP** — the human chooses which initiatives to pursue and which lane
   leads; record as D-xxx in `decisions.md`. Do not write a recommended ranking.

## Output (common 3 parts)

1. **Body** — the 評価マトリクス section in `04-options.md`.
2. **Facts** — no new numbers; evidence cells cite existing IDs ([I-xxx], [C-xxx], [F-xxx]).
   Scores are judgements, not ledger facts.
3. **前提と未確認事項** — scores marked `—`, red lines not yet confirmed, flips from the script.

## Pitfalls

[references/pitfalls.md](references/pitfalls.md): weights chosen after seeing scores; scores without
evidence; mixed directions (high = bad on some axes); ranking by total and treating small gaps as
real; dropping a red-line option silently instead of showing it.

Seed questions for the senior: [references/questions.md](references/questions.md).
