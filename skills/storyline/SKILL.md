---
name: storyline
description: >-
  Turn a finished case folder into a conclusion-first storyline: one governing message, a pyramid
  (claim → about three reasons → ID-tagged facts per reason), and a ghost deck (headline-only page
  list where every headline is a claim sentence carrying the IDs it rests on). Always written in
  two lanes — Lane 1 follows the client's mid-term plan and shows how much must be done to reach
  the target; Lane 2 shows the path outside the plan that base rates and capital constraints point
  to. Stops for the manager to choose which lane leads and records it as D-xxx. Ends at a Markdown
  ghost deck; building slides is out of scope.
  Triggers: 「ストーリーにして」「ゴーストデッキ作って」「結論から組み立てて」「ピラミッドにして」
  「メッセージを一言で」「経営会議向けの骨子作って」
disable-model-invocation: false
verb: communicate
categories:
  - business
autonomy: review
maturity: formal
workflows:
  - A
  - B
  - C
  - D
---

# storyline

Write `deliverables/storyline.md`: the answer first, then the reasons, then the facts, then a
page-by-page headline list — twice, once per lane. The storyline computes nothing and invents no
number. Every number already exists in `facts/facts.csv`; the storyline only chooses, orders and
words them.

Human guide (Japanese): [README.md](README.md). Conventions: `CONVENTIONS.md` at the repo root.

## When to use

- Workflow A step 10 (and the last step of B, C, D): the analysis is done and the team must say
  what the client's leader can say Go to, and on what grounds.
- Mid-project, to test whether the analysis so far supports any message at all (a thin storyline
  shows where the gaps are).

Do not use it to produce slides. Hand the ghost deck to the slide tool with IDs intact.

## Inputs

Read these from the case folder. Missing files become gaps in 前提と未確認事項, not invented content.

| File | What the storyline takes from it |
|------|--------------------------------|
| `00-target-spec.md` | The target (T-) as agreed: value, deadline, definition, capital-efficiency target, required growth rate |
| `01-issue-tree.md` | The key question the governing message must answer (Q-) |
| `03-gap-bridge.md` | Status quo (S-) and gap (G-), and any red flags (e.g. share gain far above base rates) |
| `05-initiatives.md` | Sized initiatives (I-) and their confidence |
| `06-capital.md` | Investment vs funding capacity (C-) |
| `08-kpi-roadmap.md` | Gates and exit criteria (K-) |
| `decisions.md` | Every D- so far — the storyline must not contradict a decision |
| `facts/facts.csv` | Values, units, source tags, confidentiality of every ID cited |
| `facts/leadership.md`, `facts/midterm-plan.md` | What the leader has said in public (labelled) and what the plan commits to |

See [references/intake.md](references/intake.md) for what to confirm first (audience, the one
question, the time slot).

## Rules

- **Conclusion first.** The governing message is the first section. Each lane opens with its own
  one-sentence answer; page 1 of each ghost deck states that answer. Never order pages in the
  order the analysis was done.
- **Every headline is a sentence that makes a claim** and ends with 「。」. 「市場概要」「成長の内訳」
  「打ち手の比較」 are topic labels, not headlines.
- **Every headline carries at least one `[ID]`.** Put the ID right after the number it backs:
  `成り行き 2,553 億円 [S-001]`. `deliverables/` is audited strictly — a unit-bearing number with
  no ID in the same clause is an error.
- **No new numbers.** If a claim needs a number that is not in the ledger, write `—`, list it in
  前提と未確認事項, and say which skill would produce it. Base rates (e.g. the share of companies
  that hit their mid-term revenue target) may be cited only after they are registered in the
  ledger as `公開` rows with source and page.
- **No 社外秘 IDs** in `deliverables/` (outside-in mode has none; inside-out mode must check).
- **Two lanes, always.** Lane 1 is not the "safe" lane and Lane 2 is not the "no" lane. A red flag
  in the gap bridge is the reason Lane 2 exists, not a verdict that the target is impossible.
- **Leader statements** are quoted only from public remarks with their label (本人発言 / メディア解釈)
  and date, as recorded in `facts/leadership.md`.

## Steps

1. **Frame.** Write down the audience, the single question they need answered (from Q- or the
   brief), and the decisions already made (D-). If the target interpretation (D- for T-) is not in
   `decisions.md`, stop: the storyline cannot lead with a target nobody agreed.
2. **Lane 1 answer.** Following the plan: "to reach T-xxx by the deadline, these initiatives at this
   scale and this capital are needed". Draw from G-, I-, C-, K-.
3. **Lane 2 answer.** Outside the plan: what base rates and capital limits imply — e.g. M&A,
   portfolio reshaping, a different market mix, a later deadline or a different definition.
   Draw from the red flags in G-, base-rate F- rows, C-, and the leader's public statements.
4. **Pyramid per lane.** Claim (= the lane answer) → 2–5 reasons (aim for 3), each a sentence →
   under each reason, the facts as `事実: … [ID]`. A reason with no fact under it is cut or
   becomes an open item.
