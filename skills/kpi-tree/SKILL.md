---
name: kpi-tree
description: >-
  Provisional. Break the revenue target (e.g. 5,000 億円 in FY2030) into a KPI tree — status quo
  by segment, segment revenue as volume × price, new initiatives, and the remaining gap — and
  break ROIC into NOPAT margin × invested-capital turnover. Every node gets a K- ID and a value
  taken from the ledger or model/model.csv (never computed in the conversation), or — when
  unknown. Writes 07-kpi-tree.md, which kpi-roadmap uses to pick yearly targets and gate metrics.
  Triggers: 「KPI ツリー作って」「5000 億を分解して」「何が動けば達成か整理して」「ROIC を分解して」
  「売上を数量と単価に分けて」
disable-model-invocation: false
verb: split
categories:
  - business
  - finance
autonomy: review
maturity: provisional
workflows:
  - A
  - B
---

# kpi-tree (provisional)

Show what has to move for the target to be met. Two trees on one page:

1. **Revenue tree** — target `T-` → status quo `S-` by segment → segment revenue = volume ×
   price → initiatives `I-` → remaining gap `G-`
2. **ROIC tree** — ROIC = NOPAT margin × invested-capital turnover; NOPAT margin from operating
   margin and tax; turnover from revenue and invested capital (working capital, fixed assets,
   goodwill from M&A)

This is a provisional skill: one template (`templates/07-kpi-tree.md`) and the pitfalls. Fill
the rest with general reasoning, and keep the rules below.

## Inputs

| Input | File | If missing |
|---|---|---|
| Target (value, year, definition) | `00-target-spec.md` (`T-`) | Stop. Ask for the target spec |
| Status quo and gap by segment | `03-gap-bridge.md` (`S-`, `G-`) | Leave the nodes — |
| Initiative revenue | `05-initiatives.md/.csv` (`I-`) | Leave — |
| Margin, turnover, ROIC by year | `model/model.csv` (rows NOPAT マージン, 投下資本回転率, ROIC) | Leave — ; do not derive by hand |
| Volume and price by segment | `facts/market-sizing.md`, company disclosures | Usually not public. Write — and list as 未確認 (inside-out) |

## Steps

1. Read the inputs. Check that every node uses the same definition as the target
   (consolidated vs organic, M&A included or not, fiscal year).
2. Copy `templates/07-kpi-tree.md` to `<case>/07-kpi-tree.md`. Fill nodes top-down. Each node:
   name, value with its ID, source tag, and whether the company can influence it.
3. Give every new KPI node a `K-` ID and register it in `facts/facts.csv` (value or `—`;
   `推定` rows cite the input IDs in `source`). Use the smallest unused number. Nodes that are
   already `S-`, `G-`, `I-`, `F-` keep their IDs; do not duplicate them as `K-`.
4. Any multiplication or sum that is not already in the ledger or `model/model.csv` is computed
   by the owning skill's script (market-sizing, initiative-sizing, business-case-model), not here.
   If no script produces it, leave — and list it.
5. Check that children add up (or multiply) to the parent. Write any mismatch in
   前提と未確認事項 rather than forcing it.
6. **Stop point (human).** Ask the reviewer which nodes become managed KPIs (candidates for
   yearly targets and gates in kpi-roadmap). Record as `D-xxx` in `decisions.md`.

## Output (the three common parts)

1. **Body** — `07-kpi-tree.md` (two trees as indented lists + node table)
2. **Facts** — `K-` rows in `facts/facts.csv`; `[K-xxx]` next to every value in the tree
3. **前提と未確認事項** — nodes left —, definition mismatches, children that do not add up

## Files

| Reads | Writes |
|---|---|
| `00-target-spec.md`, `03-gap-bridge.md`, `05-initiatives.md/.csv`, `model/model.csv`, `facts/facts.csv` | `07-kpi-tree.md`, `facts/facts.csv` (K- rows), `decisions.md` (D-) |

Read `references/pitfalls.md` before filling the template. Seeds for the senior's questions are
in `references/questions.md` (not part of the steps).
