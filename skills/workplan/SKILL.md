---
name: workplan
description: >-
  Turn the prioritised issue tree into a work plan: for each question and hypothesis (Q-xxx /
  A-xxx), the analysis that tests it, the data source, the skill that does it, the owner, the
  deadline, and the output file in the case folder; plus the calendar of human gates and the three
  senior question times (先輩質問タイム) within the case period. Writes 02-workplan.md. Use right
  after the hypothesis priority is decided. Triggers: 「ワークプラン作って」「作業計画引いて」
  「誰がいつまでに何やるか整理して」「2週間の段取り組んで」「質問タイムいつ入れる？」
disable-model-invocation: false
verb: split
categories:
  - delivery
autonomy: review
maturity: provisional
workflows:
  - A
  - C
---

# workplan

Make the issue tree executable: every hypothesis the manager chose gets one analysis, one data
source, one skill, one owner and one date. The plan also fixes when the gates and the three
question times happen, so the team stops to decide at the right moments instead of at the end.

Read `references/pitfalls.md` before writing. Human-facing guide: `README.md`.

## When to use

- `01-issue-tree.md` exists and the hypothesis priority is decided (a `D-xxx` in `decisions.md`)
- At the start of a case, and again when a gate sends the team back down the ladder

## Inputs to ask for

| Input | Source | If missing |
|---|---|---|
| Prioritised Q/A list | `01-issue-tree.md`, `decisions.md` | Stop; run issue-tree and get the priority decided |
| Case period, deadline, meeting date | `brief.md` | Ask |
| Team members and their availability | User | Leave owner as — and list as 未確認 |
| Mode (outside-in: public data only / inside-out: client data) | `brief.md` | Ask; it decides which data sources are allowed |
| Senior and manager availability for question times | User | Propose dates; mark as 未確認 |

## Steps

1. List the hypotheses in the decided order. Drop the ones the manager dropped (keep the IDs, mark 取り下げ).
2. For each hypothesis, write the one analysis that would confirm or kill it, the data source
   (public / client-provided; outside-in allows public only), the skill that does it, and the
   output file (CONVENTIONS §5 layout: `00-target-spec.md`, `facts/…`, `03-gap-bridge.md` …).
3. Order the work by dependency along the ladder (target → issues → facts → gap → options →
   capital → KPI → roadmap → story). An analysis cannot be due before its input.
4. Place the gates and the three question times:
   - ① before the target interpretation is agreed
   - ② before the initiatives to pursue are chosen (after capital-capacity)
   - ③ before the final message and lane are fixed
   Each is 15–20 minutes, held before the gate, with the senior asking and the manager present.
5. Add a buffer: at least half a day before each question time for rework.
6. Write `<case>/02-workplan.md` from `templates/02-workplan.md`. Stop at the gate.

## Gate (STOP)

Hand back to the manager:

- owners and deadlines (the skill only proposes them)
- dates of the gates and question times
- anything that cannot be done in the period with the allowed data, and what to drop

Record the decision in `<case>/decisions.md` as `D-xxx`.

## Output

1. **Body** — `<case>/02-workplan.md`: work table (Q/A → analysis → data → skill → owner →
   deadline → output file), calendar with gates and question times.
2. **Facts** — the plan rarely has numbers. If it quotes one (e.g. the target), cite the ledger ID
   in brackets. Q/A/D IDs are written without brackets.
3. **前提と未確認事項** — owners not yet confirmed, data not yet available, dependencies at risk.

## ID rules

- Q-xxx, A-xxx and D-xxx are written without brackets in the plan. Bracketed IDs are checked
  against `facts/facts.csv` by number-audit.

## Rules

- One hypothesis, one analysis. If an analysis serves no hypothesis, drop it.
- Do not plan analyses that need client data in outside-in mode.
- The question times are part of the plan. Do not schedule them after the gate they precede.
- The plan does not include quizzes or self-review steps for the junior.
