#!/usr/bin/env python3
"""市場規模をトップダウン（市場規模 × 成長）とボトムアップ（要因の掛け算）の両方で幅つきで見積もり、突き合わせる。

トップダウン（セグメントごと）:
  対象市場（基準年）= 業界団体の市場規模 × 自社の定義に合う割合（scope）
  対象市場（目標年）= 対象市場（基準年） × (1 + 成長率)^年数
  幅: 低 = 成長率の低ケース × scope の低、高 = 成長率の高ケース × scope の高。
      成長率の低ケースを渡さなければ「基準ケース − haircut」と置く（業界見通しは下方修正されがち）。
      高ケースを渡さなければ基準ケースと同じにする（上振れは置かない）
  自社の推定シェア（基準年）= 自社売上 / 対象市場（基準年）
ボトムアップ（--bottom-up の CSV）:
  セグメントごとに要因（台数 × 搭載率 × 単価 など）を掛ける。低・基準・高をそれぞれ掛ける
  列: segment,factor,low,base,high,unit,id,source_tag,source,replace_by
  （id があれば台帳の値を基準に使う。なければ source_tag と source で台帳に載せる）
突き合わせ: 目標年の基準ケースで、トップダウンとボトムアップの差が --tolerance %% を超えたら注意を出す

使い方の例:
  python3 market_sizing.py --facts case/facts/facts.csv --years 5 --base-year FY2025 \\
      --size 自動車向け=@F-207 --growth 自動車向け=@F-202 --scope 自動車向け=0.10:0.15:0.20 \\
      --company 自動車向け=@F-184 --bottom-up case/facts/market-bottom-up.csv \\
      --out case/facts/market-sizing.body.md --write
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


def _formula_key(src: str) -> str:
    """計算式の比較用。空白と記号の書き方の違いを落とす。"""
    return re.sub(r"\s+", "", src or "").replace("−", "-").replace("／", "/").replace("÷", "/").replace("×", "*")


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
            # 同じ計算式（入力 ID と演算）の行が別のスキルから登録済みなら使い回す（同じ事実を二重に載せない）
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
def parse_triple(spec: str) -> tuple[str, list[float]]:
    name, rhs = spec.split("=", 1)
    parts = [float(x) for x in rhs.split(":")]
    if len(parts) == 1:
        parts = parts * 3
    if len(parts) != 3 or not (parts[0] <= parts[1] <= parts[2]):
        sys.exit(f"エラー: {spec!r} は 名前=低:基準:高（低 ≤ 基準 ≤ 高）で渡す")
    return name.strip(), parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", action="append", default=[], help="基準年の市場規模（業界団体の定義）。名前=値[@ID]")
    ap.add_argument("--growth", action="append", default=[], help="成長率の基準ケース（年 %%）。名前=値[@ID]")
    ap.add_argument("--growth-low", action="append", default=[], help="成長率の低ケース。名前=値[@ID]")
    ap.add_argument("--growth-high", action="append", default=[], help="成長率の高ケース。名前=値[@ID]")
    ap.add_argument("--haircut", type=float, default=1.0, help="低ケースを渡さないときに基準から引く pt（既定 1.0）")
    ap.add_argument("--scope", action="append", default=[],
                    help="業界団体の市場のうち自社の定義に合う割合。名前=低:基準:高（0〜1）。渡さなければ 1 で注意を出す")
    ap.add_argument("--company", action="append", default=[], help="自社の基準年売上（推定シェア用）。名前=値[@ID]")
    ap.add_argument("--years", type=int, required=True)
    ap.add_argument("--base-year", default="FY2025")
    ap.add_argument("--bottom-up", type=Path, help="ボトムアップの要因 CSV")
    ap.add_argument("--tolerance", type=float, default=30.0, help="突き合わせで許す差（%%）")
    ap.add_argument("--unit", default="億円")
    ap.add_argument("--replace-by", default="", help="仮置きで置く値（定義に合う割合など）の差し替え期限")
    ap.add_argument("--facts", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    L = Ledger(args.facts, args.today)
    n, unit = args.years, args.unit
    m = re.fullmatch(r"FY(\d{4})", args.base_year)
    end_year = f"FY{int(m.group(1)) + n}" if m else f"基準年+{n}"
    period = f"{args.base_year}-{end_year}"
    notes: list[str] = []

    def vals(specs: list[str], suffix: str = "") -> dict[str, Val]:
        d = {}
        for s in specs:
            v = parse_val(s, L)
            v.suffix = suffix
            d[v.name] = v
        return d

    size, g_base = vals(args.size), vals(args.growth, "%")
    g_low, g_high = vals(args.growth_low, "%"), vals(args.growth_high, "%")
    company = vals(args.company)
    scope = dict(parse_triple(s) for s in args.scope)

    if args.write:
        no_id = [v.name for d in (size, g_base, g_low, g_high, company) for v in d.values() if not v.id]
        if no_id:
            sys.exit(f"エラー: --write するには入力に台帳の ID が要る。ID がないもの: {', '.join(sorted(set(no_id)))}")

    out: list[str] = [f"## 市場規模（{args.base_year} → {end_year}、{n} 年）", ""]
    td: dict[str, tuple[float, float, float, list[str]]] = {}
    if size:
        out += ["### トップダウン（市場規模 × 自社の定義に合う割合 × 成長）", "",
                f"| 市場 | 市場規模 {args.base_year}（{unit}） | 定義に合う割合（低/基準/高） | 成長率 低/基準/高（%/年） | "
                f"対象市場 {end_year} 低（{unit}） | 基準 | 高 | 自社の推定シェア {args.base_year}（%） |",
                "|---|---:|---|---|---:|---:|---:|---:|"]
    for name, sz in size.items():
        if name not in g_base:
            sys.exit(f"エラー: {name} の成長率（--growth）がない")
        gb = g_base[name]
        if name in g_low:
            gl = g_low[name]
        else:
            lid = L.add("F", gb.value - args.haircut, "%",
                        f"市場成長率の低ケース（{name}、基準 − {args.haircut}pt。見通しの下方修正を見込む）", period,
                        "推定", f"{gb.ref()} − {args.haircut}pt", [gb.id] if gb.id else [])
            gl = Val(name, gb.value - args.haircut, lid, "%")
            notes.append(f"{name}: 成長率の低ケース {pct(gl.value)}% [{lid}] は、見通しの下方修正を見込んで基準から引いて置いた（--growth-low で上書きできる）")
        gh = g_high.get(name, gb)
        if name not in g_high:
            notes.append(f"{name}: 成長率の高ケースは基準と同じに置いた（上振れは置かない）")
        sc = scope.get(name)
        if sc is None:
            sc = [1.0, 1.0, 1.0]
            notes.append(f"{name}: 業界団体の市場の定義と自社の売上の定義の差を見ていない（scope=1）。シェアと対象市場は過大になりうる")
        sc_ids = []
        for lab, v in zip(("低", "基準", "高"), sc):
            sc_ids.append(L.add("F", v * 100, "%", f"業界団体の市場のうち自社の定義に合う割合（{name}、{lab}）",
                                args.base_year, "仮置き" if name in scope else "推定",
                                "—" if name in scope else "定義の差を見ていないため 1 と置いた",
                                replace_by=args.replace_by if name in scope else ""))
        res, ids = [], []
        for lab, g, s, sid in zip(("低", "基準", "高"), (gl, gb, gh), sc, sc_ids):
            v = sz.value * s * (1 + g.value / 100) ** n
            rid = L.add("F", v, unit, f"対象市場（{name}、{lab}ケース）", end_year, "推定",
                        f"{sz.ref()} × {sid} × (1+{g.ref()})^{n}", [x for x in (sz.id, sid, g.id) if x])
            res.append(v)
            ids.append(rid)
        td[name] = (res[0], res[1], res[2], ids)
        share_cell = "—"
        if name in company:
            cv = company[name]
            sh = cv.value / (sz.value * sc[1]) * 100
            shid = L.add("F", sh, "%", f"自社の推定シェア（{name}、対象市場の基準ケース）", args.base_year, "推定",
                         f"{cv.ref()} / ({sz.ref()} × {sc_ids[1]})", [x for x in (cv.id, sz.id, sc_ids[1]) if x])
            share_cell = f"{pct(sh)} [{shid}]"
        # 割合の値の直後に ID を付ける（number-audit が値と台帳を突き合わせられるように）
        sc_cell = " / ".join(f"{x:.0%} [{sid}]" for x, sid in zip(sc, sc_ids))
        out.append(f"| {name} | {oku(sz.value)}{tag(sz.id)} | {sc_cell} | "
                   f"{pct(gl.value)}{tag(gl.id)} / {pct(gb.value)}{tag(gb.id)} / {pct(gh.value)}{tag(gh.id)} | "
                   f"{oku(res[0])} [{ids[0]}] | {oku(res[1])} [{ids[1]}] | {oku(res[2])} [{ids[2]}] | {share_cell} |")
    if size:
        out.append("")

    bu: dict[str, tuple[float, float, float, list[str]]] = {}
    if args.bottom_up:
        factors: dict[str, list[dict[str, str]]] = {}
        with args.bottom_up.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                factors.setdefault(r["segment"].strip(), []).append(r)
        out += [f"### ボトムアップ（{end_year} の対象市場を要因の掛け算で）", "",
                "| 市場 | 要因 | 低 | 基準 | 高 | 単位 |", "|---|---|---:|---:|---:|---|"]
        for seg, rows in factors.items():
            prod = [1.0, 1.0, 1.0]
            fids = []
            for r in rows:
                lo, ba, hi = (float(r[k]) for k in ("low", "base", "high"))
                if not (lo <= ba <= hi):
                    sys.exit(f"エラー: {seg} の {r['factor']} は 低 ≤ 基準 ≤ 高 にする")
                rid = (r.get("id") or "").strip()
                if not rid:
                    tagv = (r.get("source_tag") or "").strip()
                    if args.write and tagv not in {"公開", "クライアント提供", "推定", "仮置き"}:
                        sys.exit(f"エラー: {seg} の {r['factor']} に id も source_tag もない")
                    if args.write and tagv == "仮置き" and not (r.get("replace_by") or "").strip():
                        sys.exit(f"エラー: {seg} の {r['factor']} は仮置きなので replace_by が要る")
                    rid = L.add("F", ba, r["unit"], f"ボトムアップの要因（{seg}、{r['factor']}、基準。幅 {lo:g}〜{hi:g}）",
                                end_year, tagv or "仮置き", (r.get("source") or "—").strip() or "—",
                                replace_by=(r.get("replace_by") or "").strip())
                fids.append(rid)
                prod = [prod[0] * lo, prod[1] * ba, prod[2] * hi]
                out.append(f"| {seg} | {r['factor']} | {lo:g} | {ba:g} [{rid}] | {hi:g} | {r['unit']} |")
            ids = []
            for lab, v in zip(("低", "基準", "高"), prod):
                ids.append(L.add("F", v, unit, f"対象市場（{seg}、ボトムアップ、{lab}ケース）", end_year, "推定",
                                 " × ".join(fids) + ("（低・高は各要因の幅の積）" if lab != "基準" else ""), fids))
            bu[seg] = (prod[0], prod[1], prod[2], ids)
            out.append(f"| **{seg}** | **積（{unit}）** | {oku(prod[0])} [{ids[0]}] | **{oku(prod[1])} [{ids[1]}]** | {oku(prod[2])} [{ids[2]}] | {unit} |")
        out += ["", "要因の単位の積が対象市場の単位になるように置く（例: 万台 × 万円 = 億円）。スクリプトは単位を確かめない。", ""]

    both = [s for s in td if s in bu]
    if both:
        out += [f"### 突き合わせ（{end_year}）", "",
                "| 市場 | トップダウン 基準（{u}） | ボトムアップ 基準（{u}） | 差（%） | 幅の重なり | 判定 |".format(u=unit),
                "|---|---:|---:|---:|---|---|"]
        for s in both:
            t, b = td[s], bu[s]
            diff = (b[1] - t[1]) / t[1] * 100
            did = L.add("F", diff, "%", f"ボトムアップとトップダウンの差（{s}、基準ケース）", end_year, "推定",
                        f"({b[3][1]} − {t[3][1]}) / {t[3][1]}", [b[3][1], t[3][1]])
            overlap = not (b[2] < t[0] or t[2] < b[0])
            ok = abs(diff) <= args.tolerance and overlap
            out.append(f"| {s} | {oku(t[1])} [{t[3][1]}] | {oku(b[1])} [{b[3][1]}] | {pct(diff)} [{did}] | "
                       f"{'重なる' if overlap else '重ならない'} | {'範囲内' if ok else '**要確認**（定義か要因を見直す）'} |")
        out.append("")
    for s in td:
        if s not in bu and args.bottom_up:
            notes.append(f"{s}: ボトムアップがない。トップダウンだけの値は 1 点の見積もりとして扱わない")
    if not args.bottom_up:
        notes.append("ボトムアップがない。トップダウンだけで成り行きの前提を確定しない")

    out += ["### 前提と未確認事項", ""]
    out.append("- 業界団体の市場の定義は、自社のセグメントの売上の定義と一致しない（どの製品・地域・取引段階を含むか）")
    out.append("- 業界見通しは過去に下方修正が続いたことがある。改定履歴を確かめる")
    for x in notes + L.warnings + [f"台帳にある同じ事実を使った: {u}" for u in L.reused]:
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
            bad = [r["id"] for r in L.new_rows if r["source_tag"] == "仮置き" and not r["replace_by"]]
            if bad:
                sys.exit(f"エラー: 仮置きの行に差し替え期限がない: {', '.join(bad)}（--replace-by を渡す）")
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
