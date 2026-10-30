#!/usr/bin/env python3
"""施策ごとの上乗せ売上と投資を年次で見積もる（initiative-sizing）。

入力 CSV の 1 行が 1 施策。数値は入力 CSV に直接書かず、ファクト台帳 facts.csv の ID を書く。
スクリプトは台帳から値を引いて計算する（入力と台帳の値が食い違わないようにするため）。

  方式 market_share : 対象市場 × 上乗せシェア × 立ち上がり率
                       対象市場_y = 市場規模 × (1 + 市場成長率)^(y − 基準年)
  方式 acquisition  : 買収先の売上 × (1 + 市場成長率)^(y − 開始年)。開始年から連結（満額）

  立ち上がり率（開始年を 1 年目とする t、立ち上がり年数 R）
    linear : min(1, t / R)
    s      : ロジスティック曲線を t=0 で 0、t=R で 1 になるよう正規化（中間点 R/2）
    step   : 開始年から 1（初年度から満額。買収以外で使うと警告）

入力 CSV の列:
  id,initiative,option_id,method,market_ref,growth_ref,share_gain_ref,acq_revenue_ref,
  base_year,start_year,ramp_years,curve,investment_ref,invest_from,invest_to,invest_weights,confidence

  - *_ref は台帳の ID（例 F-101）。market_share 方式は market_ref/growth_ref/share_gain_ref が必須、
    acquisition 方式は acq_revenue_ref/growth_ref が必須
  - base_year を空にすると market_ref の period（例 FY2025）を使う
  - investment_ref は投資総額の ID。invest_from〜invest_to に invest_weights（例 3:4:3）で配る。空なら均等
  - confidence は 高/中/低/—。人が決める。決まるまで — のまま

出力:
  --out-csv   05-initiatives.csv（id,initiative,year,revenue,investment,unit,confidence）
  --out-md    施策カードと年次表の Markdown（05-initiatives.md に貼る）
  --append-ledger を付けると、施策ごとに I-xxx 行（最終年度の上乗せ売上、推定）を台帳に書く。
  同じ ID の行があれば値と計算式を上書きする（再実行しても重複しない）。

使い方:
  python3 sizing.py --ledger facts/facts.csv --inputs initiative-inputs.csv \\
      --from FY2026 --to FY2030 --out-csv 05-initiatives.csv --out-md 05-initiatives.tables.md \\
      --append-ledger --today 2026-11-02
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import re
import sys
from pathlib import Path

LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]
TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0}
CONFIDENCE = {"高", "中", "低", "—"}
ID_RE = re.compile(r"^[TQAFSGOICKD]-\d{3,}$")


class InputError(Exception):
    pass


def fy(text: str) -> int:
    m = re.fullmatch(r"\s*(?:FY)?(\d{4})\s*", text or "")
    if not m:
        raise InputError(f"年度の形式が不正です: {text!r}（FY2027 の形で書く）")
    return int(m.group(1))


def load_ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise InputError(f"台帳がありません: {path}")
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in LEDGER_COLS})


class Ledger:
    def __init__(self, rows: list[dict[str, str]]):
        self.rows = rows
        self.by_id = {r["id"].strip(): r for r in rows}

    def get(self, rid: str, what: str) -> dict[str, str]:
        rid = (rid or "").strip()
        if not rid:
            raise InputError(f"{what} の ID が空です。先に台帳に登録し、その ID を書く")
        if rid not in self.by_id:
            raise InputError(f"{what} の ID {rid} が台帳にありません")
        return self.by_id[rid]

    def number(self, rid: str, what: str, kind: str) -> float | None:
        """台帳の値を数値で返す。— なら None。kind: oku（億円に換算）/ pct（% を小数に）"""
        row = self.get(rid, what)
        raw = (row["value"] or "").replace(",", "").strip()
        if raw in {"", "—"}:
            return None
        try:
            v = float(raw)
        except ValueError:
            raise InputError(f"{rid} の値 {row['value']!r} が数値ではありません")
        unit = (row["unit"] or "").strip()
        if kind == "oku":
            if unit not in TO_OKU:
                raise InputError(f"{rid} の単位 {unit!r} を億円に換算できません")
            return v * TO_OKU[unit]
        if kind == "pct":
            if unit not in {"%", "％", "pt"}:
                raise InputError(f"{rid} の単位 {unit!r} は % か pt にしてください")
            return v / 100.0
        return v

    def confidential(self, ids: list[str]) -> bool:
        return any((self.by_id[i].get("confidentiality") or "").strip() == "社外秘"
                   for i in ids if i in self.by_id)

    def upsert_by_definition(self, prefix: str, row: dict[str, str]) -> str:
        """定義と期間が同じ行があれば上書きし、なければ未使用の最小番号で足す。"""
        for r in self.rows:
            if r["id"].startswith(prefix + "-") and r["definition"] == row["definition"] and r["period"] == row["period"]:
                r.update({k: v for k, v in row.items() if k != "id"})
                return r["id"]
        used = {int(i.split("-")[1]) for i in self.by_id if i.startswith(prefix + "-")}
        n = 1
        while n in used:
            n += 1
        rid = f"{prefix}-{n:03d}"
        row = dict(row, id=rid)
        self.rows.append(row)
        self.by_id[rid] = row
        return rid

    def upsert(self, row: dict[str, str]) -> str:
        rid = row["id"]
        if rid in self.by_id:
            self.by_id[rid].update(row)
            return "更新"
        self.rows.append(row)
        self.by_id[rid] = row
        return "追加"


def ramp(year: int, start: int, years: int, curve: str) -> float:
    t = year - start + 1
    if t <= 0:
        return 0.0
    if curve == "step" or years <= 0:
        return 1.0
    if t >= years:
        return 1.0
    if curve == "linear":
        return t / years
    if curve == "s":
        k = 2 * math.log(19) / years  # t=0 で 5%、t=R で 95% になる傾き
        mid = years / 2
        lo = 1 / (1 + math.exp(k * mid))
        hi = 1 / (1 + math.exp(-k * (years - mid)))
        v = 1 / (1 + math.exp(-k * (t - mid)))
        return max(0.0, min(1.0, (v - lo) / (hi - lo)))
    raise InputError(f"curve は linear / s / step のいずれかです: {curve!r}")


def weights(text: str, n: int) -> list[float]:
    if not (text or "").strip():
        return [1.0 / n] * n
    parts = [float(p) for p in re.split(r"[:：/]", text.strip()) if p.strip()]
    if len(parts) != n:
        raise InputError(f"invest_weights の数 {len(parts)} が投資年数 {n} と合いません")
    s = sum(parts)
    return [p / s for p in parts]


def fmt(v: float | None, d: int = 1) -> str:
    return "—" if v is None else f"{v:,.{d}f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", required=True, help="facts/facts.csv")
    ap.add_argument("--inputs", required=True, help="施策の入力 CSV")
    ap.add_argument("--from", dest="y_from", required=True, help="最初の年度（例 FY2026）")
    ap.add_argument("--to", dest="y_to", required=True, help="最後の年度（例 FY2030）。I-xxx の値はこの年度")
    ap.add_argument("--out-csv", help="05-initiatives.csv の出力先")
    ap.add_argument("--out-md", help="Markdown 表の出力先（省略時は標準出力のみ）")
    ap.add_argument("--append-ledger", action="store_true", help="I-xxx 行を台帳に書く")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    args = ap.parse_args()

    try:
        ledger_path = Path(args.ledger)
        led = Ledger(load_ledger(ledger_path))
        y0, y1 = fy(args.y_from), fy(args.y_to)
        years = list(range(y0, y1 + 1))
        with Path(args.inputs).open(encoding="utf-8") as f:
            specs = [r for r in csv.DictReader(f) if (r.get("id") or "").strip()]
        if not specs:
            raise InputError("入力 CSV に施策がありません")

        warnings: list[str] = []
        results = []
        seen: set[str] = set()
        for s in specs:
            iid = s["id"].strip()
            if not ID_RE.match(iid) or not iid.startswith("I-"):
                raise InputError(f"施策の ID は I-001 の形にしてください: {iid!r}")
            if iid in seen:
                raise InputError(f"{iid} が入力 CSV で重複しています")
            seen.add(iid)
            name = s["initiative"].strip()
            method = (s.get("method") or "market_share").strip()
            curve = (s.get("curve") or "s").strip()
            start = fy(s["start_year"])
            ramp_years = int((s.get("ramp_years") or "0").strip() or 0)
            conf = (s.get("confidence") or "—").strip() or "—"
            if conf not in CONFIDENCE:
                raise InputError(f"{iid}: confidence は 高/中/低/— のいずれかです: {conf!r}")
            if conf == "—":
                warnings.append(f"{iid} {name}: 確度が — のまま。人が 高/中/低 を決める")

            growth_ref = s["growth_ref"].strip()
            g = led.number(growth_ref, f"{iid} 市場成長率", "pct")
            refs = [growth_ref]
            if method == "market_share":
                mref, sref = s["market_ref"].strip(), s["share_gain_ref"].strip()
                m0 = led.number(mref, f"{iid} 対象市場", "oku")
                sh = led.number(sref, f"{iid} 上乗せシェア", "pct")
                refs += [mref, sref]
                base = fy(s.get("base_year") or led.get(mref, "対象市場")["period"].split("-")[0])
                if curve == "step":
                    warnings.append(f"{iid} {name}: 初年度から満額（step）。自前の施策なら立ち上がりを置く")
                elif ramp_years <= 1:
                    warnings.append(f"{iid} {name}: 立ち上がり {ramp_years} 年は、ほぼ初年度から満額")
                if sh is not None and sh > 0.05:
                    warnings.append(f"{iid} {name}: 上乗せシェア {sh*100:.1f}pt [{sref}] は大きい。成り行き分と二重に数えていないか確かめる")
                rev = {}
                for y in years:
                    if m0 is None or g is None or sh is None:
                        rev[y] = None
                    else:
                        rev[y] = m0 * (1 + g) ** (y - base) * sh * ramp(y, start, ramp_years, curve)
                formula = (f"{mref} × (1+{growth_ref})^(年度−FY{base}) × {sref} × 立ち上がり率"
                           f"（{ {'s': 'S字', 'linear': '直線', 'step': '満額'}[curve] }、FY{start} 開始、{ramp_years} 年）")
                basis = f"市場 {mref} × 上乗せシェア {sref}、成長 {growth_ref}"
            elif method == "acquisition":
                aref = s["acq_revenue_ref"].strip()
                a0 = led.number(aref, f"{iid} 買収先の売上", "oku")
                refs.append(aref)
                curve, ramp_years = "step", 0
                rev = {}
                for y in years:
                    if y < start:
                        rev[y] = 0.0
                    elif a0 is None or g is None:
                        rev[y] = None
                    else:
                        rev[y] = a0 * (1 + g) ** (y - start)
                formula = f"{aref} × (1+{growth_ref})^(年度−FY{start})（FY{start} から連結）"
                basis = f"買収先売上 {aref}、成長 {growth_ref}"
            else:
                raise InputError(f"{iid}: method は market_share / acquisition のいずれかです: {method!r}")

            # 投資
            inv = {y: 0.0 for y in years}
            iref = (s.get("investment_ref") or "").strip()
            inv_total = None
            if iref:
                inv_total = led.number(iref, f"{iid} 投資総額", "oku")
                refs.append(iref)
                fa, fb = fy(s.get("invest_from") or f"FY{start}"), fy(s.get("invest_to") or s.get("invest_from") or f"FY{start}")
                span = list(range(fa, fb + 1))
                ws = weights(s.get("invest_weights") or "", len(span))
                # 0.1 億円単位に丸め、丸めの端数は最後の年度に寄せる（合計が投資総額と一致するように）
                alloc = [None if inv_total is None else round(inv_total * w, 1) for w in ws]
                if inv_total is not None:
                    alloc[-1] = round(inv_total - sum(alloc[:-1]), 1)
                for y, a in zip(span, alloc):
                    if y not in inv:
                        warnings.append(f"{iid}: 投資年度 FY{y} が見積もり期間の外。期間内の分だけ数える")
                        continue
                    inv[y] = a
            else:
                warnings.append(f"{iid} {name}: 投資が置かれていない。売上だけ積むと capital-capacity で手当てを確かめられない")
                inv = {y: None for y in years}

            results.append(dict(id=iid, name=name, option=(s.get("option_id") or "—").strip() or "—",
                                method=method, curve=curve, start=start, ramp_years=ramp_years,
                                conf=conf, rev=rev, inv=inv, inv_ref=iref, inv_total=inv_total,
                                formula=formula, basis=basis, refs=refs))

        # 入力に使った仮置きを拾う
        provisional = []
        for r in results:
            for ref in r["refs"]:
                row = led.by_id[ref]
                if (row["source_tag"] or "").strip() == "仮置き":
                    provisional.append((ref, row["definition"], row.get("replace_by", "")))
        provisional = sorted(set(provisional))

        # CSV
        csv_rows = []
        for r in results:
            for y in years:
                csv_rows.append({"id": r["id"], "initiative": r["name"], "year": f"FY{y}",
                                 "revenue": fmt(r["rev"][y]).replace(",", ""),
                                 "investment": fmt(r["inv"][y]).replace(",", ""),
                                 "unit": "億円", "confidence": r["conf"]})
        if args.out_csv:
            with Path(args.out_csv).open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["id", "initiative", "year", "revenue", "investment", "unit", "confidence"],
                                   lineterminator="\n")
                w.writeheader()
                w.writerows(csv_rows)

        # 台帳
        ledger_msgs = []
        total_final, total_id = None, ""
        if args.append_ledger:
            for r in results:
                v = r["rev"][y1]
                row = {"id": r["id"], "value": "—" if v is None else f"{v:.1f}", "unit": "億円",
                       "definition": f"施策 {r['id']} {r['name']} の上乗せ売上（成り行きへの上乗せ分、連結）",
                       "period": f"FY{y1}", "source_tag": "推定", "source": r["formula"],
                       "retrieved_at": args.today,
                       "confidentiality": "社外秘" if led.confidential(r["refs"]) else "公開",
                       "replace_by": ""}
                ledger_msgs.append(f"{r['id']} を{led.upsert(row)}")
            finals = [r["rev"][y1] for r in results]
            total_final = None if any(v is None for v in finals) else sum(round(v, 1) for v in finals)
            total_id = led.upsert_by_definition("F", {
                "value": "—" if total_final is None else f"{total_final:.1f}", "unit": "億円",
                "definition": "施策の上乗せ売上の合計（05-initiatives.csv の全施策、成り行きへの上乗せ分）",
                "period": f"FY{y1}", "source_tag": "推定",
                "source": " + ".join(r["id"] for r in results), "retrieved_at": args.today,
                "confidentiality": "社外秘" if led.confidential([i for r in results for i in r["refs"]]) else "公開",
                "replace_by": ""})
            ledger_msgs.append(f"合計を {total_id} に記録")
            write_ledger(ledger_path, led.rows)

        # Markdown
        L = []
        L.append(f"## 施策カード（単位: 億円、FY{y1} の値）")
        L.append("")
        L.append(f"| ID | 施策 | 打ち手 | 方式 | 前提（台帳 ID） | 立ち上がり | FY{y1} 上乗せ売上 | 投資総額 | 確度 |")
        L.append("|----|------|--------|------|----------------|-----------|------------------|---------|------|")
        for r in results:
            if r["method"] == "acquisition":
                ramp_txt = f"FY{r['start']} から連結"
            else:
                ramp_txt = f"FY{r['start']} 開始、{ {'s': 'S字', 'linear': '直線', 'step': '満額'}[r['curve']] } {r['ramp_years']} 年"
            v = r["rev"][y1]
            rev_txt = f"{fmt(v)} [{r['id']}]" if args.append_ledger else fmt(v)
            inv_txt = f"{fmt(r['inv_total'])} [{r['inv_ref']}]" if r["inv_ref"] else "—"
            L.append(f"| {r['id']} | {r['name']} | {r['option']} | {'市場×シェア' if r['method']=='market_share' else '買収'} "
                     f"| {r['basis']} | {ramp_txt} | {rev_txt} | {inv_txt} | {r['conf']} |")
        L.append("")
        L.append("## 年次の上乗せ売上（単位: 億円）")
        L.append("")
        L.append("| ID | 施策 | " + " | ".join(f"FY{y}" for y in years) + " |")
        L.append("|----|------|" + "|".join("------:" for _ in years) + "|")
        for r in results:
            L.append(f"| {r['id']} | {r['name']} | " + " | ".join(fmt(r["rev"][y]) for y in years) + " |")
        tot = []
        for y in years:
            vals = [r["rev"][y] for r in results]
            tot.append(None if any(v is None for v in vals) else sum(vals))
        tot_cells = [fmt(t) for t in tot]
        if args.append_ledger:
            tot_cells[-1] = f"{fmt(total_final)} [{total_id}]"
        L.append("| 計 | | " + " | ".join(tot_cells) + " |")
        L.append("")
        L.append("## 年次の投資（単位: 億円）")
        L.append("")
        L.append("| ID | 施策 | " + " | ".join(f"FY{y}" for y in years) + " |")
        L.append("|----|------|" + "|".join("------:" for _ in years) + "|")
        for r in results:
            L.append(f"| {r['id']} | {r['name']} | " + " | ".join(fmt(r["inv"][y]) for y in years) + " |")
        tot = []
        for y in years:
            vals = [r["inv"][y] for r in results]
            tot.append(None if any(v is None for v in vals) else sum(vals))
        L.append("| 計 | | " + " | ".join(fmt(t) for t in tot) + " |")
        L.append("")
        L.append("## 計算式")
        L.append("")
        for r in results:
            L.append(f"- {r['id']}: {r['formula']}")
        L.append("")
        L.append("## 前提と未確認事項（スクリプトが拾ったもの）")
        L.append("")
        L.append("- 売上は成り行き（S）への上乗せ分。成り行きに含まれる市場成長は数えていない")
        for ref, d, rb in provisional:
            L.append(f"- 仮置きの入力: {ref} {d}（差し替え期限 {rb or '—'}）")
        for w_ in warnings:
            L.append(f"- 注意: {w_}")
        if ledger_msgs:
            L.append(f"- 台帳: {'、'.join(ledger_msgs)}")
        text = "\n".join(L) + "\n"
        if args.out_md:
            Path(args.out_md).write_text(text, encoding="utf-8")
        print(text)
        return 0
    except InputError as e:
        print(f"入力エラー: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
