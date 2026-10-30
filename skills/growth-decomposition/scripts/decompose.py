#!/usr/bin/env python3
"""過去の売上成長を、セグメントごとに「市場成長」「M&A」「シェア・残差」に分ける。

計算すること（期首 R0、期末 R1、年数 n、市場成長率 m、買収した事業の売上寄与 MA）:
  市場成長 = R0 × ((1+m)^n − 1)
  M&A     = MA（期中に買収した事業の売上寄与。期末時点の寄与が分からなければ初年度の寄与で置く）
  シェア・残差 = (R1 − R0) − 市場成長 − M&A
  年率の内訳: 合計 = (R1/R0)^(1/n) − 1、オーガニック = ((R1 − MA)/R0)^(1/n) − 1、
             M&A = 合計 − オーガニック、シェア・残差 = オーガニック − m
参照する内訳: McKinsey 2017 の成長企業（年 8.7%）= 市場 5.4% / M&A 2.5% / シェア 0.8%

セグメントの組み替え:
  financials.csv に「売上高（組み替え後・参考）」の行があれば、その年を組み替えの比較年とみなす。
  期間が組み替えをまたぐとき、
    - 期首が比較年なら、組み替え後の値を期首に使う
    - 期首がそれより前なら、そのセグメントは分解しない（—）。代わりに
      (a) 組み替え前の期間と組み替え後の期間に分けた表、(b) 影響するセグメントの合算行 を出す

使い方の例:
  python3 decompose.py --financials case/facts/financials.csv --facts case/facts/facts.csv \\
      --from FY2016 --to FY2025 \\
      --market-growth 自動車部品=@F-210 --market-growth 産業機械部品=@F-211 --market-growth 電子部品=@F-212 \\
      --acquisition 産業機械部品:FY2019=@F-206 --out case/facts/growth-decomposition.md --write
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
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
MCK_SOURCE = "McKinsey「How growth champions thrive even in stagnating markets」(2017-08)"
MCK = [("合計", 8.7), ("市場成長（ポートフォリオ）", 5.4), ("M&A", 2.5), ("シェア獲得", 0.8)]
RESTATED_ITEM = "売上高（組み替え後・参考）"


def fy(s: str) -> int:
    m = re.fullmatch(r"FY(\d{4})", s.strip())
    if not m:
        sys.exit(f"エラー: 年度は FY2025 の形で渡す: {s!r}")
    return int(m.group(1))


class Fin:
    def __init__(self, path: Path, item: str) -> None:
        self.data: dict[tuple[int, str, str], dict[str, str]] = {}
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.data[(fy(r["fiscal_year"]), r["item"].strip(), r["segment"].strip())] = r
        self.item = item
        self.restated = {(y, seg): r for (y, it, seg), r in self.data.items() if it == RESTATED_ITEM}
        self.reorg_year = {seg: y for (y, seg) in self.restated}  # 比較年（組み替え後の値がある最後の旧年度）

    def get(self, year: int, seg: str, restated: bool = False) -> dict[str, str] | None:
        if restated:
            return self.restated.get((year, seg))
        return self.data.get((year, self.item, seg))

    def segments(self) -> list[str]:
        segs = []
        for (y, it, seg) in self.data:
            if it == self.item and seg not in ("連結", "調整額") and seg not in segs:
                segs.append(seg)
        return segs

    def years(self) -> list[int]:
        return sorted({y for (y, it, seg) in self.data if it == self.item})


class Line:
    def __init__(self, name: str, r0: float, r1: float, ids0: list[str], ids1: list[str], note: str = "") -> None:
        self.name, self.r0, self.r1, self.ids0, self.ids1, self.note = name, r0, r1, ids0, ids1, note
        self.m: Val | None = None
        self.ma: list[Val] = []
        self.refused = ""


def ref_sum(ids: list[str], vals: list[float]) -> str:
    parts = [i if i else f"{v:g}" for i, v in zip(ids, vals)]
    return parts[0] if len(parts) == 1 else "(" + " + ".join(parts) + ")"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--financials", type=Path, required=True, help="facts/financials.csv（縦持ち）")
    ap.add_argument("--item", default="売上高", help="分解する科目（既定: 売上高）")
    ap.add_argument("--from", dest="y0", help="期首の年度。例: FY2016（既定: データの最初）")
    ap.add_argument("--to", dest="y1", help="期末の年度。例: FY2025（既定: データの最後）")
    ap.add_argument("--market-growth", action="append", default=[],
                    help="期間中の市場成長率（年 %%）。セグメント=値[@ID] / セグメント=@ID。ないセグメントは —")
    ap.add_argument("--acquisition", action="append", default=[],
                    help="買収した事業の売上寄与。セグメント:年度=値[@ID]。例: 産業機械部品:FY2019=60@F-206")
    ap.add_argument("--facts", type=Path, help="facts/facts.csv。@ID の読み取りと追記に使う")
    ap.add_argument("--write", action="store_true", help="計算した行を facts.csv に追記する")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", type=Path, help="Markdown の本体を書き出すパス")
    args = ap.parse_args()

    L = Ledger(args.facts, args.today)
    F = Fin(args.financials, args.item)
    years = F.years()
    if not years:
        sys.exit(f"エラー: {args.financials} に科目 {args.item} がない")
    y0 = fy(args.y0) if args.y0 else years[0]
    y1 = fy(args.y1) if args.y1 else years[-1]
    if y1 <= y0:
        sys.exit("エラー: 期末は期首より後にする")
    segs = F.segments()
    warnings: list[str] = []

    mg: dict[str, Val] = {}
    for s in args.market_growth:
        v = parse_val(s, L)
        v.suffix = "%"
        mg[v.name] = v
    acqs: list[tuple[str, int, Val]] = []
    for s in args.acquisition:
        if "=" not in s or ":" not in s.split("=", 1)[0]:
            sys.exit(f"エラー: --acquisition は セグメント:年度=値 の形で渡す: {s!r}")
        lhs, rhs = s.split("=", 1)
        seg, year = lhs.split(":", 1)
        acqs.append((seg.strip(), fy(year), parse_val(f"{seg}={rhs}", L)))
        if seg.strip() not in segs:
            sys.exit(f"エラー: 買収のセグメント {seg} が financials.csv にない")

    if args.write:
        missing = [v.name for v in mg.values() if not v.id] + [v.name for _, _, v in acqs if not v.id]
        if missing:
            sys.exit(f"エラー: --write するには市場成長率と買収の寄与に台帳の ID が要る。ID がないもの: {', '.join(missing)}")

    # 期間の組み立て
    reorg_segs = sorted(F.reorg_year)
    periods = [(y0, y1)]
    crosses = [s for s in reorg_segs if y0 < F.reorg_year[s] + 1 <= y1 and y0 != F.reorg_year[s]]
    if crosses:
        ry = F.reorg_year[crosses[0]]
        periods += [(y0, ry), (ry, y1)]
        warnings.append(
            f"{'・'.join(crosses)} は FY{ry + 1} にセグメントを組み替えている（FY{ry} 以前は組み替え前の値）。"
            f"FY{y0}→FY{y1} ではこのセグメントを分解しない。FY{y0}→FY{ry}（組み替え前）と FY{ry}→FY{y1}（組み替え後）に分け、"
            f"合算行も出す")

    def acq_in(seg_list: list[str], a: int, b: int) -> list[Val]:
        out = []
        for seg, year, v in acqs:
            if seg in seg_list and a < year <= b:
                out.append(v)
        return out

    def growth_for(seg_list: list[str], r0s: list[float], label: str) -> Val | None:
        vals = [mg.get(s) for s in seg_list]
        if any(v is None for v in vals):
            return None
        if len(vals) == 1:
            return vals[0]
        w = sum(v.value * r for v, r in zip(vals, r0s)) / sum(r0s)
        return Val(label, w, None, "%")  # 合算行の市場成長率は期首売上で加重（台帳には推定で載せる）

    tables = []
    for (a, b) in periods:
        n = b - a
        lines: list[Line] = []
        for seg in segs:
            use_restated = seg in F.reorg_year and a == F.reorg_year[seg] and b > a
            r0row = F.get(a, seg, restated=use_restated)
            r1row = F.get(b, seg)
            if not r0row or not r1row:
                warnings.append(f"{seg} の FY{a} か FY{b} の{args.item}がない")
                continue
            ln = Line(seg, float(r0row["value"]), float(r1row["value"]), [r0row.get("id", "")], [r1row.get("id", "")],
                      "期首は組み替え後" if use_restated else "")
            if seg in crosses and (a, b) == (y0, y1):
                ln.refused = "組み替えをまたぐため分解しない"
            ln.m = mg.get(seg)
            ln.ma = acq_in([seg], a, b)
            lines.append(ln)
        # 合算行（組み替えをまたぐ期間）
        if crosses and (a, b) == (y0, y1):
            r0rows = [F.get(a, s) for s in crosses]
            r1rows = [F.get(b, s) for s in crosses]
            if all(r0rows) and all(r1rows):
                ln = Line("+".join(crosses) + "（合算）", sum(float(r["value"]) for r in r0rows),
                          sum(float(r["value"]) for r in r1rows), [r.get("id", "") for r in r0rows],
                          [r.get("id", "") for r in r1rows], "組み替えの影響を受けない合算")
                ln.m = growth_for(crosses, [float(r["value"]) for r in r0rows], ln.name)
                if ln.m is not None:
                    ws = [mg[s] for s in crosses]
                    ln.m.id = L.add("F", ln.m.value, "%", f"市場成長率（{ln.name}、期首売上で加重）", f"FY{a}-FY{b}", "推定",
                                    "(" + " + ".join(f"{w.ref()} × {i or r['value']}" for w, r, i in
                                                     zip(ws, r0rows, [r.get('id', '') for r in r0rows])) + ") / "
                                    + ref_sum([r.get("id", "") for r in r0rows], [float(r["value"]) for r in r0rows]),
                                    [w.id for w in ws if w.id] + [r.get("id", "") for r in r0rows if r.get("id")])
                ln.ma = acq_in(crosses, a, b)
                lines.append(ln)
        # 連結
        c0, c1 = F.get(a, "連結"), F.get(b, "連結")
        if c0 and c1:
            ln = Line("連結", float(c0["value"]), float(c1["value"]), [c0.get("id", "")], [c1.get("id", "")])
            ln.ma = acq_in(segs, a, b)
            if "連結" in mg:
                ln.m = mg["連結"]
            tables.append((a, b, n, lines, ln))
        else:
            tables.append((a, b, n, lines, None))

    out: list[str] = [f"## 成長の内訳（{args.item}）", ""]
    ref_ids = [L.add("F", v, "%", f"成長企業の年成長率の内訳: {k}", "10 年平均", "公開", MCK_SOURCE) for k, v in MCK]

    for (a, b, n, lines, cons) in tables:
        period = f"FY{a}-FY{b}"
        title = f"FY{a} → FY{b}（{n} 年）"
        if (a, b) != (y0, y1):
            title += "、組み替え前の基準" if b <= min(F.reorg_year.values(), default=9999) else "、組み替え後の基準"
        out += [f"### {title}", "",
                "| セグメント | 期首（億円） | 期末（億円） | 増分 | 市場成長 | M&A | シェア・残差 | 年率 合計（%） | 市場（%） | M&A（pt） | シェア・残差（pt） | 注 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
        seg_market_ids, seg_market_vals = [], []
        all_rows = lines + ([cons] if cons else [])
        # 連結の市場成長は、分解できたセグメント（合算行を含む）の市場成長の和で置く
        if cons and cons.m is None:
            usable = [ln for ln in lines if not ln.refused and ln.m is not None and
                      not (crosses and (a, b) == (y0, y1) and ln.name in crosses)]
            covered = sum(ln.r0 for ln in usable)
            if usable and abs(covered - cons.r0) < 0.5:
                cons.note = "市場成長はセグメントの和"
                cons.m = "SUM"  # type: ignore[assignment]
                cons_usable = usable
            else:
                cons_usable = []
        for ln in all_rows:
            r0ref = ref_sum(ln.ids0, [ln.r0] if len(ln.ids0) == 1 else [0] * len(ln.ids0))
            r1ref = ref_sum(ln.ids1, [ln.r1] if len(ln.ids1) == 1 else [0] * len(ln.ids1))
            inputs = [i for i in ln.ids0 + ln.ids1 if i]
            r0cell = f"{oku(ln.r0)}" + (f" [{ln.ids0[0]}]" if len(ln.ids0) == 1 and ln.ids0[0] else "")
            r1cell = f"{oku(ln.r1)}" + (f" [{ln.ids1[0]}]" if len(ln.ids1) == 1 and ln.ids1[0] else "")
            if ln.refused:
                # 組み替えをまたぐ値は台帳に載せない（期首と期末の範囲が違う）
                out.append(f"| {ln.name} | {r0cell} | {r1cell} | — | — | — | — | — | — | — | — | {ln.refused} |")
                continue
            d = ln.r1 - ln.r0
            did = L.add("F", d, "億円", f"{args.item}の増分（{ln.name}）", period, "推定", f"{r1ref} − {r0ref}", inputs)
            c = (ln.r1 / ln.r0) ** (1 / n) - 1
            cid = L.add("F", c * 100, "%", f"{args.item}の年平均成長率（{ln.name}）", period, "推定",
                        f"({r1ref} / {r0ref})^(1/{n}) − 1", inputs)
            ma = sum(v.value for v in ln.ma)
            ma_ref = " + ".join(v.ref() for v in ln.ma)
            if len(ln.ma) == 1 and ln.ma[0].id:
                maid = ln.ma[0].id
            elif ln.ma:
                maid = L.add("F", ma, "億円", f"M&A による売上寄与（{ln.name}）", period, "推定", ma_ref,
                             [v.id for v in ln.ma if v.id])
            else:
                maid = None
            ma_cell = f"{oku(ma)}" + (f" [{maid}]" if maid else "") if ln.ma else "0"
            co = ((ln.r1 - ma) / ln.r0) ** (1 / n) - 1
            mapt = c - co
            mapt_cell = "0.0"
            if ln.ma:
                mptid = L.add("F", mapt * 100, "pt", f"M&A による年率の寄与（{ln.name}）", period, "推定",
                              f"({r1ref} / {r0ref})^(1/{n}) − (({r1ref} − {maid or ma_ref}) / {r0ref})^(1/{n})",
                              inputs + ([maid] if maid else []))
                mapt_cell = f"{pct(mapt * 100)} [{mptid}]"
            if ln.m is None:
                oid = L.add("F", co * 100, "%", f"オーガニックの年平均成長率（{ln.name}）", period, "推定",
                            f"(({r1ref} − {maid or ma_ref or 0}) / {r0ref})^(1/{n}) − 1", inputs + ([maid] if maid else []))
                out.append(f"| {ln.name} | {r0cell} | {r1cell} | {oku(d)} [{did}] | — | {ma_cell} | — | {pct(c * 100)} [{cid}] | — | {mapt_cell} | — | 市場成長率がない（オーガニック {pct(co * 100)}% [{oid}]）{('。' + ln.note) if ln.note else ''} |")
                continue
            if ln.m == "SUM":
                mk = sum(x[0] for x in seg_market_vals)
                mkid = L.add("F", mk, "億円", f"市場成長による増分（{ln.name}、セグメントの和）", period, "推定",
                             " + ".join(seg_market_ids), seg_market_ids)
                meff = (1 + mk / ln.r0) ** (1 / n) - 1
                mpid = L.add("F", meff * 100, "%", f"市場成長の年率換算（{ln.name}）", period, "推定",
                             f"(1 + {mkid} / {r0ref})^(1/{n}) − 1", [mkid] + inputs)
                m_cell = f"{pct(meff * 100)} [{mpid}]"
                mval = meff
                mref = mpid
            else:
                mval = ln.m.value / 100
                mk = ln.r0 * ((1 + mval) ** n - 1)
                mref = ln.m.ref()
                mkid = L.add("F", mk, "億円", f"市場成長による増分（{ln.name}）", period, "推定",
                             f"{r0ref} × ((1+{mref})^{n} − 1)", inputs + ([ln.m.id] if ln.m.id else []))
                m_cell = f"{pct(ln.m.value)}" + (f" [{ln.m.id}]" if ln.m.id else "")
            if ln.name != "連結" and not (crosses and (a, b) == (y0, y1) and ln.name in crosses):
                seg_market_ids.append(mkid)
                seg_market_vals.append((mk, ln.name))
            sh = d - mk - ma
            shid = L.add("F", sh, "億円", f"シェア・残差による増分（{ln.name}）", period, "推定",
                         f"{did} − {mkid}" + (f" − {maid}" if maid else ""), [did, mkid] + ([maid] if maid else []))
            shpt = co - mval
            shpid = L.add("F", shpt * 100, "pt", f"シェア・残差による年率の寄与（{ln.name}）", period, "推定",
                          f"(({r1ref} − {maid or 0}) / {r0ref})^(1/{n}) − 1 − {mref}",
                          inputs + [x for x in (maid, mref) if x and ID_RE.fullmatch(x)])
            out.append(f"| {ln.name} | {r0cell} | {r1cell} | {oku(d)} [{did}] | {oku(mk)} [{mkid}] | {ma_cell} | "
                       f"{oku(sh)} [{shid}] | {pct(c * 100)} [{cid}] | {m_cell} | {mapt_cell} | {pct(shpt * 100)} [{shpid}] | {ln.note} |")
        out.append("")

    out += ["### 参照する内訳（McKinsey 2017、成長企業の年平均）", "",
            "| 内訳 | 年率（%） |", "|---|---:|"]
    for (k, v), rid in zip(MCK, ref_ids):
        out.append(f"| {k} | {pct(v)} [{rid}] |")
    out += ["", "シェア・残差が大きいときは、シェアを取った証拠（受注、顧客数、価格）を別に探す。"
            "残差には価格・為替・製品構成の変化も入る。", ""]

    out += ["### 前提と未確認事項", ""]
    if not mg:
        out.append("- 過去の市場成長率が渡されていない。市場成長とシェア・残差は — のまま")
    for seg in segs + ["連結"]:
        if seg not in mg and seg != "連結" and mg:
            out.append(f"- {seg} の市場成長率がない（— のまま）")
    for seg, year, v in acqs:
        out.append(f"- {seg} の FY{year} の買収は、売上寄与 {oku(v.value)}億円{(' [' + v.id + ']') if v.id else ''} を期末まで同じ額で置いた。"
                   "買収後の伸びはオーガニック（シェア・残差）に入る。期末時点の寄与は未確認")
    if F.reorg_year:
        for seg, y in F.reorg_year.items():
            out.append(f"- {seg}: FY{y + 1} に組み替え。組み替え後の比較値は FY{y} だけある。それより前は組み替え前の値")
    out.append("- 市場成長率の定義（業界団体の市場）と、売上の定義（セグメント）が一致するかは未確認")
    for w in warnings + L.warnings:
        out.append(f"- 注意: {w}")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
