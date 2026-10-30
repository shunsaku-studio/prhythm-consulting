---
name: leadership-lens
description: >-
  Structure a client executive's public statements (earnings calls, integrated
  report messages, interviews, AGM answers) into a dated, sourced table labeled
  本人発言 / メディア解釈 / 推測, grouped by theme, and draft candidate
  "non-negotiables" (譲れない線) as hypotheses for a human to decide on together.
  Public statements and actions only: no private life, health or family, no
  personality diagnosis, short quotes only. Writes facts/leadership.md.
  「社長の発言を整理して」「経営者が何を大事にしてるか見て」「社長の譲れない線は？」
  「説明会で社長が何て言ってたかまとめて」「トップメッセージを読んで」
disable-model-invocation: false
verb: investigate
categories:
  - business
autonomy: together
maturity: provisional
workflows:
  - A
  - B
---

# leadership-lens (provisional)

Read what the executive has said and done in public, so the proposal starts from the client's own words.
The output is a structured record plus hypotheses. The skill does not judge the person.

Human guide (Japanese): [README.md](README.md)

## Guardrails (non-negotiable for this skill)

- **Public statements and public actions only**: earnings calls and their transcripts, integrated / annual reports, AGM, press releases, published interviews, the company's own IR pages
- **Never** collect or mention private life, health, family, personal relationships, or anything not said in a public business context. If a source contains such content, skip it and do not summarize it
- **No personality diagnosis** or psychological labels ("he is risk-averse", "type A"). Describe what was said and done, with dates
- **Every row gets a label**: `本人発言` (the executive's own words, first-hand transcript or official document), `メディア解釈` (a reporter's or analyst's reading, headline, "とみられる"), `推測` (our inference). Never relabel メディア解釈 as 本人発言
- **Short quotes only** (one short phrase per row at most); otherwise summarize in your own words with the source and page. Paid or media articles: summary and source only
- Client-provided material (inside-out) goes to `client/`, is `社外秘`, and is never used as a web search query

## When to use

- Workflow A step 1, with target-math and midterm-plan-reader: the target often first appears as a spoken statement
- Workflow B: what the executive has committed to on capital policy (ROE, payout, buybacks)
- Before choosing which lane to put forward: what the executive has publicly ruled in or out

## Intake

Ask for: the executive's name and role, the period to cover (default: the last 2–3 years), the sources available (transcripts, integrated report, interviews) with pages, and the themes that matter for the case (e.g. target, M&A, capital policy, portfolio). Do not ask for anything outside public business statements.

## Steps

1. **Collect** public statements in the period. Record date, venue, source and page for each.
2. **Label** each row 本人発言 / メディア解釈 / 推測. A headline or "記者は…とみている" is メディア解釈 even if it appears in quotation marks.
3. **Summarize** each statement in one line; keep at most one short quote per row.
4. **Group by theme** (target, M&A, capital policy, portfolio, strengths, risks). Note repetitions across dates and any change of stance (with both dates).
5. **Register numbers** the executive stated (target values, ROE, payout ratio, mix targets) in `facts/facts.csv` as `公開` with the source page; reuse IDs already registered by target-math (e.g. T-001). Non-numeric statements do not get ledger IDs; refer to them by row number (#1, #2).
6. **Draft 譲れない線 candidates** as hypotheses: each with the supporting rows, whether they are 本人発言, how often repeated, and what would contradict it. Mark the strength (本人発言で複数回 / 本人発言で 1 回 / メディア解釈のみ).
7. **STOP — gate (together): 譲れない線の扱いを一緒に決める.** Present the candidates. The manager (with the user) decides which to treat as constraints for the proposal, which to test with the client, and which to drop. Record the decision in `decisions.md` as `D-xxx` with the row numbers and IDs used.
8. Write `facts/leadership.md` with [templates/leadership.md](templates/leadership.md).

## Output (always these three parts)

1. **Body** — statements table (date, venue, label, summary, theme, source), theme view, 譲れない線 candidates table
2. **Facts** — every stated number with `[T-xxx]` or `[F-xxx]` (ledger rows `公開`)
3. **前提と未確認事項** — statements not found in a primary source (media only), gaps in the period, inferences labeled 推測

## Pitfalls

[references/pitfalls.md](references/pitfalls.md): mixing media interpretation with the executive's words; treating one remark as a firm line; drifting into personality or private matters; long quotes.

Senior question seeds: [references/questions.md](references/questions.md).
