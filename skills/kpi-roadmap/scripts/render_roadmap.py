#!/usr/bin/env python3
"""年度別の KPI 目標、施策の矢羽（年単位）、Go/No-Go ゲートの表を CSV から組み、欠けを点検する。

読むもの（既定は <case>/roadmap/ の下）:
  kpi-targets.csv  id,kpi,fiscal_year,value,unit,source_tag,source
                   id が空の行は --assign-ids で K- の番号を振り、台帳に載せる
  arrows.csv       initiative_id,initiative,phase,start,end   （start/end は FY2027 か 2027）
  gates.csv        gate,date,initiative_id,kpi_id,metric,comparator,threshold,unit,data_source,
                   go_action,exit_criteria,decision_id
  <case>/facts/facts.csv

書くもの:
  <case>/08-kpi-roadmap.md の <!-- roadmap:begin --> と <!-- roadmap:end --> の間を置き換える
  （印がなければ画面に出すだけ）

点検すること（ゲートに判定基準が書かれていない、を機械で拾う）:
  - ゲートの 指標・閾値・期日・データの出どころ・撤退基準 が空でないか
  - 閾値が kpi_id の台帳の値と一致するか（閾値は台帳に載った K- の値で持つ）
  - 期日が計画期間に入っているか、ゲートの施策が矢羽にあるか
  - decision_id が空のゲート（人がまだ決めていない）を一覧にする

使い方:
  python3 render_roadmap.py --case cases/hokushin
  python3 render_roadmap.py --case cases/hokushin --assign-ids      # K- を振って台帳に載せる
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

FIRST_FY, LAST_FY = 2026, 2030
DASH = "—"
BEGIN, END = "<!-- roadmap:begin -->", "<!-- roadmap:end -->"
GATE_REQUIRED = ["date", "kpi_id", "metric", "comparator", "threshold", "data_source", "exit_criteria"]


def read_csv(p: Path) -> tuple[list[str], list[dict]]:
    if not p.exists():
        return [], []
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def fy_of(s: str) -> int | None:
    m = re.search(r"\d{4}", s or "")
    return int(m.group()) if m else None


def fy_of_date(d: dt.date, start_month: int) -> int:
    return d.year if d.month >= start_month else d.year - 1


def next_free(prefix: str, used: set[str]) -> str:
    n = 1
    while f"{prefix}-{n:03d}" in used:
        n += 1
    return f"{prefix}-{n:03d}"


def same_value(a: str, b: str) -> bool:
    try:
        return abs(float(a.replace(",", "")) - float(b.replace(",", ""))) < 1e-9
    except ValueError:
        return a.strip() == b.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    ap.add_argument("--dir", help="CSV の置き場所（既定: <case>/roadmap）")
    ap.add_argument("--out", help="既定: <case>/08-kpi-roadmap.md（印の間だけ書き換える）")
    ap.add_argument("--assign-ids", action="store_true", help="id が空の KPI 目標に K- を振り、台帳に載せる")
    ap.add_argument("--fy-start-month", type=int, default=4, help="期首の月（既定 4 = 4 月始まり）")
    a = ap.parse_args()

    case = Path(a.case)
    d = Path(a.dir) if a.dir else case / "roadmap"
    years = list(range(FIRST_FY, LAST_FY + 1))
    ledger_p = case / "facts" / "facts.csv"
    lf, ledger = read_csv(ledger_p)
    by_id = {r["id"]: r for r in ledger}
    problems: list[str] = []
    pending: list[str] = []

    # ---- KPI 目標
    tf, targets = read_csv(d / "kpi-targets.csv")
    if a.assign_ids and targets:
        if not lf:
            print(f"エラー: {ledger_p} がないので K- を振れません", file=sys.stderr)
            return 2
        used = set(by_id)
        today = dt.date.today().isoformat()
        for t in targets:
            if (t.get("id") or "").strip():
                continue
            dfn, period = f"{t['kpi']}の目標", f"FY{fy_of(t['fiscal_year'])}"
            hit = next((r for r in ledger if r["definition"] == dfn and r["period"] == period), None)
            if hit:
                t["id"] = hit["id"]
                hit.update({"value": t["value"], "unit": t["unit"], "source_tag": t["source_tag"], "source": t["source"]})
            else:
                t["id"] = next_free("K", used)
                used.add(t["id"])
                row = {f: "" for f in lf}
                row.update({"id": t["id"], "value": t["value"], "unit": t["unit"], "definition": dfn, "period": period,
                            "source_tag": t["source_tag"], "source": t["source"], "retrieved_at": today,
                            "confidentiality": "公開"})
                if t["source_tag"] == "仮置き":
                    row["replace_by"] = (dt.date.today() + dt.timedelta(days=14)).isoformat()
                ledger.append(row)
                by_id[t["id"]] = row
        with ledger_p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=lf)
            w.writeheader()
            w.writerows(ledger)
        with (d / "kpi-targets.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=tf)
            w.writeheader()
            w.writerows(targets)
    kpis: dict[str, dict] = {}
    for t in targets:
        rid = (t.get("id") or "").strip()
        y = fy_of(t.get("fiscal_year", ""))
        k = kpis.setdefault(t["kpi"], {"unit": t.get("unit", ""), "cells": {}, "tags": set()})
        k["tags"].add(t.get("source_tag", ""))
        if not rid:
            problems.append(f"KPI 目標 {t['kpi']} FY{y}: id がない（--assign-ids で振る）")
        elif rid not in by_id:
            problems.append(f"KPI 目標 {t['kpi']} FY{y}: {rid} が台帳にない")
        elif not same_value(t["value"], by_id[rid]["value"]):
            problems.append(f"KPI 目標 {t['kpi']} FY{y}: 値 {t['value']} が台帳 {rid} の {by_id[rid]['value']} と違う")
        k["cells"][y] = (t["value"], rid)

    # ---- 矢羽
    _, arrows = read_csv(d / "arrows.csv")
    rows: dict[str, dict] = {}
    for r in arrows:
        s, e = fy_of(r.get("start", "")), fy_of(r.get("end", ""))
        iid = r["initiative_id"]
        if s is None or e is None or s > e:
            problems.append(f"矢羽 {iid} {r.get('phase')}: start/end を読めない")
            continue
        x = rows.setdefault(iid, {"name": r.get("initiative", ""), "cells": {y: [] for y in years}})
        for y in range(max(s, FIRST_FY), min(e, LAST_FY) + 1):
            if s == e:
                mark = f"【{r['phase']}】▶"
            elif y == s or y == FIRST_FY:
                mark = f"【{r['phase']}】"
            elif y == e:
                mark = "━━▶"
            else:
                mark = "━━━"
            x["cells"][y].append(mark)

    # ---- ゲート
    _, gates = read_csv(d / "gates.csv")
    for g in gates:
        name = g.get("gate") or "(名前なし)"
        miss = [c for c in GATE_REQUIRED if (g.get(c) or "").strip() in {"", DASH}]
        if miss:
            problems.append(f"ゲート {name}: 判定基準が欠けている（{', '.join(miss)}）")
        kid = (g.get("kpi_id") or "").strip()
        if kid and kid not in by_id:
            problems.append(f"ゲート {name}: {kid} が台帳にない（閾値は台帳の K- で持つ）")
        elif kid and (g.get("threshold") or "").strip() and not same_value(g["threshold"], by_id[kid]["value"]):
            problems.append(f"ゲート {name}: 閾値 {g['threshold']} が台帳 {kid} の値 {by_id[kid]['value']} と違う")
        try:
            gd = dt.date.fromisoformat((g.get("date") or "").strip())
            gy = fy_of_date(gd, a.fy_start_month)
            g["_fy"] = gy
            if not FIRST_FY <= gy <= LAST_FY:
                problems.append(f"ゲート {name}: 期日 {gd} が計画期間 FY{FIRST_FY}〜FY{LAST_FY} の外")
        except ValueError:
            g["_fy"] = None
            if "date" not in miss:
                problems.append(f"ゲート {name}: 期日は YYYY-MM-DD で書く")
        iid = (g.get("initiative_id") or "").strip()
        if iid and iid not in rows:
            problems.append(f"ゲート {name}: 施策 {iid} が矢羽にない")
        if iid in rows and g["_fy"] in rows[iid]["cells"]:
            rows[iid]["cells"][g["_fy"]].append(f"◆{name}")
        if not re.fullmatch(r"D-\d{3,}", (g.get("decision_id") or "").strip()):
            pending.append(f"ゲート {name}（{g.get('date') or DASH}）: 閾値と撤退基準を人が決め、decisions.md に D- で残す")

    # ---- Markdown
    L = [BEGIN, "", "<!-- render_roadmap.py が書く。この間は手で直さない -->", "", "### 年度別の KPI 目標", ""]
    L.append("| KPI | 単位 | " + " | ".join(f"FY{y}" for y in years) + " | 出典タグ |")
    L.append("|---|---|" + "---:|" * len(years) + "---|")
    for name, k in kpis.items():
        cells = []
        for y in years:
            v, rid = k["cells"].get(y, (DASH, ""))
            cells.append(f"{v} [{rid}]" if rid and v != DASH else v)
        L.append(f"| {name} | {k['unit']} | " + " | ".join(cells) + f" | {'・'.join(sorted(t for t in k['tags'] if t))} |")
    L += ["", "### 施策の矢羽（年単位）", "", "【フェーズ】で始まり ━━▶ で終わる。◆ はゲート。", ""]
    L.append("| 施策 | " + " | ".join(f"FY{y}" for y in years) + " |")
    L.append("|---|" + "---|" * len(years))
    for iid, x in rows.items():
        L.append(f"| {iid} {x['name']} | " + " | ".join(" ".join(x["cells"][y]) for y in years) + " |")
    L += ["", "### Go/No-Go ゲート", ""]
    L.append("| ゲート | 期日 | 施策 | 判定基準（指標・閾値・データの出どころ） | Go のとき | 撤退基準 | 決定 |")
    L.append("|---|---|---|---|---|---|---|")
    for g in gates:
        kid = (g.get("kpi_id") or "").strip()
        th = (g.get("threshold") or "").strip() or DASH
        crit = f"{g.get('metric') or DASH} {g.get('comparator') or ''} {th}{(g.get('unit') or '') if th != DASH else ''}{f' [{kid}]' if kid and th != DASH else ''}（{g.get('data_source') or DASH}）"
        L.append(f"| {g.get('gate')} | {g.get('date') or DASH} | {g.get('initiative_id') or DASH} | {crit} | "
                 f"{g.get('go_action') or DASH} | {g.get('exit_criteria') or DASH} | {g.get('decision_id') or '未決定'} |")
    L += ["", END]
    block = "\n".join(L)

    out = Path(a.out) if a.out else case / "08-kpi-roadmap.md"
    if out.exists() and BEGIN in out.read_text(encoding="utf-8") and END in out.read_text(encoding="utf-8"):
        text = out.read_text(encoding="utf-8")
        text = text[: text.index(BEGIN)] + block + text[text.index(END) + len(END):]
        out.write_text(text, encoding="utf-8")
        print(f"{out} の印の間を書き換えた\n")
    print(block)
    if problems:
        print(f"\n## 直すこと（{len(problems)} 件）\n")
        print("\n".join(f"- {p}" for p in problems))
    if pending:
        print(f"\n## 人が決めること（{len(pending)} 件）\n")
        print("\n".join(f"- {p}" for p in pending))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
