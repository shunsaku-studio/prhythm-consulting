---
name: pest
description: >-
  PEST / PESTEL macro-environment analysis tied to one question from the issue tree or the target
  spec: which political, economic, social, technological (and legal, environmental) changes could
  move the assumptions of the target market over a stated horizon, which of them are near-certain
  and which are uncertain. Writes a factor table (要因 / 事実 with ledger IDs / direction and path of
  impact on the market / timing / certainty / size of impact), then an impact × uncertainty matrix
  that routes high-impact, low-uncertainty factors to market-sizing and the gap-bridge status quo,
  and high-impact, high-uncertainty factors to scenario-sensitivity as scenario axes. Keeps facts
  and interpretation apart, leaves unknowns as —, and stops so a human chooses which factors to
  carry forward (decisions.md D-xxx). Writes <case>/frameworks/pest.md.
  Triggers: 「PEST やって」「PESTEL で整理して」「マクロ環境整理して」「外部環境の変化を洗い出して」
  「市場の前提が変わりそうな要因ある？」「EV 化とか為替とか、効きそうなもの並べて」
disable-model-invocation: false
verb: investigate
categories:
  - business
autonomy: review
maturity: formal
workflows:
  - A
  - C
---

# pest

Answer one question: **which macro changes could move the assumptions of the target market, and
which of them are certain and which are not.** PEST is a checklist for not missing a kind of
change. It is not a form to fill. A table with something in every letter is usually a bad table.

What this skill adds over a generic fill-in:

1. It starts from a question (Q-xxx) and a market and a horizon, not from the letters.
2. Every fact carries a ledger ID; interpretation sits in a separate column; unknowns stay —.
3. Factors are prioritised on impact × uncertainty, and each kept factor is routed to the skill
   that uses it (market-sizing / gap-bridge, scenario-sensitivity, option-longlist, issue-tree).
4. A human chooses which factors to carry forward.

Human-facing guide: `README.md`. Detailed guidance in `references/`:

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: question, market, horizon, sources |
| `references/method.md` | Steps and why in this order; how to rate impact and certainty |
| `references/pitfalls.md` | Before writing the table; list-filling and fact/interpretation mixing |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |
| `references/sources.md` | Where the practices come from (Aguilar 1967, scenario planning, CIPD, etc.) |

## When to use

- Workflow A step 4 (成り行き), before or alongside market-sizing: to check which macro changes
  the industry growth forecast already assumes, and which could break it
- Workflow C step 2 (市場を測る): to find what drives demand for a new market (energy prices,
  regulation, subsidies) before sizing it
- When someone asks "what outside changes matter here?" and the answer must feed a number

Do not use:

- without a question and a market. Ask for them (intake). A PEST of "the company" is too wide
- as a deliverable on its own. Its output is used by the next skill or it is not used
- for industry structure (who captures profit) — that is five-forces; for customers and
  competitors — three-c; for summarising strengths and threats — swot

## Inputs to ask for

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| The question (Q-xxx) this answers | `01-issue-tree.md`, or `00-target-spec.md` | Ask. Do not start from the letters |
| Target market (product × region × customer) and its definition | market-sizing, segment notes, user | Ask. Write the definition at the top |
| Horizon (e.g. FY2025→FY2030) | Target spec | Use the target year; say so |
| Sources already in the case | `sources/`, `facts/facts.csv` | Collect public sources; leave gaps as — |
| Exposure of the company (segment share, overseas ratio) | `facts/` | Write — for size of impact |

## Steps

1. Read `references/intake.md`. Write the question, market, horizon at the top of
   `templates/pest.md` → `<case>/frameworks/pest.md`.
2. **Scan wide, keep narrow.** Go through P / E / S / T (and L / E if regulation or environment
   matter for this market) as a checklist. Write down candidate changes. A letter with no change
   that moves this market stays empty, with one line saying so.
