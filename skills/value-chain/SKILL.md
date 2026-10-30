---
name: value-chain
description: >-
  Porter's value chain for one business (segment), adapted to its industry: list the activities the
  business actually performs (not the generic nine boxes), and for each one record what the company
  does, cost / asset intensity evidence with ledger IDs where public data allows (capex/sales, D&A/sales,
  R&D/sales from financial-analysis; activity-level splits are usually unknown outside-in and stay —,
  flagged for インサイドアウト), cost drivers and differentiation drivers, how a named competitor
  does the same activity, and the linkages between activities and into the supplier and buyer
  chains (value system). Separates facts from hypotheses on every row. Stops for the human to judge
  which activities are sources of advantage and which are candidates for make / buy / partner,
  synergy or carve-out (D-xxx). Writes frameworks/value-chain.md.
  Triggers: 「バリューチェーンで見て」「どこで稼いでるか分解して」「どの機能が強み？」
  「強みってどの活動にあるの？」「内製と外注、どこを切り分ける？」「買収したらどこが重なる？」
  「ノンコアを切り出すと何が残る？」
disable-model-invocation: false
verb: split
categories:
  - business
  - finance
autonomy: review
maturity: formal
workflows:
  - A
  - B
  - D
---

# value-chain

Split one business into the activities through which it creates and delivers value, and ask of each
activity: what does it cost, what makes it cost that, what makes it different, and how does it
connect to the next activity. The point is to locate cost or differentiation advantage — and where
capital sits — in specific activities and links, not to fill nine boxes.

A generic LLM fills the nine boxes with plausible text. This skill does not: it adapts the activity
list to the industry, puts an ID or — on every number, labels every claim 事実 / 会社の主張 / 仮説,
and hands the judgment of "where the advantage is" to a human.

Human guide (Japanese): [README.md](README.md). Details in `references/`:

| File | Read when |
|---|---|
| `references/intake.md` | Before starting: which business, which question, which competitor |
| `references/method.md` | Steps and why in this order |
| `references/pitfalls.md` | Before writing the body; good and bad examples |
| `references/questions.md` | Not used by the skill. Seeds for the senior's question time |
| `references/eval-scenarios.md`, `references/eval-rubric.md` | When evaluating this skill |
| `references/sources.md` | Where the practices come from (Porter 1985, McKinsey business system, BCG on carve-outs) |

## When to use

- Workflow A step 3 (現状と成長の内訳) or step 6 (打ち手): when the question is *why* the client
  earns what it earns in a business, or which strength an option builds on
- Workflow B: when a business earns below its cost of capital and the question is which activities
  carry the cost or the assets
- Workflow D: synergy (which activities overlap with a target) and carve-out (which shared activities
  a non-core business depends on)
- When the leader names a strength (e.g. 「量産立ち上げの速さ」) and it needs to be pinned to
  activities and evidence

Do not use for: a company-wide strategy summary (one chain per business), the external environment
(`pest`, `five-forces`), a strengths/weaknesses list (`swot`), positioning against customer and
competitor (`three-c`), valuation, or the synergy amount itself (business-case-model).

## Inputs to ask for

Details in `references/intake.md`. Minimum:

| Input | Source | If missing |
|---|---|---|
| The business (segment) to draw | User; segments in `facts/financials.md` | Ask. One chain per business. A company with three segments gets up to three chains, never one blended chain |
| The question | User; the issue tree (Q-xxx) | Ask. One of: cost position / differentiation source / make-buy-partner / synergy / carve-out. It decides which columns are heavy |
| The competitor to compare (1–2) | User; `facts/competitor-benchmark.md` | Ask. Without one, the 競合との違い column is — |
| Ratios already computed | `facts/financial-analysis.md` (capex/sales, D&A/sales, margins), `facts/competitor-benchmark.md` | Run financial-analysis first, or leave — |
| The company's own claims about strengths | `facts/leadership.md`, 統合報告書, 中計 | Leave the 会社の主張 column empty; do not invent a strength |
| For synergy: the other company's business; for carve-out: the business to separate | User | Ask |

## Steps

Method and reasons: `references/method.md`.

1. **Fix the scope.** Business, question, competitor (`references/intake.md`). Write them at the top
   of the output.
2. **Adapt the activity list.** Start from Porter's five primary and four support activities, then
   rename, split or merge them so each row is an activity this business actually performs (a B2B
   parts maker: 受注前の技術営業・設計参画 / 試作・量産立ち上げ / 量産 / 品質保証・納入 / 補給・
   アフター; support: 開発、調達、設備投資・生産技術、人材、全般管理). Write why each generic box
   was renamed, merged or dropped.
