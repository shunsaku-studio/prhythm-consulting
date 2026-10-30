#!/usr/bin/env python3
"""成り行き（S）とギャップ（G）を計算し、ギャップを打ち手のレバーに割り当てたときの無理の度合いを示す。

計算すること:
  1. 成り行き S = 基準年売上 × (1 + 市場成長率)^年数（セグメント別と合計）
  2. ギャップ G = 目標 − 成り行き（合計。セグメント別の目標があればセグメント別も）
  3. 目標に必要な年率
  4. レバー（シェア、新市場、M&A、価格…）への割り当てと未割当
  5. 各レバーが「市場成長に上乗せして年何 pt」を求めるか。
     シェアのレバーが年 5pt を超えたら赤旗。平均的な 0.8pt なら何億円にとどまるかも示す
     （McKinsey 2017: 成長企業の内訳 市場 5.4% / M&A 2.5% / シェア 0.8%。シェアだけで年 5% 超を
     10 年平均で得た企業は 13%）

値の渡し方:
  名前=値            例: 自動車部品=1050
  名前=値@ID         値と台帳の ID を両方渡す。例: 自動車部品=1050@F-184
  名前=@ID           値を facts.csv から読む。例: 自動車部品=@F-184
  レバーをセグメントに載せるときは 名前:セグメント=値。例: シェア:自動車部品=400

使い方の例（企画書の検算例）:
  python3 gap_bridge.py --base 連結=2000 --growth 5 --years 5 --target 5000 --lever シェア=800

案件フォルダで台帳に追記する例:
  python3 gap_bridge.py --facts case/facts/facts.csv \\
      --base 自動車部品=@F-184 --base 産業機械部品=@F-186 --base 電子部品=@F-188 \\
      --growth 自動車部品=@F-202 --growth 産業機械部品=@F-203 --growth 電子部品=@F-204 \\
      --years 5 --base-year FY2025 --target @T-001 --lever シェア=800 --lever M&A=1000 \\
      --replace-by 2026-11-13 --out case/03-gap-bridge.body.md --write
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
MCK_SOURCE = "McKinsey「How growth champions thrive even in stagnating markets」(2017-08)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", action="append", required=True,
                    help="基準年の売上。セグメントごとに繰り返す。名前=値[@ID] / 名前=@ID")
    ap.add_argument("--growth", action="append", required=True,
                    help="市場成長率（年 %%）。1 つだけなら全セグメント共通。名前=値[@ID] か 値[@ID]")
    ap.add_argument("--years", type=int, required=True, help="年数（基準年から目標年まで）")
    ap.add_argument("--base-year", default="", help="基準年。例: FY2025（目標年は基準年+年数）")
    ap.add_argument("--target", help="合計の売上目標。値[@ID] / @ID")
    ap.add_argument("--target-seg", action="append", default=[],
                    help="セグメント別の目標（人が決めたものだけ）。名前=値[@ID]")
    ap.add_argument("--lever", action="append", default=[],
                    help="ギャップの割り当て。名前=値[@ID] か 名前:セグメント=値[@ID]。シェアは「シェア」か「share」")
    ap.add_argument("--unit", default="億円")
    ap.add_argument("--share-redflag", type=float, default=5.0, help="シェア由来の上乗せがこの pt/年を超えたら赤旗")
    ap.add_argument("--share-avg", type=float, default=0.8, help="平均的なシェア由来の成長 pt/年（McKinsey 2017）")
    ap.add_argument("--facts", type=Path, help="facts/facts.csv。@ID の読み取りと追記に使う")
    ap.add_argument("--write", action="store_true", help="計算した行を facts.csv に追記する")
    ap.add_argument("--replace-by", default="", help="ID のないレバー割り当てを仮置きで登録するときの差し替え期限")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", type=Path, help="Markdown の本体を書き出すパス")
    args = ap.parse_args()

    L = Ledger(args.facts, args.today)
    n = args.years
    unit = args.unit
    warnings: list[str] = []

    bases = [parse_val(s, L, "連結") for s in args.base]
    names = [b.name for b in bases]
    if len(set(names)) != len(names):
        sys.exit("エラー: --base の名前が重複しています")

    growth: dict[str, Val] = {}
    if len(args.growth) == 1 and "=" not in args.growth[0]:
        g = parse_val(args.growth[0], L, "共通")
        g.suffix = "%"
        for nm in names:
            growth[nm] = g
    else:
        for s in args.growth:
            g = parse_val(s, L)
            g.suffix = "%"
            growth[g.name] = g
        missing = [nm for nm in names if nm not in growth]
        if missing:
            sys.exit(f"エラー: 市場成長率がないセグメント: {', '.join(missing)}")

    base_year = args.base_year
    if not base_year and bases[0].id and L.get(bases[0].id):
        base_year = L.get(bases[0].id)["period"]
    m = re.fullmatch(r"FY(\d{4})", base_year or "")
    end_year = f"FY{int(m.group(1)) + n}" if m else f"基準年+{n}"
    period = f"{base_year}-{end_year}" if m else f"{n} 年"

    if args.write:
        no_id = [b.name for b in bases if not b.id] + [g.name for g in growth.values() if not g.id]
        if no_id:
            sys.exit("エラー: --write するには基準年売上と市場成長率に台帳の ID が要る（@ID で渡す）。"
                     f" ID がないもの: {', '.join(sorted(set(no_id)))}")

    # 1. 成り行き
    seg_rows = []
    s_ids: dict[str, str] = {}
    s_val: dict[str, float] = {}
    for b in bases:
        g = growth[b.name]
        s = b.value * (1 + g.value / 100) ** n
        s_val[b.name] = s
        sid = L.add("S", s, unit, f"成り行き売上（{b.name}、市場成長のみ）", end_year, "推定",
                    f"{b.ref()} × (1+{g.ref()})^{n}", [x for x in (b.id, g.id) if x])
        s_ids[b.name] = sid
        seg_rows.append((b, g, s, sid))

    base_total = sum(b.value for b in bases)
    s_total = sum(s_val.values())
    multi = len(bases) > 1
    if multi:
        st_id = L.add("S", s_total, unit, "成り行き売上（合計、市場成長のみ）", end_year, "推定",
                      " + ".join(s_ids[nm] for nm in names), list(s_ids.values()))
    else:
        st_id = s_ids[names[0]]
    base_ref = " + ".join(b.ref() for b in bases) if multi else bases[0].ref()
    base_ref_p = f"({base_ref})" if multi else base_ref
    inc_id = L.add("S", s_total - base_total, unit, "市場成長による増分（合計）", period, "推定",
                   f"{st_id} − {base_ref_p}", [st_id] + [b.id for b in bases if b.id])
    g_blend = (s_total / base_total) ** (1 / n) - 1
    if multi:
        gb_id = L.add("S", g_blend * 100, "%", "市場成長の加重平均（成り行きから逆算した年率）", period, "推定",
                      f"({st_id} / {base_ref_p})^(1/{n}) − 1", [st_id] + [b.id for b in bases if b.id])
    else:
        gb_id = growth[names[0]].id

    # 2. 目標とギャップ
    target = parse_val(args.target, L, "合計") if args.target else None
    g_total = None
    gt_id = req_id = None
    req = 0.0
    if target:
        g_total = target.value - s_total
        gt_id = L.add("G", g_total, unit, "ギャップ（合計、目標 − 成り行き）", end_year, "推定",
                      f"{target.ref()} − {st_id}", [x for x in (target.id, st_id) if x])
        req = (target.value / base_total) ** (1 / n) - 1
        # target-math が同じ目標・同じ期間の必要年率（T-）を登録済みなら、その ID を使う（同じ事実を二重に載せない）
        tm = None
        if target.id:
            for r in L.rows + L.new_rows:
                if (r["id"].startswith("T-") and r["period"] == period and r["unit"] == "%" and r["source_tag"] == "推定"
                        and _formula_key(r["source"]).startswith(f"({target.id}/") and f"^(1/{n})" in r["source"]):
                    try:
                        if abs(float(r["value"]) - req * 100) <= 0.051:
                            tm = r["id"]
                            L.reused.append(f"{r['id']}（{r['definition']}）")
                            break
                    except ValueError:
                        pass
        req_id = tm or L.add("G", req * 100, "%", "目標達成に必要な年率（合計）", period, "推定",
                             f"({target.ref()} / {base_ref_p})^(1/{n}) − 1",
                             [x for x in [target.id] + [b.id for b in bases] if x])
    seg_targets = {v.name: v for v in (parse_val(s, L) for s in args.target_seg)}
    g_seg: dict[str, tuple[float, str]] = {}
    for nm, tv in seg_targets.items():
        if nm not in s_val:
            sys.exit(f"エラー: --target-seg の {nm} が --base にない")
        gv = tv.value - s_val[nm]
        gid = L.add("G", gv, unit, f"ギャップ（{nm}、目標 − 成り行き）", end_year, "推定",
                    f"{tv.ref()} − {s_ids[nm]}", [x for x in (tv.id, s_ids[nm]) if x])
        g_seg[nm] = (gv, gid)
    if seg_targets and target:
        st_sum = sum(v.value for v in seg_targets.values())
        if len(seg_targets) == len(names) and abs(st_sum - target.value) > 0.5:
            warnings.append(f"セグメント別目標の合計 {oku(st_sum)} が合計の目標 {oku(target.value)} と一致しない")

    # 3. レバー
    levers = []  # (name, seg, Val, alloc_id)
    for spec in args.lever:
        if "=" not in spec:
            sys.exit(f"エラー: --lever は 名前=値 の形で渡す: {spec!r}")
        lhs, rhs = spec.split("=", 1)
        lname, seg = (lhs.split(":", 1) + [""])[:2] if ":" in lhs else (lhs, "")
        lname, seg = lname.strip(), seg.strip()
        if seg and seg not in s_val:
            sys.exit(f"エラー: レバー {lhs} のセグメント {seg} が --base にない")
        v = parse_val(f"{lname}={rhs}", L)
        if v.id:
            aid = v.id
        else:
            if args.write and not args.replace_by:
                sys.exit("エラー: ID のないレバー割り当てを台帳に載せるには --replace-by（差し替え期限）が要る")
            aid = L.add("G", v.value, unit, f"ギャップの割り当て（{lname}{'、' + seg if seg else ''}）", end_year,
                        "仮置き", "—", replace_by=args.replace_by)
        levers.append((lname, seg, v, aid))

    lever_rows = []
    redflags = []
    for lname, seg, v, aid in levers:
        if seg:
            b0, s0, sref = next(b for b in bases if b.name == seg).value, s_val[seg], s_ids[seg]
            bref = next(b for b in bases if b.name == seg).ref()
            g0 = growth[seg].value / 100
            gref = growth[seg].ref()
        else:
            b0, s0, sref, bref, g0, gref = base_total, s_total, st_id, base_ref_p, g_blend, gb_id or f"{g_blend*100:.2f}%"
        implied = ((s0 + v.value) / b0) ** (1 / n) - 1 - g0
        where = seg or "合計"
        pid = L.add("G", implied * 100, "pt", f"{lname}のレバーが求める年率の上乗せ（{where}、市場成長への上乗せ）",
                    period, "推定", f"(({sref} + {aid}) / {bref})^(1/{n}) − 1 − {gref}",
                    [x for x in (sref, aid, gref) if x and ID_RE.fullmatch(x)] + [b.id for b in bases if b.id])
        is_share = lname.lower() in {"シェア", "share", "シェア獲得"}
        row = {"name": lname, "seg": where, "val": v, "aid": aid, "implied": implied, "pid": pid,
               "share": is_share}
        if is_share:
            if abs(args.share_avg - 0.8) < 1e-9:
                avg_id = L.add("F", args.share_avg, "%", "成長企業の年成長率の内訳: シェア獲得",
                               "10 年平均", "公開", MCK_SOURCE)
            else:
                if args.write and not args.replace_by:
                    sys.exit("エラー: --share-avg を 0.8 以外にするなら、仮置きとして --replace-by が要る")
                avg_id = L.add("F", args.share_avg, "%", "シェア獲得による成長の想定（年率、McKinsey の 0.8 から置き換えた値）",
                               period, "仮置き", "—", replace_by=args.replace_by)
            pct13 = L.add("F", 13, "%", "シェア獲得だけで年 5% 超の成長を 10 年平均で得た企業の割合",
                          "10 年平均", "公開", MCK_SOURCE)
            avg_amt = b0 * (1 + g0 + args.share_avg / 100) ** n - s0
            avg_amt_id = L.add("G", avg_amt, unit, f"平均的なシェア獲得（{args.share_avg}pt/年）で得られる売上（{where}）",
                               end_year, "推定", f"{bref} × (1+{gref}+{avg_id})^{n} − {sref}",
                               [x for x in (avg_id, sref, gref) if x and ID_RE.fullmatch(x)] + [b.id for b in bases if b.id])
            row.update(avg_id=avg_id, pct13=pct13, avg_amt=avg_amt, avg_amt_id=avg_amt_id)
            if implied * 100 > args.share_redflag:
                redflags.append(row)
        lever_rows.append(row)

    alloc_total = sum(r["val"].value for r in lever_rows)
    un_id = None
    if g_total is not None and lever_rows:
        un = g_total - alloc_total
        un_id = L.add("G", un, unit, "ギャップの未割当（ギャップ − 割り当ての合計）", end_year, "推定",
                      f"{gt_id} − (" + " + ".join(r["aid"] for r in lever_rows) + ")",
                      [gt_id] + [r["aid"] for r in lever_rows])
        if un < -0.5:
            warnings.append(f"割り当ての合計がギャップを {oku(-un)}{unit} 超えている（二重計上か、目標の上振れを狙うのかを確かめる）")

    # ---------------------------------------------------------------- 出力
    out: list[str] = []
    out += [f"## 成り行きとギャップ（{base_year or '基準年'} → {end_year}、{n} 年）", ""]
    out += ["### 成り行き（市場成長だけで伸びた場合）", "",
            f"| セグメント | 基準年売上（{unit}） | 市場成長率（%/年） | 成り行き {end_year}（{unit}） | 目標（{unit}） | ギャップ（{unit}） |",
            "|---|---:|---:|---:|---:|---:|"]
    for b, g, s, sid in seg_rows:
        tv = seg_targets.get(b.name)
        gs = g_seg.get(b.name)
        if not multi and target:
            tv, gs = target, (g_total, gt_id)
        out.append(f"| {b.name} | {oku(b.value)}{tag(b.id)} | {pct(g.value)}{tag(g.id)} | {oku(s)} [{sid}] | "
                   f"{(oku(tv.value) + tag(tv.id)) if tv else '—'} | {(oku(gs[0]) + ' [' + gs[1] + ']') if gs else '—'} |")
    if multi:
        out.append(f"| **合計** | — | {pct(g_blend * 100)} [{gb_id}] | **{oku(s_total)} [{st_id}]** | "
                   f"{(oku(target.value) + tag(target.id)) if target else '—'} | "
                   f"{('**' + oku(g_total) + ' [' + gt_id + ']**') if target else '—'} |")
    out.append("")
    if multi and not seg_targets:
        out += ["セグメント別のギャップは — のまま残す。セグメント別の目標は人が決める（按分しない）。", ""]
    if target:
        out += [f"- 目標に必要な年率: {pct(req * 100)}% [{req_id}]"
                f"（市場成長の加重平均 {pct(g_blend * 100)}%{tag(gb_id)}）", ""]

    out += ["### ブリッジ（ウォーターフォール）", "", f"| 段 | 金額（{unit}） | 市場成長への上乗せ（pt/年） |", "|---|---:|---:|"]
    out.append(f"| 基準年売上 {base_year} | {oku(base_total)}"
               + (tag(bases[0].id) if not multi else "（" + "、".join(f"{oku(b.value)}{tag(b.id)}" for b in bases) + "）")
               + " | — |")
    out.append(f"| ＋ 市場成長 | +{oku(s_total - base_total)} [{inc_id}] | — |")
    out.append(f"| ＝ 成り行き {end_year} | {oku(s_total)} [{st_id}] | — |")
    for r in lever_rows:
        flag = " 赤旗" if r in redflags else ""
        out.append(f"| ＋ {r['name']}（{r['seg']}） | +{oku(r['val'].value)} [{r['aid']}] | {pct(r['implied'] * 100)} [{r['pid']}]{flag} |")
    if un_id:
        out.append(f"| ＋ 未割当 | {oku(float(L.get(un_id)['value']))} [{un_id}] | — |")
    if target:
        out.append(f"| ＝ 目標 {end_year} | {oku(target.value)}{tag(target.id)} | — |")
    out.append("")

    share_rows = [r for r in lever_rows if r["share"]]
    if share_rows:
        out += ["### シェアのレバーの点検", ""]
        for r in share_rows:
            head = "**赤旗**" if r in redflags else "範囲内"
            out.append(f"- {head}（{r['seg']}）: シェアに {oku(r['val'].value)}{unit} [{r['aid']}] を載せると、"
                       f"市場成長に上乗せして年 {pct(r['implied'] * 100)}pt [{r['pid']}] のシェア由来成長が {n} 年続く計算になる")
            out.append(f"- 平均的なシェア獲得 {pct(args.share_avg)}pt/年 [{r['avg_id']}] なら、{n} 年で "
                       f"{oku(r['avg_amt'])}{unit} [{r['avg_amt_id']}] にとどまる")
        if redflags:
            out.append(f"- 参考: シェア獲得だけで年 5% 超を 10 年平均で得た企業は 13% [{share_rows[0]['pct13']}]（McKinsey 2017）")
            out.append("- 赤旗は「無理」と言うためではない。二本目のレーン（M&A、市場の選び直し）を検討する根拠にする")
        out.append("")

    out += ["### 前提と未確認事項", ""]
    out.append(f"- 成り行きは市場成長だけで伸び、シェアは基準年のまま一定と置いた")
    out.append("- 市場成長率の定義（業界団体の市場）と、売上の定義（自社のセグメント）が一致するかは未確認")
    if not target:
        out.append("- 目標が渡されていないので、ギャップは — のまま")
    if lever_rows and any(L.get(r["aid"]) and L.get(r["aid"])["source_tag"] == "仮置き" for r in lever_rows):
        out.append("- レバーへの割り当ては仮置き。追う打ち手は人が決める")
    for w in warnings + L.warnings + [f"台帳にある同じ事実を使った: {u}" for u in L.reused]:
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
