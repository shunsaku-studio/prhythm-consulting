#!/usr/bin/env python3
"""有報・短信から取った財務データを facts/financials.csv（縦持ち）に揃え、台帳に登録し、不連続を報告する。

読める入力（自動判別。複数ファイルを続けて渡してよい）:
  (a) 縦持ち CSV（UTF-8）: fiscal_year,item,segment,value,unit,basis,source_page,note
      例: case/sources/yuho-excerpt.csv
  (b) EDINET API v2 の CSV（書類取得 type=5 の zip の中身。UTF-16、タブ区切り）
      列: 要素ID, 項目名, コンテキストID, 相対年度, 連結・個別, 期間・時点, ユニットID, 単位, 値
      --fiscal-year（その書類の「当期」の年度）と --doc-name（資料名）が要る

出力:
  --out      facts/financials.csv  列 id,fiscal_year,item,segment,value,unit,basis,source,note
  --ledger   facts/facts.csv に同じ id で追記（--append のとき。出典タグ「公開」）
  --report   不連続の報告と推移表（Markdown。例: facts/financials.md）

見つける不連続:
  - 注記にセグメントの組み替え・移管・会計基準の変更などの語がある
  - 同じ項目・セグメントで会計基準（basis）が年によって違う
  - 前年比が閾値（--jump、既定 20%）を超える（要確認。原因は人が確かめる）
  - セグメントの合計（+ 調整額）が連結と合わない
  - 子会社株式の取得による支出がある年（M&A による非連続の可能性）

使い方:
  python3 normalize.py case/sources/yuho-excerpt.csv \\
      --out case/facts/financials.csv --ledger case/facts/facts.csv --append \\
      --report case/facts/financials.md --company 対象会社
  python3 normalize.py edinet/XBRL_TO_CSV/jpcrp030000-asr-001_E00000-000_2026-03-31_01_2026-06-25.csv \\
      --fiscal-year FY2025 --doc-name "有価証券報告書 FY2025（EDINET S100XXXX）" --out ...

標準ライブラリだけで動く。Python 3.10 以上。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------- 台帳（facts.csv）
LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]
FIN_COLS = ["id", "fiscal_year", "item", "segment", "value", "unit", "basis", "source", "note"]


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
                self.warnings.append(f"{r['id']}（{definition} {period}）は台帳の値 {r['value']} と今回の値 {value} が違う。新しい ID で登録した（訂正報告書や遡及修正か確かめる）")
        rid = self.next_id(prefix)
        self.new.append({
            "id": rid, "value": value, "unit": unit, "definition": definition, "period": period,
            "source_tag": tag, "source": source, "retrieved_at": self.today,
            "confidentiality": confidentiality, "replace_by": replace_by if tag == "仮置き" else "",
        })
        return rid

    def find_same_public(self, value: str, unit: str, period: str, keywords: tuple[str, ...],
                         own_definition: str) -> dict[str, str] | None:
        """同じ事実が別の言い回しで「公開」として登録済みか。期間・単位・値が同じで、定義に keywords が全部入っている行。
        自分と同じ定義の行は register が見るので除く。"""
        for r in self.all_rows():
            if (r["id"].startswith("F-") and r["source_tag"] == "公開" and r["period"] == period
                    and r["unit"] == unit and r["definition"] != own_definition and _same(r["value"], value)
                    and all(k in r["definition"] for k in keywords)):
                return r
        return None

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


# ---------------------------------------------------------------- EDINET の要素 ID
# 代表的な要素だけ。実際の書類で要素 ID を確かめ、足りなければ --element-map で足す。
ELEMENT_MAP = {
    # 日本基準
    "jppfs_cor:NetSales": "売上高",
    "jppfs_cor:OperatingIncome": "営業利益",
    "jppfs_cor:OrdinaryIncome": "経常利益",
    "jppfs_cor:ProfitLossAttributableToOwnersOfParent": "親会社株主に帰属する当期純利益",
    "jppfs_cor:Assets": "総資産",
    "jppfs_cor:NetAssets": "純資産",
    "jppfs_cor:CashAndDeposits": "現金及び預金",
    "jppfs_cor:ShortTermLoansPayable": "短期借入金",
    "jppfs_cor:LongTermLoansPayable": "長期借入金",
    "jppfs_cor:BondsPayable": "社債",
    "jppfs_cor:NetCashProvidedByUsedInOperatingActivities": "営業活動によるキャッシュ・フロー",
    "jppfs_cor:NetCashProvidedByUsedInInvestmentActivities": "投資活動によるキャッシュ・フロー",
    "jppfs_cor:DepreciationAndAmortizationOpeCF": "減価償却費",
    "jppfs_cor:PurchaseOfPropertyPlantAndEquipmentInvCF": "有形固定資産の取得による支出",
    "jppfs_cor:PurchaseOfInvestmentsInSubsidiariesResultingInChangeInScopeOfConsolidationInvCF": "子会社株式の取得による支出",
    "jppfs_cor:CashDividendsPaidFinCF": "配当金の支払額",
    # 経営指標等の推移（有報の冒頭。5 期分が載る。要素名は書類で確かめる）
    "jpcrp_cor:NetSalesSummaryOfBusinessResults": "売上高",
    "jpcrp_cor:OrdinaryIncomeLossSummaryOfBusinessResults": "経常利益",
    "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults": "親会社株主に帰属する当期純利益",
    "jpcrp_cor:NetAssetsSummaryOfBusinessResults": "純資産",
    "jpcrp_cor:TotalAssetsSummaryOfBusinessResults": "総資産",
    "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults": "売上収益",
    # IFRS
    "jpigp_cor:RevenueIFRS": "売上収益",
    "jpigp_cor:OperatingProfitLossIFRS": "営業利益",
    "jpigp_cor:ProfitLossAttributableToOwnersOfParentIFRS": "親会社の所有者に帰属する当期利益",
    "jpigp_cor:AssetsIFRS": "資産合計",
    "jpigp_cor:EquityAttributableToOwnersOfParentIFRS": "親会社の所有者に帰属する持分",
    "jpigp_cor:CashAndCashEquivalentsIFRS": "現金及び現金同等物",
    "jpigp_cor:NetCashProvidedByUsedInOperatingActivitiesIFRS": "営業活動によるキャッシュ・フロー",
}
BASIS_BY_PREFIX = {"jppfs_cor": "日本基準", "jpigp_cor": "IFRS", "jpcrp_cor": "—"}
SCALE = {"億円": 1e8, "百万円": 1e6, "千円": 1e3, "円": 1.0}

NOTE_RE = re.compile(r"組み?替|移管|再編|新設|統合|廃止|遡及|会計基準|基準の変更|会計方針の変更|IFRS|決算期の変更|変則決算")
MA_ITEMS = {"子会社株式の取得による支出", "連結の範囲の変更を伴う子会社株式の取得による支出"}
SALES_ITEMS = {"売上高", "売上収益"}
PROFIT_ITEMS = {"セグメント利益", "営業利益"}


def is_utf16(path: Path) -> bool:
    head = path.read_bytes()[:2]
    return head in (b"\xff\xfe", b"\xfe\xff")


def read_longform(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "fiscal_year": r["fiscal_year"].strip(),
                "item": r["item"].strip(),
                "segment": (r.get("segment") or "連結").strip() or "連結",
                "value": (r["value"] or "").strip(),
                "unit": (r.get("unit") or "").strip(),
                "basis": (r.get("basis") or "—").strip() or "—",
                "source": (r.get("source_page") or r.get("source") or "").strip(),
                "note": (r.get("note") or "").strip(),
            })
    return rows


def rel_year(label: str, fy: int) -> int | None:
    label = label.strip()
    if label.startswith("当期"):
        return fy
    if label.startswith("前々期"):
        return fy - 2
    if label.startswith("前期"):
        return fy - 1
    m = re.match(r"(\d+)期前", label)
    if m:
        return fy - int(m.group(1))
    return None


def segment_from_context(ctx: str, seg_map: dict[str, str]) -> str | None:
    """コンテキスト ID からセグメントを読む。None のときはセグメント以外のメンバー（取り込まない）。"""
    parts = ctx.split("_")[1:]
    if not parts:
        return "連結"
    members = [p for p in parts if p.endswith("Member")]
    if not members:
        return "連結"
    if any(m in ("NonConsolidatedMember",) for m in members):
        return "単体"
    seg = [m for m in members if "ReportableSegment" in m or "Segment" in m]
    if len(seg) == 1 and len(members) == 1:
        key = seg[0].split("-")[-1]
        key = re.sub(r"^\d+", "", key)
        return seg_map.get(key, key)
    return None


def read_edinet(path: Path, fiscal_year: str, doc_name: str, to_unit: str,
                element_map: dict[str, str], seg_map: dict[str, str], include_nonconsol: bool) -> list[dict[str, str]]:
    fy_m = re.search(r"(\d{4})", fiscal_year or "")
    if not fy_m:
        sys.exit("エラー: EDINET の CSV には --fiscal-year（例: FY2025）が要ります")
    fy = int(fy_m.group(1))
    text = path.read_bytes().decode("utf-16")
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = [h.strip().strip('"') for h in next(reader)]
    idx = {h: i for i, h in enumerate(header)}
    need = ["要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別", "期間・時点", "単位", "値"]
    miss = [c for c in need if c not in idx]
    if miss:
        sys.exit(f"エラー: EDINET の CSV の列が足りません: {', '.join(miss)}")
    rows = []
    for rec in reader:
        if not rec:
            continue
        g = lambda c: rec[idx[c]].strip().strip('"') if idx[c] < len(rec) else ""  # noqa: E731
        eid = g("要素ID")
        if eid not in element_map:
            continue
        cons = g("連結・個別")
        if cons == "個別" and not include_nonconsol:
            continue
        y = rel_year(g("相対年度"), fy)
        if y is None:
            continue
        seg = segment_from_context(g("コンテキストID"), seg_map)
        if seg is None:
            continue
        if cons == "個別":
            seg = "単体"
        unit = g("単位")
        val = g("値").replace(",", "")
        if val in ("", "－", "-", "—"):
            continue
        try:
            v = float(val)
        except ValueError:
            continue
        if unit in SCALE:
            v = v * SCALE[unit] / SCALE[to_unit]
            unit = to_unit
        prefix = eid.split(":")[0]
        rows.append({
            "fiscal_year": f"FY{y}",
            "item": element_map[eid],
            "segment": seg,
            "value": f"{v:.1f}".rstrip("0").rstrip(".") if unit == to_unit else val,
            "unit": unit,
            "basis": ("IFRS" if "IFRS" in eid else "日本基準") if prefix == "jpcrp_cor" else BASIS_BY_PREFIX.get(prefix, "—"),
            "source": f"{doc_name}（{g('相対年度')}、要素 {eid}）",
            "note": "" if y == fy else f"{fiscal_year} の書類の比較情報（{g('相対年度')}）",
        })
    # 同じ年度・項目・セグメントが複数の書類から来たら、当期の書類（新しいもの）を優先
    return rows


def to_float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def fy_n(fy: str) -> int:
    m = re.search(r"(\d{4})", fy)
    return int(m.group(1)) if m else 0


def fmt(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


# ---------------------------------------------------------------- 本体
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="縦持ち CSV か EDINET の CSV")
    ap.add_argument("--company", default="対象企業", help="定義に書く社名")
    ap.add_argument("--fiscal-year", help="EDINET の CSV の「当期」の年度（例: FY2025）")
    ap.add_argument("--doc-name", default="有価証券報告書", help="EDINET の CSV の資料名（出典に書く）")
    ap.add_argument("--to-unit", default="百万円", choices=["億円", "百万円"], help="EDINET の円単位の値をこの単位に直す")
    ap.add_argument("--element-map", help="要素ID=項目名 をカンマ区切りで追加（EDINET）")
    ap.add_argument("--segment-map", help="セグメントのメンバー名=セグメント名 をカンマ区切り（EDINET）")
    ap.add_argument("--include-nonconsolidated", action="store_true", help="個別（単体）の値も取り込む")
    ap.add_argument("--jump", type=float, default=20.0, help="前年比の閾値 %%（既定 20）")
    ap.add_argument("--tolerance", type=float, default=0.5, help="セグメント合計と連結の差の許容 %%（既定 0.5）")
    ap.add_argument("--out", type=Path, required=True, help="facts/financials.csv")
    ap.add_argument("--ledger", type=Path, help="facts/facts.csv")
    ap.add_argument("--append", action="store_true", help="台帳に追記する")
    ap.add_argument("--report", type=Path, help="不連続の報告と推移表の Markdown")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    a = ap.parse_args()

    emap = dict(ELEMENT_MAP)
    if a.element_map:
        for kv in a.element_map.split(","):
            k, v = kv.split("=")
            emap[k.strip()] = v.strip()
    smap = {}
    if a.segment_map:
        for kv in a.segment_map.split(","):
            k, v = kv.split("=")
            smap[k.strip()] = v.strip()

    raw: list[dict[str, str]] = []
    for p in a.inputs:
        if is_utf16(p):
            raw += read_edinet(p, a.fiscal_year, a.doc_name, a.to_unit, emap, smap, a.include_nonconsolidated)
        else:
            raw += read_longform(p)

    # 既存の financials.csv の ID を使い回す（差分更新）
    existing: dict[tuple, dict[str, str]] = {}
    if a.out.exists():
        with a.out.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[(r["fiscal_year"], r["item"], r["segment"], r["basis"])] = r

    ledger = Ledger(a.ledger, a.today)
    merged: dict[tuple, dict[str, str]] = dict(existing)
    changed: list[str] = []
    reused: list[str] = []
    for r in raw:
        key = (r["fiscal_year"], r["item"], r["segment"], r["basis"])
        if key in merged and merged[key]["value"] != r["value"]:
            old = merged[key]
            # 当期の書類の値を比較情報より優先する
            if "比較情報" in r["note"] and "比較情報" not in old.get("note", ""):
                continue
            changed.append(f"{r['fiscal_year']} {r['segment']} {r['item']}: {old['value']} → {r['value']}（{r['source']}）")
        definition = f"{a.company} {r['segment']} {r['item']}（{r['basis']}）"
        if r["value"] in ("", "—"):
            rid = ledger.register("F", "—", r["unit"], definition, r["fiscal_year"], "公開", r["source"] or "—")
        else:
            # target-math・midterm-plan-reader が先に同じ値を別の言い回しで登録していれば、その ID を使う
            seg_kw = "連結" if r["segment"] == "連結" else r["segment"]
            hit = ledger.find_same_public(r["value"], r["unit"], r["fiscal_year"], (r["item"], seg_kw), definition)
            if hit:
                rid = hit["id"]
                reused.append(f"{rid}（{hit['definition']}、{r['fiscal_year']}）を {r['segment']} {r['item']} の ID として使い回した")
            else:
                rid = ledger.register("F", r["value"], r["unit"], definition, r["fiscal_year"], "公開", r["source"] or "—")
        merged[key] = {"id": rid, **r}

    rows = sorted(merged.values(), key=lambda r: (fy_n(r["fiscal_year"]), r["segment"] != "連結", r["segment"], r["item"]))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIN_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in FIN_COLS})

    # ------------------------------------------------ 不連続の検出
    findings: list[tuple[str, str, str, str, str]] = []  # (年度, 種類, 対象, 内容, ID)
    series: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        series[(r["item"], r["segment"])].append(r)

    note_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        if r["note"] and NOTE_RE.search(r["note"]):
            note_groups[(r["fiscal_year"], r["note"])].append(r)
    note_segs: dict[str, set[str]] = defaultdict(set)  # 年度 → 注記のあるセグメント（参考値の行は除く）
    for (fy, note), grp in note_groups.items():
        targets = "、".join(f"{r['segment']} {r['item']}" for r in grp)
        ids = ", ".join(r["id"] for r in grp)
        kind = "参考（組み替え後の比較情報）" if all("参考" in r["item"] for r in grp) else "不連続（注記）"
        findings.append((fy, kind, targets, f"注記の原文: `{note}`", ids))
        for r in grp:
            if "参考" not in r["item"]:
                note_segs[fy].add(r["segment"])

    for (item, seg), lst in series.items():
        lst.sort(key=lambda r: fy_n(r["fiscal_year"]))
        bases = {r["basis"] for r in lst}
        if len(bases) > 1:
            prev = None
            for r in lst:
                if prev and r["basis"] != prev["basis"]:
                    findings.append((r["fiscal_year"], "不連続（会計基準）", f"{seg} {item}",
                                     f"{prev['basis']} → {r['basis']}。前後の年は同じ基準で比べられない", f"{prev['id']}, {r['id']}"))
                prev = r
        for p, c in zip(lst, lst[1:]):
            if fy_n(c["fiscal_year"]) - fy_n(p["fiscal_year"]) != 1:
                findings.append((c["fiscal_year"], "要確認（欠年）", f"{seg} {item}", f"{p['fiscal_year']} の次が {c['fiscal_year']}", c["id"]))
                continue
            pv, cv = to_float(p["value"]), to_float(c["value"])
            if pv is None or cv is None or pv == 0 or "参考" in item or item in MA_ITEMS:
                continue
            if p["unit"] != c["unit"]:
                findings.append((c["fiscal_year"], "要確認（単位）", f"{seg} {item}", f"{p['unit']} → {c['unit']}", c["id"]))
                continue
            yoy = (cv / pv - 1) * 100
            if abs(yoy) > a.jump:
                kind = "要確認（前年比）"
                if seg in note_segs.get(c["fiscal_year"], set()):
                    kind = "不連続（注記のある年の変動）"
                findings.append((c["fiscal_year"], kind, f"{seg} {item}",
                                 f"{fmt(pv)} {p['unit']} [{p['id']}] → {fmt(cv)} {c['unit']} [{c['id']}]（前年比 {yoy:+.1f}%）。原因を確かめる", f"{p['id']}, {c['id']}"))

    # 組み替え後の参考値があれば、同じ定義での前年比を出す
    restated = [r for r in rows if "組み替え後" in r["item"] or "組替後" in r["item"]]
    like_for_like: list[tuple[str, str, float, float, str, str]] = []
    for r in restated:
        base_item = re.sub(r"（.*?）", "", r["item"]).strip()
        nxt = f"FY{fy_n(r['fiscal_year']) + 1}"
        cur = next((x for x in rows if x["item"] == base_item and x["segment"] == r["segment"] and x["fiscal_year"] == nxt), None)
        if cur and to_float(cur["value"]) and to_float(r["value"]):
            g = (float(cur["value"]) / float(r["value"]) - 1) * 100
            gid = ledger.register("F", f"{g:.2f}", "%", f"{a.company} {r['segment']} {base_item}の前年比（組み替え後の定義で比較）",
                                  nxt, "推定", f"{cur['id']}/{r['id']}-1")
            like_for_like.append((r["segment"], f"{r['fiscal_year']}→{nxt}", float(r["value"]), float(cur["value"]), r["id"], cur["id"], g, gid))

    # セグメント合計と連結の突き合わせ
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_year[r["fiscal_year"]].append(r)
    recon: list[tuple[str, str, float, float, str]] = []
    for fy, lst in sorted(by_year.items(), key=lambda kv: fy_n(kv[0])):
        cons = {r["item"]: r for r in lst if r["segment"] == "連結"}
        segs = [r for r in lst if r["segment"] not in ("連結", "調整額", "単体") and "参考" not in r["item"]]
        adj = sum(to_float(r["value"]) or 0 for r in lst if r["segment"] == "調整額")
        for s_item in SALES_ITEMS:
            parts = [r for r in segs if r["item"] == s_item]
            if parts and s_item in cons and to_float(cons[s_item]["value"]):
                total = sum(to_float(r["value"]) or 0 for r in parts)
                cv = float(cons[s_item]["value"])
                ok = abs(total - cv) / cv * 100 <= a.tolerance
                recon.append((fy, f"{s_item}: セグメント計 {fmt(total)} / 連結 {fmt(cv)}", total, cv, "一致" if ok else "差あり"))
                if not ok:
                    findings.append((fy, "要確認（合計）", f"セグメント {s_item}", f"セグメント計 {fmt(total)} と連結 {fmt(cv)} [{cons[s_item]['id']}] が合わない（セグメント間取引の消去か、組み替えか）", cons[s_item]["id"]))
        parts = [r for r in segs if r["item"] == "セグメント利益"]
        if parts and "営業利益" in cons and to_float(cons["営業利益"]["value"]):
            total = sum(to_float(r["value"]) or 0 for r in parts) + adj
            cv = float(cons["営業利益"]["value"])
            ok = abs(total - cv) <= max(abs(cv) * a.tolerance / 100, 0.05)
            recon.append((fy, f"セグメント利益計 + 調整額 {fmt(total)} / 連結営業利益 {fmt(cv)}", total, cv, "一致" if ok else "差あり"))
            if not ok:
                findings.append((fy, "要確認（合計）", "セグメント利益", f"セグメント利益計 + 調整額 {fmt(total)} と連結営業利益 {fmt(cv)} [{cons['営業利益']['id']}] が合わない", cons["営業利益"]["id"]))

    for r in rows:
        if r["item"] in MA_ITEMS and (to_float(r["value"]) or 0) > 0:
            findings.append((r["fiscal_year"], "非連続（M&A）", "連結", f"子会社株式の取得 {r['value']} {r['unit']} [{r['id']}]。翌年以降の売上に買収による上積みを含む可能性", r["id"]))

    findings.sort(key=lambda f: (fy_n(f[0]), f[1]))

    # ------------------------------------------------ 報告
    out: list[str] = []
    P = out.append
    years = sorted({r["fiscal_year"] for r in rows}, key=fy_n)
    P(f"# {a.company} 財務データの推移と不連続の報告")
    P("")
    P(f"- 入力: {', '.join(p.name for p in a.inputs)}")
    P(f"- 年度: {years[0]}〜{years[-1]}（{len(years)} 期）、行数: {len(rows)}")
    P(f"- 台帳に足した行: {len(ledger.new)}")
    P("")
    P("## 1. 不連続と要確認")
    P("")
    if findings:
        P("| 年度 | 種類 | 対象 | 内容 | 関係する ID |")
        P("|------|------|------|------|------------|")
        for f_ in findings:
            P(f"| {f_[0]} | {f_[1]} | {f_[2]} | {f_[3]} | {f_[4]} |")
    else:
        P("— （見つからなかった。見つからないことは不連続がないことの証明ではない）")
    P("")
    if like_for_like:
        P("### 組み替え後の定義での前年比")
        P("")
        P("| セグメント | 期間 | 組み替え後の前年 | 当年 | 前年比 |")
        P("|-----------|------|----------------|------|-------|")
        for seg, per, pv, cv, pid, cid, g, gid in like_for_like:
            P(f"| {seg} | {per} | {fmt(pv)} [{pid}] | {fmt(cv)} [{cid}] | {g:+.1f}% [{gid}] |")
        P("")
        P("組み替えのある年の前年比は、組み替え前の数字どうしで比べない。この表の値を使う。")
        P("")
    P("## 2. 連結の主要項目の推移")
    P("")
    key_items = ["売上高", "売上収益", "営業利益", "親会社株主に帰属する当期純利益", "親会社の所有者に帰属する当期利益",
                 "総資産", "資産合計", "純資産", "親会社の所有者に帰属する持分", "現金及び預金", "有利子負債",
                 "営業活動によるキャッシュ・フロー", "設備投資額", "子会社株式の取得による支出"]
    cons_rows = {(r["item"], r["fiscal_year"]): r for r in rows if r["segment"] == "連結"}
    present = [i for i in key_items if any((i, y) in cons_rows for y in years)]
    unit = next((r["unit"] for r in rows if r["segment"] == "連結"), "")
    P(f"単位: {unit}。各セルの [ID] で facts.csv の出典をたどれる。")
    P("")
    P("| 項目 | " + " | ".join(years) + " |")
    P("|------|" + "|".join("------" for _ in years) + "|")
    for i in present:
        cells = []
        for y in years:
            r = cons_rows.get((i, y))
            cells.append(f"{r['value']} [{r['id']}]" if r else "—")
        P(f"| {i} | " + " | ".join(cells) + " |")
    P("")
    seg_names = sorted({r["segment"] for r in rows if r["segment"] not in ("連結", "調整額", "単体")})
    if seg_names:
        P("## 3. セグメント別の売上高と利益")
        P("")
        P("| セグメント | 項目 | " + " | ".join(years) + " |")
        P("|-----------|------|" + "|".join("------" for _ in years) + "|")
        seg_rows = {(r["segment"], r["item"], r["fiscal_year"]): r for r in rows}
        for s in seg_names:
            for i in sorted({r["item"] for r in rows if r["segment"] == s}, key=lambda x: (x not in SALES_ITEMS, "参考" in x, x)):
                cells = []
                for y in years:
                    r = seg_rows.get((s, i, y))
                    cells.append(f"{r['value']} [{r['id']}]" if r else "—")
                P(f"| {s} | {i} | " + " | ".join(cells) + " |")
        P("")
    if recon:
        P("## 4. セグメント合計と連結の突き合わせ")
        P("")
        P("| 年度 | 突き合わせ | 結果 |")
        P("|------|-----------|------|")
        for fy, label, _t, _c, res in recon:
            P(f"| {fy} | {label} | {res} |")
        P("")
    P("## 前提と未確認事項（スクリプトが置いた前提）")
    P("")
    P(f"- 前年比の閾値は --jump の値（今回 {a.jump:g}）。閾値を超えた変動が組み替え・買収・会計基準の変更によるものかは、有報の注記で人が確かめる")
    P("- 不連続が見つからなかった項目も、原資料の注記（セグメント情報、会計方針の変更、企業結合）を読まずに連続とみなさない")
    for c in changed:
        P(f"- 値の上書き: {c}")
    for wmsg in ledger.warnings:
        P(f"- {wmsg}")
    for rmsg in reused:
        P(f"- 台帳にある同じ事実を使った: {rmsg}")
    P("")
    text = "\n".join(out)
    print(text)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(text + "\n", encoding="utf-8")
    if a.ledger and a.append:
        ledger.write()
        print(f"<!-- 台帳 {a.ledger} に {len(ledger.new)} 行を追記した -->", file=sys.stderr)
    elif ledger.new:
        print(f"<!-- 台帳に追記する予定の行: {len(ledger.new)}（--ledger と --append で追記） -->", file=sys.stderr)
    print(f"<!-- {a.out} に {len(rows)} 行を書いた -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
