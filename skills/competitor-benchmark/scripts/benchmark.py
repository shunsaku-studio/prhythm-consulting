#!/usr/bin/env python3
"""対象企業と競合の財務・KPI・戦略を 1 枚の比較表にする。定義の違う数字は注記なしで同じ列に置かない。

入力:
  --competitors  競合の縦持ち CSV（company,fiscal_year,item,value,unit,basis,source,note[,id]）
  --financials   対象企業の facts/financials.csv（id,fiscal_year,item,segment,value,unit,basis,source,note）
  --target       対象企業の名前（financials.csv には社名の列がないため）
  --extra        追加の縦持ち CSV（競合と同じ列。対象企業の海外売上比率など。id 列があれば台帳の ID を使う）

列:
  財務: 売上 / 営業利益 / 営業利益率 / 当期純利益 / ROE / 売上の年平均成長率
  戦略・KPI: 海外売上比率 / M&A 投資額累計 / 主力セグメント

定義の扱い:
  - 日本基準の科目（売上高、営業利益、親会社株主に帰属する当期純利益、純資産、総資産）を列の基準にする
  - IFRS の売上収益・事業利益・営業利益・親会社の所有者に帰属する持分などは、違いの注記（※）を付けて置く
  - 説明を用意していない定義の組み合わせは、その列に置かず — にして「前提と未確認事項」に書く
  - 比較年の値がない会社は、最も近い過去の期を注記付きで置く
  - 年平均成長率は全社に共通する期間でそろえる。--cagr-years の期間がそろわなければ短い期間に揃えて明記する

使い方の例:
  python3 benchmark.py --competitors cases/hokushin/sources/competitors.csv \\
      --financials case/facts/financials.csv --target 北辰工業 --extra case/facts/benchmark-extra.csv \\
      --year FY2025 --facts case/facts/facts.csv --out case/facts/competitor-benchmark.body.md --write
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------- 台帳の読み書き（共通部品）
LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]
ID_RE = re.compile(r"[TQAFSGOICKD]-\d{3,}")


class Ledger:
    """facts.csv を読み、追記する行を溜める。接頭辞ごとに使われていない最小の番号から振る。"""

    def __init__(self, path: Path | None, today: str) -> None:
        self.path = path
        self.today = today
        self.rows: list[dict[str, str]] = []
        self.new_rows: list[dict[str, str]] = []
        self.warnings: list[str] = []
        self.reused: list[str] = []
        if path and path.exists():
            with path.open(encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def get(self, rid: str) -> dict[str, str] | None:
        for r in self.rows + self.new_rows:
            if r["id"] == rid:
                return r
        return None

    def value(self, rid: str) -> float:
        row = self.get(rid)
        if row is None:
            sys.exit(f"エラー: {rid} が台帳にありません（--facts を確認）")
        try:
            return float(row["value"].replace(",", ""))
        except ValueError:
            sys.exit(f"エラー: {rid} の値 {row['value']!r} は数値ではありません（— の値は計算に使えない）")

    def _used(self, prefix: str) -> set[int]:
        used = set()
        for r in self.rows + self.new_rows:
            m = re.fullmatch(prefix + r"-(\d{3,})", r["id"])
            if m:
                used.add(int(m.group(1)))
        return used

    def _next(self, prefix: str) -> str:
        used = self._used(prefix)
        n = 1
        while n in used:
            n += 1
        return f"{prefix}-{n:03d}"

    def confidentiality(self, ids: list[str]) -> str:
        for rid in ids:
            row = self.get(rid)
            if row and row.get("confidentiality", "").strip() == "社外秘":
                return "社外秘"
        return "公開"

    def add(self, prefix: str, value: float | str, unit: str, definition: str, period: str,
            source_tag: str, source: str, inputs: list[str] | None = None,
            replace_by: str = "") -> str:
        """行を足して ID を返す。定義・期間・タグ・値が同じ行が既にあれば、その ID を使い回す。"""
        vtext = value if isinstance(value, str) else f"{round(value, 1):.1f}"
        for r in self.rows + self.new_rows:
            if (r["definition"] == definition and r["period"] == period
                    and r["source_tag"] == source_tag):
                if r["value"] == vtext:
                    return r["id"]
                self.warnings.append(
                    f"{r['id']}（{definition} {period}）の値 {r['value']} が今回の計算 {vtext} と違う。"
                    f"新しい行を足すので、古い行を参照している成果物を確認すること")
        if source_tag == "推定":
            # 同じ計算式（入力 ID と演算）の行が別のスキルから登録済みなら使い回す（例: target-math の ROE）
            key = _formula_key(source)
            for r in self.rows + self.new_rows:
                if (r["id"].startswith(prefix + "-") and r["source_tag"] == "推定" and r["period"] == period
                        and r["unit"] == unit and _formula_key(r["source"]) == key and re.search(r"[A-Z]-\d{3}", key)):
                    try:
                        if abs(float(r["value"]) - float(vtext)) <= 0.051:
                            self.reused.append(f"{r['id']}（{r['definition']}）")
                            return r["id"]
                    except ValueError:
                        pass
        rid = self._next(prefix)
        self.new_rows.append({
            "id": rid, "value": vtext, "unit": unit, "definition": definition, "period": period,
            "source_tag": source_tag, "source": source, "retrieved_at": self.today,
            "confidentiality": self.confidentiality(inputs or []), "replace_by": replace_by,
        })
        return rid

    def csv_text(self) -> str:
        lines = []
        for r in self.new_rows:
            lines.append(",".join(_csv_cell(r[c]) for c in LEDGER_COLS))
        return "\n".join(lines)

    def write(self) -> None:
        if not self.path:
            sys.exit("エラー: --write には --facts が要る")
        new_file = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS)
            if new_file:
                w.writeheader()
            for r in self.new_rows:
                w.writerow(r)


def _formula_key(src: str) -> str:
    """計算式の比較用。空白と記号の書き方の違いを落とす。"""
    return re.sub(r"\s+", "", src or "").replace("−", "-").replace("／", "/").replace("÷", "/").replace("×", "*")


def _csv_cell(s: str) -> str:
    return f'"{s}"' if any(ch in s for ch in ',"\n') else s


class Val:
    """渡された値。id があれば台帳の行を指す。"""

    def __init__(self, name: str, value: float, rid: str | None, suffix: str = "") -> None:
        self.name, self.value, self.id, self.suffix = name, value, rid, suffix

    def ref(self) -> str:
        return self.id or f"{self.value:g}{self.suffix}"


def parse_val(spec: str, ledger: Ledger, default_name: str = "") -> Val:
    if "=" in spec:
        name, rhs = spec.split("=", 1)
    else:
        name, rhs = default_name, spec
    rhs = rhs.strip()
    rid = None
    if "@" in rhs:
        rhs, rid = rhs.split("@", 1)
        rid = rid.strip()
        if not ID_RE.fullmatch(rid):
            sys.exit(f"エラー: {rid!r} は ID の形式ではありません")
    if rhs.strip() == "":
        if not rid:
            sys.exit(f"エラー: {spec!r} に値も ID もありません")
        value = ledger.value(rid)
    else:
        try:
            value = float(rhs.replace(",", ""))
        except ValueError:
            sys.exit(f"エラー: {spec!r} の値を数値として読めません")
        if rid and ledger.get(rid):
            lv = ledger.value(rid)
            if abs(lv - value) > 1e-9:
                sys.exit(f"エラー: {spec!r} の値と台帳 {rid} の値 {lv:g} が違う")
    return Val(name.strip(), value, rid)


def tag(rid: str | None) -> str:
    return f" [{rid}]" if rid else ""


def oku(v: float) -> str:
    return f"{v:,.0f}"


def pct(v: float) -> str:
    return f"{v:.1f}"


# ---------------------------------------------------------------- 本体
# 列（概念）ごとに、基準にする日本基準の科目と、注記付きで置ける科目
CONCEPTS = {
    "売上": ["売上高", "売上収益"],
    "営業利益": ["営業利益", "事業利益"],
    "純利益": ["親会社株主に帰属する当期純利益", "親会社の所有者に帰属する当期利益"],
    "純資産": ["純資産", "親会社の所有者に帰属する持分"],
    "総資産": ["総資産", "資産合計"],
    "海外売上比率": ["海外売上比率"],
    "M&A 投資額累計": ["M&A 投資額累計", "子会社株式の取得による支出"],
    "主力セグメント": ["主力セグメント"],
}
REFERENCE = {("売上高", "日本基準"), ("営業利益", "日本基準"), ("親会社株主に帰属する当期純利益", "日本基準"),
             ("純資産", "日本基準"), ("総資産", "日本基準"), ("海外売上比率", "*"), ("M&A 投資額累計", "*"),
             ("主力セグメント", "*")}
NOTES = {
    ("売上収益", "IFRS"): "IFRS の売上収益。日本基準の売上高に近いが、本人・代理人の判定などで差が出うる",
    ("事業利益", "IFRS"): "IFRS の事業利益（売上総利益 − 販管費、会社独自の段階利益）。その他の収益・費用を含まない。日本基準の営業利益とは定義が違う",
    ("営業利益", "IFRS"): "IFRS の営業利益。その他の収益・費用（減損など）を含む。日本基準の営業利益とは定義が違う",
    ("親会社の所有者に帰属する当期利益", "IFRS"): "IFRS の親会社の所有者に帰属する当期利益。日本基準の親会社株主に帰属する当期純利益に相当",
    ("親会社の所有者に帰属する持分", "IFRS"): "IFRS の親会社の所有者に帰属する持分。日本基準の純資産と違い、非支配持分を含まない",
    ("資産合計", "IFRS"): "IFRS の資産合計。日本基準の総資産に相当",
    ("子会社株式の取得による支出", "日本基準"): "キャッシュ・フロー計算書の支出額（取得した子会社の現金を差し引いた純額）。他社の M&A 投資額（買収金額）とは定義が違う",
}
TO_OKU = {"億円": 1.0, "百万円": 0.01}


class Row:
    def __init__(self, company: str, fy: str, item: str, value: str, unit: str, basis: str,
                 source: str, note: str, rid: str = "") -> None:
        self.company, self.fy, self.item, self.value, self.unit = company, fy.strip(), item.strip(), value.strip(), unit.strip()
        self.basis, self.source, self.note, self.id = basis.strip(), source.strip(), note.strip(), rid.strip()

    def num(self) -> float:
        v = float(self.value.replace(",", ""))
        return v * TO_OKU[self.unit] if self.unit in TO_OKU else v


def fy_end(s: str) -> int:
    m = re.search(r"FY(\d{4})$", s)
    return int(m.group(1)) if m else -1


def fmt(v: float, unit: str) -> str:
    if unit in ("億円", "百万円"):
        return f"{v:,.0f}" if abs(v) >= 1000 or float(v).is_integer() else f"{v:,.1f}"
    return f"{v:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--competitors", type=Path, action="append", default=[], help="競合の縦持ち CSV")
    ap.add_argument("--financials", type=Path, help="対象企業の financials.csv")
    ap.add_argument("--target", default="対象企業", help="対象企業の名前")
    ap.add_argument("--extra", type=Path, action="append", default=[], help="追加の縦持ち CSV（競合と同じ列）")
    ap.add_argument("--year", help="比較年。例: FY2025（既定: 全社の最新年のうち最も早い年）")
    ap.add_argument("--cagr-years", type=int, default=5, help="年平均成長率の年数（既定 5）")
    ap.add_argument("--ifrs-op", default="事業利益", choices=["事業利益", "営業利益"],
                    help="IFRS の会社の営業利益の列に置く科目（既定: 事業利益。もう一方は注記に書く）")
    ap.add_argument("--facts", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    L = Ledger(args.facts, args.today)
    rows: list[Row] = []
    seg_rev: dict[tuple[str, str], list[Row]] = defaultdict(list)  # (company, fy) -> segment revenue rows
    capex_ma: list[Row] = []
    for p in args.competitors + args.extra:
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(Row(r["company"], r["fiscal_year"], r["item"], r["value"], r["unit"], r["basis"],
                                r.get("source", ""), r.get("note", "") or "", r.get("id", "") or ""))
    companies: list[str] = []
    if args.financials:
        companies.append(args.target)
        with args.financials.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                row = Row(args.target, r["fiscal_year"], r["item"], r["value"], r["unit"], r["basis"],
                          r.get("source", ""), r.get("note", "") or "", r.get("id", "") or "")
                seg = r["segment"].strip()
                if seg == "連結":
                    if row.item == "子会社株式の取得による支出":
                        capex_ma.append(row)
                    else:
                        rows.append(row)
                elif row.item == "売上高" and seg != "調整額":
                    row.item = seg
                    seg_rev[(args.target, row.fy)].append(row)
    for r in rows:
        if r.company not in companies:
            companies.append(r.company)

    # 台帳の ID を振る（id 列のない行は公開として載せる）
    def ensure_id(r: Row) -> str:
        if r.id:
            return r.id
        r.id = L.add("F", r.num(), "億円" if r.unit in TO_OKU else r.unit, f"{r.item}（{r.basis}、連結）{r.company}",
                     r.fy, "公開", r.source or "—")
        return r.id

    by = defaultdict(list)
    for r in rows:
        by[(r.company, r.item)].append(r)

    years_by_co = {c: {fy_end(r.fy) for r in rows if r.company == c and r.item in CONCEPTS["売上"]} for c in companies}
    latest = [max(v) for v in years_by_co.values() if v]
    Y = fy_end(args.year) if args.year else (min(latest) if latest else -1)
    year_label = f"FY{Y}"

    notes: list[str] = []          # 表の下の注記（※n）
    note_index: dict[str, int] = {}
    unresolved: list[str] = []
    cautions: list[str] = []

    def mark(text: str) -> str:
        if text not in note_index:
            notes.append(text)
            note_index[text] = len(notes)
        return f" ※{note_index[text]}"

    def pick(company: str, concept: str, prefer_year: int | None = None) -> tuple[Row | None, str]:
        """その会社の概念に当たる行を選び、(行, 注記マーク) を返す。置けなければ (None, 理由)。"""
        cands = []
        for item in CONCEPTS[concept]:
            for r in by.get((company, item), []):
                cands.append(r)
        if concept == "営業利益":
            ifrs = [r for r in cands if r.basis == "IFRS"]
            if ifrs:
                chosen = [r for r in ifrs if r.item == args.ifrs_op]
                other = [r for r in ifrs if r.item != args.ifrs_op]
                cands = chosen or ifrs
                for o in other:
                    cautions.append(f"{company}: IFRS の{o.item}は {fmt(o.num(), '億円')}億円 [{ensure_id(o)}]"
                                    f"（{o.note or '—'}）。--ifrs-op で列に置く科目を切り替えられる")
        if not cands:
            return None, ""
        target_year = prefer_year if prefer_year is not None else Y
        exact = [r for r in cands if fy_end(r.fy) == target_year]
        r = exact[0] if exact else max(cands, key=lambda x: fy_end(x.fy)) if all(fy_end(x.fy) <= target_year for x in cands) else None
        if r is None:
            older = [x for x in cands if fy_end(x.fy) < target_year]
            r = max(older, key=lambda x: fy_end(x.fy)) if older else None
        if r is None:
            return None, ""
        m = ""
        key = (r.item, r.basis)
        if key not in REFERENCE and (r.item, "*") not in REFERENCE:
            if key in NOTES:
                m += mark(f"{company}: {NOTES[key]}")
            else:
                unresolved.append(f"{company} の {r.item}（{r.basis}）は、{concept}の列と定義が同じか説明できないため置かなかった")
                return None, ""
        if r.unit not in TO_OKU and r.unit not in ("%", "—"):
            unresolved.append(f"{company} の {r.item} の単位 {r.unit} は換算できないため置かなかった")
            return None, ""
        if fy_end(r.fy) != target_year and "-" not in r.fy:
            m += mark(f"{company}: {concept}は {r.fy} の値（比較年 FY{target_year} の値がない）")
        return r, m

    # ---- 財務の表
    fin_cols = ["売上", "営業利益", "営業利益率", "純利益", "ROE", "CAGR"]
    # CAGR の共通期間
    starts = None
    for k in range(args.cagr_years, 0, -1):
        s = Y - k
        if all(s in years_by_co[c] and Y in years_by_co[c] for c in companies):
            starts = s
            break
    cagr_n = (Y - starts) if starts is not None else None
    cagr_head = f"売上の年平均成長率 FY{starts}→{year_label}（{cagr_n} 年、%）" if starts is not None else "売上の年平均成長率（%）"
    if starts is None:
        cautions.append("全社に共通する期間がないため、売上の年平均成長率は — のまま")
    elif cagr_n != args.cagr_years:
        cautions.append(f"{args.cagr_years} 年の期間が全社でそろわないため、FY{starts}→{year_label}（{cagr_n} 年）にそろえた。"
                        f"「{args.cagr_years} 年 CAGR」と呼ばない")

    out = [f"## 競合比較（{year_label}、連結）", "", "### 財務", "",
           f"| 会社 | 会計基準 | 売上（億円） | 営業利益（億円） | 営業利益率（%） | 当期純利益（億円） | ROE（%） | {cagr_head} |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for c in companies:
        cells = {}
        rev, mrev = pick(c, "売上")
        op, mop = pick(c, "営業利益")
        ni, mni = pick(c, "純利益")
        eq, meq = pick(c, "純資産")
        basis = rev.basis if rev else "—"
        for name, r, mk in (("売上", rev, mrev), ("営業利益", op, mop), ("純利益", ni, mni)):
            cells[name] = f"{fmt(r.num(), '億円')} [{ensure_id(r)}]{mk}" if r else "—"
        if rev and op:
            v = op.num() / rev.num() * 100
            rid = L.add("F", v, "%", f"営業利益率（{op.item}／{rev.item}、{op.basis}）{c}", op.fy, "推定",
                        f"{ensure_id(op)} / {ensure_id(rev)}", [op.id, rev.id])
            cells["営業利益率"] = f"{pct(v)} [{rid}]{mop}"
        else:
            cells["営業利益率"] = "—"
        if ni and eq:
            v = ni.num() / eq.num() * 100
            rid = L.add("F", v, "%", f"ROE（{ni.item}／期末{eq.item}、{eq.basis}）{c}", ni.fy, "推定",
                        f"{ensure_id(ni)} / {ensure_id(eq)}", [ni.id, eq.id])
            cells["ROE"] = f"{pct(v)} [{rid}]{meq}"
        else:
            cells["ROE"] = "—"
        if starts is not None:
            r0, m0 = pick(c, "売上", starts)
            r1 = rev
            if r0 and r1 and fy_end(r0.fy) == starts:
                v = ((r1.num() / r0.num()) ** (1 / cagr_n) - 1) * 100
                rid = L.add("F", v, "%", f"売上の年平均成長率（{r1.item}、{r1.basis}）{c}", f"FY{starts}-{year_label}",
                            "推定", f"({ensure_id(r1)} / {ensure_id(r0)})^(1/{cagr_n}) − 1", [r1.id, r0.id])
                cells["CAGR"] = f"{pct(v)} [{rid}]{mrev}"
            else:
                cells["CAGR"] = "—"
        else:
            cells["CAGR"] = "—"
        out.append(f"| {c} | {basis} | " + " | ".join(cells[k] for k in fin_cols) + " |")
    out.append("")

    # ---- 戦略・KPI の表
    ma_period = next((r.fy for r in rows if r.item == "M&A 投資額累計" and "-" in r.fy), None)
    out += ["### 戦略・KPI", "",
            f"| 会社 | 海外売上比率（%） | M&A 投資額累計 {ma_period or ''}（億円） | 主力セグメント（売上構成比） |",
            "|---|---:|---:|---|"]
    for c in companies:
        ovs, movs = pick(c, "海外売上比率")
        ovs_cell = f"{pct(ovs.num())} [{ensure_id(ovs)}]{movs}" if ovs else "—"
        # M&A
        ma_cell = "—"
        ma_rows = [r for r in by.get((c, "M&A 投資額累計"), [])]
        if ma_rows:
            r = ma_rows[0]
            ma_cell = f"{fmt(r.num(), '億円')} [{ensure_id(r)}]" + (mark(f"{c}: {r.note}") if r.note else "")
        elif c == args.target and capex_ma and ma_period:
            a, b = (int(x) for x in re.findall(r"FY(\d{4})", ma_period))
            inside = [r for r in capex_ma if a <= fy_end(r.fy) <= b]
            outside = [r for r in capex_ma if r.num() > 0 and not (a <= fy_end(r.fy) <= b)]
            if inside and len(inside) == b - a + 1:
                v = sum(r.num() for r in inside)
                ids = [ensure_id(r) for r in inside]
                rid = L.add("F", v, "億円", f"子会社株式の取得による支出の累計（日本基準、連結）{c}", ma_period, "推定",
                            " + ".join(ids), ids)
                ma_cell = f"{fmt(v, '億円')} [{rid}]" + mark(f"{c}: {NOTES[('子会社株式の取得による支出', '日本基準')]}")
                for o in outside:
                    cautions.append(f"{c}: 期間外の {o.fy} に子会社株式の取得 {fmt(o.num(), '億円')}億円 [{ensure_id(o)}] がある"
                                    + (f"（{o.note}）" if o.note else ""))
            else:
                unresolved.append(f"{c} の {ma_period} の子会社株式の取得による支出がそろっていない")
        # 主力セグメント
        seg_cell = "—"
        segr = by.get((c, "主力セグメント"), [])
        if segr:
            parts = []
            for piece in re.split(r"\s*/\s*", segr[0].value):
                mm = re.fullmatch(r"(.+?)\s*([\d.]+)\s*%", piece)
                if mm:
                    rid = L.add("F", float(mm.group(2)), "%", f"主力セグメント（{mm.group(1)}）の売上構成比 {c}",
                                segr[0].fy, "公開", segr[0].source or "—")
                    parts.append(f"{mm.group(1)} {float(mm.group(2)):.0f}% [{rid}]")
                else:
                    parts.append(piece)
            seg_cell = " / ".join(parts)
        elif (c, year_label) in seg_rev:
            total, _ = pick(c, "売上")
            segs = sorted(seg_rev[(c, year_label)], key=lambda r: -r.num())
            if total and segs:
                top = segs[0]
                v = top.num() / total.num() * 100
                rid = L.add("F", v, "%", f"主力セグメント（{top.item}）の売上構成比 {c}", year_label, "推定",
                            f"{ensure_id(top)} / {ensure_id(total)}", [top.id, total.id])
                seg_cell = f"{top.item} {pct(v)}% [{rid}]" + mark(f"{c}: セグメント間の内部売上を含むかは未確認（構成比は外部売上の合計で割った）")
        out.append(f"| {c} | {ovs_cell} | {ma_cell} | {seg_cell} |")
    out.append("")

    if notes:
        out += ["注記:", ""]
        out += [f"- ※{i} {t}" for i, t in enumerate(notes, 1)]
        out.append("")

    out += ["### 前提と未確認事項", ""]
    out.append("- ROE は期末の純資産（IFRS は親会社の所有者に帰属する持分）で割った。期首・期末平均ではない。日本基準の純資産は非支配株主持分を含む")
    out.append("- 決算月がそろっているかは未確認（FY の表記が同じでも期末月が違うことがある）")
    out.append("- 海外売上比率の「海外」の定義（顧客の所在地か、拠点の所在地か）は会社ごとに確認する")
    for x in cautions + [f"置かなかった値: {u}" for u in unresolved] + L.warnings + [f"台帳にある同じ事実を使った: {u}" for u in L.reused]:
        out.append(f"- {x}")
    out.append("")

    text = "\n".join(out)
    print(text)
    if L.new_rows:
        print("### 台帳に追記する行（facts.csv）\n")
        print("```csv")
        print(L.csv_text())
        print("```")
        if args.write:
            L.write()
            print(f"\n{len(L.new_rows)} 行を {args.facts} に追記した。")
        else:
            print("\n（--write を付けると facts.csv に追記する。付けない場合、本体の ID は予定の番号）")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
