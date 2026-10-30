---
name: midterm-plan-reader
description: >-
  Read a company's medium-term management plan (中期経営計画) and its final-year
  review, and structure it into one table of targets, actuals, initiatives,
  investment plan and achievement status, each number with a ledger ID. Separates
  M&A-inclusive targets from organic ones and flags definition drift between the
  plan, the review and the filings. Writes facts/midterm-plan.md.
  「中計を整理して」「前の中計、何が未達だった？」「中計の目標と実績を並べて」
  「中計の施策と投資計画まとめて」「次の中計の方針は？」
disable-model-invocation: false
verb: investigate
categories:
  - business
  - finance
autonomy: solo
maturity: provisional
workflows:
  - A
  - B
---

# midterm-plan-reader (provisional)

Structure a 中計 so later skills can start from what the company itself promised and delivered.
Provisional skill: one template, the pitfalls and a small script. Fill the rest with judgment.

Human guide (Japanese): [README.md](README.md)

## When to use

- Workflow A step 1 (目標を仕様にする), next to target-math and leadership-lens
- Workflow B: the ROE / capital policy targets of the current plan
- Whenever someone says "the company already has a plan" and nobody has checked what it actually says

## Intake

Ask for: the plan document(s) and pages, the final-year review (決算説明資料 etc.), the plan period, and whether a next plan has been announced. If the review is missing, actuals come from company-financials (`facts/financials.csv`) and the definition must be checked.

## Steps

1. **List the targets** exactly as stated: metric, base year value, target year, target value, unit, and any note on definition (M&A included, FX assumption, "以上").
2. **Separate M&A.** If a target includes an M&A contribution, record the amount; the organic target is target − M&A. If the plan is silent, write — and list it as unconfirmed. Never assume organic.
3. **Match actuals** from the final-year review; check them against the 有報 values in `facts/financials.csv` (same ID when the value and definition match). If definitions differ (e.g. review uses a different segment split or excludes one-offs), record the difference, do not overwrite.
4. **Run `scripts/plan_check.py`** for achievement rate, progress rate and gap to organic target. Do not compute in conversation.
5. **List initiatives and the investment plan** (planned vs executed amounts), each with the company's own explanation of results (short summary + page). Mark which explanations are the company's view.
6. **Note the next plan's direction** (timing, horizon, stated policies) as input to target-math's definition check.
7. Write `facts/midterm-plan.md` with [templates/midterm-plan.md](templates/midterm-plan.md). No gate in this skill; the target interpretation gate is in target-math.

## Output (always these three parts)

1. **Body** — targets/actuals/achievement table, initiatives table, investment table, next-plan direction
2. **Facts** — every number with `[F-xxx]`; plan targets and actuals are `公開` with document and page; computed rates are `推定` (the script registers them)
3. **前提と未確認事項** — M&A inclusion unknown, definition drift, actuals not cross-checked with the 有報

## Script

```bash
python3 skills/midterm-plan-reader/scripts/plan_check.py <plan.csv> \
  --plan-name "Hokushin Vision 2025" --company 北辰工業 \
  --ledger <case>/facts/facts.csv --append --out /tmp/plan-check.md
```

Input CSV columns: `metric,unit,base_year,base_value,target_year,target_value,actual_value,ma_included,source_target,source_actual,note`. Unknown values are — or empty. `%` metrics get gaps in pt. Re-running reuses IDs. Keep the CSV next to the case (e.g. `facts/midterm-plan.csv`) so it can be re-run.

## Pitfalls

[references/pitfalls.md](references/pitfalls.md): M&A-inclusive targets read as organic; definition drift between plan, review and filings; taking the company's explanation of a miss as fact.

Senior question seeds: [references/questions.md](references/questions.md).
