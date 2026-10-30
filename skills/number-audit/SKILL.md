---
name: number-audit
description: >-
  Audit every number in a consulting case folder against the fact ledger facts/facts.csv.
  Runs scripts/audit.py to list ledger defects, untagged numbers, values that disagree with
  the ledger, expired placeholders, confidential values in client-facing deliverables,
  deliverable numbers that rest on placeholders, and hard-coded numbers in the Excel model.
  Use before anything goes up to a manager or into a deck, and after any number changes.
  Triggers: 「数字の裏取りして」「数字チェックして」「出典のない数字ない？」「台帳と合ってるか見て」
  「仮置き残ってない？」「デッキに出す前に点検して」
disable-model-invocation: false
verb: audit
categories:
  - finance
autonomy: solo
maturity: formal
workflows:
  - A
  - B
  - C
  - D
---

# number-audit

Check that every number in a case folder can be traced to one row of `facts/facts.csv`, and that
the number shown equals the number in the ledger. The script does the checking; the agent runs it,
sorts the findings, fixes what is mechanical, and asks the human only where a fix means choosing
between two values or dropping a number.

Human guide (Japanese): [README.md](README.md). Conventions: `CONVENTIONS.md` at the repo root.

## When to use

- Before any file goes to a manager, a question-time session, or a deck builder.
- After a number changes upstream (a placeholder replaced, a model rerun) — rerun to find every
  place that still shows the old value.
- At the start of an inside-out update, to see which placeholders are due.

Do not use it to judge whether an estimate is *reasonable*. It checks traceability and consistency,
not the quality of an assumption.

## Inputs

| Input | Required | Notes |
|-------|----------|-------|
| Case folder (e.g. `case/`) | yes | Must contain `facts/facts.csv` with the 10 columns in CONVENTIONS §2 |
| Today's date | yes | Pass `--today` so placeholder deadlines are judged against the session date, not the machine clock |
| Scope hint | no | "only deliverables" etc. The script always checks the whole folder; filter the report instead |

Ask nothing else before running. Read [references/intake.md](references/intake.md) only if the
folder layout differs from CONVENTIONS §5.

## What the script checks

`scripts/audit.py` (Python 3.10+, stdlib only):

1. Ledger rows: ID format, duplicates, source tag is one of 公開 / クライアント提供 / 推定 / 仮置き,
   source present for 公開 and クライアント提供, formula present for 推定, クライアント提供 is 社外秘.
