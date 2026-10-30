---
name: kpi-roadmap
description: >-
  Turn the KPI tree and the business-case model into a yearly roadmap for FY2026–FY2030: yearly
  KPI targets with K- IDs, one row of year-by-year arrows (矢羽) per initiative, and Go/No-Go
  gates that each state a metric, a threshold held as a K- ledger value, a date, a data source,
  the action on Go, and an exit criterion. A stdlib-only script renders the tables into
  08-kpi-roadmap.md and flags any gate without full criteria. The human decides thresholds and
  exit criteria. Triggers: 「ロードマップ引いて」「年度ごとの KPI 目標置いて」「ゲートと撤退基準決めたい」
  「いつ何で判断するか整理して」「矢羽書いて」「Go/No-Go の基準作って」
disable-model-invocation: false
verb: plan
categories:
  - delivery
  - business
autonomy: together
maturity: formal
workflows:
  - A
  - B
  - C
---

# kpi-roadmap

Answer "when, and on what evidence, do we decide?" for each initiative. The roadmap has three
tables, all generated from CSV so the numbers stay tied to the ledger:

1. **Yearly KPI targets** (FY2026–FY2030), one `K-` ID per KPI × year
2. **Arrows (矢羽)** — one row per initiative, one column per fiscal year, phases drawn as
   `【フェーズ】 ━━━ ━━▶`, gates as `◆G1`
3. **Gates** — each with 指標, 閾値 (a `K-` value), 期日, データの出どころ, Go のとき, 撤退基準, 決定 (D-)

The rule that carries the skill: **a gate without a written criterion is not a gate.** The
script treats a missing metric, threshold, date, data source or exit criterion as an error.

This skill is △ together: draft the tables, then sit with the manager to set thresholds and
exit criteria. Human-facing guide: `README.md`. Read `references/pitfalls.md` first.

## When to use

- The model (`model/model.csv`) and, ideally, the sensitivity (`model/sensitivity.md`) exist
- The initiatives to pursue were chosen (decision D- at the capital gate)
- Someone asks for targets by year, a roadmap, or gates and exit criteria

Do not use to choose initiatives or to build the model. Do not write a calendar of tasks; the
grid is yearly on purpose.

## Inputs

| Input | File | If missing |
|---|---|---|
| Yearly values for revenue, margin, ROIC | `model/model.csv` (business-case-model) | Stop. Targets must come from the model or the ledger |
| KPI tree | `07-kpi-tree.md` (kpi-tree) | Use the model lines only; say the tree is missing |
| Initiatives and their phases | `05-initiatives.md`, `05-initiatives.csv` | Ask for start/end years per phase |
| Variables that move the answer most | `model/sensitivity.md` (scenario-sensitivity) | Draft gates from the initiative cards; say so |
| Data available at each gate | Mode (outside-in vs inside-out), `client/` | Write `—` and list it; many gate data come only after the engagement starts |

## Files the script reads

Copy the templates into `<case>/roadmap/`.

- `kpi-targets.csv` — `id,kpi,fiscal_year,value,unit,source_tag,source`. One row per KPI × year.
  Leave `id` blank and run with `--assign-ids` to get `K-` IDs and ledger rows (upserted by
  definition `<kpi>の目標` and period). Values from the model are `推定` with the model's `F-` ID
  in `source`; a threshold someone chose is `仮置き` until the gate decision fixes it. A 仮置き row takes its
  `replace_by` from an optional `replace_by` column, else `--replace-by`, else `--today` + 14 days.
- `arrows.csv` — `initiative_id,initiative,phase,start,end` (write `FY2027`, CONVENTIONS 共通の定義; a bare `2027` is still read). One row per phase.
- `gates.csv` — `gate,date,initiative_id,kpi_id,metric,comparator,threshold,unit,data_source,go_action,exit_criteria,decision_id`.
  Gate names are `G1`, `G2`… (labels, not ledger IDs). `threshold` must equal the ledger value of
  `kpi_id`. `decision_id` stays blank until the human decides.

## Steps

1. Read `model/model.csv`, `07-kpi-tree.md`, `05-initiatives.md`, `model/sensitivity.md`,
   `decisions.md`.
2. Draft `roadmap/kpi-targets.csv`: the yearly path of revenue (and ROIC, margin) from the
   model, plus one or two leading KPIs per initiative from the tree.
3. Draft `roadmap/arrows.csv`: phases per initiative in years. Use the phases in the initiative
   card (e.g. 受注獲得 → 量産立ち上げ → 拡販; 候補探索と DD → PMI).
4. Draft `roadmap/gates.csv`: one gate before each irreversible commitment (a large capex, a
   signing, a market entry). Take metrics from the top of the tornado. For each gate fill a
   proposed threshold, the data source, what Go triggers, and the exit criterion.
5. Run:

   ```bash
   python3 skills/kpi-roadmap/scripts/render_roadmap.py --case case --assign-ids --today YYYY-MM-DD
   ```

   It writes between `<!-- roadmap:begin -->` and `<!-- roadmap:end -->` in
   `08-kpi-roadmap.md` (copy `templates/08-kpi-roadmap.md` first), and prints 直すこと (errors,
   exit code 1) and 人が決めること (gates without a D-).
6. Fix every 直すこと item. Never fill a missing threshold with a number you did not agree on;
   write `—` and keep the gate on the 人が決めること list.
7. **Stop point (human).** With the manager, set each gate's threshold, date and exit criterion.
   This is the gate "ゲートと撤退基準を確定" in workflow A. Record each as `D-xxx` in
   `decisions.md`, write the D- into `gates.csv`, update the threshold's ledger row from 仮置き
   to the decided value, and re-run the script.
8. Fill the hand-written parts of `08-kpi-roadmap.md` (why each gate sits where it does,
   前提と未確認事項). Run number-audit.

## Arrow grid format

| Cell | Meaning |
|---|---|
| `【受注獲得】` | First year of a phase |
| `━━━` | The phase continues |
| `━━▶` | Last year of a phase |
| `【量産立ち上げ】▶` | One-year phase |
| `◆G1` | Gate G1 falls in this fiscal year (April start by default; `--fy-start-month`) |

## Output (the three common parts)

1. **Body** — `08-kpi-roadmap.md` (generated tables + reasons for each gate)
2. **Facts** — each yearly target and each gate threshold is a `K-` row in `facts/facts.csv`;
   tables show `4282.6 [K-005]`
3. **前提と未確認事項** — thresholds still 仮置き, data that only arrives after the engagement
   starts (inside-out), gates without a decision

## Files

| Reads | Writes |
|---|---|
| `model/model.csv`, `model/sensitivity.md`, `07-kpi-tree.md`, `05-initiatives.md/.csv`, `decisions.md`, `facts/facts.csv` | `roadmap/kpi-targets.csv`, `roadmap/arrows.csv`, `roadmap/gates.csv`, `08-kpi-roadmap.md`, `facts/facts.csv` (K- rows), `decisions.md` (D-) |

## Responsibility boundary

- kpi-tree — which KPIs exist and how they add up; this skill puts them on a timeline
- business-case-model / scenario-sensitivity — where target values and gate candidates come from
- storyline — tells the gates to management; this skill does not write the message
