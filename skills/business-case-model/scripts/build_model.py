#!/usr/bin/env python3
"""ドライバーと施策から、年次のビジネスケース・モデルを組む。

読むもの:
  <case>/model/inputs.csv      id,label,value,unit,source_tag,key（key はドライバーの機械名）
  <case>/05-initiatives.csv    id,initiative,year,revenue,investment,unit,confidence
  <case>/facts/facts.csv       ファクト台帳（入力値の照合と、結果の登録に使う）

書くもの:
  <case>/model/model.csv           年次の計算結果（縦持ち。主要な行だけ id を持つ）
  <case>/model/business-case.xlsx  inputs シート（値・単位・ID・出典タグ）と、
                                   inputs のセルだけを参照する数式の calc シート
  <case>/model/facts-rows.csv      台帳に載せる行（--ledger-write のときは台帳にも反映）

使い方:
  python3 build_model.py --case cases/hokushin
  python3 build_model.py --case cases/hokushin --exclude-confidence 低 --label ベースケース --ledger-write

計算の正本はこのファイルの compute()。scenario-sensitivity/scripts/sensitivity.py に
同じ関数の写しがある（スキルは単体で動かすため）。直すときは両方を直す。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

# ==== モデルの定義と計算（ここから「ここまで」までを sensitivity.py に写す） ====
BASE_YEAR = 2025
END_YEAR = 2030

# ドライバー: key -> (既定のラベル, 単位の種類)。pct は inputs.csv では % の値、計算では割合
DRIVERS: dict[str, tuple[str, str]] = {
    "base_revenue": ("基準年の連結売上高", "amount"),
    "base_op": ("基準年の連結営業利益", "amount"),
    "base_equity": ("基準年末の純資産", "amount"),
    "base_debt": ("基準年末の有利子負債（期間中は一定）", "amount"),
    "base_cash": ("基準年末の現金及び預金", "amount"),
    "base_growth": ("成り行きの売上成長率（年率）", "pct"),
    "base_margin": ("成り行き事業の営業利益率", "pct"),
    "init_margin": ("施策売上の営業利益率", "pct"),
    "da_rate": ("成り行き売上に対する減価償却費の比率", "pct"),
    "maint_capex_rate": ("成り行き売上に対する維持更新投資の比率", "pct"),
    "dep_life": ("施策投資の償却年数（翌年度から定額）", "years"),
    "nwc_rate": ("売上増加額に対する運転資本の増加率", "pct"),
    "tax_rate": ("実効税率", "pct"),
    "interest_rate": ("有利子負債の平均金利", "pct"),
    "payout_ratio": ("配当性向", "pct"),
    "wacc": ("WACC", "pct"),
}

# 計算結果の行: key, ラベル, 単位（"億円" / "%" / "倍"）
ITEMS: list[tuple[str, str, str]] = [
    ("rev_base", "成り行き売上", "億円"),
    ("rev_init", "施策売上", "億円"),
    ("rev", "連結売上高", "億円"),
    ("op_base", "成り行き営業利益", "億円"),
    ("op_init", "施策営業利益", "億円"),
    ("op", "営業利益", "億円"),
    ("opm", "営業利益率", "%"),
    ("da_base", "減価償却費（成り行き）", "億円"),
    ("da_init", "減価償却費（施策投資）", "億円"),
    ("da", "減価償却費", "億円"),
    ("capex_maint", "維持更新投資", "億円"),
    ("capex_init", "施策投資", "億円"),
    ("capex", "投資合計", "億円"),
    ("dnwc", "運転資本の増加", "億円"),
    ("tax_op", "営業利益に対する税金", "億円"),
    ("nopat", "NOPAT", "億円"),
    ("fcf", "フリー・キャッシュ・フロー", "億円"),
    ("ic", "投下資本（期末）", "億円"),
    ("roic", "ROIC（期首期末平均の投下資本）", "%"),
    ("spread", "ROIC − WACC", "%"),
    ("nopat_margin", "NOPAT マージン", "%"),
    ("turnover", "投下資本回転率", "倍"),
    ("interest", "支払利息", "億円"),
    ("ni", "当期純利益（近似）", "億円"),
    ("div", "配当金", "億円"),
    ("equity", "純資産（期末）", "億円"),
    ("roe", "ROE（近似、期首期末平均）", "%"),
    ("cash", "現金及び預金（期末、借入一定）", "億円"),
    ("net_de", "ネット D/E レシオ", "倍"),
]
ITEM_UNIT = {k: u for k, _, u in ITEMS}
ITEM_LABEL = {k: l for k, l, _ in ITEMS}

# 台帳に載せる主要な結果: (item, 期間の種類)
HEADLINES = [
    ("rev", "end"), ("rev_base", "end"), ("rev_init", "end"), ("op", "end"), ("opm", "end"),
    ("roic", "end"), ("roe", "end"), ("net_de", "end"), ("cash", "end"),
    ("fcf", "sum"), ("capex_init", "sum"),
]

TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0}
DASH = "—"


def compute(d: dict[str, float], inits: list[dict], years: list[int]) -> dict[int, dict[str, float | None]]:
    """年次のモデルを計算する。d の pct は割合（0.05）。inits は {rev: {年: 億円}, inv: {年: 億円}}。

    基準年（years[0]）は実績の列。計画年は次の順で積む。
    売上 → 営業利益 → 減価償却 → 投資 → 運転資本 → NOPAT → FCF → 投下資本 → ROIC → 純利益 → 純資産 → 現預金
    """
    out: dict[int, dict[str, float | None]] = {}
    y0 = years[0]
    b = {k: None for k, _, _ in ITEMS}
    b["rev_base"] = d["base_revenue"]
    b["rev"] = d["base_revenue"]
    b["op"] = d["base_op"]
    b["opm"] = d["base_op"] / d["base_revenue"]
    b["equity"] = d["base_equity"]
    b["cash"] = d["base_cash"]
    b["ic"] = d["base_equity"] + d["base_debt"] - d["base_cash"]
    b["net_de"] = (d["base_debt"] - d["base_cash"]) / d["base_equity"]
    out[y0] = b
    for i, y in enumerate(years[1:], start=1):
        p = out[years[i - 1]]
        r: dict[str, float | None] = {}
        r["rev_base"] = p["rev_base"] * (1 + d["base_growth"])
        r["rev_init"] = sum(x["rev"].get(y, 0.0) for x in inits)
        r["rev"] = r["rev_base"] + r["rev_init"]
        r["op_base"] = r["rev_base"] * d["base_margin"]
        r["op_init"] = r["rev_init"] * d["init_margin"]
        r["op"] = r["op_base"] + r["op_init"]
        r["opm"] = r["op"] / r["rev"]
        r["da_base"] = r["rev_base"] * d["da_rate"]
        past_inv = sum(v for x in inits for yy, v in x["inv"].items() if y0 < yy < y)
        r["da_init"] = past_inv / d["dep_life"]
        r["da"] = r["da_base"] + r["da_init"]
        r["capex_maint"] = r["rev_base"] * d["maint_capex_rate"]
        r["capex_init"] = sum(x["inv"].get(y, 0.0) for x in inits)
        r["capex"] = r["capex_maint"] + r["capex_init"]
        r["dnwc"] = (r["rev"] - p["rev"]) * d["nwc_rate"]
        r["tax_op"] = r["op"] * d["tax_rate"]
        r["nopat"] = r["op"] - r["tax_op"]
        r["fcf"] = r["nopat"] + r["da"] - r["capex"] - r["dnwc"]
        r["ic"] = p["ic"] + r["capex"] - r["da"] + r["dnwc"]
        avg_ic = (p["ic"] + r["ic"]) / 2
        r["roic"] = r["nopat"] / avg_ic
        r["spread"] = r["roic"] - d["wacc"]
        r["nopat_margin"] = r["nopat"] / r["rev"]
        r["turnover"] = r["rev"] / avg_ic
        r["interest"] = d["base_debt"] * d["interest_rate"]
        r["ni"] = (r["op"] - r["interest"]) * (1 - d["tax_rate"])
        r["div"] = r["ni"] * d["payout_ratio"]
        r["equity"] = p["equity"] + r["ni"] - r["div"]
        r["roe"] = r["ni"] / ((p["equity"] + r["equity"]) / 2)
        r["cash"] = p["cash"] + r["fcf"] - r["interest"] * (1 - d["tax_rate"]) - r["div"]
        r["net_de"] = (d["base_debt"] - r["cash"]) / r["equity"]
        out[y] = r
    return out
# ==== ここまで ====


def fail(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_num(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if s in {"", DASH, "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_year(s: str) -> int:
    m = re.search(r"(\d{4})", s or "")
    if not m:
        fail(f"年度を読めません: {s!r}（2027 か FY2027 の形で書く）")
    return int(m.group(1))


def load_ledger(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def load_inputs(path: Path, ledger: list[dict]) -> tuple[dict[str, float], list[dict], list[str]]:
    if not path.exists():
        fail(f"{path} がありません。templates/inputs.csv を写して埋める")
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    need = {"id", "label", "value", "unit", "source_tag", "key"}
    if rows and not need <= set(rows[0].keys()):
        fail(f"inputs.csv の列が足りません: {', '.join(sorted(need - set(rows[0].keys())))}")
    by_id = {r["id"]: r for r in ledger}
    drivers: dict[str, float] = {}
    notes: list[str] = []
    missing: list[str] = []
    for r in rows:
        key = (r.get("key") or "").strip()
        if key not in DRIVERS:
            notes.append(f"inputs.csv: 未知の key {key!r} は使わない（{r.get('id')}）")
            continue
        v = parse_num(r["value"])
        if v is None:
            missing.append(f"{key}（{r.get('id') or 'ID なし'} {r.get('label')}）")
            continue
        rid = (r.get("id") or "").strip()
        if not rid:
            notes.append(f"{key}: ID がない。台帳に登録してから使う")
        elif ledger and rid not in by_id:
            notes.append(f"{key}: {rid} が台帳にない")
        elif ledger:
            lv = parse_num(by_id[rid]["value"])
            if lv is not None and abs(lv - v) > 1e-9:
                notes.append(f"{key}: inputs の値 {v} が台帳 {rid} の値 {lv} と違う")
        if DRIVERS[key][1] == "pct":
            v = v / 100.0
        elif DRIVERS[key][1] == "amount":
            u = (r.get("unit") or "億円").strip()
            if u not in TO_OKU:
                fail(f"{key}: 単位 {u!r} を億円に換算できません")
            v = v * TO_OKU[u]
        drivers[key] = v
    absent = [k for k in DRIVERS if k not in drivers and not any(k in m for m in missing)]
    if missing or absent:
        lines = [f"  - {m}" for m in missing] + [f"  - {k}（行がない）" for k in absent]
        fail("値が — のドライバーがあるため計算しない。値を確かめるか、仮置きを決めて台帳に載せる:\n" + "\n".join(lines))
    if drivers["dep_life"] < END_YEAR - BASE_YEAR:
        fail(f"dep_life は {END_YEAR - BASE_YEAR} 年以上にする（計画期間内で償却が終わる扱いをしていない）")
    return drivers, rows, notes


def load_initiatives(path: Path, exclude: set[str], years: list[int]) -> tuple[list[dict], list[str]]:
    notes: list[str] = []
    if not path.exists():
        notes.append(f"{path.name} がない。施策なし（成り行きだけ）で計算した")
        return [], notes
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    inits: dict[str, dict] = {}
    for r in rows:
        rid = (r.get("id") or "").strip()
        conf = (r.get("confidence") or "").strip()
        if conf in exclude:
            continue
        y = parse_year(r.get("year", ""))
        if not (years[0] < y <= years[-1]):
            notes.append(f"{rid} の {y} 年度はモデルの期間外なので使わない")
            continue
        u = (r.get("unit") or "億円").strip()
        if u not in TO_OKU:
            fail(f"05-initiatives.csv: {rid} の単位 {u!r} を換算できません")
        k = TO_OKU[u]
        x = inits.setdefault(rid, {"id": rid, "name": r.get("initiative", ""), "conf": conf, "rev": {}, "inv": {}})
        rev, inv = parse_num(r.get("revenue", "")), parse_num(r.get("investment", ""))
        if rev is None or inv is None:
            notes.append(f"{rid} {y}: 売上か投資が — なので 0 として扱った（要確認）")
        x["rev"][y] = x["rev"].get(y, 0.0) + (rev or 0.0) * k
        x["inv"][y] = x["inv"].get(y, 0.0) + (inv or 0.0) * k
    if exclude:
        notes.append(f"確度 {', '.join(sorted(exclude))} の施策を除いた")
    return list(inits.values()), notes


def display(item: str, v: float | None) -> str:
    if v is None:
        return ""
    if ITEM_UNIT[item] == "%":
        t = f"{v * 100:.1f}"
    elif ITEM_UNIT[item] == "倍":
        t = f"{v:.2f}"
    else:
        t = f"{v:.1f}"
    return "0" + t[2:] if t.startswith("-0") and float(t) == 0 else t


# ---------------------------------------------------------------- 台帳
def next_free(prefix: str, used: set[str]) -> str:
    n = 1
    while f"{prefix}-{n:03d}" in used:
        n += 1
    return f"{prefix}-{n:03d}"


def headline_rows(res: dict, years: list[int], label: str, src: str) -> list[dict]:
    today = dt.date.today().isoformat()
    y_end = years[-1]
    rows = []
    for item, kind in HEADLINES:
        unit = ITEM_UNIT[item]
        if kind == "end":
            v = res[y_end][item]
            period = f"FY{y_end}"
            definition = f"{ITEM_LABEL[item]}（business-case-model {label}）"
        else:
            v = sum(res[y][item] for y in years[1:])
            period = f"FY{years[1]}-FY{y_end}"
            definition = f"{ITEM_LABEL[item]}の累計（business-case-model {label}）"
        rows.append({
            "id": "", "value": display(item, v), "unit": unit, "definition": definition,
            "period": period, "source_tag": "推定", "source": src, "retrieved_at": today,
            "confidentiality": "公開", "replace_by": "",
            "_item": item, "_kind": kind,
        })
    return rows


def upsert(ledger_fields: list[str], ledger: list[dict], new: list[dict]) -> list[str]:
    """definition と period が同じ行があれば値を更新し、なければ使われていない最小の F- 番号で足す。"""
    used = {r["id"] for r in ledger}
    log = []
    for n in new:
        hit = next((r for r in ledger if r["definition"] == n["definition"] and r["period"] == n["period"]), None)
        if hit:
            n["id"] = hit["id"]
            if hit["value"] != n["value"] or hit["source"] != n["source"]:
                hit.update({k: n[k] for k in ("value", "unit", "source", "retrieved_at")})
                log.append(f"更新 {hit['id']} {n['definition']} {n['period']} = {n['value']}{n['unit']}")
        else:
            n["id"] = next_free("F", used)
            used.add(n["id"])
            ledger.append({k: n.get(k, "") for k in ledger_fields})
            log.append(f"追加 {n['id']} {n['definition']} {n['period']} = {n['value']}{n['unit']}")
    return log


# ---------------------------------------------------------------- xlsx（標準ライブラリだけ）
def col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


STYLE_TEXT, STYLE_NUM, STYLE_PCT, STYLE_HEAD, STYLE_X = 0, 1, 2, 3, 4


def c_str(ref: str, text: str, style: int = STYLE_TEXT) -> str:
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(str(text))}</t></is></c>'


def c_num(ref: str, v: float, style: int) -> str:
    return f'<c r="{ref}" s="{style}"><v>{v!r}</v></c>'


def c_f(ref: str, formula: str, v: float | None, style: int) -> str:
    cached = "" if v is None else f"<v>{v!r}</v>"
    return f'<c r="{ref}" s="{style}"><f>{escape(formula)}</f>{cached}</c>'


def sheet_xml(rows: dict[int, list[str]], widths: list[int]) -> str:
    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1))
    body = "".join(f'<row r="{r}">{"".join(cells)}</row>' for r, cells in sorted(rows.items()))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{body}</sheetData></worksheet>')


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="3"><numFmt numFmtId="164" formatCode="#,##0.0"/><numFmt numFmtId="165" formatCode="0.0%"/>'
    '<numFmt numFmtId="166" formatCode="0.00"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="5">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)

UNIT_STYLE = {"億円": STYLE_NUM, "%": STYLE_PCT, "倍": STYLE_X}


def build_xlsx(path: Path, inputs_rows: list[dict], drivers: dict[str, float], inits: list[dict],
               years: list[int], res: dict, ledger_tags: dict[str, str]) -> None:
    plan = years[1:]
    # ---- inputs シート（列は id,label,value,unit,source_tag,key。値と単位は inputs.csv のまま）
    # 率（%）は % の値のまま置き、calc では後置の % 演算子（inputs!$C$7%）で割合にする。/100 を直打ちしない
    ins: dict[int, list[str]] = {1: [c_str(f"{c}1", h, STYLE_HEAD) for c, h in
                                     zip("ABCDEF", ["id", "label", "value", "unit", "source_tag", "key"])]}
    ref: dict[str, str] = {}
    r = 2
    for row in inputs_rows:
        key = (row.get("key") or "").strip()
        if key not in drivers:
            continue
        kind = DRIVERS[key][1]
        raw = parse_num(row["value"])
        style = STYLE_NUM if kind != "years" else STYLE_TEXT
        ins[r] = [c_str(f"A{r}", row["id"]), c_str(f"B{r}", row["label"]),
                  c_num(f"C{r}", raw, style), c_str(f"D{r}", row["unit"]),
                  c_str(f"E{r}", row["source_tag"]), c_str(f"F{r}", key)]
        if kind == "pct":
            ref[key] = f"inputs!$C${r}%"
        elif kind == "amount" and TO_OKU[(row.get("unit") or "億円").strip()] != 1.0:
            fail(f"{key}: xlsx では億円の入力だけを扱う。inputs.csv を億円で書く")
        else:
            ref[key] = f"inputs!$C${r}"
        r += 1
    r += 1
    year_cols = {y: col(7 + i) for i, y in enumerate(plan)}  # G 列から
    blocks: dict[str, tuple[int, int] | None] = {}
    for metric, mlabel, mkey in (("rev", "売上", "init_rev"), ("inv", "投資", "init_inv")):
        # 小見出しの行は A 列（id）を空にする（台帳との照合の対象にしない）
        ins[r] = [c_str(f"B{r}", f"施策の{mlabel}（05-initiatives.csv から。億円）", STYLE_HEAD)]
        ins[r] += [c_str(f"{year_cols[y]}{r}", f"FY{y}", STYLE_HEAD) for y in plan]
        r += 1
        first = r
        for x in inits:
            ins[r] = [c_str(f"A{r}", x["id"]), c_str(f"B{r}", f"{x['name']} {mlabel}（確度 {x['conf'] or '—'}）"),
                      c_str(f"D{r}", "億円"), c_str(f"E{r}", ledger_tags.get(x["id"], "")), c_str(f"F{r}", mkey)]
            ins[r] += [c_num(f"{year_cols[y]}{r}", x[metric].get(y, 0.0), STYLE_NUM) for y in plan]
            r += 1
        blocks[metric] = (first, r - 1) if inits else None
        r += 1

    # ---- calc シート（数式は inputs のセルと calc のセルだけを参照する）
    row_of = {k: i + 2 for i, (k, _, _) in enumerate(ITEMS)}
    ycol = {y: col(3 + i) for i, y in enumerate(years)}  # C 列が基準年

    def at(item: str, y: int) -> str:
        return f"{ycol[y]}{row_of[item]}"

    calc: dict[int, list[str]] = {1: [c_str("A1", "項目", STYLE_HEAD), c_str("B1", "単位", STYLE_HEAD)]
                                  + [c_str(f"{ycol[y]}1", f"FY{y}{'（実績）' if y == years[0] else ''}", STYLE_HEAD) for y in years]}
    for k, label, unit in ITEMS:
        calc[row_of[k]] = [c_str(f"A{row_of[k]}", label), c_str(f"B{row_of[k]}", unit)]
    R = ref
    y0 = years[0]
    f0 = {
        "rev_base": f"{R['base_revenue']}", "rev": f"{at('rev_base', y0)}", "op": f"{R['base_op']}",
        "opm": f"{at('op', y0)}/{at('rev', y0)}", "equity": f"{R['base_equity']}", "cash": f"{R['base_cash']}",
        "ic": f"{R['base_equity']}+{R['base_debt']}-{R['base_cash']}",
        "net_de": f"({R['base_debt']}-{at('cash', y0)})/{at('equity', y0)}",
    }
    for k, fml in f0.items():
        calc[row_of[k]].append(c_f(at(k, y0), fml, res[y0][k], UNIT_STYLE[ITEM_UNIT[k]]))
    for i, y in enumerate(plan):
        p = years[i]
        yc = year_cols[y]
        rb, ib = blocks.get("rev"), blocks.get("inv")
        f: dict[str, str | None] = {
            "rev_base": f"{at('rev_base', p)}*(1+{R['base_growth']})",
            "rev_init": f"SUM(inputs!{yc}{rb[0]}:{yc}{rb[1]})" if rb else None,
            "rev": f"{at('rev_base', y)}+{at('rev_init', y)}",
            "op_base": f"{at('rev_base', y)}*{R['base_margin']}",
            "op_init": f"{at('rev_init', y)}*{R['init_margin']}",
            "op": f"{at('op_base', y)}+{at('op_init', y)}",
            "opm": f"{at('op', y)}/{at('rev', y)}",
            "da_base": f"{at('rev_base', y)}*{R['da_rate']}",
            "da_init": (f"SUM(inputs!$G${ib[0]}:{year_cols[p]}{ib[1]})/{R['dep_life']}" if ib and i > 0 else None),
            "da": f"{at('da_base', y)}+{at('da_init', y)}",
            "capex_maint": f"{at('rev_base', y)}*{R['maint_capex_rate']}",
            "capex_init": f"SUM(inputs!{yc}{ib[0]}:{yc}{ib[1]})" if ib else None,
            "capex": f"{at('capex_maint', y)}+{at('capex_init', y)}",
            "dnwc": f"({at('rev', y)}-{at('rev', p)})*{R['nwc_rate']}",
            "tax_op": f"{at('op', y)}*{R['tax_rate']}",
            "nopat": f"{at('op', y)}-{at('tax_op', y)}",
            "fcf": f"{at('nopat', y)}+{at('da', y)}-{at('capex', y)}-{at('dnwc', y)}",
            "ic": f"{at('ic', p)}+{at('capex', y)}-{at('da', y)}+{at('dnwc', y)}",
            "roic": f"{at('nopat', y)}/AVERAGE({at('ic', p)},{at('ic', y)})",
            "spread": f"{at('roic', y)}-{R['wacc']}",
            "nopat_margin": f"{at('nopat', y)}/{at('rev', y)}",
            "turnover": f"{at('rev', y)}/AVERAGE({at('ic', p)},{at('ic', y)})",
            "interest": f"{R['base_debt']}*{R['interest_rate']}",
            "ni": f"({at('op', y)}-{at('interest', y)})*(1-{R['tax_rate']})",
            "div": f"{at('ni', y)}*{R['payout_ratio']}",
            "equity": f"{at('equity', p)}+{at('ni', y)}-{at('div', y)}",
            "roe": f"{at('ni', y)}/AVERAGE({at('equity', p)},{at('equity', y)})",
            "cash": f"{at('cash', p)}+{at('fcf', y)}-{at('interest', y)}*(1-{R['tax_rate']})-{at('div', y)}",
            "net_de": f"({R['base_debt']}-{at('cash', y)})/{at('equity', y)}",
        }
        for k, fml in f.items():
            if fml is None:
                continue  # 空セル（0 扱い）。0 を直打ちしない
            calc[row_of[k]].append(c_f(at(k, y), fml, res[y][k], UNIT_STYLE[ITEM_UNIT[k]]))

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'),
        "xl/workbook.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns}>'
            '<sheets><sheet name="inputs" sheetId="1" r:id="rId1"/><sheet name="calc" sheetId="2" r:id="rId2"/></sheets>'
            '<calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>'),
        "xl/styles.xml": STYLES,
        "xl/worksheets/sheet1.xml": sheet_xml(ins, [10, 40, 14, 8, 18, 18] + [11] * len(plan)),
        "xl/worksheets/sheet2.xml": sheet_xml(calc, [34, 6] + [11] * len(years)),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True, help="案件フォルダ（例: cases/hokushin）")
    ap.add_argument("--inputs", help="既定: <case>/model/inputs.csv")
    ap.add_argument("--initiatives", help="既定: <case>/05-initiatives.csv")
    ap.add_argument("--ledger", help="既定: <case>/facts/facts.csv")
    ap.add_argument("--out-dir", help="既定: <case>/model")
    ap.add_argument("--exclude-confidence", default="", help="除く確度（カンマ区切り。例: 低）")
    ap.add_argument("--label", default="ベースケース", help="台帳の定義に入れるケース名")
    ap.add_argument("--ledger-write", action="store_true", help="主要な結果を台帳に追記・更新する")
    a = ap.parse_args()

    case = Path(a.case)
    inputs_p = Path(a.inputs) if a.inputs else case / "model" / "inputs.csv"
    inits_p = Path(a.initiatives) if a.initiatives else case / "05-initiatives.csv"
    ledger_p = Path(a.ledger) if a.ledger else case / "facts" / "facts.csv"
    out = Path(a.out_dir) if a.out_dir else case / "model"
    out.mkdir(parents=True, exist_ok=True)
    years = list(range(BASE_YEAR, END_YEAR + 1))

    fields, ledger = load_ledger(ledger_p)
    drivers, in_rows, notes = load_inputs(inputs_p, ledger)
    exclude = {s.strip() for s in a.exclude_confidence.split(",") if s.strip()}
    inits, n2 = load_initiatives(inits_p, exclude, years)
    notes += n2
    res = compute(drivers, inits, years)

    # 台帳に載せる行
    ledger_ids = {r["id"] for r in ledger}
    in_ids = [r["id"] for r in in_rows if r.get("id") and r["id"] in ledger_ids]
    init_ids = [x["id"] for x in inits if x["id"] in ledger_ids]
    src = f"build_model.py（入力: {', '.join(in_ids + init_ids) or '—'}; 05-initiatives.csv）"
    heads = headline_rows(res, years, a.label, src)
    if a.ledger_write:
        if not fields:
            fail(f"{ledger_p} がないので台帳に書けません")
        log = upsert(fields, ledger, heads)
        with ledger_p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(ledger)
    else:
        used = set(ledger_ids)
        for h in heads:
            hit = next((r for r in ledger if r["definition"] == h["definition"] and r["period"] == h["period"]), None)
            h["id"] = hit["id"] if hit else next_free("F", used)
            used.add(h["id"])
        log = []
    head_id = {(h["_item"], h["_kind"]): h["id"] for h in heads}

    # model.csv（縦持ち。主要な行だけ id。id のある行は台帳と同じ値・同じ丸め）
    with (out / "model.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "fiscal_year", "item", "value", "unit", "note"])
        for k, label, unit in ITEMS:
            for y in years:
                v = res[y][k]
                if v is None:
                    continue
                rid = head_id.get((k, "end"), "") if y == years[-1] else ""
                w.writerow([rid if a.ledger_write else "", f"FY{y}", label, display(k, v), unit,
                            "実績" if y == years[0] else a.label])
        for k, kind in HEADLINES:
            if kind == "sum":
                v = sum(res[y][k] for y in years[1:])
                w.writerow([head_id[(k, kind)] if a.ledger_write else "", f"FY{years[1]}-FY{years[-1]}",
                            f"{ITEM_LABEL[k]}の累計", display(k, v), ITEM_UNIT[k], a.label])
    with (out / "facts-rows.csv").open("w", encoding="utf-8", newline="") as f:
        cols = ["id", "value", "unit", "definition", "period", "source_tag", "source", "retrieved_at",
                "confidentiality", "replace_by"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        # 台帳に書く前は id を空にする（予定の ID が台帳になく、number-audit がエラーにするため）
        w.writerows(heads if a.ledger_write else [{**h, "id": ""} for h in heads])
    build_xlsx(out / "business-case.xlsx", in_rows, drivers, inits, years, res,
               {r["id"]: r["source_tag"] for r in ledger})

    # ---- 画面に出す要約（Markdown）
    y0 = years[0]
    approx_ni = (drivers["base_op"] - drivers["base_debt"] * drivers["interest_rate"]) * (1 - drivers["tax_rate"])
    print(f"# business-case-model の結果（{a.label}）\n")
    print("## 基準年の再現チェック（開示値と比べる）\n")
    print(f"- FY{y0} 営業利益率: {res[y0]['opm'] * 100:.1f}%（入力の base_margin は {drivers['base_margin'] * 100:.1f}%）")
    print(f"- FY{y0} 純利益の近似: {approx_ni:.1f} 億円 / ROE 近似（期末純資産）: {approx_ni / drivers['base_equity'] * 100:.1f}%")
    print(f"- FY{y0} ROIC 近似（期末投下資本 {res[y0]['ic']:.1f} 億円）: "
          f"{drivers['base_op'] * (1 - drivers['tax_rate']) / res[y0]['ic'] * 100:.1f}%")
    print("  → 開示の純利益・ROE と大きくずれるなら、税率・金利の入力を先に直す\n")
    print("## 年次の主要項目\n")
    show = ["rev_base", "rev_init", "rev", "op", "opm", "capex", "fcf", "ic", "roic", "spread", "roe", "cash", "net_de"]
    print("| 項目 | 単位 | " + " | ".join(f"FY{y}" for y in years) + " |")
    print("|---|---|" + "---:|" * len(years))
    for k in show:
        print(f"| {ITEM_LABEL[k]} | {ITEM_UNIT[k]} | " + " | ".join(display(k, res[y][k]) or DASH for y in years) + " |")
    print("\n## 台帳に載せる行\n")
    print("| ID | 定義 | 期間 | 値 | 単位 |\n|---|---|---|---:|---|")
    for h in heads:
        print(f"| {h['id']} | {h['definition']} | {h['period']} | {h['value']} | {h['unit']} |")
    if not a.ledger_write:
        print("\n（台帳はまだ書いていない。確認後に --ledger-write を付けて再実行する。ID は予定）")
    for line in log:
        print(f"- {line}")
    flags = []
    cash_min = min(res[y]["cash"] for y in years[1:])
    if cash_min < 0:
        flags.append(f"現預金が期中にマイナス（最小 {cash_min:.1f} 億円）。借入か資金調達の手当てが要る")
    de_max = max(res[y]["net_de"] for y in years)
    if de_max > 0.5:
        flags.append(f"ネット D/E が最大 {de_max:.2f} 倍。財務規律（例: 0.5 倍以内）と照らす")
    if res[years[-1]]["spread"] < 0:
        flags.append("最終年度の ROIC が WACC を下回る")
    if flags or notes:
        print("\n## 前提と未確認事項（スクリプトが気づいたこと）\n")
        for s in flags + notes:
            print(f"- {s}")
    print(f"\n書いたファイル: {out / 'model.csv'}, {out / 'business-case.xlsx'}, {out / 'facts-rows.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