2. 仮置き rows have `replace_by` and it has not passed.
3. 推定 formulas reference IDs that exist in the ledger, and not themselves.
4. Every bracketed `[ID]` in Markdown and every `id` in CSV exists in the ledger.
   Q-, A-, O-, D- IDs carry no number, so they may instead be defined in a case Markdown file
   (heading, first table cell, or list item start — e.g. `## D-003` in `decisions.md`, `| O-007 |`
   in `04-options.md`, `| Q-001 |` in `01-issue-tree.md`). An ID that appears only mid-row (A- in
   the issue tree's 4th column) is not a definition, so `[A-xxx]` fails; write A- without brackets.
   CSV `id` columns are checked against the ledger only (I-, K-, F- …), never against these definitions.
5. The number just before `[ID]` (within 6 characters) equals the ledger value, allowing unit
   conversion (億円/百万円/兆円/万円, % ⇄ 倍) and display rounding. Fiscal years, dates and IDs
   before a tag are not treated as values.
6. Unit-bearing numbers (億円, %, pt, 倍 …) with no ID in the same clause:
   **error in `deliverables/`, warning elsewhere**.
7. 社外秘 IDs cited in `deliverables/`.
8. IDs cited in `deliverables/` whose 推定 formula chain reaches a 仮置き or a `—` value (warning).
9. `model/business-case.xlsx`: the `inputs` sheet (`id,label,value,unit,source_tag`) matches the
   ledger; calc sheets contain no numeric cell without a formula (row 1 is treated as headers).
10. CSV `value` columns are compared using the row's `unit` (or the ledger unit if absent);
    a `source_tag` column must match the ledger.

Exempt: `sources/` (copies of primary documents), `reviews/` (question-time notes and audit
reports), `brief.md`, the ledger itself, and the `--out` file.

## Steps

1. Run the audit and write the report into `reviews/` (exempt from auditing, so the report never
   audits itself):

   ```bash
   python3 skills/number-audit/scripts/audit.py case \
     --today 2026-11-12 --out case/reviews/number-audit.md
   ```

   Exit code 1 means at least one error.
2. Read the report. Sort each finding into one of four fixes (see
   [references/method.md](references/method.md)):
   - **Tag it** — the number is right, the `[ID]` is missing. Add the ID.
   - **Fix the file** — the file shows a stale value; the ledger is right. Copy the ledger value.
   - **Fix the ledger** — the ledger row is malformed (missing source, bad tag, expired date).
   - **Drop or blank it** — no source exists. Replace with `—` and list it under 未確認事項.
3. Apply the mechanical fixes (tag it, fix the file, malformed rows whose correct content is
   obvious from the source). Never compute a new value in conversation; if a fix needs arithmetic,
   rerun the owning skill's script.
4. **STOP and ask the human** for anything in the list under "Where it stops".
5. Rerun until `deliverables/` has zero errors. Then run once more with `--strict` before the
   final message gate; with `--strict`, warnings count as errors. Findings that remain under
   `--strict` (typically deliverable numbers resting on a 仮置き or `—`) are not forced to zero:
   list each in the triage file with its reason, and the deck notes 「仮置きを含む」 for that number.
6. Write the three-part output (below) and fill the triage table from
   [templates/number-audit-triage.md](templates/number-audit-triage.md) into
   `reviews/number-audit-triage.md`.

## Reading errors vs warnings

| | Meaning | What to do |
|-|---------|-----------|
| Error | Breaks traceability: unknown ID, value mismatch, malformed ledger row, expired placeholder, untagged number or 社外秘 value **in `deliverables/`**, hard-coded cell in the model | Fix before the file goes up. Exit code 1 |
| Warning | Allowed while work is in progress: untagged numbers in working files (`03-gap-bridge.md` etc.), non-numeric ledger values, deliverable numbers resting on 仮置き or `—` | Fix before the number reaches `deliverables/`. `--strict` turns all of them into errors |

`deliverables/` is strict because it is what leaves the team. A working file may hold a rough
number for a day; a deliverable may not.

## Where it stops (human decisions)

The skill stops and asks the user when:

- A file and the ledger disagree and **both look sourced** (e.g. two documents give different
  revenue). Show both values, sources and definitions; the human picks one.
- A placeholder is past `replace_by` and no real value exists yet. Options: extend the deadline,
  replace with an estimate from a script, or blank it to `—`. Extending or blanking a number that
  a deliverable shows is recorded in `decisions.md` as `D-xxx`.
- A number must be **dropped from a deliverable**. Record `D-xxx` with what was dropped and why.
- A 社外秘 value appears in `deliverables/`. The human decides whether to remove it or to agree
  with the client that it may be shown.

Format of the decision (CONVENTIONS §7):

```markdown
## D-012 期限切れの仮置き F-031 の扱い（2026-11-06）
- 決めたこと: 期限を 2026-11-12 に延ばす。デッキには「仮置き」と注記して載せる
- 比べた案: 延長 / market-sizing の推定に差し替え / — にしてデッキから外す
- 決めた人: マネージャー
- 根拠: [F-031] [S-001]
```

## Output (three parts, CONVENTIONS §1)

1. **Body** — `reviews/number-audit.md` (written by the script) and
   `reviews/number-audit-triage.md` (each error with its fix and status).
2. **Facts** — this skill adds no facts. It may correct ledger rows; every correction keeps the ID.
3. **Assumptions and open items** — the script's report ends with "このスクリプトが見ないこと".
   Add to the triage file anything you could not resolve and every value left as `—`.

## Files written

| File | Written by |
|------|-----------|
| `reviews/number-audit.md` | script (`--out`) |
| `reviews/number-audit-triage.md` | agent, from the template |
| `facts/facts.csv`, other case files | agent, only mechanical fixes |
| `decisions.md` | agent, after the human decides |

## Adding a raw fact to the ledger

Numbers that no other skill's script produces (a disclosed WACC, an industry market size, a
placeholder put down for discussion) still go through a script, never a hand edit of the CSV:

```bash
python3 skills/number-audit/scripts/add_fact.py case/facts/facts.csv \
  --value 6.0 --unit % --definition "WACC（会社開示）" --period FY2025 \
  --tag 公開 --source "資本コスト経営の開示 p.2"
python3 skills/number-audit/scripts/add_fact.py case/facts/facts.csv \
  --value 30 --unit % --definition "実効税率" --period FY2025-FY2030 \
  --tag 仮置き --replace-by 2026-11-27
```

It prints the ID to cite. It assigns the smallest unused number for the prefix (`--prefix`, default
`F`), reuses an existing row with the same definition, period, tag and value, and refuses rows that
break the ledger rules (公開/推定 without `--source`, 仮置き without `--replace-by`).

## Self-test

```bash
python3 skills/number-audit/scripts/test_audit.py
```

Builds throwaway cases in the OS temp directory (override with `AUDIT_FIXTURE_DIR`) and covers
every check above. Run it after editing `audit.py`. `--out` creates `reviews/` if it is missing.

## Known limits

See [references/pitfalls.md](references/pitfalls.md). In short: definitions are not compared, bare
numbers without a unit are not flagged, a stray integer close to a tag (`表 3 [F-001]`) is compared
to the ledger, and `05-initiatives.csv` has no `value` column so only its IDs are checked.

## References

- [references/intake.md](references/intake.md) — what to confirm before running
- [references/method.md](references/method.md) — order of fixes and why
- [references/pitfalls.md](references/pitfalls.md) — false positives, false negatives
- [references/questions.md](references/questions.md) — seeds for the senior (not called by this skill)
- [references/eval-scenarios.md](references/eval-scenarios.md), [references/eval-rubric.md](references/eval-rubric.md)