3. **Fill what the company does** per activity, from public documents, with page references.
4. **Attach intensity evidence.** Only numbers already in `facts/facts.csv` (capex/sales, D&A/sales,
   R&D/sales, segment margin, headcount). Activity-level cost or asset splits are almost never
   public: write — and add the row to 「インサイドアウトで取るデータ」. Do not compute ratios in the
   conversation; a missing ratio means run financial-analysis or leave —. Raw disclosed numbers not
   yet in the ledger are added with `skills/number-audit/scripts/add_fact.py` (公開, with page).
5. **Write drivers.** For each activity: cost drivers (scale, learning, utilisation, linkages,
   interrelationships with other businesses, timing, policy choices, location, regulation) and
   differentiation drivers (what the buyer pays for or chooses on). Label each 事実 (source) /
   会社の主張 (who said it, where) / 仮説.
6. **Compare with the competitor** activity by activity. Most rows will be qualitative or —. Say
   that the whole-system fit is harder to compare than single activities.
7. **Draw the linkages.** Inside the chain (e.g. 設計参画 → 量産立ち上げ) and into the value system
   (supplier chain, buyer's design and production chain). Advantage usually sits in a link, not a box.
8. **Question-specific section.** Only the one the question calls for:
   - make / buy / partner: activities where the company is not distinctive and scale sits elsewhere
   - synergy: overlapping activities, cost synergy vs revenue synergy kept apart, no amounts here
   - carve-out: shared support activities and contracts, dis-synergy and stranded-cost candidates
9. **Stop for the human** (below). Do not write the judgment yourself.
10. Fill `templates/value-chain.md` into `<case>/frameworks/value-chain.md` (or
    `value-chain-<business>.md` when there is more than one chain). Run number-audit.

## Where the human decides

Autonomy: review (○). The skill prepares the table and stops. The human (manager, with the senior)
decides:

- which activities and links are judged sources of advantage (and which are only the company's claim)
- which activities are candidates for make / buy / partner, or in Workflow D which overlaps count as
  synergy and which shared activities block a carve-out
- whether the inside-out data list is worth requesting after the engagement starts

Present the candidates side by side with their evidence label (事実 / 会社の主張 / 仮説) and stop.
Record the decision in `<case>/decisions.md` as `D-xxx` (CONVENTIONS §7). Until it is recorded, the
output says 「判断待ち」.

## Output

1. **Body** — `<case>/frameworks/value-chain.md`: scope; adapted activity list with reasons; the
   activity table (what the company does / intensity [ID] or — / cost drivers / differentiation
   drivers / competitor / label); linkages and value system; the question-specific section; the
   candidates handed to the human.
2. **Facts** — every number carries an existing ledger ID. This skill rarely creates numbers; raw
   disclosed values go in via `add_fact.py`. Ratios come from financial-analysis.
3. **前提と未確認事項** — which numbers are consolidated rather than segment-level, every — and the
   inside-out data that would fill it, every claim that is only the company's own.

No 示唆 or next-question sections.

## Hand-offs

- Upstream: [financial-analysis](../financial-analysis/README.md) (intensity ratios, segment
  margins), [competitor-benchmark](../competitor-benchmark/README.md) (the competitor's figures and
  how it grew), [leadership-lens](../leadership-lens/README.md) (the leader's stated strengths)
- Downstream: [option-longlist](../option-longlist/README.md) (options that build on or fix an
  activity; make / buy / partner column), [capital-capacity](../capital-capacity/README.md) (where
  capex sits; carve-out proceeds), [business-case-model](../business-case-model/README.md)
  (synergy and dis-synergy amounts are sized there, not here)
- Siblings: [three-c](../three-c/README.md) (customer and competitor positioning),
  [swot](../swot/README.md) (a strength in SWOT should point to an activity here),
  [five-forces](../five-forces/README.md) (supplier and buyer power sit at the value-system edges)

## Rules

- One chain per business. Never blend segments into one chain.
- Never keep a generic box the business does not perform; never leave out an activity it does.
- Every number has an existing `[ID]`, or is —. No activity-level cost split from outside-in.
- Every driver and strength carries 事実 / 会社の主張 / 仮説. A leader's statement is 会社の主張
  until another source confirms it.
- Do not compute in the conversation. Do not size synergies here.
- Q-, A-, O-, D- are written without brackets unless a definition line exists in the case.
