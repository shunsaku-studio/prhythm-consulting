---
name: issue-tree
description: >-
  Break the client's question (from the target spec) into an issue tree of sub-questions (Q-xxx)
  with one testable hypothesis each (A-xxx), check the tree for MECE gaps and overlaps, and
  propose a priority order for testing. Writes 01-issue-tree.md. The human decides which
  hypotheses to test first. Use right after the target is specified and before the workplan.
  Triggers: 「論点出して」「論点ツリー作って」「何に答えればいいか整理して」「仮説立てて」
  「イシューツリー」「MECE になってる？」
disable-model-invocation: false
verb: split
categories:
  - business
autonomy: review
maturity: provisional
workflows:
  - A
  - C
---

# issue-tree

Turn one client question into the few questions that must be answered, each with a hypothesis that
data can confirm or kill. The tree decides what gets analysed in the next two weeks, so it has to
be complete enough not to miss the answer and small enough to finish.

Read `references/pitfalls.md` before writing. Human-facing guide: `README.md`.

## When to use

- `00-target-spec.md` exists (target value, deadline, definition agreed at gate 1)
- Before workplan; the workplan maps each Q/A to an analysis

## Inputs to ask for

| Input | Source | If missing |
|---|---|---|
| The question to answer, in the client's words | `brief.md`, `00-target-spec.md` | Stop; the target must be specified first |
| Target spec: value, year, definition, capital-efficiency target (IDs) | `00-target-spec.md` | Leave — and list as 未確認 |
| What management has said in public | `facts/midterm-plan.md`, `facts/leadership.md` | Build the tree without it; mark hypotheses that depend on it |
| Constraints: time (e.g. 2 weeks), mode (outside-in = public data only) | Brief | Ask |

## Steps

1. Write the top question as one sentence with the target spec in it
   (e.g. "How can a B2B precision-parts maker (revenue 2,000 億円, three segments) reach consolidated revenue 5,000 億円 [T-001] by FY20xx, M&A included,
   while lifting ROE to 8%?").
2. Split it into 3–5 first-level questions (Q-001…). Use a split that matches the ladder of the
   case: where the gap is (by segment / market), what can fill it (organic / new market / M&A),
   whether capital allows it, and what must be true to decide.
3. Under each Q, write one hypothesis (A-001…) as a falsifiable statement with the data that would
   confirm or kill it. One Q may have up to two competing hypotheses.
4. Run the MECE check in the template: overlaps, gaps, a "none of the above" question, and whether
   each Q can be answered with public data in time.
5. Propose a priority order with a reason (impact on the answer × testable in time). This is a
   proposal only.
6. Write `<case>/01-issue-tree.md` from `templates/01-issue-tree.md`. Stop at the gate.

## Gate (STOP) — 検証する仮説の優先順位

Hand the tree and the proposed order to the human. The manager decides:

- which hypotheses to test, in which order, and which to drop
- whether a hypothesis that touches management's stated intent (e.g. M&A appetite) is in scope

Record the decision in `<case>/decisions.md` as `D-xxx`. Then run workplan.

## Output

1. **Body** — `<case>/01-issue-tree.md`: top question, Q/A tree, MECE check, proposed priority.
2. **Facts** — any number written in the tree (target, current revenue, ROE) cites a ledger ID in
   brackets, e.g. `5,000 億円 [T-001]`. Register new numbers in `facts/facts.csv` before using them.
3. **前提と未確認事項** — what the tree assumes (target definition, deadline) and what is unknown.

## ID rules

- Q-xxx and A-xxx are labels, not ledger rows. Write them without brackets by default (`Q-001`).
  number-audit accepts a bracketed `[Q-001]` only because the tree table defines it (Q- is the first
  cell of its row). A- sits in the 4th column, which is not a defining position, so never bracket A-.
- Numbers inside a hypothesis still need ledger IDs in brackets.
- Never reuse a Q/A number. If a question is dropped, mark it 取り下げ; do not renumber.

## Rules

- Do not write PEST, SWOT, 3C or other frameworks that no question needs.
- A hypothesis must say what data would kill it. "Growth is possible" is not a hypothesis.
- Do not decide the priority. Propose it with reasons and stop.
