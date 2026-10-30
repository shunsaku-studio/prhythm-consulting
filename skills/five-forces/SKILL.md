---
name: five-forces
description: >-
  Run a Porter five-forces industry analysis that answers one question from the issue tree (enter
  or not, which segment to lean into, how attractive an acquisition target's industry is). Forces
  an explicit industry definition (product scope × geographic scope) before any force is assessed,
  then for each force lists the drivers with ledger IDs, a strength (強/中/弱) with reasons and a
  trend direction; keeps factors that are not forces (regulation, technology, growth, complements)
  in a separate table that says which force each acts through; and ties the overall structure to
  evidence of industry profitability (peer OP margin / ROIC from competitor-benchmark). Unknown
  drivers stay —. Stops for a human to fix the industry definition and the overall judgement
  (decisions.md D-xxx). Writes <case>/frameworks/five-forces.md. Triggers: 「ファイブフォースやって」
  「業界の儲かりやすさ見て」「この業界、参入して儲かる？」「5 フォースで業界分析して」
  「自動車向けと半導体向け、どっちの業界がおいしい？」「買収先の業界の魅力度は？」
disable-model-invocation: false
verb: interpret
categories:
  - business
  - finance
autonomy: review
maturity: formal
workflows:
  - A
  - C
  - D
---

# five-forces

Explain why an industry earns what it earns, and where inside it a company could position itself.
The analysis is about the industry's structure and its profit potential, not about the company's
strengths (that is competitor-benchmark and financial-analysis) and not a list of trends (that is
not what the framework is for).

The value of this skill over a generic fill-in is discipline:

1. The industry is defined first, on two axes (products and geography), and the human agrees it.
2. Every force is pushed down to its underlying drivers, each with evidence or —.
3. Factors that are not forces (growth, technology, regulation, complements) are kept apart and
   routed through the force they act on.
4. The overall judgement is checked against how profitable the industry actually is.

Human-facing guide: `README.md`. Detailed guidance in `references/`:

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: the question served, the industry definition, the evidence on hand |
| `references/method.md` | Steps and why in this order; driver checklist per force |
| `references/pitfalls.md` | Before writing the strengths and the overall judgement |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |
| `references/sources.md` | Where the practices come from |

## When to use

- Workflow C (new entry): "is this industry worth entering, and in which segment?" Before
  option-longlist decides how to enter.
- Workflow A (revenue growth): comparing the industries behind two segments to decide where to put
  the weight (e.g. automotive vs semiconductor-equipment parts).
- Workflow D (M&A): reading how attractive the target's industry is, before or alongside screening.

Do not use it to score the company's own capabilities, to forecast demand (market-sizing does that),
or as a box-filling exercise with no question attached. If no question from the issue tree is
named, ask for one.

## Inputs to ask for

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| The question the analysis serves (Q-xxx, or a sentence) | issue-tree, user | Ask. Do not start without it |
| Industry definition: product scope and geographic scope, and the participants | User; draft from sources | Draft one and stop for agreement (gate 1) |
| Peer list and their figures | `facts/competitor-benchmark.md` | Run competitor-benchmark first, or leave profitability as — |
| Market size and growth by segment | `facts/market-sizing.md` | Leave as —; growth is a factor, not a force |
| Evidence on buyers, suppliers, substitutes, entrants | Filings, integrated reports, industry body reports, briefing transcripts | Leave the driver as — and list it as unconfirmed |

## Steps

1. Read `references/intake.md`. Write down the question served and what the result will be used for.
2. Draft the industry definition: product scope, geographic scope, the participants (competitors,
   buyers, suppliers, substitutes, potential entrants) and how they segment. Test the boundary: if
   two product groups or two regions differ on a force (different buyers, different substitutes),
   they are separate industries. **Stop (gate 1)**: show the draft and ask the human to agree it.
   Record as `D-xxx` in `<case>/decisions.md`.
3. For each of the five forces, go through the driver checklist in `references/method.md`. For each
   driver, write the evidence with an ID (`[F-xxx]`) or a source page, or `—`. Label anything not
   backed by a source as 一般論 or 推測.
4. Give each force a strength (強/中/弱 = how much it pushes industry profit down) with one or two
   reasons drawn from the drivers, and a direction (強まる/横ばい/弱まる). If the drivers are mostly
   —, write — for the strength. Do not average.
5. Fill the "not a force" table: growth rate, technology, regulation/government, complements. For
   each, say which force it acts through and in which direction.
6. Put industry profitability evidence next to the structure: peer OP margin and ROIC over several
   years, from competitor-benchmark or financial-analysis IDs. Say whether the evidence matches the
   structural reading. If they disagree, say so; do not adjust the strengths to fit.
7. Draft the overall structure (案) in 3–5 lines, and the positioning questions it raises.
   **Stop (gate 2)**: ask the human to agree the overall judgement. Record as `D-xxx`.
8. Fill `templates/five-forces.md` into `<case>/frameworks/five-forces.md`. Run number-audit.

## Where the human decides

Autonomy is review (○): the skill drafts everything, then stops twice.

| Gate | What the human decides | Recorded as |
|---|---|---|
| 1 Industry definition | Product scope, geography, whether to split into separate industries | `D-xxx` in decisions.md |
| 2 Overall judgement | Whether the industry (or which segment) is structurally attractive, and what that means for the question | `D-xxx` in decisions.md |

The skill does not decide whether to enter, which segment to choose or whether to buy. It does not
mark the outcome in the body until the gate is passed; until then the body says 人の確認待ち.

## Output

1. **Body** — `<case>/frameworks/five-forces.md` from `templates/five-forces.md`: question served,
   industry definition, one table per industry (force, drivers with evidence, strength, direction),
   the "not a force" table, the structure vs profitability table, and the positioning questions.
2. **Facts** — every number carries an ID from `facts/facts.csv`. Numbers that come from no other
   skill's script (an industry body's concentration ratio, a disclosed customer share) are added
   with `skills/number-audit/scripts/add_fact.py` as F- rows (公開 with source and page). Ratios
   come from other skills' scripts (competitor-benchmark, financial-analysis); never compute them
   in the conversation.
