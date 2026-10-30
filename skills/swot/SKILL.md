---
name: swot
description: >-
  Build an objective-specific SWOT and a TOWS (cross-SWOT) matrix from evidence already in the case
  folder. Every strength and weakness is stated relative to named competitors and carries a ledger
  ID; every opportunity and threat is external and sourced; every item says why it matters for the
  stated objective (e.g. 5,000 億円 by FY2030). Items are capped (3–5 per quadrant) and prioritised
  by the human; claims without evidence go to a separate 未確認 list instead of the grid. The TOWS
  step pairs items into SO / WO / ST / WT candidate moves, which are handed to option-longlist as
  O-candidates, not decided here. Writes frameworks/swot.md. Triggers:
  「SWOT やって」「強み弱み整理して」「クロス SWOT 作って」「TOWS で打ち手の種出して」
  「うちの強みって何？」「機会と脅威を並べて」
disable-model-invocation: false
verb: interpret
categories:
  - business
autonomy: review
maturity: formal
workflows:
  - A
  - B
  - C
---

# swot

Make a SWOT that someone actually uses later. The classic failure (Hill & Westbrook 1997) is a
long, generic, unprioritised, unverified list that nobody reads again. This skill counters each of
those five failures with a rule, and ends by turning the grid into candidate moves for
option-longlist.

> Human guide (Japanese): [README.md](README.md)

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: objective, comparison set, horizon |
| `references/method.md` | Steps and why in this order |
| `references/pitfalls.md` | Before writing items; good and bad examples |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |
| `references/sources.md` | Where the best practices come from |

## When to use

- After the "current state" step (competitor-benchmark, financial-analysis, leadership-lens, and
  pest / five-forces / three-c if present), before or alongside option-longlist
- When someone asks "what are our strengths?" and the answer must hold up against peers
- Workflow A (revenue growth), B (capital efficiency: is the balance sheet a strength for *this*
  objective?), C (new entry: which strengths carry into the new market?)

Do NOT use to: collect new facts (use the investigate skills), size or rank options
(initiative-sizing, option-evaluation), or produce a generic company profile with no objective.

## Inputs

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| Objective the SWOT serves | `00-target-spec.md` (T-xxx), decisions.md | Stop and ask. A SWOT without an objective is not built |
| Comparison set (named competitors) | `facts/competitor-benchmark.md` | Ask. Without peers, every S/W goes to 未確認 |
| Time horizon | Target spec (e.g. FY2030; FY2033 per a decision) | Ask; write it in the header |
| Internal evidence | `facts/financial-analysis.md`, `facts/midterm-plan.md`, `facts/leadership.md` | Item goes to 未確認 |
| External evidence | `facts/market-sizing.md`, pest / five-forces / three-c outputs | Item goes to 未確認 |
| Gaps | `03-gap-bridge.md` (G-xxx) if it exists | Relevance column cites T-xxx only |

## Steps

1. **Fix the frame.** Write the objective (with its T-/G- IDs), the comparison set and why each
   peer is in it, and the horizon at the top of `templates/swot.md` → `<case>/frameworks/swot.md`.
2. **External first (O, T).** Following Weihrich, list what in the market and environment will
   change over the horizon. Each item: what changes, source with `[ID]`, and how it bears on the
   objective. O and T are things the company does not control; "we could enter X" is not an
   opportunity, it is a move (it belongs in TOWS).
3. **Internal, relative (S, W).** Each item names the peer(s) it is compared with and shows both
   sides with IDs (e.g. `41.0% [F-xxx]` against each peer's value, each with its own ID). An
   attribute that is good in absolute terms but not better than peers is not a strength. For each
   candidate strength, ask the VRIO questions (valuable for this objective? rare among the peers?
   hard to imitate? is the company organised to use it?) and write the answer in one line.
4. **Separate what is not evidenced.** Self-descriptions (e.g. a CEO's "our strength is…"), media
   readings, and items with no peer comparison go to the 未確認 table with what would verify them.
   Never mix them into the grid.
5. **Cap and propose an order.** Keep at most 5 items per quadrant in the grid (aim for 3).
   Propose an order by relevance to the objective, but do not decide it.
6. **TOWS.** Pair items into candidate moves: SO (use S to take O), WO (fix W to take O), ST (use S
   to blunt T), WT (limit exposure where W meets T). Each candidate cites the item labels it pairs
   (`S1×O2`) and the gap it would address (G-xxx). WT candidates are defensive; say so. Do not size
   them, rank them, or assign O- IDs: option-longlist assigns O-xxx. If a candidate matches an
   existing O-xxx in `04-options.md`, write that ID (bare, no brackets).
7. **前提と未確認事項.** Write assumptions (horizon, peer set, definition caveats inherited from
   competitor-benchmark), the 未確認 table, and what was left —.
8. **STOP for review (○).** Ask the reviewer to decide (a) which items stay in the grid and their
   order, and (b) which TOWS candidates go to option-longlist (回す / 保留 / 落とす). Record as
   `D-xxx` in `decisions.md`. Do not pass candidates downstream before this.

Method and rationale: [references/method.md](references/method.md).

## Output (common 3 parts)

1. **Body** — `<case>/frameworks/swot.md`: frame (objective, peers, horizon), four quadrant tables
   (label, item, evidence with IDs, compared with, relevance to the objective), TOWS table, 未確認
   table, hand-off table to option-longlist.
2. **Facts** — this skill normally creates no new numbers. Every number cites an existing ledger
   ID. If a needed number is missing (e.g. a peer's net D/E), leave `—` and list it. If a raw public
   fact must be added, register it with `skills/number-audit/scripts/add_fact.py`; never compute a
   ratio in the conversation (ratios come from financial-analysis or competitor-benchmark scripts).
3. **前提と未確認事項** — at the end of `frameworks/swot.md`.

Item labels (`S1`, `W2`, `O3`, `T1`, `SO1`, `WT2`) are local to the file. Do not write them with a
hyphen and digits (`S-1`, `T-1`), which look like ledger IDs (`T-` is the target-spec prefix).

## Hand-off

| Reads from | Writes to |
|---|---|
| competitor-benchmark (peers, relative S/W), financial-analysis (ratios, drivers), leadership-lens (stated strengths → 未確認 until evidenced; red lines), midterm-plan-reader (what failed), market-sizing, pest, five-forces, three-c (O/T) | option-longlist: TOWS candidates approved at the gate, as O-candidates with their item labels and G-xxx. storyline may cite the grid |

## Rules

- No objective, no SWOT. Write the objective and horizon before any item.
- S/W are relative to named competitors; O/T are external. A move is not an opportunity.
- Every item has evidence with `[ID]` or goes to 未確認. No generic phrases ("高い技術力").
- At most 5 per quadrant. The human sets priority and what passes to option-longlist.
- A strength is judged against the objective: a cash-rich balance sheet is a strength only if the
  objective needs it (e.g. funding M&A), and may be a weakness for a capital-efficiency objective.
- Leader statements: public only, labelled 本人発言 / メディア解釈 / 推測 with date. A self-stated
  strength is a claim, not evidence.
- Client-provided values stay in `client/` and are never used as web search terms.
- No learning quiz. Seed questions for the senior are in `references/questions.md`.
