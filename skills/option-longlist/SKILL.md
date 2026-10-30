---
name: option-longlist
description: >-
  Build an exhaustive long list of options (打ち手) that could close the revenue gap, before anyone
  sizes or ranks them. Lays options on a coverage grid — existing/new market × existing/new product
  (Ansoff) × build/partner/buy, plus price-mix and portfolio (exit) rows — ties each option O-xxx to
  the gap G-xxx it addresses, tags it lane 1 (within the mid-term plan) or lane 2 (outside it: M&A,
  re-choosing markets, exits), and runs a coverage check that flags empty cells instead of filling
  them with plausible text. Stops for review before initiative-sizing.
  「打ち手を洗い出して」「ギャップを何で埋めるか、候補を全部出して」「打ち手の抜け漏れ見て」
  「M&A も含めて選択肢並べて」「ロングリスト作って」
disable-model-invocation: false
verb: decide
categories:
  - business
autonomy: review
maturity: formal
workflows:
  - A
  - B
  - C
---

# option-longlist

Turn a gap into a complete, reviewable set of candidate options. The goal is coverage, not a short
list of good ideas. Sizing (initiative-sizing) and choosing (option-evaluation, then the human gate)
come later.

> Human guide (Japanese): [README.md](README.md)

## When to use

- After gap-bridge has written `03-gap-bridge.md` with G-xxx, and before initiative-sizing
- When someone has listed three or four favourite ideas and nobody has checked what is missing
- Workflows A (revenue growth), B (capital efficiency: options include portfolio exits and mix), C (new entry)

Do NOT use for: sizing options (initiative-sizing), scoring options (option-evaluation),
checking funding (capital-capacity).

## Inputs

Read these from the case folder before starting. If one is missing, note it under
前提と未確認事項 and continue; do not invent its contents.

| File | What you need from it |
|------|----------------------|
| `03-gap-bridge.md` | G-xxx list: which gap, in which segment, how large |
| `00-target-spec.md` | Target definition (consolidated or organic, incl. M&A or not). Decides whether 買収 options can count |
| `facts/midterm-plan.md` | Mid-term plan priorities → lane 1 options |
| `facts/leadership.md` | Leader's public red lines (e.g. "no overpaying for M&A"), with label 本人発言/メディア解釈/推測 |
| `facts/market-sizing.md`, `facts/facts.csv` | Market growth by sub-market, to cite as 根拠 |

Intake questions: [references/intake.md](references/intake.md).

## Steps

1. **Copy the template.** `templates/options.md` → `<case>/04-options.md`. Fill 埋めるギャップ from
   `03-gap-bridge.md` (values with their `[G-xxx]`), and 制約と譲れない線 with sources.
2. **List options freely, one per row.** Start from three sources in this order:
   (a) mid-term plan priorities (lane 1), (b) each G-xxx — "what would close this gap?",
   (c) each grid cell — "what would sit here?". Give each a new O-xxx (next free number).
   Fill 類型 / 市場 / 製品 / 進め方 / 対象ギャップ / レーン / 根拠. Every number in 根拠 carries an
   existing ledger ID (`+15% [F-021]`). If no source exists, write `—`.
3. **Make lane 2 explicit.** Add options outside the mid-term plan: acquisitions, re-choosing markets
   (moving weight to faster sub-markets), exits and shrinking of declining businesses. Lane 2 is the
   basis for the second storyline, not a fallback. Which lane leads is decided later by the manager.
4. **Run the coverage check** (no judgement in conversation; the script lays out the grid):
   ```bash
   python3 skills/option-longlist/scripts/coverage.py <case>/04-options.md \
       --gaps <case>/03-gap-bridge.md --write
   ```
   It writes the grid between `<!-- COVERAGE:BEGIN -->` and `<!-- COVERAGE:END -->` and lists:
   empty cells, gaps with no option, options with no gap or lane, malformed rows. Exit code 1 means
   something is open.
5. **Handle empty cells honestly.** For each empty cell, either add a real option (with a source) or
   leave it 空欄. Only write a row in 該当なしの判断 when there is a stated reason; the reviewer, not
   you, signs it off. Never fill a cell with generic text to make the grid look complete.
6. **Write 前提と未確認事項**: assumptions (e.g. "M&A counts toward the target" per T-xxx),
   what could not be checked, cells left empty.
7. **STOP for review (○).** Present the grid and the list. Ask the reviewer (senior or manager) to
   decide which options go to initiative-sizing (回す / 保留 / 落とす) and to confirm 該当なし cells.
   Record the decision in `decisions.md` as D-xxx. Do not start sizing before this.

Method and rationale: [references/method.md](references/method.md).

## Output (common 3 parts)

1. **Body** — `04-options.md`: gap table, constraints, option table, 該当なし table, coverage grid,
   sizing selection table.
2. **Facts** — this skill creates no new numbers. Every number cited must already be in
   `facts/facts.csv` and carry `[ID]`. If a needed number is missing, leave `—` and list it.
3. **前提と未確認事項** — at the end of `04-options.md`.

## Hand-off

| File | Read by |
|------|---------|
| `04-options.md` (O-xxx, with G-xxx and lane) | initiative-sizing (one I-xxx per option sent to sizing; `option_id` column), option-evaluation, storyline |

## Pitfalls

See [references/pitfalls.md](references/pitfalls.md). Most common: a handful of favourite ideas
with no coverage check; empty cells filled with plausible text; lane 2 missing; options not tied to
any G-xxx; acquisitions listed while the target is defined as organic.

## Rules

- Do not rank or size options here. No revenue numbers per option.
- Leader's statements are public ones only, labelled 本人発言 / メディア解釈 / 推測 with date.
  A media interpretation is not the leader's intent.
- Client-provided values stay in `client/` and are never used as web search terms.
- Seed questions for the senior are in [references/questions.md](references/questions.md); the
  skill does not quiz the user.
