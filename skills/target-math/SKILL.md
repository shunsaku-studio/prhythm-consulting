---
name: target-math
description: >-
  Turn a top-down target (e.g. "revenue 500 billion yen") into a target spec: the
  required annual growth rate for each candidate deadline, checked against an
  outside-view base rate, the company's own historical growth, and the capital
  efficiency target (ROE). Surfaces the undefined parts of the target (deadline,
  consolidated or not, organic or M&A-inclusive, FX) and stops so a human can agree
  the interpretation. Writes 00-target-spec.md and ledger rows with T-/F- IDs.
  「5000億って年何%？」「目標の難易度見て」「この目標、無理筋？」
  「何年で届く計算？」「ROE 8%と売上目標って両立する？」「目標を仕様にして」
disable-model-invocation: false
verb: estimate
categories:
  - finance
  - business
autonomy: solo
maturity: formal
workflows:
  - A
  - B
  - D
---

# target-math

Turn a target someone said out loud into a target spec that every later skill can build on.
The skill does the arithmetic with a script, lays the interpretations side by side, and stops.
It does not decide which interpretation is right.

Human guide (Japanese): [README.md](README.md)

## When to use

- A client or manager states a growth target and nobody has written down its deadline or definition
- Before the issue tree: the first step of workflow A (売上成長), and the target-check step in B (ROE) and D (M&A)
- After company-financials has run, re-run to fill the own-history and ROE rows from `facts/financials.csv`

Do NOT use for:

- Market growth or status quo projection (that is market-sizing / gap-bridge)
- Valuation, share price targets, investment advice

## Intake (ask before computing)

Ask only what is missing. Details and wording: [references/intake.md](references/intake.md).

| Input | Example (お題A) | If unknown |
|-------|----------------|-----------|
| Target value, metric, and who said it where | 売上 5,000 億円, 社長, FY2025 決算説明会 p.12 | Cannot start. Ask |
| Base value and base year | 2,000 億円, FY2025 | Take from `facts/financials.csv` or the latest 有報 |
| Candidate deadlines | 5 / 7 / 10 years | Default `5,7,10`; add any year the source text implies |
| Definition: consolidated or not, organic or M&A-inclusive, FX assumption | unknown | Leave as — and list it in the definition check |
| Capital efficiency target | ROE 8% (stated, not met) | Leave as — |
| Market growth (optional) | 5% | Register as 仮置き with `replace_by` |
| Equity, net income, payout (optional) | 1,150 / 80.7 / 35% | From financials.csv or 有報 |
| FX rate for reference-class size check | 145 円/ドル | Skip the size check and say so |

## Steps

Method and reasoning: [references/method.md](references/method.md).

1. **Quote the target.** Record the exact words, speaker, date and source (short quote or summary). Register the target value as `T-001` (`公開` with the source page).
2. **Fill the definition check** in the template: deadline, consolidated/standalone, organic/M&A-inclusive, FX, metric definition (売上高 vs 売上収益), base year, capital efficiency target. Anything not stated in a source stays —.
3. **Run the script** (below) for every candidate deadline. Do not compute CAGR, percentiles or ROE consistency in conversation.
4. **Compare with the base rate.** Report the percentile, and always write the three caveats the script prints: the distribution is for 5-year periods; it is approximated as normal; the reference class (US-listed, starting revenue $2–5B, 1950–2024) must be re-chosen for size, country and period. If the company is outside the size class, say so explicitly.
5. **Compare with own history** (CAGR over the longest window and the last 5 years). Note that history may include M&A and segment reorganizations; point to company-financials' discontinuity report.
6. **Check ROE consistency.** Required net income and implied net margin at the target revenue, and the ROE if today's margin holds. Write which equity assumption was used.
7. **Build the options table** (template section 7): 2–4 interpretations, each with deadline, definition, required CAGR [T-], base-rate position [T-], and what it implies for later steps (e.g. "needs M&A lane"). Do not rank them.
8. **STOP — gate: 目標の解釈を合意する.** Present the options table and the open definition items. Ask the user (manager) to choose. The question-time ① with a senior usually happens before this gate; do not run it yourself.
9. After the decision, record it in `decisions.md` as `D-xxx` (format in CONVENTIONS §7) citing the T-/F- IDs compared, then fill template section 8 and keep the chosen interpretation as the reference for later skills.

