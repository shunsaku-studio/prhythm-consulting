#!/usr/bin/env python3
"""中計の目標と実績を突き合わせ、達成率・進捗率・M&A を除いた目標との差を出す。

入力 CSV（UTF-8、1 行 1 指標）:
  metric,unit,base_year,base_value,target_year,target_value,actual_value,ma_included,source_target,source_actual,note
  - unit: 億円 / 百万円 / % / 倍 など（% の指標は差を pt で出す）
  - ma_included: 目標に含まれる M&A の上積み（同じ単位。なければ空）
  - 分からない値は — か空のまま（計算せずに — を出す）

出力:
  Markdown の表（目標・実績・達成率・進捗率・オーガニック目標との差）と、台帳に追記する行
  目標・実績・基準は「公開」、計算した値は「推定」で登録する（すべて F-）

使い方:
  python3 plan_check.py plan.csv --plan-name "Hokushin Vision 2025" --company 北辰工業 \\
      --ledger case/facts/facts.csv --append --out /tmp/plan-check.md --today 2026-10-30

標準ライブラリだけで動く。Python 3.10 以上。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]


class Ledger:
    """facts.csv の読み書き。同じ定義・期間・単位の行があれば ID を使い回す。"""

    def __init__(self, path: Path | None, today: str) -> None:
        self.path = path
        self.today = today
        self.rows: list[dict[str, str]] = []
        self.new: list[dict[str, str]] = []
        if path and path.exists():
            with path.open(encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def next_id(self, prefix: str) -> str:
        used = {r["id"] for r in self.rows + self.new}
        n = 1
        while f"{prefix}-{n:03d}" in used:
            n += 1
        return f"{prefix}-{n:03d}"

    def register(self, value: str, unit: str, definition: str, period: str, tag: str, source: str) -> str:
        for r in self.rows + self.new:
            if (r["definition"], r["period"], r["unit"], r["value"]) == (definition, period, unit, value) and r["id"].startswith("F-"):
                return r["id"]
        rid = self.next_id("F")
        self.new.append({"id": rid, "value": value, "unit": unit, "definition": definition, "period": period,
                         "source_tag": tag, "source": source, "retrieved_at": self.today,
                         "confidentiality": "公開", "replace_by": ""})
        return rid

    def write(self) -> None:
        if not self.path or not self.new:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.path.exists() and self.path.stat().st_size > 0
        with self.path.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS)
            if not exists:
                w.writeheader()
            w.writerows(self.new)


def num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if s in ("", "—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def raw(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def fmt(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan_csv", type=Path)
    ap.add_argument("--plan-name", default="中期経営計画")
    ap.add_argument("--company", default="対象企業")
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    led = Ledger(a.ledger, a.today)
    with a.plan_csv.open(encoding="utf-8-sig") as f:
        plan = list(csv.DictReader(f))

    out: list[str] = []
    P = out.append
    P(f"# {a.company}「{a.plan_name}」目標と実績の突き合わせ")
    P("")
    P("| 指標 | 基準 | 目標 | うち M&A | 実績 | 達成率 | 目標との差 | 進捗率 | オーガニック目標との差 |")
    P("|------|------|------|---------|------|-------|-----------|-------|--------------------|")
    notes: list[str] = []
    for r in plan:
        m, u = r["metric"].strip(), r["unit"].strip()
        pct = u in ("%", "％")
        du = "pt" if pct else u
        by, ty = r["base_year"].strip(), r["target_year"].strip()
        b, t, ac, ma = num(r["base_value"]), num(r["target_value"]), num(r["actual_value"]), num(r.get("ma_included"))
        pre = f"{a.company} {m}"
        bid = led.register(raw(b), u, f"{pre}（{a.plan_name} の基準年実績）", by, "公開", r["source_target"]) if b is not None else None
        tid = led.register(raw(t), u, f"{pre}の目標（{a.plan_name}）", ty, "公開", r["source_target"]) if t is not None else None
        aid = led.register(raw(ac), u, f"{pre}の実績（{a.plan_name} 最終年度）", ty, "公開", r["source_actual"]) if ac is not None else None
        mid = led.register(raw(ma), u, f"{pre}の目標に含まれる M&A の上積み（{a.plan_name}）", ty, "公開", r["source_target"]) if ma is not None else None

        def c(v: float | None, rid: str | None, unit: str, nd: int = 1) -> str:
            if v is None:
                return "—"
            sp = "" if unit in ("%", "pt", "倍") else " "
            return f"{fmt(v, nd)}{sp}{unit} [{rid}]"

        ach = gap = prog = ogap = None
        ach_c = gap_c = prog_c = ogap_c = "—"
        if t and ac is not None:
            ach = ac / t * 100
            ach_c = c(ach, led.register(raw(ach), "%", f"{pre}の達成率（実績 ÷ 目標）", ty, "推定", f"{aid}/{tid}"), "%")
            gap = ac - t
            gap_c = c(gap, led.register(raw(gap), du, f"{pre}の目標との差（実績 − 目標）", ty, "推定", f"{aid}-{tid}"), du)
        if b is not None and t is not None and ac is not None and t != b:
            prog = (ac - b) / (t - b) * 100
            prog_c = c(prog, led.register(raw(prog), "%", f"{pre}の進捗率（(実績 − 基準) ÷ (目標 − 基準)）", ty, "推定", f"({aid}-{bid})/({tid}-{bid})"), "%")
        if ma is not None and t is not None and ac is not None:
            org = t - ma
            org_id = led.register(raw(org), u, f"{pre}のオーガニック目標（目標 − M&A の上積み）", ty, "推定", f"{tid}-{mid}")
            ogap = ac - org
            ogap_c = c(ogap, led.register(raw(ogap), du, f"{pre}のオーガニック目標との差（実績 − オーガニック目標）", ty, "推定", f"{aid}-{org_id}"), du)
            notes.append(f"{m}: 目標 {fmt(t)} {u} [{tid}] は M&A の上積み {fmt(ma)} {u} [{mid}] を含む。オーガニック目標は {fmt(org)} {u} [{org_id}]")
        if t is None or ac is None:
            notes.append(f"{m}: 目標か実績が — のため、達成率を出していない")
        P(f"| {m} | {c(b, bid, u)} | {c(t, tid, u)} | {c(ma, mid, u)} | {c(ac, aid, u)} | {ach_c} | {gap_c} | {prog_c} | {ogap_c} |")
        if r.get("note", "").strip():
            notes.append(f"{m}: `{r['note'].strip()}`")
    P("")
    P("## 前提と未確認事項（スクリプトが置いた前提）")
    P("")
    P("- 達成率は 実績 ÷ 目標、進捗率は 基準から目標までのうち実績で進んだ割合。% の指標の差は pt で出した")
    P("- 目標の定義（連結か、M&A 込みか、為替前提）と実績の定義が同じかは、このスクリプトでは確かめない。資料の注記で確かめる")
    for n in notes:
        P(f"- {n}")
    P("")
    text = "\n".join(out)
    print(text)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n", encoding="utf-8")
    if a.ledger and a.append:
        led.write()
        print(f"<!-- 台帳 {a.ledger} に {len(led.new)} 行を追記した -->", file=sys.stderr)
    elif led.new:
        print(f"<!-- 台帳に追記する予定の行: {len(led.new)}（--ledger と --append で追記） -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
