#!/usr/bin/env python3
"""施策の投資総額と調達余力を突き合わせ、ROIC への影響を出す（capital-capacity）。

入力:
  --initiatives  05-initiatives.csv（id,initiative,year,revenue,investment,unit,confidence）
  --ledger       facts/facts.csv（値はここから引く）
  --inputs       capital-inputs.csv（key,ref,note）。key ごとに台帳の ID を書く
  --financials   facts/financials.csv（任意）。--fy の年度の連結の値を基準値に使う。
                 --inputs に同じ key があれば --inputs が優先

key（* は必須。financials から取れるものは financials でもよい）
  （financials の item 名は company-financials が書く有報の科目名。IFRS の名前も読む。違う名前なら --fin-map）
  ocf_base*          営業 CF（年、基準年度）            financials: 営業活動によるキャッシュ・フロー
  net_income_base*   当期純利益（配当の計算に使う）      financials: 親会社株主に帰属する当期純利益 / 親会社の所有者に帰属する当期利益
  sales_base*        売上高（最低手元資金の計算に使う）   financials: 売上高 / 売上収益
  cash*              現金及び預金                        financials: 現金及び預金 / 現金及び現金同等物
  debt*              有利子負債                          financials: 有利子負債（内訳しかなければ ratios.py の合計の ID を inputs に書く）
  equity*            自己資本（純資産で代用してよい）     financials: 純資産 / 親会社の所有者に帰属する持分
  op_income_base     営業利益（全社 ROIC の基準）         financials: 営業利益
  maintenance_capex* 維持投資（年）。成長投資は 05-initiatives.csv 側に置く
  payout_ratio*      配当性向（%）
  min_cash_months*   最低手元資金（売上の何か月分）
  net_de_limit*      ネット D/E の上限（倍）
  tax_rate*          実効税率（%）
  op_margin*         施策の営業利益率（%）。施策ごとに変えるなら op_margin.I-001 の形
  wacc*              WACC（%）
  ocf_growth         営業 CF の年成長率（%）。なければ 0（横ばい）
  ni_growth          当期純利益の年成長率（%）。なければ 0
  asset_sale.FY2027  資産売却による入金（その年度）。複数年度は行を分ける
  wc_ratio           施策の運転資本（上乗せ売上に対する %）。なければ 0

計算:
  営業 CF 余力   = Σ（営業 CF − 維持投資 − 配当）。配当 = 純利益 × 配当性向
  手元資金余力   = 現金 − 最低手元資金（売上 ÷ 12 × 月数）
  借入余力       = 上限 × 期末自己資本 −（有利子負債 − 現金）− 手元資金余力
                   ※ネット D/E では現金を使うことも借りることも同じだけネット負債を増やす。
                     手元資金余力と借入余力は合わせて「上限までの枠」で、足し算で二重に数えない
  期末自己資本   = 期首 + Σ（純利益 − 配当）。施策の利益は入れない（保守側）
  増分 ROIC      = Σ（施策の最終年度売上 × 営業利益率）×（1 − 税率）÷（投資累計 + 運転資本）

出力: Markdown（標準出力、--out-md）。--append-ledger で C-xxx 行を台帳に書く。
      C-xxx は定義と期間が同じ行があれば上書きする（再実行しても重複しない）。新しい行は未使用の最小番号。
      案を比べるとき（初回案で不足 → 打ち手を見直して再計算）は --label で案の名前を付ける。
      案によって変わる行（投資総額、過不足、ネット D/E の最大、増分 ROIC、施策を足した後の ROIC）の定義に
      案の名前が入るので、前の案の C- 行は上書きされずに残り、decisions.md から引ける。調達余力の行は案によらず 1 つ
  全社 ROIC = 税引後営業利益 ÷（純資産 + 有利子負債 − 現金及び預金）。CONVENTIONS の共通の定義（期末残高）

使い方:
  python3 capacity.py --initiatives 05-initiatives.csv --ledger facts/facts.csv \\
      --inputs capital-inputs.csv --financials facts/financials.csv --fy FY2025 \\
      --out-md 06-capital.tables.md --append-ledger --today 2026-11-04
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

LEDGER_COLS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
               "retrieved_at", "confidentiality", "replace_by"]
TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0}
PCT_KEYS = {"payout_ratio", "tax_rate", "op_margin", "wacc", "ocf_growth", "ni_growth", "wc_ratio"}
REQUIRED = ["ocf_base", "net_income_base", "sales_base", "cash", "debt", "equity", "maintenance_capex",
            "payout_ratio", "min_cash_months", "net_de_limit", "tax_rate", "op_margin", "wacc"]
# financials.csv の item 名（company-financials は有報の科目名のまま書く）。左から順に探す
FIN_MAP = {
    "ocf_base": ["営業活動によるキャッシュ・フロー"],
    "net_income_base": ["親会社株主に帰属する当期純利益", "親会社の所有者に帰属する当期利益"],
    "sales_base": ["売上高", "売上収益"],
    "cash": ["現金及び預金", "現金及び現金同等物"],
    "debt": ["有利子負債"],
    "equity": ["純資産", "親会社の所有者に帰属する持分"],
    "op_income_base": ["営業利益"],
}
DEBT_PARTS = ["短期借入金", "長期借入金", "社債", "コマーシャル・ペーパー", "リース債務"]


class InputError(Exception):
    pass


def fy(text: str) -> int:
    m = re.fullmatch(r"\s*(?:FY)?(\d{4})\s*", text or "")
    if not m:
        raise InputError(f"年度の形式が不正です: {text!r}（FY2027 の形で書く）")
    return int(m.group(1))


def num(raw: str) -> float | None:
    raw = (raw or "").replace(",", "").strip()
    if raw in {"", "—"}:
        return None
    try:
        return float(raw)
    except ValueError:
        raise InputError(f"数値ではありません: {raw!r}")


def add(*vals):
    return None if any(v is None for v in vals) else sum(vals)


def fmt(v, d=1):
    return "—" if v is None else f"{v:,.{d}f}"


class Ledger:
    def __init__(self, path: Path):
        if not path.exists():
            raise InputError(f"台帳がありません: {path}")
        self.path = path
        with path.open(encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.by_id = {r["id"].strip(): r for r in self.rows}

    def value(self, rid: str, key: str) -> float | None:
        if rid not in self.by_id:
            raise InputError(f"{key} の ID {rid} が台帳にありません")
        row = self.by_id[rid]
        v = num(row["value"])
        if v is None:
            return None
        unit = (row["unit"] or "").strip()
        base = key.split(".")[0]
        if base in PCT_KEYS:
            if unit not in {"%", "％", "pt"}:
                raise InputError(f"{key} は % で台帳に登録してください（{rid} の単位 {unit!r}）")
            return v / 100
        if base in {"net_de_limit"}:
            if unit != "倍":
                raise InputError(f"{key} は 倍 で登録してください（{rid}）")
            return v
        if base in {"min_cash_months"}:
            return v
        if unit not in TO_OKU:
            raise InputError(f"{key} の単位 {unit!r} を億円に換算できません（{rid}）")
        return v * TO_OKU[unit]

    def next_id(self, prefix: str) -> str:
        used = {int(i.split("-")[1]) for i in self.by_id if i.startswith(prefix + "-")}
        n = 1
        while n in used:
            n += 1
        return f"{prefix}-{n:03d}"

    def upsert(self, prefix: str, row: dict) -> str:
        for r in self.rows:
            if r["id"].startswith(prefix + "-") and r["definition"] == row["definition"] and r["period"] == row["period"]:
                r.update({k: v for k, v in row.items() if k != "id"})
                return r["id"]
        rid = self.next_id(prefix)
        row = dict(row, id=rid)
        self.rows.append(row)
        self.by_id[rid] = row
        return rid

    def save(self):
        with self.path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS, lineterminator="\n")
            w.writeheader()
            for r in self.rows:
                w.writerow({c: r.get(c, "") for c in LEDGER_COLS})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--initiatives", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--financials")
    ap.add_argument("--fy", help="financials から取る基準年度（例 FY2025）")
    ap.add_argument("--fin-map", help='financials の item 名の対応を JSON で上書き（例 \'{"equity":"自己資本"}\'）')
    ap.add_argument("--count-initiative-cf", action="store_true",
                    help="施策の税引後営業利益を営業 CF 余力に足す（既定は足さない＝保守側）")
    ap.add_argument("--label", default="",
                    help="C- の定義に付ける案の名前（例: 初回案、見直し案）。案を比べるときに、前の案の行を上書きしないため")
    ap.add_argument("--out-md")
    ap.add_argument("--append-ledger", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    args = ap.parse_args()

    try:
        led = Ledger(Path(args.ledger))
        # ---- 入力を集める（値は台帳から）
        refs: dict[str, str] = {}
        fin_debt_parts: list[str] = []
        if args.financials:
            if not args.fy:
                raise InputError("--financials を使うときは --fy（基準年度）を指定する")
            fmap = {k: list(v) for k, v in FIN_MAP.items()}
            if args.fin_map:
                for k, item in json.loads(args.fin_map).items():
                    fmap[k] = [item] if isinstance(item, str) else list(item)
            by_item: dict[str, str] = {}
            with Path(args.financials).open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if r["fiscal_year"].strip() == args.fy and r["segment"].strip() == "連結":
                        by_item[r["item"].strip()] = r["id"].strip()
            if not by_item:
                raise InputError(f"financials.csv に {args.fy} の連結の行がありません（年度は FY2025 の形で書く）")
            for k, items in fmap.items():
                hit = next((i for i in items if i in by_item), None)
                if hit is None:
                    continue
                rid = by_item[hit]
                if rid not in led.by_id:
                    raise InputError(f"financials.csv の {rid}（{hit}）が台帳にありません")
                refs[k] = rid
            if "debt" not in refs and any(p in by_item for p in DEBT_PARTS):
                fin_debt_parts = [p for p in DEBT_PARTS if p in by_item]
            else:
                fin_debt_parts = []
        with Path(args.inputs).open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                k = (r.get("key") or "").strip()
                if k:
                    if not (r.get("ref") or "").strip():
                        raise InputError(f"{k} の ref（台帳 ID）が空です。値は台帳に登録してから ID を書く")
                    refs[k] = r["ref"].strip()
        missing = [k for k in REQUIRED if k not in refs]
        if missing:
            hint = ""
            if "debt" in missing and args.financials and fin_debt_parts:
                hint = ("。financials.csv に有利子負債の合計がなく、内訳（" + "、".join(fin_debt_parts) +
                        "）だけがある。financial-analysis の ratios.py が台帳に載せる「有利子負債」（推定）の ID を "
                        "06-capital-inputs.csv の debt に書く")
            raise InputError("必須の入力が足りません: " + ", ".join(missing) + hint)
        v = {k: led.value(rid, k) for k, rid in refs.items()}
        for opt in ("ocf_growth", "ni_growth", "wc_ratio"):
            v.setdefault(opt, 0.0)

        # ---- 施策
        inits: dict[str, dict] = {}
        with Path(args.initiatives).open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                iid = r["id"].strip()
                if r.get("unit", "億円").strip() != "億円":
                    raise InputError(f"{iid}: 05-initiatives.csv の単位は億円にする")
                d = inits.setdefault(iid, {"name": r["initiative"].strip(), "rev": {}, "inv": {},
                                           "conf": r["confidence"].strip()})
                y = fy(r["year"])
                d["rev"][y] = num(r["revenue"])
                d["inv"][y] = num(r["investment"])
        if not inits:
            raise InputError("05-initiatives.csv に施策がありません")
        for iid in inits:
            if iid not in led.by_id:
                raise InputError(f"{iid} が台帳にありません。initiative-sizing を --append-ledger 付きで回す")
        years = sorted({y for d in inits.values() for y in d["inv"]})
        y_last = years[-1]
        period = f"FY{years[0]}-FY{y_last}"
        n = len(years)

        notes: list[str] = []
        none_inputs = [f"{k}（{refs[k]}）" for k in refs if v.get(k) is None]
        if none_inputs:
            notes.append("値が — の入力があり、関係する欄は — のまま: " + "、".join(none_inputs))

        # ---- 年次
        inv_y = {y: add(*[d["inv"].get(y, 0.0) for d in inits.values()]) for y in years}
        margin = {iid: v.get(f"op_margin.{iid}", v["op_margin"]) for iid in inits}
        nopat_y = {}
        for y in years:
            parts = []
            for iid, d in inits.items():
                rv = d["rev"].get(y, 0.0)
                parts.append(None if rv is None or margin[iid] is None or v["tax_rate"] is None
                             else rv * margin[iid] * (1 - v["tax_rate"]))
            nopat_y[y] = add(*parts)
        min_cash = None if v["sales_base"] is None or v["min_cash_months"] is None else v["sales_base"] / 12 * v["min_cash_months"]
        nd0 = add(v["debt"], None if v["cash"] is None else -v["cash"])
        eq, nd = v["equity"], nd0
        rows = []
        fcf_total, asset_total = 0.0, 0.0
        for i, y in enumerate(years, start=1):
            ocf = None if v["ocf_base"] is None else v["ocf_base"] * (1 + v["ocf_growth"]) ** i
            ni = None if v["net_income_base"] is None else v["net_income_base"] * (1 + v["ni_growth"]) ** i
            div = None if ni is None or v["payout_ratio"] is None else ni * v["payout_ratio"]
            fcf = add(ocf, None if v["maintenance_capex"] is None else -v["maintenance_capex"], None if div is None else -div)
            if args.count_initiative_cf:
                fcf = add(fcf, nopat_y[y])
            asset = v.get(f"asset_sale.FY{y}", 0.0)
            eq = add(eq, ni, None if div is None else -div)
            nd = add(nd, inv_y[y], None if fcf is None else -fcf, None if asset is None else -asset)
            de = None if nd is None or eq in (None, 0) else nd / eq
            over = None if de is None or v["net_de_limit"] is None else de > v["net_de_limit"] + 1e-9
            rows.append((y, inv_y[y], ocf, div, fcf, asset, nd, eq, de, over))
            fcf_total = add(fcf_total, fcf)
            asset_total = add(asset_total, asset)
        eq_end = eq
        inv_total = add(*inv_y.values())
        cash_room = add(v["cash"], None if min_cash is None else -min_cash)
        if cash_room is not None and cash_room < 0:
            notes.append("現金が最低手元資金を下回っている。手元資金余力はマイナス（使えない）")
        frame = None if v["net_de_limit"] is None or eq_end is None or nd0 is None else v["net_de_limit"] * eq_end - nd0
        borrow = add(frame, None if cash_room is None else -cash_room)
        capacity = add(fcf_total, cash_room, borrow, asset_total)
        gap = add(capacity, None if inv_total is None else -inv_total)
        breach = [f"FY{r[0]}" for r in rows if r[9]]
        max_de = max((r[8] for r in rows if r[8] is not None), default=None)

        # ---- ROIC
        roic_rows = []
        inc_nopat, inc_ic = 0.0, 0.0
        for iid, d in inits.items():
            rv = d["rev"].get(y_last)
            nop = None if rv is None or margin[iid] is None or v["tax_rate"] is None else rv * margin[iid] * (1 - v["tax_rate"])
            ic = add(*d["inv"].values())
            ic = add(ic, None if rv is None or v["wc_ratio"] is None else rv * v["wc_ratio"])
            r_ = None if nop is None or not ic else nop / ic
            roic_rows.append((iid, d["name"], rv, margin[iid], nop, ic, r_))
            inc_nopat, inc_ic = add(inc_nopat, nop), add(inc_ic, ic)
        inc_roic = None if inc_nopat is None or not inc_ic else inc_nopat / inc_ic
        base_roic = after_roic = None
        if "op_income_base" in v and v["op_income_base"] is not None and v["tax_rate"] is not None:
            base_nopat = v["op_income_base"] * (1 - v["tax_rate"])
            base_ic = add(v["equity"], nd0)
            if base_ic:
                base_roic = base_nopat / base_ic
                if inc_nopat is not None and inc_ic is not None:
                    after_roic = (base_nopat + inc_nopat) / (base_ic + inc_ic)
        else:
            notes.append("op_income_base がないため全社 ROIC は出していない")

        # ---- 台帳
        ids: dict[str, str] = {}
        inc_ids = ", ".join(inits)
        conf = "社外秘" if any((led.by_id[r].get("confidentiality") or "") == "社外秘"
                               for r in list(refs.values()) + list(inits)) else "公開"
        R = refs
        sale_keys = sorted(k for k in R if k.startswith("asset_sale."))
        grouped: dict[str, list[str]] = {}
        for k in sale_keys:
            grouped.setdefault(R[k], []).append(k.split(".", 1)[1])
        asset_refs = "、".join(f"{rid}（{', '.join(ys)}）" for rid, ys in grouped.items()) or "0"
        defs = [
            ("inv", inv_total, "億円", "施策の投資総額（05-initiatives.csv の全施策）", period, f"Σ 05-initiatives.csv の investment（{inc_ids}）"),
            ("fcf", fcf_total, "億円", "営業 CF 余力（営業 CF − 維持投資 − 配当）", period,
             f"Σ({R['ocf_base']}×(1+成長)^i − {R['maintenance_capex']} − {R['net_income_base']}×{R['payout_ratio']})"
             + ("＋施策の税引後営業利益" if args.count_initiative_cf else "")),
            ("cash", cash_room, "億円", "手元資金余力（現金 − 最低手元資金）", f"FY{years[0]}",
             f"{R['cash']} − {R['sales_base']} ÷ 12 × {R['min_cash_months']}"),
            ("borrow", borrow, "億円", "借入余力（ネット D/E 上限まで、手元資金余力を除く）", period,
             f"{R['net_de_limit']} × 期末自己資本({R['equity']} + Σ{R['net_income_base']}×(1−{R['payout_ratio']})) − ({R['debt']} − {R['cash']}) − 手元資金余力"),
            ("asset", asset_total, "億円", "資産売却による入金", period, asset_refs if asset_refs != "0" else "入力なし（0）"),
            ("cap", capacity, "億円", "調達余力の合計", period, "営業 CF 余力 + 手元資金余力 + 借入余力 + 資産売却"),
            ("gap", gap, "億円", "調達余力 − 投資総額（マイナスは不足）", period, "調達余力の合計 − 施策の投資総額"),
            ("maxde", max_de, "倍", "期間中のネット D/E の最大値", period,
             f"(({R['debt']} − {R['cash']}) + 累計投資 − 累計営業 CF 余力 − 累計資産売却) ÷ 自己資本"),
            ("inc_roic", None if inc_roic is None else inc_roic * 100, "%", "施策の増分 ROIC（05-initiatives.csv の全施策の合計）", f"FY{y_last}",
             f"Σ(売上 × {R['op_margin']}) × (1 − {R['tax_rate']}) ÷ 投資累計（{inc_ids}）"),
        ]
        if base_roic is not None:
            defs.append(("base_roic", base_roic * 100, "%", "全社 ROIC（基準年度、税引後営業利益 ÷（自己資本 + ネット有利子負債））",
                         args.fy or "基準年度", f"{R['op_income_base']} × (1 − {R['tax_rate']}) ÷ ({R['equity']} + {R['debt']} − {R['cash']})"))
        if after_roic is not None:
            defs.append(("after_roic", after_roic * 100, "%", "全社 ROIC（施策を足した後、成り行き事業は基準年度のまま）", f"FY{y_last}",
                         "（基準の税引後営業利益 + 施策の増分）÷（基準の投下資本 + 施策の投資累計）"))
        digits = {"倍": 2, "%": 1, "億円": 1}
        # 案によって変わる行だけに案の名前を付ける（調達余力の側は案によらないので、同じ事実を二重に載せない）
        plan_keys = {"inv", "gap", "maxde", "inc_roic", "after_roic"} | ({"fcf", "cap"} if args.count_initiative_cf else set())
        for key, val, unit, definition, per, src in defs:
            if args.label and key in plan_keys:
                definition = f"{definition}（{args.label}）"
            if args.append_ledger:
                d = digits[unit]
                ids[key] = led.upsert("C", {"value": "—" if val is None else f"{val:.{d}f}", "unit": unit,
                                            "definition": definition, "period": per, "source_tag": "推定",
                                            "source": src, "retrieved_at": args.today,
                                            "confidentiality": conf, "replace_by": ""})
        if args.append_ledger:
            # 合計と過不足の計算式は、C- の ID で書き直す（推定の行は入力 ID でたどれるようにする）
            formula = {"cap": ("fcf", "cash", "borrow", "asset"), "gap": ("cap", "inv")}
            for key, parts in formula.items():
                if key in ids and all(p in ids for p in parts):
                    src = " + ".join(ids[p] for p in parts) if key == "cap" else f"{ids['cap']} − {ids['inv']}"
                    led.by_id[ids[key]]["source"] = src
            led.save()

        def tag(key, val, d=1):
            return f"{fmt(val, d)} [{ids[key]}]" if key in ids else fmt(val, d)

        # ---- Markdown
        L = [f"## 投資総額と調達余力（{period}、単位: 億円）", "",
             "| 項目 | 金額 | 入力（台帳 ID） |", "|------|-----:|----------------|",
             f"| 施策の投資総額 | {tag('inv', inv_total)} | {inc_ids} |",
             f"| 営業 CF 余力（維持投資・配当の後） | {tag('fcf', fcf_total)} | {R['ocf_base']}, {R['maintenance_capex']}, {R['net_income_base']}, {R['payout_ratio']} |",
             f"| 手元資金余力（最低手元資金を超える分） | {tag('cash', cash_room)} | {R['cash']}, {R['sales_base']}, {R['min_cash_months']} |",
             f"| 借入余力（ネット D/E 上限まで） | {tag('borrow', borrow)} | {R['net_de_limit']}, {R['equity']}, {R['debt']}, {R['cash']} |",
             f"| 資産売却 | {tag('asset', asset_total)} | {asset_refs if asset_refs != '0' else '—'} |",
             f"| 調達余力の合計 | {tag('cap', capacity)} | |",
             f"| **過不足（調達余力 − 投資総額）** | **{tag('gap', gap)}** | |", ""]
        L += [f"## 年次の資金とネット D/E（単位: 億円、D/E は倍。上限 {fmt(v['net_de_limit'], 2)} [{R['net_de_limit']}]）", "",
              "| 年度 | 施策投資 | 営業 CF | 配当 | 営業 CF 余力 | 資産売却 | ネット有利子負債（期末） | 自己資本（期末） | ネット D/E | 上限超え |",
              "|------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|:----:|"]
        for y, inv, ocf, div, fcf, asset, nd_, eq_, de, over in rows:
            L.append(f"| FY{y} | {fmt(inv)} | {fmt(ocf)} | {fmt(div)} | {fmt(fcf)} | {fmt(asset)} | {fmt(nd_)} | {fmt(eq_)} | {fmt(de, 2)} | {'—' if over is None else ('超え' if over else '')} |")
        L.append("")
        L.append(f"- 期間中のネット D/E の最大: {tag('maxde', max_de, 2)}（倍）")
        L.append("")
        L += [f"## ROIC への影響（FY{y_last}、単位: 億円。WACC {fmt(None if v['wacc'] is None else v['wacc']*100)}% [{R['wacc']}]）", "",
              "| ID | 施策 | 上乗せ売上 | 営業利益率（台帳 ID） | 税引後営業利益 | 投資累計 | 増分 ROIC（%） | WACC との比較 |",
              "|----|------|-----:|------|-----:|-----:|-----:|------|"]
        for iid, name, rv, m, nop, ic, r_ in roic_rows:
            mref = R.get(f"op_margin.{iid}", R["op_margin"])
            cmp_ = "—" if r_ is None or v["wacc"] is None else ("上回る" if r_ > v["wacc"] else "下回る")
            L.append(f"| {iid} | {name} | {fmt(rv)} | {mref} | {fmt(nop)} | {fmt(ic)} | {fmt(None if r_ is None else r_*100)} | {cmp_} |")
        cmp_all = "—" if inc_roic is None or v["wacc"] is None else ("上回る" if inc_roic > v["wacc"] else "下回る")
        L.append(f"| 計 | | | | {fmt(inc_nopat)} | {fmt(inc_ic)} | {tag('inc_roic', None if inc_roic is None else inc_roic*100)} | {cmp_all} |")
        L.append("")
        if base_roic is not None:
            L.append(f"- 全社 ROIC（%）: 基準年度 {tag('base_roic', base_roic*100)} → 施策を足した後 {tag('after_roic', None if after_roic is None else after_roic*100)}")
            L.append("")
        L += ["## 前提と未確認事項（スクリプトが拾ったもの）", ""]
        L.append(f"- 最低手元資金は売上の {fmt(v['min_cash_months'])} か月分 [{R['min_cash_months']}]。基準年度の売上で固定")
        L.append("- 借入余力はネット D/E の上限までの枠から手元資金余力を引いた残り。両者を足しても上限までの枠を超えない")
        L.append("- 期末自己資本は成り行きの純利益と配当だけで積む。施策の利益、増資、自己株買いは入れていない")
        if not args.count_initiative_cf:
            L.append("- 施策が生む CF は営業 CF 余力に入れていない（保守側）")
        L.append("- 増分 ROIC は投資累計（減価償却で減らさない総額）で割る。立ち上がり途中の施策は低く出る")
        L.append("- 買収の投資にはのれんを含む買収額全体を置く")
        for k, rid in sorted(refs.items()):
            row = led.by_id[rid]
            if (row["source_tag"] or "").strip() == "仮置き":
                L.append(f"- 仮置きの入力: {k} = {rid} {row['definition']}（差し替え期限 {row.get('replace_by') or '—'}）")
        unconf = [iid for iid, d in inits.items() if d["conf"] in {"", "—"}]
        if unconf:
            L.append(f"- 確度が — の施策: {', '.join(unconf)}")
        if breach:
            L.append(f"- 注意: ネット D/E が上限を超える年度がある: {'、'.join(breach)}")
        if gap is not None and gap < 0:
            L.append("- 注意: 調達余力が投資総額に足りない。どう埋めるかは人が決める（打ち手・時期・目標の見直し）")
        for nt in notes:
            L.append(f"- 注意: {nt}")
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
