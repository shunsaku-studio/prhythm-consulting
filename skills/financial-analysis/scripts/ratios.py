#!/usr/bin/env python3
"""facts/financials.csv から財務比率を計算し、ROE と営業利益率の変化を要因に分ける。

計算すること（連結、年度ごと）:
  収益性  営業利益率、純利益率、ROE、ROA、ROIC
  効率性  総資産回転率
  安全性  自己資本比率、ネット有利子負債、ネット D/E レシオ
  CF     フリー CF（営業 CF − 設備投資）、設備投資 ÷ 減価償却費、配当性向
  分解   ROE = 純利益率 × 総資産回転率 × 財務レバレッジ（DuPont）
         2 時点の ROE の変化を 3 つの要因の寄与（pt）に分ける（対数で按分）
         2 時点の営業利益率の変化を、セグメントの構成（ミックス）・セグメント内の利益率・調整額に分ける
  セグメント  セグメント利益率、売上構成比（セグメント資産がないので ROIC は出さない）
  同業（任意） --peers の CSV（company,fiscal_year,item,value,unit,basis,source,note）から同じ比率

定義（仮置きを含む。台帳に載せる）:
  ROE・ROA・回転率・レバレッジは期首と期末の平均残高（期首がない年は期末）。--balance end で期末に切り替え
  ROIC = NOPAT ÷ 投下資本（期中平均）
    NOPAT = 営業利益 × (1 − 税率)          税率は --tax-rate（既定 30%、仮置き）
    投下資本 = 純資産 + 有利子負債 − 余剰現金
    余剰現金 = max(0, 現金及び預金 − 売上高 × 必要現金の月数 ÷ 12)  月数は --cash-months（既定 1、仮置き）
  純資産には非支配株主持分などが入る。ROE の分母を株主資本にしたいときは financials.csv に足して --equity-item で指定

使い方:
  python3 ratios.py case/facts/financials.csv --ledger case/facts/facts.csv --append \\
      --compare FY2021,FY2025 --out case/facts/financial-analysis.md --today 2026-10-30
  --register all で全年度の比率を台帳に載せる（既定は --compare の 2 時点だけ）

標準ライブラリだけで動く。Python 3.10 以上。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------- 台帳（facts.csv）
LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]


class Ledger:
    """facts.csv の読み書き。同じ定義・期間・単位の行があれば ID を使い回す。"""

    def __init__(self, path: Path | None, today: str) -> None:
        self.path = path
        self.today = today
        self.rows: list[dict[str, str]] = []
        self.new: list[dict[str, str]] = []
        self.warnings: list[str] = []
        if path and path.exists():
            with path.open(encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def all_rows(self) -> list[dict[str, str]]:
        return self.rows + self.new

    def has(self, rid: str) -> bool:
        return any(r["id"] == rid for r in self.all_rows())

    def next_id(self, prefix: str) -> str:
        used = {r["id"] for r in self.all_rows()}
        n = 1
        while f"{prefix}-{n:03d}" in used:
            n += 1
        return f"{prefix}-{n:03d}"

    def register(self, prefix: str, value: str, unit: str, definition: str, period: str,
                 tag: str, source: str, confidentiality: str = "公開", replace_by: str = "") -> str:
        for r in self.all_rows():
            if (r["definition"], r["period"], r["unit"]) == (definition, period, unit) and r["id"].startswith(prefix + "-"):
                if _same(r["value"], value):
                    return r["id"]
                self.warnings.append(f"{r['id']}（{definition} {period}）は台帳の値 {r['value']} と今回の値 {value} が違う。新しい ID で登録した")
        rid = self.next_id(prefix)
        self.new.append({
            "id": rid, "value": value, "unit": unit, "definition": definition, "period": period,
            "source_tag": tag, "source": source, "retrieved_at": self.today,
            "confidentiality": confidentiality, "replace_by": replace_by if tag == "仮置き" else "",
        })
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


def _same(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return a == b


# ---------------------------------------------------------------- 項目の読み替え
ALIASES = {
    "sales": ["売上高", "売上収益"],
    "op": ["営業利益"],
    "ni": ["親会社株主に帰属する当期純利益", "親会社の所有者に帰属する当期利益"],
    "assets": ["総資産", "資産合計"],
    "equity": ["純資産", "親会社の所有者に帰属する持分"],
    "cash": ["現金及び預金", "現金及び現金同等物"],
    "debt": ["有利子負債"],
    "ocf": ["営業活動によるキャッシュ・フロー"],
    "capex": ["設備投資額", "有形固定資産の取得による支出"],
    "dep": ["減価償却費"],
    "ma": ["子会社株式の取得による支出"],
    "div": ["配当金の支払額"],
    "seg_profit": ["セグメント利益"],
    "adj": ["調整額（全社費用）", "調整額"],
}
DEBT_PARTS = ["短期借入金", "長期借入金", "社債", "コマーシャル・ペーパー", "リース債務"]
TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0}
DISCONT_RE = re.compile(r"組み?替|移管|再編|会計基準|会計方針の変更|遡及")


def fy_n(fy: str) -> int:
    m = re.search(r"(\d{4})", fy)
    return int(m.group(1)) if m else 0


def r2(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}"


def fmt(x: float | None, nd: int = 1) -> str:
    return "—" if x is None else f"{x:,.{nd}f}"


class Val:
    """値と台帳 ID（ID がなければ None）"""

    def __init__(self, v: float, rid: str | None) -> None:
        self.v = v
        self.id = rid


class Fin:
    def __init__(self, rows: list[dict[str, str]], unit: str, equity_item: str | None) -> None:
        self.unit = unit
        self.data: dict[tuple[str, str, str], Val] = {}
        self.notes: dict[str, list[str]] = defaultdict(list)
        if equity_item:
            ALIASES["equity"] = [equity_item]
        for r in rows:
            try:
                v = float(r["value"])
            except ValueError:
                continue
            if r["unit"] in TO_OKU and unit in TO_OKU:
                v = v * TO_OKU[r["unit"]] / TO_OKU[unit]
            self.data[(r["fiscal_year"], r["segment"], r["item"])] = Val(v, r["id"])
            if r.get("note") and DISCONT_RE.search(r["note"]):
                self.notes[r["fiscal_year"]].append(f"{r['segment']} {r['item']}: {r['note']}")
        self.years = sorted({k[0] for k in self.data}, key=fy_n)
        self.segments = sorted({k[1] for k in self.data if k[1] not in ("連結", "調整額", "単体")})

    def get(self, fy: str, key: str, seg: str = "連結") -> Val | None:
        for item in ALIASES.get(key, [key]):
            v = self.data.get((fy, seg, item))
            if v is not None:
                return v
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("financials", type=Path, help="facts/financials.csv")
    ap.add_argument("--company", default="対象企業")
    ap.add_argument("--unit", default="億円", choices=["億円", "百万円"], help="金額の表示単位")
    ap.add_argument("--balance", default="avg", choices=["avg", "end"], help="残高を期中平均にするか期末にするか")
    ap.add_argument("--tax-rate", type=float, default=30.0, help="NOPAT の税率 %%（仮置き）")
    ap.add_argument("--tax-rate-id", help="税率の台帳 ID（実効税率を登録済みのとき）")
    ap.add_argument("--cash-months", type=float, default=1.0, help="事業に要る現金（月商の何か月分か。仮置き）")
    ap.add_argument("--cash-months-id")
    ap.add_argument("--equity-item", help="ROE の分母に使う項目名（既定: 純資産）")
    ap.add_argument("--compare", help="要因分解する 2 時点 FY2021,FY2025（既定: 最初と最後の年）")
    ap.add_argument("--register", default="compare", help="台帳に載せる年度: compare / all / FY2024,FY2025")
    ap.add_argument("--peers", type=Path, help="同業の CSV（company,fiscal_year,item,value,unit,basis,source,note）")
    ap.add_argument("--peer-year", help="同業比較の年度（既定: 最新）")
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--replace-by", help="仮置きの差し替え期限（既定: 今日 + 14 日）")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.today)
    replace_by = a.replace_by or (today + dt.timedelta(days=14)).isoformat()
    with a.financials.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fin = Fin(rows, a.unit, a.equity_item)
    led = Ledger(a.ledger, a.today)
    u = a.unit
    co = a.company
    years = fin.years
    if a.compare:
        y0, y1 = [s.strip() for s in a.compare.split(",")]
    else:
        y0, y1 = years[0], years[-1]
    if a.register == "all":
        reg_years = set(years)
    elif a.register == "compare":
        reg_years = {y0, y1}
    else:
        reg_years = {s.strip() for s in a.register.split(",")}
    notes: list[str] = []

    # 入力 ID が台帳にあるか（推定の計算式が参照する）
    if a.ledger:
        missing = {v.id for v in fin.data.values() if v.id and not led.has(v.id)}
        if missing:
            notes.append(f"financials.csv の ID {len(missing)} 件が台帳にない（例: {sorted(missing)[0]}）。company-financials を --ledger 付きで再実行する")

    # 仮置きの前提
    if a.tax_rate_id:
        tax_id = a.tax_rate_id
    else:
        tax_id = led.register("F", r2(a.tax_rate, 1), "%", "NOPAT の計算に使う税率（法定実効税率の近似）", "—", "仮置き", "—", replace_by=replace_by)
    if a.cash_months_id:
        cm_id = a.cash_months_id
    else:
        cm_id = led.register("F", r2(a.cash_months, 1), "か月", "事業に要る現金（月商の何か月分か。余剰現金の計算用）", "—", "仮置き", "—", replace_by=replace_by)

    def reg(fy: str, value: float | None, unit: str, label: str, formula: str, nd: int = 2) -> str | None:
        if value is None or fy not in reg_years:
            return None
        return led.register("F", r2(value, nd), unit, f"{co} 連結 {label}", fy, "推定", formula)

    def cell(value: float | None, rid: str | None, nd: int = 1, suffix: str = "") -> str:
        if value is None:
            return "—"
        return f"{fmt(value, nd)}{suffix} [{rid}]" if rid else f"{fmt(value, nd)}"

    def bal(fy: str, key: str) -> tuple[float, str] | None:
        """期中平均（または期末）の残高と、計算式に書く ID 表現"""
        cur = fin.get(fy, key)
        if cur is None:
            return None
        if a.balance == "avg":
            i = years.index(fy)
            prev = fin.get(years[i - 1], key) if i > 0 else None
            if prev is not None:
                return (cur.v + prev.v) / 2, f"avg({prev.id},{cur.id})"
        return cur.v, f"{cur.id}"

    # 有利子負債がなければ借入金・社債の合計で作る
    for fy in years:
        if fin.get(fy, "debt") is None:
            parts = [fin.data.get((fy, "連結", p)) for p in DEBT_PARTS]
            parts = [p for p in parts if p is not None]
            if parts:
                v = sum(p.v for p in parts)
                rid = led.register("F", r2(v, 1), u, f"{co} 連結 有利子負債（{'＋'.join(DEBT_PARTS)}のうちあるもの）", fy, "推定", "+".join(p.id for p in parts))
                fin.data[(fy, "連結", "有利子負債")] = Val(v, rid)
                notes.append(f"{fy} の有利子負債は借入金・社債の合計で作った（リース債務の扱いを確かめる）")

    res: dict[str, dict[str, tuple[float | None, str | None]]] = defaultdict(dict)
    for fy in years:
        s, op, ni = fin.get(fy, "sales"), fin.get(fy, "op"), fin.get(fy, "ni")
        eq, assets, cash, debt = fin.get(fy, "equity"), fin.get(fy, "assets"), fin.get(fy, "cash"), fin.get(fy, "debt")
        R = res[fy]
        if s and op:
            v = op.v / s.v * 100
            R["opm"] = (v, reg(fy, v, "%", "営業利益率", f"{op.id}/{s.id}"))
        if s and ni:
            v = ni.v / s.v * 100
            R["npm"] = (v, reg(fy, v, "%", "純利益率（親会社株主に帰属する当期純利益 ÷ 売上）", f"{ni.id}/{s.id}"))
        be, ba = bal(fy, "equity"), bal(fy, "assets")
        bl = "期中平均" if a.balance == "avg" else "期末"
        if ni and be:
            v = ni.v / be[0] * 100
            R["roe"] = (v, reg(fy, v, "%", f"ROE（{bl}純資産）", f"{ni.id}/{be[1]}"))
        if ni and ba:
            v = ni.v / ba[0] * 100
            R["roa"] = (v, reg(fy, v, "%", f"ROA（純利益 ÷ {bl}総資産）", f"{ni.id}/{ba[1]}"))
        if s and ba:
            v = s.v / ba[0]
            R["turn"] = (v, reg(fy, v, "倍", f"総資産回転率（売上 ÷ {bl}総資産）", f"{s.id}/{ba[1]}", 3))
        if ba and be:
            v = ba[0] / be[0]
            R["lev"] = (v, reg(fy, v, "倍", f"財務レバレッジ（{bl}総資産 ÷ {bl}純資産）", f"{ba[1]}/{be[1]}", 3))
        if eq and assets:
            v = eq.v / assets.v * 100
            R["eqr"] = (v, reg(fy, v, "%", "自己資本比率（純資産 ÷ 総資産、期末）", f"{eq.id}/{assets.id}"))
        if debt and cash:
            v = debt.v - cash.v
            nd_id = reg(fy, v, u, "ネット有利子負債（有利子負債 − 現金及び預金、期末）", f"{debt.id}-{cash.id}", 1)
            R["netdebt"] = (v, nd_id)
            if eq:
                v2 = v / eq.v
                R["nde"] = (v2, reg(fy, v2, "倍", "ネット D/E レシオ（ネット有利子負債 ÷ 純資産、期末）", f"({debt.id}-{cash.id})/{eq.id}", 3))
        # ROIC
        if op and s and eq and debt and cash:
            nopat = op.v * (1 - a.tax_rate / 100)
            R["nopat"] = (nopat, reg(fy, nopat, u, "NOPAT（営業利益 × (1 − 税率)）", f"{op.id}×(1-{tax_id})", 1))

            def ic_of(y: str) -> tuple[float, str] | None:
                e_, d_, c_, s_ = fin.get(y, "equity"), fin.get(y, "debt"), fin.get(y, "cash"), fin.get(y, "sales")
                if not (e_ and d_ and c_ and s_):
                    return None
                excess = max(0.0, c_.v - s_.v * a.cash_months / 12)
                return e_.v + d_.v - excess, f"({e_.id}+{d_.id}-max(0,{c_.id}-{s_.id}×{cm_id}/12))"
            ic = ic_of(fy)
            R["ic"] = (ic[0], reg(fy, ic[0], u, "投下資本（純資産 + 有利子負債 − 余剰現金、期末）", ic[1], 1))
            i = years.index(fy)
            icp = ic_of(years[i - 1]) if (a.balance == "avg" and i > 0) else None
            ic_avg, ic_f = ((ic[0] + icp[0]) / 2, f"avg({icp[1]},{ic[1]})") if icp else ic
            v = nopat / ic_avg * 100
            R["roic"] = (v, reg(fy, v, "%", f"ROIC（NOPAT ÷ {'期中平均' if icp else '期末'}投下資本。税率・余剰現金は仮置き）", f"{op.id}×(1-{tax_id})/{ic_f}"))
        ocf, capex, dep, div, ma = fin.get(fy, "ocf"), fin.get(fy, "capex"), fin.get(fy, "dep"), fin.get(fy, "div"), fin.get(fy, "ma")
        if ocf and capex:
            v = ocf.v - capex.v
            R["fcf"] = (v, reg(fy, v, u, "フリー CF（営業 CF − 設備投資額。M&A は含めない）", f"{ocf.id}-{capex.id}", 1))
        if capex and dep and dep.v:
            v = capex.v / dep.v
            R["capdep"] = (v, reg(fy, v, "倍", "設備投資額 ÷ 減価償却費", f"{capex.id}/{dep.id}", 3))
        if div and ni and ni.v:
            v = div.v / ni.v * 100
            R["payout"] = (v, reg(fy, v, "%", "配当性向（配当金の支払額 ÷ 純利益。CF ベースの近似）", f"{div.id}/{ni.id}"))
        if ma and ma.v > 0:
            notes.append(f"{fy} に子会社株式の取得 {fmt(ma.v)} {u} [{ma.id}] がある。前後の比率の変化に買収の影響が入る")

    out: list[str] = []
    P = out.append
    P(f"# {co} 財務分析（連結）")
    P("")
    P(f"- 入力: {a.financials.name}（{years[0]}〜{years[-1]}）")
    P(f"- 残高: {'期首と期末の平均（期首がない年は期末）' if a.balance == 'avg' else '期末'}")
    P(f"- 台帳に載せた年度: {', '.join(sorted(reg_years, key=fy_n))}（ID のない値は推移を見るための参考。上に出すなら --register に年度を足して再実行）")
    P("")

    def table(title: str, keys: list[tuple[str, str, int, str]]) -> None:
        P(f"## {title}")
        P("")
        P("| 指標 | " + " | ".join(years) + " |")
        P("|------|" + "|".join("------" for _ in years) + "|")
        for k, label, nd, suf in keys:
            if not any(k in res[y] for y in years):
                continue
            cells = [cell(res[y][k][0], res[y][k][1], nd, suf) if k in res[y] else "—" for y in years]
            P(f"| {label} | " + " | ".join(cells) + " |")
        P("")

    table("1. 収益性", [("opm", "営業利益率 %", 1, "%"), ("npm", "純利益率 %", 1, "%"), ("roe", "ROE %", 1, "%"),
                      ("roa", "ROA %", 1, "%"), ("roic", "ROIC %（仮置きあり）", 1, "%")])
    table("2. 効率性と DuPont 分解（ROE = 純利益率 × 総資産回転率 × 財務レバレッジ）",
          [("npm", "純利益率 %", 2, "%"), ("turn", "総資産回転率 倍", 3, "倍"), ("lev", "財務レバレッジ 倍", 3, "倍"), ("roe", "ROE %", 2, "%")])
    table("3. 安全性", [("eqr", "自己資本比率 %", 1, "%"), ("netdebt", f"ネット有利子負債 {u}", 1, f" {u}"), ("nde", "ネット D/E 倍", 2, "倍")])
    table("4. キャッシュ・フローと投資", [("fcf", f"フリー CF {u}", 1, f" {u}"), ("capdep", "設備投資 ÷ 減価償却 倍", 2, "倍"), ("payout", "配当性向 %", 1, "%")])

    # ------------------------------------------------ 要因分解
    P(f"## 5. 要因分解（{y0} → {y1}）")
    P("")
    span = [y for y in years if fy_n(y0) < fy_n(y) <= fy_n(y1)]
    disc = [f"{y}: {n}" for y in span for n in fin.notes.get(y, [])]
    if disc:
        P("> 比べる期間に不連続がある。セグメントの比較は組み替え後の定義で読み直すこと。")
        for d_ in sorted(set(disc)):
            P(f"> - {d_}")
        P("")
    r0, r1 = res.get(y0, {}), res.get(y1, {})
    if all(k in r0 and k in r1 for k in ("npm", "turn", "lev", "roe")):
        P("### 5-1. ROE の変化の内訳（対数で按分）")
        P("")
        d_roe = r1["roe"][0] - r0["roe"][0]
        logs = {k: math.log(r1[k][0] / r0[k][0]) for k in ("npm", "turn", "lev")}
        tot = sum(logs.values())
        P("| 要因 | " + f"{y0} | {y1} | ROE 変化への寄与 |")
        P("|------|------|------|----------------|")
        labels = {"npm": ("純利益率", "%", 2), "turn": ("総資産回転率", "倍", 3), "lev": ("財務レバレッジ", "倍", 3)}
        for k, (lab, un, nd) in labels.items():
            c = d_roe * logs[k] / tot if tot else 0.0
            ids = [i for i in (r0[k][1], r1[k][1], r0["roe"][1], r1["roe"][1]) if i]
            cid = led.register("F", r2(c, 2), "pt", f"{co} 連結 ROE 変化のうち{lab}の寄与（対数按分）", f"{y0}-{y1}", "推定",
                               f"({ids[3]}-{ids[2]})×ln({ids[1]}/{ids[0]})/Σln" if len(ids) == 4 else "—") if len(ids) == 4 else None
            P(f"| {lab} | {cell(r0[k][0], r0[k][1], nd, un if un == '倍' else '%')} | {cell(r1[k][0], r1[k][1], nd, un if un == '倍' else '%')} | {cell(c, cid, 2, 'pt')} |")
        P(f"| ROE | {cell(r0['roe'][0], r0['roe'][1], 2, '%')} | {cell(r1['roe'][0], r1['roe'][1], 2, '%')} | — |")
        P("")
    # 営業利益率のミックス分解
    segs = [s_ for s_ in fin.segments if fin.get(y0, "sales", s_) and fin.get(y1, "sales", s_)
            and fin.get(y0, "seg_profit", s_) and fin.get(y1, "seg_profit", s_)]
    s0, s1 = fin.get(y0, "sales"), fin.get(y1, "sales")
    if segs and s0 and s1 and "opm" in r0 and "opm" in r1:
        P("### 5-2. 営業利益率の変化の内訳（セグメントの構成と利益率）")
        P("")
        P("| セグメント | 構成比 " + y0 + " | 構成比 " + y1 + " | 利益率 " + y0 + " | 利益率 " + y1 + " | 構成の効果 | 利益率の効果 |")
        P("|-----------|------|------|------|------|----------|------------|")
        mix_t = rate_t = 0.0
        for s_ in segs:
            a0, a1 = fin.get(y0, "sales", s_), fin.get(y1, "sales", s_)
            p0, p1 = fin.get(y0, "seg_profit", s_), fin.get(y1, "seg_profit", s_)
            w0, w1 = a0.v / s0.v, a1.v / s1.v
            m0, m1 = p0.v / a0.v * 100, p1.v / a1.v * 100
            mix = (w1 - w0) * m0
            rate = w1 * (m1 - m0)
            mix_t += mix
            rate_t += rate
            ids = {}
            for nm, val, f_, un in (("w0", w0 * 100, f"{a0.id}/{s0.id}", "%"), ("w1", w1 * 100, f"{a1.id}/{s1.id}", "%"),
                                    ("m0", m0, f"{p0.id}/{a0.id}", "%"), ("m1", m1, f"{p1.id}/{a1.id}", "%")):
                per = y0 if nm.endswith("0") else y1
                lab = "売上構成比" if nm.startswith("w") else "セグメント利益率"
                ids[nm] = led.register("F", r2(val, 2), un, f"{co} {s_} {lab}", per, "推定", f_)
            mix_id = led.register("F", r2(mix, 2), "pt", f"{co} 連結営業利益率の変化のうち {s_} の構成の効果", f"{y0}-{y1}", "推定",
                                  f"({ids['w1']}-{ids['w0']})×{ids['m0']}")
            rate_id = led.register("F", r2(rate, 2), "pt", f"{co} 連結営業利益率の変化のうち {s_} の利益率の効果", f"{y0}-{y1}", "推定",
                                   f"{ids['w1']}×({ids['m1']}-{ids['m0']})")
            P(f"| {s_} | {fmt(w0 * 100)}% [{ids['w0']}] | {fmt(w1 * 100)}% [{ids['w1']}] | {fmt(m0)}% [{ids['m0']}] | {fmt(m1)}% [{ids['m1']}] | {fmt(mix, 2)}pt [{mix_id}] | {fmt(rate, 2)}pt [{rate_id}] |")
        adj0, adj1 = fin.get(y0, "adj", "調整額"), fin.get(y1, "adj", "調整額")
        other = (r1["opm"][0] - r0["opm"][0]) - mix_t - rate_t
        o_ids = [i for i in (r0["opm"][1], r1["opm"][1]) if i]
        oid = led.register("F", r2(other, 2), "pt", f"{co} 連結営業利益率の変化のうち調整額（全社費用）と端数", f"{y0}-{y1}", "推定",
                           f"({o_ids[1]}-{o_ids[0]})-Σ構成の効果-Σ利益率の効果") if len(o_ids) == 2 else None
        P(f"| 調整額ほか | — | — | — | — | — | {cell(other, oid, 2, 'pt')} |")
        mt_id = led.register("F", r2(mix_t, 2), "pt", f"{co} 連結営業利益率の変化のうち構成の効果の合計", f"{y0}-{y1}", "推定", "Σ各セグメントの構成の効果")
        rt_id = led.register("F", r2(rate_t, 2), "pt", f"{co} 連結営業利益率の変化のうち利益率の効果の合計", f"{y0}-{y1}", "推定", "Σ各セグメントの利益率の効果")
        P(f"| 合計（営業利益率の変化） | — | — | {cell(r0['opm'][0], r0['opm'][1], 2, '%')} | {cell(r1['opm'][0], r1['opm'][1], 2, '%')} | {fmt(mix_t, 2)}pt [{mt_id}] | {fmt(rate_t, 2)}pt [{rt_id}] |")
        P("")
        if adj0 is None and adj1 is None:
            notes.append("調整額（全社費用）が financials.csv にない。セグメント利益の合計と連結営業利益の差はまとめて「調整額ほか」に入れた")
    # セグメントの推移
    if fin.segments:
        P("## 6. セグメント別の利益率と構成比")
        P("")
        P("| セグメント | 指標 | " + " | ".join(years) + " |")
        P("|-----------|------|" + "|".join("------" for _ in years) + "|")
        for s_ in fin.segments:
            mrow, wrow = [], []
            for y in years:
                a_, p_, t_ = fin.get(y, "sales", s_), fin.get(y, "seg_profit", s_), fin.get(y, "sales")
                mrow.append(fmt(p_.v / a_.v * 100) if a_ and p_ else "—")
                wrow.append(fmt(a_.v / t_.v * 100) if a_ and t_ else "—")
            P(f"| {s_} | 利益率 % | " + " | ".join(mrow) + " |")
            P(f"| {s_} | 構成比 % | " + " | ".join(wrow) + " |")
        P("")
        P("セグメント資産と負債が開示にないため、セグメント別の ROIC は出していない（—）。出すなら、セグメント資産の開示か、社内データ（インサイドアウト）が要る。")
        P("")

    # ------------------------------------------------ 同業
    if a.peers:
        with a.peers.open(encoding="utf-8") as f:
            prow = list(csv.DictReader(f))
        py = a.peer_year or max((r["fiscal_year"] for r in prow if re.fullmatch(r"FY\d{4}", r["fiscal_year"])), key=fy_n)
        P(f"## 7. 同業との比較（{py}、期末残高）")
        P("")
        P("| 会社 | 会計基準 | 売上 | 営業利益率 | ROE（期末） | 自己資本比率 | 定義の注意 |")
        P("|------|---------|------|-----------|-----------|------------|-----------|")
        comp: dict[str, dict[str, tuple[float, str, str]]] = defaultdict(dict)
        basis: dict[str, str] = {}
        cautions: dict[str, list[str]] = defaultdict(list)
        for r in prow:
            if r["fiscal_year"] != py:
                continue
            try:
                v = float(r["value"])
            except ValueError:
                continue
            if r["unit"] in TO_OKU:
                v = v * TO_OKU[r["unit"]] / TO_OKU[u]
            unit = u if r["unit"] in TO_OKU else r["unit"]
            rid = led.register("F", r2(v, 1), unit, f"{r['company']} {r['item']}（{r['basis']}）", py, "公開", r["source"])
            comp[r["company"]][r["item"]] = (v, rid, r.get("note", ""))
            basis[r["company"]] = r["basis"]
            if r.get("note"):
                cautions[r["company"]].append(f"{r['item']}: `{r['note']}`")
        own = {"売上高": fin.get(py, "sales"), "営業利益": fin.get(py, "op"), "純利益": fin.get(py, "ni"),
               "純資産": fin.get(py, "equity"), "総資産": fin.get(py, "assets")}
        if all(own.values()):
            opm = own["営業利益"].v / own["売上高"].v * 100
            roe = own["純利益"].v / own["純資産"].v * 100
            eqr = own["純資産"].v / own["総資産"].v * 100
            i1 = led.register("F", r2(opm, 2), "%", f"{co} 連結 営業利益率", py, "推定", f"{own['営業利益'].id}/{own['売上高'].id}")
            i2 = led.register("F", r2(roe, 2), "%", f"{co} 連結 ROE（期末純資産）", py, "推定", f"{own['純利益'].id}/{own['純資産'].id}")
            i3 = led.register("F", r2(eqr, 2), "%", f"{co} 連結 自己資本比率（純資産 ÷ 総資産、期末）", py, "推定", f"{own['純資産'].id}/{own['総資産'].id}")
            P(f"| {co} | — | {fmt(own['売上高'].v, 0)} {u} [{own['売上高'].id}] | {fmt(opm)}% [{i1}] | {fmt(roe)}% [{i2}] | {fmt(eqr)}% [{i3}] | — |")

        def pick(d: dict, names: list[str]):
            return next((d[n] for n in names if n in d), None)
        for c, d in comp.items():
            sv = pick(d, ["売上高", "売上収益"])
            ov = pick(d, ["営業利益"])
            nv = pick(d, ["親会社株主に帰属する当期純利益", "親会社の所有者に帰属する当期利益"])
            ev = pick(d, ["純資産", "親会社の所有者に帰属する持分"])
            av = pick(d, ["総資産", "資産合計"])
            cells = [f"{fmt(sv[0], 0)} {u} [{sv[1]}]" if sv else "—"]
            for num, den, lab in ((ov, sv, "営業利益率"), (nv, ev, "ROE（期末）"), (ev, av, "自己資本比率")):
                if num and den and den[0]:
                    v = num[0] / den[0] * 100
                    rid = led.register("F", r2(v, 2), "%", f"{c} {lab}", py, "推定", f"{num[1]}/{den[1]}")
                    cells.append(f"{fmt(v)}% [{rid}]")
                else:
                    cells.append("—")
            caut = []
            if basis.get(c) != "日本基準":
                caut.append(f"{basis.get(c)}。純資産は親会社の所有者に帰属する持分（非支配持分を含まない）")
            caut += cautions.get(c, [])
            P(f"| {c} | {basis.get(c, '—')} | " + " | ".join(cells) + f" | {'／'.join(caut) or '—'} |")
        P("")
        P("会計基準や利益の定義が違う数字は同じ列に並べても比べられない。注意の列を読んでから比べる。詳しい比較は competitor-benchmark で行う。")
        P("")

    P("## 前提と未確認事項（スクリプトが置いた前提）")
    P("")
    P(f"- NOPAT の税率 {fmt(a.tax_rate)}% [{tax_id}] は仮置き。有報の税効果会計の注記にある法定実効税率で差し替える")
    P(f"- 余剰現金は、現金及び預金のうち月商 {fmt(a.cash_months)} か月 [{cm_id}] を超える分とした（仮置き）。投下資本と ROIC はこの前提で動く")
    P("- 純資産を ROE の分母にした（非支配株主持分などを含む）。会社の開示する ROE と少しずれることがある")
    P("- 配当性向は CF 計算書の配当金の支払額で近似した。会社の開示値（1 株配当 ÷ 1 株利益）とは時期がずれる")
    for n in sorted(set(notes)):
        P(f"- {n}")
    for wmsg in led.warnings:
        P(f"- {wmsg}")
    P("- 比率の変化の理由（価格、数量、コスト、為替、買収、組み替え）はこの表からは分からない。要因の表を起点に、有報の MD&A と説明会資料で確かめる")
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