5. **Ghost deck per lane.** 6–12 pages. Page 1 = the answer. Then one page per reason, each
   followed by the pages that prove it. Last pages: what to decide and the gates (K-, exit
   criteria). Each page: `n. 見出し。[ID]` plus an optional indented `- 根拠: [ID] [ID]` line.
6. **Fill the template** [templates/storyline.md](templates/storyline.md) with both lanes. Set the
   governing message to `—` and 前に出すレーン to `—`.
7. **Check structure** with `outline_check.py` (below) and fix every error.
8. **Check numbers** with number-audit:
   `python3 skills/number-audit/scripts/audit.py <case> --today <date> --out <case>/reviews/number-audit.md`.
   Zero errors in `deliverables/` before going on.
9. **STOP — the manager chooses the lead lane.** Present both lane answers side by side: what each
   asks the client to believe, the IDs it rests on, its weakest fact (仮置き / `—`), and what the
   leader has said publicly that each lane aligns with or contradicts. Do not recommend a lane
   unless asked; if asked, give the reasoning and still leave the choice. Wait for the answer.
   This gate normally follows question time ③ (outside this skill).
10. **Record the decision** in `decisions.md`:

    ```markdown
    ## D-009 前に出すレーン（2026-11-12）
    - 決めたこと: レーン2 を前に出す。レーン1 は「中計どおりなら要る規模」として後半に置く
    - 比べた案: レーン1 先 / レーン2 先
    - 決めた人: マネージャー（質問タイム③ 通過後）
    - 根拠: [G-002] [C-003] [F-201]
    ```

11. **Finalise.** Copy the leading lane's one-sentence answer into 統治メッセージ, set
    `前に出すレーン: レーン2 [D-009]`, move the leading lane's section first, and run
    `outline_check.py --final` (zero errors) and number-audit again (zero errors in
    `deliverables/`). Then run number-audit with `--strict`: what remains is usually numbers resting
    on a 仮置き or `—`. Do not invent values to clear them; they stay listed in
    `reviews/number-audit-triage.md` and in 前提と未確認事項, and the slide note says 「仮置きを含む」.

## Where it stops (human decisions)

| Stop | Who decides | Recorded as |
|------|-------------|-------------|
| Target interpretation not yet decided | manager (upstream gate) | existing D- from target-math; storyline waits |
| Which lane leads, and the final governing message | manager | D-xxx in `decisions.md` |
| A claim needs a number that does not exist | manager / team | open item; the owning skill produces it, or the claim is dropped |

The skill never chooses the lead lane on its own and never rewrites a decision.

## Output (three parts, CONVENTIONS §1)

1. **Body** — `deliverables/storyline.md`: governing message, then each lane's one-sentence
   answer, pyramid and ghost deck.
2. **Facts** — no new facts. Every number cites an existing ledger ID. Base rates are cited only
   once registered.
3. **Assumptions and open items** — the last section of the storyline: assumptions the message
   relies on (especially 仮置き IDs), numbers left as `—`, and claims dropped for lack of facts.

## Files written

| File | Notes |
|------|-------|
| `deliverables/storyline.md` | from [templates/storyline.md](templates/storyline.md) |
| `decisions.md` | D-xxx for the lead lane, after the manager decides |
| `reviews/number-audit.md` | via number-audit |

## Scripts

```bash
# structure: governing message first, both lanes, sentence headlines with IDs
python3 skills/storyline/scripts/outline_check.py cases/hokushin/deliverables/storyline.md
# after the lane decision
python3 skills/storyline/scripts/outline_check.py cases/hokushin/deliverables/storyline.md --final
# self-test
python3 skills/storyline/scripts/test_outline_check.py
```

`outline_check.py` (stdlib only) errors when: the first `##` section is not 統治メッセージ; the
governing message or a lane answer is more than one sentence; a lead lane is named without a
`D-` ID; レーン1 or レーン2 is missing; a lane lacks 一言で / ピラミッド / ゴーストデッキ; a reason
has no `事実:` line or a fact has no `[ID]`; a page has no `[ID]`; a headline ends with a topic
word (概要, 分析, 比較, まとめ …) or is shorter than 15 characters. It warns when: the lane or
governing message is still `—` (error with `--final`); a headline lacks 「。」 or particles; a
pyramid has fewer than 2 or more than 5 reasons; page 1 shares no ID with the lane answer (a sign
the conclusion is not first); the lead lane is not placed first. The sentence checks are
heuristics — a pass does not prove a headline is a good claim.

## References

- [references/intake.md](references/intake.md) — audience, the one question, what must be decided first
- [references/method.md](references/method.md) — why answer-first, how to build each lane
- [references/pitfalls.md](references/pitfalls.md) — analysis-order decks, topic labels, one-sided lanes
- [references/questions.md](references/questions.md) — seeds for the senior (not called by this skill)
- [references/eval-scenarios.md](references/eval-scenarios.md), [references/eval-rubric.md](references/eval-rubric.md)