## Output (always these three parts)

Write `00-target-spec.md` in the case folder using [templates/00-target-spec.md](templates/00-target-spec.md).

1. **Body** — definition check, required CAGR table, base-rate comparison, own-history comparison, ROE consistency, options table, decision link
2. **Facts** — every number carries `[T-xxx]` or `[F-xxx]` right after the value, in the same table cell; rows are appended to `facts/facts.csv` by the script. Target-derived values use `T-`; base rates, own history and inputs use `F-`
3. **前提と未確認事項** — the script's notes plus open definition items. Unknown values stay —

Do not add 示唆 or next-question sections.

## Script

`scripts/target_math.py` (Python 3.10+, standard library only). Run `--help` for all options.

Day 1 (before company-financials; pass values with their source):

```bash
python3 skills/target-math/scripts/target_math.py \
  --base 2000 --base-source "有価証券報告書 FY2025 p.40" \
  --target 5000 --target-source "FY2025 決算説明会 書き起こし p.12" \
  --unit 億円 --base-year FY2025 --horizons 5,7,10 --market-growth 5 \
  --history FY2016=1350,FY2020=1470,FY2025=2000 \
  --roe-target 8 --roe-source "FY2025 決算説明会 書き起こし p.13" \
  --equity 1150 --equity-source "有価証券報告書 FY2025 p.44" \
  --net-income 80.7 --net-income-source "有価証券報告書 FY2025 p.41" \
  --payout 35 --payout-source "FY2025 決算説明会 書き起こし p.13" \
  --fx 145 --fx-source "業界団体見通しの為替前提 p.2" \
  --ledger <case>/facts/facts.csv --append --out /tmp/target-math.md
```

After company-financials (reuse ledger IDs instead of re-typing values):

```bash
python3 skills/target-math/scripts/target_math.py \
  --financials <case>/facts/financials.csv --base-year FY2025 \
  --target-id T-001 --roe-id T-0xx --market-growth-id F-0xx --payout-id F-0xx --fx-id F-0xx \
  --ledger <case>/facts/facts.csv --append --out /tmp/target-math.md
```

- `--xxx-source` registers the value as `公開`; `--xxx-id` reads it from the ledger; neither registers `仮置き` with `--replace-by` (default today + 14 days)
- Without `--append` the script prints the rows it would add (stderr) and writes nothing to the ledger
- `--xxx-id` is checked against the ledger row's unit and definition (e.g. `--roe-id` must point to a row whose definition contains "ROE"); the notes list every ID the script read
- Re-running is safe: rows with the same definition, period, unit and value reuse their ID. If the value differs, a new ID is registered and the note says so
- The day-1 run registers base revenue, history, equity and net income as 公開 F- rows. company-financials later reuses those IDs (it matches period, unit, value and item name), so the `--financials` re-run finds the same IDs and adds no rows. The base-year value in `--history` is the same fact as `--base` and gets the same ID
- Pass `--today` (the case date) and `--replace-by` (a date after the case's final meeting) so 仮置き deadlines do not expire inside the case
- Paste the Markdown output into template sections 3–6; do not retype numbers

Check (お題A): 2,000 → 5,000 gives 5 years 20.1%, 7 years 14.0%, 10 years 9.6%; with 5% market growth the 5-year reach is about 2,553.

## Boundaries with other skills

- The 5-year reach under market growth is shown only as a reference. Status quo by segment (S-) and gaps (G-) belong to gap-bridge
- Discontinuities in history (segment reorganization, M&A) come from company-financials
- Which lane to put forward (within the plan vs outside it) is decided later, at the storyline gate

## Pitfalls

Full list with good/bad examples: [references/pitfalls.md](references/pitfalls.md). The two that matter most:

- Computing one CAGR without confirming deadline and definition (consolidated? organic or M&A-inclusive?)
- Comparing with a base rate whose reference class does not match in size, country or period, without saying so

Senior question seeds (not used by this skill's steps): [references/questions.md](references/questions.md).
Evaluation: [references/eval-scenarios.md](references/eval-scenarios.md), [references/eval-rubric.md](references/eval-rubric.md).