3. **前提と未確認事項** — drivers left —, evidence that is a proxy (e.g. a whole segment standing in
   for a sub-industry), placeholders under any ID, statements labelled 一般論 / 推測.

```bash
# register a raw fact (example: a disclosed customer concentration)
python3 skills/number-audit/scripts/add_fact.py <case>/facts/facts.csv \
  --value 35 --unit % --definition "上位 3 社への売上の集中度（自動車部品）" \
  --period FY2025 --tag 公開 --source "有価証券報告書 FY2025 p.xx（主要な顧客）"
# then check every number in the body
python3 skills/number-audit/scripts/audit.py <case> --today YYYY-MM-DD
```

## Hand-offs

| To | What it receives |
|---|---|
| [competitor-benchmark](../competitor-benchmark/README.md) | Missing peers for the profitability evidence (e.g. a peer focused on the sub-industry) |
| [market-sizing](../market-sizing/README.md) | The agreed industry definition, so the market is sized on the same boundary |
| [option-longlist](../option-longlist/README.md) | Positioning questions and the segments that look structurally attractive |
| [option-evaluation](../option-evaluation/README.md) | The structural reading as one input to the attractiveness / risk columns |
| ma-screening (お題D, Phase 2; not built yet) | Industry attractiveness of candidate targets |

## Rules

- Define the industry before assessing any force. Product scope and geography, both written.
- Growth, technology, regulation and complements are factors, not forces. Never add them as a
  sixth row in the force table.
- Every driver has evidence with an ID or a source page, or —. Label unsourced reasoning 一般論 or 推測.
- Strength is about the industry's profit, not about the client's position in it.
- Tie the structure to profitability evidence; if there is none, say the judgement is weak.
- Look at direction as well as level: where each force is heading over the case horizon.
- No mandatory 示唆 field and no quiz. Positioning questions are inputs for the human, not conclusions.
- Quote sources only as short summaries with the source.
