#!/usr/bin/env python3
"""モデルのドライバーを、変数ごとに根拠のある幅で振り、シナリオと感応度（トルネード）を出す。

読むもの:
  <case>/model/inputs.csv               business-case-model と同じ入力（id,label,value,unit,source_tag,key）
  <case>/05-initiatives.csv             施策の年次売上と投資
  <case>/model/sensitivity-ranges.csv   振る変数と幅（key,label,downside,upside,unit,in_scenario,source_tag,source）
  <case>/facts/facts.csv                ファクト台帳（--target-id の値と、結果の登録に使う）

書くもの:
  <case>/model/sensitivity.md           シナリオ表とトルネード表（Markdown）
  台帳への行（--ledger-write のとき。上振れ・下振れの主要な結果）

使い方:
  python3 sensitivity.py --case cases/hokushin --target-id T-001
  python3 sensitivity.py --case cases/hokushin --target-id T-001 --ledger-write

モデルの計算は business-case-model/scripts/build_model.py の写し（下の「モデルの定義と計算」）。
スキルを単体で動かすために写している。model.csv は読まず、inputs.csv から計算し直す
（変数を振るには計算そのものが要るため）。ベースケースの値が model.csv と違えば、写しが古い。

特別な変数（inputs.csv にない key）:
  ramp_delay           施策売上の立ち上がりを何年ずらすか（年。+1 で 1 年遅れ。投資は計画どおり出る）
  ramp_delay:I-001     特定の施策だけずらす
  init_scale           施策売上の実現率（倍。1.0 が計画どおり）
  init_scale:I-001     特定の施策だけの売上の実現率（投資は計画どおり出る）
  init_go:I-004        施策ごとの実行率（売上と投資の両方に掛ける。M&A 不成立なら 0）
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

# ==== モデルの定義と計算（business-case-model/scripts/build_model.py の写し。直接直さない） ====
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

SOURCE_TAGS = {"公開", "クライアント提供", "推定", "仮置き"}
METRICS = [  # (key, 表示名, 単位, 期間の種類)
    ("rev", "連結売上高", "億円", "end"),
    ("op", "営業利益", "億円", "end"),
    ("roic", "ROIC", "%", "end"),
    ("roe", "ROE（近似）", "%", "end"),
    ("fcf", "フリー・キャッシュ・フロー累計", "億円", "sum"),
    ("net_de", "ネット D/E レシオ", "倍", "end"),
]
TORNADO_FOR = ["rev", "roic"]


def fail(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(2)


def num(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if s in {"", DASH, "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_drivers(p: Path) -> dict[str, float]:
    rows = read_csv(p)
    if not rows:
        fail(f"{p} がない。先に business-case-model を回す")
    d: dict[str, float] = {}
    for r in rows:
        k = (r.get("key") or "").strip()
        if k not in DRIVERS:
            continue
        v = num(r["value"])
        if v is None:
            fail(f"{k} が — のまま。business-case-model の段で値を決めてから振る")
        if DRIVERS[k][1] == "pct":
            v /= 100
        elif DRIVERS[k][1] == "amount":
            v *= TO_OKU[(r.get("unit") or "億円").strip()]
        d[k] = v
    miss = [k for k in DRIVERS if k not in d]
    if miss:
        fail("inputs.csv に足りないドライバー: " + ", ".join(miss))
    return d


def load_inits(p: Path, exclude: set[str]) -> list[dict]:
    inits: dict[str, dict] = {}
    for r in read_csv(p):
        if (r.get("confidence") or "").strip() in exclude:
            continue
        m = re.search(r"\d{4}", r.get("year", ""))
        if not m:
            fail(f"年度を読めない: {r.get('year')!r}")
        y = int(m.group())
        if not (BASE_YEAR < y <= END_YEAR):
            continue
        k = TO_OKU[(r.get("unit") or "億円").strip()]
        x = inits.setdefault(r["id"], {"id": r["id"], "name": r.get("initiative", ""), "rev": {}, "inv": {}})
        x["rev"][y] = x["rev"].get(y, 0.0) + (num(r.get("revenue", "")) or 0.0) * k
        x["inv"][y] = x["inv"].get(y, 0.0) + (num(r.get("investment", "")) or 0.0) * k
    return list(inits.values())


def shift(rev: dict[int, float], n: int, years: list[int]) -> dict[int, float]:
    """売上を n 年ずらす。遅れ（n>0）は前を 0 で埋め、前倒し（n<0）は最終年度を据え置く。"""
    plan = years[1:]
    out = {}
    for y in plan:
        src = y - n
        if src < plan[0]:
            out[y] = 0.0
        elif src > plan[-1]:
            out[y] = rev.get(plan[-1], 0.0)
        else:
            out[y] = rev.get(src, 0.0)
    return out


def apply(d: dict[str, float], inits: list[dict], changes: dict[str, float], years: list[int]):
    d2 = dict(d)
    inits2 = [{"id": x["id"], "name": x["name"], "rev": dict(x["rev"]), "inv": dict(x["inv"])} for x in inits]
    for k, v in changes.items():
        if k in DRIVERS:
            d2[k] = v / 100 if DRIVERS[k][1] == "pct" else v
    for x in inits2:
        scale = changes.get("init_scale", 1.0) * changes.get(f"init_scale:{x['id']}", 1.0)
        delay = int(round(changes.get("ramp_delay", 0.0) + changes.get(f"ramp_delay:{x['id']}", 0.0)))
        go = changes.get(f"init_go:{x['id']}", 1.0)
        x["rev"] = {y: v * scale * go for y, v in shift(x["rev"], delay, years).items()}
        x["inv"] = {y: v * go for y, v in x["inv"].items()}
    return compute(d2, inits2, years)


def metric(res: dict, key: str, kind: str, years: list[int]) -> float:
    if kind == "sum":
        return sum(res[y][key] for y in years[1:])
    return res[years[-1]][key]


def fmt(v: float, unit: str) -> str:
    if unit == "%":
        t = f"{v * 100:.1f}"
    elif unit == "倍":
        t = f"{v:.2f}"
    else:
        t = f"{v:,.1f}"
    return "0" + t[2:] if t.startswith("-0") and float(t.replace(",", "")) == 0 else t


def base_value(key: str, d: dict[str, float]) -> float:
    if key in DRIVERS:
        return d[key] * 100 if DRIVERS[key][1] == "pct" else d[key]
    if key.startswith("ramp_delay"):
        return 0.0
    if key.startswith("init_scale") or key.startswith("init_go:"):
        return 1.0
    fail(f"未知の変数 {key!r}。inputs.csv の key か ramp_delay / init_scale を使う")
    return 0.0


def load_ranges(p: Path, d: dict[str, float], init_ids: set[str]) -> tuple[list[dict], list[str]]:
    rows = read_csv(p)
    if not rows:
        fail(f"{p} がない。templates/sensitivity-ranges.csv を写して、変数ごとに根拠のある幅を書く")
    out, notes = [], []
    for i, r in enumerate(rows, start=2):
        k = (r.get("key") or "").strip()
        where = f"sensitivity-ranges.csv:{i}（{k}）"
        lo, hi = num(r.get("downside", "")), num(r.get("upside", ""))
        if lo is None or hi is None:
            notes.append(f"{where}: 幅が — なので振らない")
            continue
        tag = (r.get("source_tag") or "").strip()
        src = (r.get("source") or "").strip()
        if tag not in SOURCE_TAGS:
            fail(f"{where}: source_tag は 公開/クライアント提供/推定/仮置き のどれか（幅にも出典が要る）")
        if tag != "仮置き" and src in {"", DASH}:
            fail(f"{where}: {tag} の幅に根拠（資料名か計算式と ID）がない")
        if ":" in k and k.split(":", 1)[1] not in init_ids:
            notes.append(f"{where}: 施策 {k.split(':', 1)[1]} がモデルにない（確度で除いたか ID の誤り）")
        b = base_value(k, d)
        out.append({"key": k, "label": r.get("label") or k, "lo": lo, "hi": hi, "base": b,
                    "unit": (r.get("unit") or "").strip(), "scen": (r.get("in_scenario") or "").strip().lower() in {"yes", "y", "1", "true", "○"},
                    "tag": tag, "src": src or DASH})
        if tag == "仮置き":
            notes.append(f"{where}: 幅が仮置き。根拠が見つかったら差し替える")
    # 同じ幅で振っていないか（設計上の主な外し方）
    rel = [round(abs(x["hi"] - x["lo"]) / 2 / abs(x["base"]), 6) for x in out if x["base"] not in (0.0,)]
    if len(rel) >= 3 and len(set(rel)) == 1:
        fail(f"すべての変数を同じ幅（基準値の ±{rel[0] * 100:.0f}%）で振っている。変数ごとの根拠で幅を決め直す")
    return out, notes


def next_free(prefix: str, used: set[str]) -> str:
    n = 1
    while f"{prefix}-{n:03d}" in used:
        n += 1
    return f"{prefix}-{n:03d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    ap.add_argument("--inputs")
    ap.add_argument("--initiatives")
    ap.add_argument("--ranges")
    ap.add_argument("--ledger")
    ap.add_argument("--out", help="既定: <case>/model/sensitivity.md")
    ap.add_argument("--exclude-confidence", default="", help="business-case-model と同じ指定にする")
    ap.add_argument("--target-id", help="売上目標の ID（例: T-001）。台帳の値と比べる")
    ap.add_argument("--ledger-write", action="store_true", help="上振れ・下振れの主要な結果を台帳に追記・更新する")
    a = ap.parse_args()

    case = Path(a.case)
    years = list(range(BASE_YEAR, END_YEAR + 1))
    ledger_p = Path(a.ledger) if a.ledger else case / "facts" / "facts.csv"
    ledger = read_csv(ledger_p)
    fields = list(ledger[0].keys()) if ledger else []
    by_id = {r["id"]: r for r in ledger}
    d = load_drivers(Path(a.inputs) if a.inputs else case / "model" / "inputs.csv")
    exclude = {s.strip() for s in a.exclude_confidence.split(",") if s.strip()}
    inits = load_inits(Path(a.initiatives) if a.initiatives else case / "05-initiatives.csv", exclude)
    ranges, notes = load_ranges(Path(a.ranges) if a.ranges else case / "model" / "sensitivity-ranges.csv",
                                d, {x["id"] for x in inits})

    base = apply(d, inits, {}, years)
    up = apply(d, inits, {r["key"]: r["hi"] for r in ranges if r["scen"]}, years)
    down = apply(d, inits, {r["key"]: r["lo"] for r in ranges if r["scen"]}, years)
    scen = {"ベース": base, "上振れ": up, "下振れ": down}
    # ベースが business-case-model の結果と同じか（写しが古くないか）
    for r in read_csv(case / "model" / "model.csv"):
        if r.get("item") == ITEM_LABEL["rev"] and r.get("fiscal_year") == f"FY{years[-1]}":
            if abs(float(r["value"]) - round(base[years[-1]]["rev"], 1)) > 0.05:
                notes.append(f"ベースの FY{years[-1]} 売上 {base[years[-1]]['rev']:.1f} が model.csv の {r['value']} と違う。"
                             "モデルの写しが古いか、入力か確度の除外が違う")

    # 台帳の行（上振れ・下振れ）
    ids: dict[tuple[str, str], str] = {}
    log: list[str] = []
    if a.ledger_write:
        if not fields:
            fail(f"{ledger_p} がないので台帳に書けません")
        used = {r["id"] for r in ledger}
        in_ids = [r["id"] for r in read_csv(Path(a.inputs) if a.inputs else case / "model" / "inputs.csv")
                  if r.get("id") in by_id]
        src = f"sensitivity.py（入力: {', '.join(in_ids)}; 05-initiatives.csv; sensitivity-ranges.csv）"
        today = dt.date.today().isoformat()
        for name in ("上振れ", "下振れ"):
            for k, label, unit, kind in METRICS:
                v = fmt(metric(scen[name], k, kind, years), unit).replace(",", "")
                period = f"FY{years[1]}-FY{years[-1]}" if kind == "sum" else f"FY{years[-1]}"
                definition = f"{label}（scenario-sensitivity {name}）"
                hit = next((r for r in ledger if r["definition"] == definition and r["period"] == period), None)
                if hit:
                    if hit["value"] != v or hit["source"] != src:
                        hit.update({"value": v, "source": src, "retrieved_at": today})
                        log.append(f"更新 {hit['id']} {definition} = {v}{unit}")
                    ids[(name, k)] = hit["id"]
                else:
                    nid = next_free("F", used)
                    used.add(nid)
                    row = {f: "" for f in fields}
                    row.update({"id": nid, "value": v, "unit": unit, "definition": definition, "period": period,
                                "source_tag": "推定", "source": src, "retrieved_at": today, "confidentiality": "公開"})
                    ledger.append(row)
                    ids[(name, k)] = nid
                    log.append(f"追加 {nid} {definition} = {v}{unit}")
        with ledger_p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(ledger)

    # ベースの値は business-case-model が台帳に載せた行の ID を添える（値が一致するときだけ）
    for k, label, unit, kind in METRICS:
        dfn = f"{ITEM_LABEL[k]}{'の累計' if kind == 'sum' else ''}（business-case-model ベースケース）"
        hit = next((r for r in ledger if r["definition"] == dfn), None)
        if hit and hit["value"] == fmt(metric(base, k, kind, years), unit).replace(",", ""):
            ids[("ベース", k)] = hit["id"]

    L: list[str] = []
    L.append("# シナリオと感応度\n")
    L.append(f"- モデル: business-case-model と同じ計算（FY{years[0]} 実績、FY{years[1]}〜FY{years[-1]} 計画）")
    L.append(f"- 振った変数: {len(ranges)} 個。シナリオに入れた変数: {sum(r['scen'] for r in ranges)} 個")
    L.append("- 上振れ・下振れは、シナリオに入れた変数を同時に動かした値。すべてが同時に外れる確率は低い")
    if any(r["key"].startswith("init_go:") and r["scen"] for r in ranges):
        L.append("- 下振れは売上の下振れである。施策をやめる変数（init_go）が入ると投資も消えるので、"
                 "FCF・現預金・ネット D/E は下振れの方が良く見えることがある")
    L.append("")
    L.append("## シナリオ比較\n")
    L.append("| 指標 | 単位 | ベース | 上振れ | 下振れ |")
    L.append("|---|---|---:|---:|---:|")
    for k, label, unit, kind in METRICS:
        cells = []
        for name in ("ベース", "上振れ", "下振れ"):
            v = fmt(metric(scen[name], k, kind, years), unit)
            rid = ids.get((name, k))
            cells.append(f"{v} [{rid}]" if rid else v)
        L.append(f"| {label}{'（累計）' if kind == 'sum' else f'（FY{years[-1]}）'} | {unit} | " + " | ".join(cells) + " |")
    if a.target_id:
        t = by_id.get(a.target_id)
        tv = num(t["value"]) * TO_OKU.get(t["unit"], 1.0) if t and num(t["value"]) is not None else None
        if tv is None:
            notes.append(f"{a.target_id} が台帳にないか値が —。目標との差は出していない")
        else:
            L.append(f"| 目標 {a.target_id} との差（FY{years[-1]} 売上） | 億円 | "
                     + " | ".join(fmt(metric(scen[n], "rev", "end", years) - tv, "億円") for n in ("ベース", "上振れ", "下振れ")) + " |")
    L.append("")
    L.append("## 振った変数と幅（出典つき）\n")
    L.append("| 変数 | 単位 | 下振れ | ベース | 上振れ | シナリオ | 出典タグ | 根拠 |")
    L.append("|---|---|---:|---:|---:|:---:|---|---|")
    for r in ranges:
        L.append(f"| {r['label']} | {r['unit']} | {r['lo']:g} | {r['base']:g} | {r['hi']:g} | {'○' if r['scen'] else '—'} | {r['tag']} | {r['src']} |")
    L.append("")
    for mk in TORNADO_FOR:
        _, mlabel, munit, mkind = next(m for m in METRICS if m[0] == mk)
        bv = metric(base, mk, mkind, years)
        rows = []
        for r in ranges:
            lo = metric(apply(d, inits, {r["key"]: r["lo"]}, years), mk, mkind, years)
            hi = metric(apply(d, inits, {r["key"]: r["hi"]}, years), mk, mkind, years)
            rows.append((abs(hi - lo), r, lo, hi))
        rows.sort(key=lambda x: -x[0])
        top = rows[0][0] if rows and rows[0][0] > 0 else 1.0
        bid = ids.get(("ベース", mk))
        L.append(f"## 感応度: {mlabel}（FY{years[-1]}、ベース {fmt(bv, munit)}{munit}{f' [{bid}]' if bid else ''}）\n")
        L.append("1 変数ずつ動かし、ほかはベースのまま。振れ幅の大きい順。\n")
        L.append(f"| 順 | 変数 | 下振れ時 | 上振れ時 | 振れ幅（{'pt' if munit == '%' else munit}） | 棒 | 出典タグ |")
        L.append("|---:|---|---:|---:|---:|---|---|")
        for i, (sw, r, lo, hi) in enumerate(rows, start=1):
            bar = "█" * max(1, round(sw / top * 20)) if sw > 0 else ""
            L.append(f"| {i} | {r['label']} | {fmt(lo, munit)} | {fmt(hi, munit)} | {fmt(sw, munit)} | {bar} | {r['tag']} |")
        L.append("")
    if notes or log:
        L.append("## 前提と未確認事項（スクリプトが気づいたこと）\n")
        L += [f"- {n}" for n in notes]
        L += [f"- 台帳: {x}" for x in log]
        L.append("")
    text = "\n".join(L)
    out = Path(a.out) if a.out else case / "model" / "sensitivity.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"書いたファイル: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