3. **Facts first.** For each candidate, find the fact: a forecast, a rule with a date, a disclosed
   figure. Reuse ledger IDs. A number that is not in the ledger goes in with
   `skills/number-audit/scripts/add_fact.py` (below). No fact → write the change in words and put
   — in the fact column. Do not invent a number.
4. **Path of impact.** In a separate column, write how the change reaches the target market:
   direction (+ / − / ±) and the chain (e.g. EV share up → ICE parts demand down, thermal parts
   up). This is interpretation; keep it out of the fact column.
5. **Timing, certainty, size.** Timing: when it bites within the horizon. Certainty 高/中/低 with
   the reason (rule already enacted, forecast revised down N times, cyclical). Size 大/中/小
   anchored to exposure with IDs (segment share, overseas ratio). Do not give probabilities.
6. **Impact × uncertainty matrix.** Place every kept factor. Routing:
   - high impact × low uncertainty → assumption for market-sizing and the gap-bridge status quo
     (predetermined element: already in the pipeline)
   - high impact × high uncertainty → scenario axis for scenario-sensitivity (critical
     uncertainty). Pick at most two or three
   - low impact → keep on a watch list; do not carry forward
   - a factor that opens or closes a market → option-longlist; one that raises a new question →
     issue-tree
7. Write 「前提と未確認事項」.
8. **Stop.** Ask the human which factors to carry forward and how (see below).

## Where the human decides

Autonomy ○ review. The skill proposes; the human decides:

- which factors to carry forward, and to which skill (assumption vs scenario axis)
- the certainty and size ratings when they are disputed
- whether to drop the analysis when nothing moves the market (that is an answer too)

Record in `<case>/decisions.md`:

```markdown
## D-0xx マクロ要因の扱い（YYYY-MM-DD）
- 決めたこと: 成り行きの前提に入れる要因 / シナリオの軸にする要因 / 見送る要因
- 比べた案: …
- 決めた人: マネージャー
- 根拠: frameworks/pest.md 3 節、[F-xxx]
```

## Output

1. **Body** — `<case>/frameworks/pest.md`: factor table with exactly these columns:
   要因 / 事実（[ID] 付き）/ 対象市場への影響の向きと経路 / 時期 / 確からしさ / 影響の大きさ;
   then the impact × uncertainty matrix with the routing; then the hand-off list.
   No 示唆 column and no 次の問い column (design principle 1).
2. **Facts** — every number in the body carries a ledger ID. New raw facts via `add_fact.py`.
3. **前提と未確認事項** — market definition gaps, factors with no source (—), ratings that rest on
   judgement, letters left empty and why.

Downstream: market-sizing (growth assumptions, low case), gap-bridge (status quo), scenario-
sensitivity (ranges and axes), option-longlist (markets opening or closing), issue-tree (new Q).

## Adding a fact

There is no calculation in this skill, so no `scripts/`. When a source gives a number that is not
yet in the ledger, add it (never edit the CSV by hand):

```bash
python3 skills/number-audit/scripts/add_fact.py <case>/facts/facts.csv \
  --value 15 --unit % \
  --definition "世界市場の年平均成長率の見通し: EV 熱マネジメント向け精密部品（業界団体の定義）" \
  --period FY2025-FY2030 --tag 公開 \
  --source "<業界団体の市場見通し> p.<ページ>"
```

The script returns the existing ID if the same row is already there. Then run
`python3 skills/number-audit/scripts/audit.py <case>` and fix any error your file adds.

## Rules

- Start from a question, a market and a horizon. Write them at the top.
- The letters are a checklist, not a quota. Empty letters stay empty.
- Fact column holds facts with IDs or —. Interpretation goes in the path column only.
- Rate certainty with a reason; never with an invented probability.
- Rate size against exposure with IDs, not with adjectives.
- Every kept factor is routed to a next skill; a factor routed nowhere is dropped.
- Do not compute in the conversation (growth combinations, exposure products). If a number is
  needed, it comes from the ledger or from the skill that computes it.
- Paid reports and media: short summaries with the source; no long quotes.
