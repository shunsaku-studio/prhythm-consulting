---
name: three-c
description: >-
  Run a 3C analysis (Customer, Competitor, Company; Ohmae's strategic triangle) for one market
  and one question — e.g. which segment the client can win in, or whether it can win after
  entering. Works per segment in a fixed order: customer needs and buying criteria with segment
  size and growth from the ledger → how each competitor (incl. substitutes and entrants) meets
  those same criteria → how the company meets them → the key success factors (KSF) and the
  fit / gap per segment. Keeps facts (with ledger IDs) apart from interpretation, leaves unknowns
  as —, and marks customer criteria as hypotheses that need interviews when working outside-in.
  Stops for the human to choose which segment and KSF to carry forward (D-xxx). Writes
  frameworks/three-c.md. Triggers: 「3C やって」「顧客・競合・自社で整理して」「KSF 何？」
  「どのセグメントなら勝てる？」「この市場、参入して勝てる？」「うちの強みって顧客に効いてる？」
disable-model-invocation: false
verb: interpret
categories:
  - business
autonomy: review
maturity: formal
workflows:
  - A
  - C
---

# three-c

Lay out, for one market and one question, what customers buy on, how competitors meet that,
and how the client meets it — on the **same rows** — so the key success factors (KSF) and the
fit or gap per segment can be read off the table instead of asserted.

Ohmae's point is not "list three Cs". It is that an advantage lasts only where the company
beats competitors **on what customers actually choose on**, in a segment it chose. A generic
fill-in gives three bullet lists and no answer. This skill forces: a question first, segments,
shared buying criteria as the row axis, facts separated from hypotheses, and a human choice at
the end.

Human-facing guide: `README.md`. Detailed guidance in `references/`:

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: the question, the market, the segment grain |
| `references/method.md` | Steps, why in this order, how to derive KSF |
| `references/pitfalls.md` | Before writing the reading; good and bad examples |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |
| `references/sources.md` | Where the method comes from (Ohmae, GLOBIS, others) |

## When to use

- Workflow A step 3–6: after market-sizing and competitor-benchmark, before option-longlist,
  to see in which segment the company can win (e.g. a B2B precision-parts maker with
  automotive, industrial-machinery and electronics businesses: EV thermal management /
  semiconductor equipment / industrial sensors)
- Workflow C step 3: whether the company can win after entering a market (e.g. an industrial-equipment
  maker considering factory energy-management services). Customer side is mostly hypotheses here
- When someone asks "what is the KSF here?" or "do our strengths matter to customers?"

Do not use as a company profile, a SWOT substitute, or a list of everything known. If there is
no question, stop and ask for one (see intake). The output answers one question from the
issue tree.

## Inputs to ask for

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| The question (which segment can we win in / can we win if we enter) | User; `01-issue-tree.md` Q-xxx | **Stop and ask.** Do not start without it |
| The market and the segment grain (2–4 segments, by customer use) | User, `facts/market-sizing.md` | Propose segments from market-sizing; ask the user to confirm |
| Segment size and growth with IDs | `facts/market-sizing.md`, `facts/facts.csv` | Run market-sizing first, or leave — |
| Competitor set and their facts with IDs | `facts/competitor-benchmark.md` | Run competitor-benchmark first, or leave — |
| Company facts with IDs (segment sales, margins, share, capex) | `facts/financials.csv`, `facts/financial-analysis.md`, `facts/midterm-plan.md` | Leave — |
| Company's stated strengths | `facts/leadership.md` (本人発言), 統合報告書 | Leave —; do not invent strengths |
| Mode: outside-in (public only) or inside-out (interviews, client data) | User | Assume outside-in; mark customer criteria 仮説 |

## Steps

1. Read `references/intake.md`. Write the question, the market and the segments at the top of
   the output. If the question is missing, stop and ask.
2. **Customer, per segment.** From `facts/market-sizing.md` copy size and growth with their
   existing IDs. Write who buys, for what use, and 3–6 buying criteria (購買基準). In outside-in
   mode every criterion and its weight is a hypothesis: label it 仮説 and name the interview or
   document that would confirm it. Never present a hypothesis as a fact.
3. **Competitor, per segment, on the same criteria.** List direct competitors (reuse
   competitor-benchmark IDs), plus substitutes and possible entrants. For each criterion,
   write how each competitor meets it, as fact with ID, or 仮説, or —. Do not fill a cell because
   it looks plausible.
4. **Company, on the same criteria.** Segment sales, margin, share, capacity, strengths
   stated in public (quote only a short phrase, cite the page). Same rule: fact with ID / 仮説 / —.
5. **KSF and fit / gap, per segment.** KSF = the one or two criteria that weigh most for the
   customer **and** separate winners from the rest. For each segment write: KSF, the company's
   position vs the strongest competitor on it (上回る / 並ぶ / 下回る / —), and the gap.
   Follow `references/method.md` §5. Do not rank segments by a score you made up.
6. Fill `templates/three-c.md` into `<case>/frameworks/three-c.md`. Keep 事実 and 解釈・仮説 in
   separate columns. List every 仮説 with the interview that would test it.
7. **Stop.** Hand the comparison back and ask which segment(s) and KSF to carry forward (see
   below). Record the choice in `<case>/decisions.md` as `D-xxx`.

## Where the human decides

Autonomy is review (○): the skill builds the table; a senior reviews; the manager decides.

- Which segment(s) to carry forward and which KSF to build the options around
- Whether a hypothesis is good enough to act on, or must be confirmed by interviews first
- Whether to add Collaborators / Context (4C / 5C) for this question

The skill does not choose the segment and does not write 示唆 or recommendations. Record the
decision in `decisions.md`:

```markdown
## D-0xx 追うセグメントと KSF（YYYY-MM-DD）
- 決めたこと: …
- 比べた案: frameworks/three-c.md のセグメント別の適合とギャップ
- 決めた人: …
- 根拠: [F-xxx] …（仮説のままの基準はその旨を書く）
```

## Output

1. **Body** — `<case>/frameworks/three-c.md`: per segment, a criteria × (customer / competitors
   / company) table with 事実 and 解釈・仮説 separated; a KSF and fit / gap table.
2. **Facts** — every number carries an existing ledger ID. This skill rarely creates numbers.
   If a raw fact is not in the ledger yet (e.g. a share figure from an 統合報告書), add it with
   `skills/number-audit/scripts/add_fact.py`; never edit `facts.csv` by hand. Do not compute
   ratios in the conversation; take them from market-sizing, competitor-benchmark or
   financial-analysis, or run that skill.
3. **前提と未確認事項** — mode (outside-in / inside-out), which criteria are 仮説 and how to test
   each, cells left —, definition gaps between the market data and the company's segments.

## Hand-offs

| To / from | What |
|---|---|
| `../market-sizing/README.md` | In: segment size and growth. Out: segments whose size is — |
| `../competitor-benchmark/README.md` | In: competitor facts. Out: competitors missing from the set (substitutes, entrants) |
| `../financial-analysis/README.md` | In: segment margins and ROIC. Out: a gap that is really a cost question |
| `../leadership-lens/README.md` | In: strengths in the leader's own words (本人発言) only |
| `../swot/README.md` | Sibling. SWOT can take the fit / gap as S/W, but this table stays the source |
| `../option-longlist/README.md` | Out: the chosen segment and KSF, to build options around |
| `../issue-tree/README.md` | In: the question (Q-xxx). Out: new sub-questions where KSF is — |

## Rules

- No question, no 3C. Ask first.
- Customer first. Never start from the company's strengths.
- The same criteria rows in all three Cs. A KSF must point to a row.
- Facts with IDs and hypotheses in separate columns. Unknown is —.
- Outside-in: customer criteria are 仮説 until interviews confirm them.
- Winning means beating the strongest competitor on the KSF, not "having a strength".
- No 示唆 field, no recommendation. The human chooses the segment.
- Quote media and reports only as short summaries with the source.
