#!/usr/bin/env python3
"""目標値を「必要な年率」に直し、ベースレート・自社実績・資本効率の目標と突き合わせる。

計算すること:
  1. 期限の候補ごとの必要年率（CAGR）  例: 2,000 → 5,000 は 5 年 20.1%、7 年 14.0%、10 年 9.6%
  2. 市場成長を置いたとき、市場成長に上乗せして要る年率 (1+r)/(1+g)-1（任意）
  3. ベースレートとの照合（既定は Mauboussin & Callahan「Bayes and Base Rates」2026-02:
     売上 20〜50 億ドルで始まった米国上場企業の 5 年売上成長 年率平均 7.0%、標準偏差 10.6%）
     正規分布で近似したときのパーセンタイル。参照クラスの規模・国・期間が合っているかの警告つき
  4. 自社の過去の売上 CAGR との比較（financials.csv か --history から）
  5. ROE 目標との整合（目標年に要る純利益と、目標売上に対する純利益率）

使い方（北辰工業の例）:
  python3 target_math.py --base 2000 --base-source "有価証券報告書 FY2025 p.40" \\
      --target 5000 --target-source "FY2025 決算説明会 書き起こし p.12" \\
      --unit 億円 --base-year FY2025 --horizons 5,7,10 --market-growth 5 \\
      --history FY2016=1350,FY2020=1470,FY2025=2000 \\
      --roe-target 8 --roe-source "FY2025 決算説明会 書き起こし p.13" \\
      --equity 1150 --equity-source "有価証券報告書 FY2025 p.44" \\
      --net-income 80.7 --net-income-source "有価証券報告書 FY2025 p.41" --payout 35 \\
      --ledger case/facts/facts.csv --append --out /tmp/target-math.md

  company-financials の後なら --financials case/facts/financials.csv を渡すと、基準値・自己資本・
  純利益・売上の推移を financials.csv から読み、その ID を計算式に使う。

値の出典:
  --xxx-id   台帳にある ID を使う（値は台帳から読む）
  --xxx-source 資料名とページ → 出典タグ「公開」で台帳に登録
  どちらもない → 出典タグ「仮置き」で登録（--replace-by が差し替え期限）

標準ライブラリだけで動く。Python 3.10 以上。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import re
import sys
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

    def get(self, rid: str) -> dict[str, str] | None:
        return next((r for r in self.all_rows() if r["id"] == rid), None)

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

    def new_rows_csv(self) -> str:
        lines = [",".join(LEDGER_COLS)]
        for r in self.new:
            lines.append(",".join(_csv_cell(r[c]) for c in LEDGER_COLS))
        return "\n".join(lines)


def _csv_cell(s: str) -> str:
    return f'"{s}"' if any(ch in s for ch in ',"\n') else s


def _same(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return a == b


def fmt(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def raw(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}"


# ---------------------------------------------------------------- 入力の解決
class Inputs:
    def __init__(self, ledger: Ledger, replace_by: str) -> None:
        self.ledger = ledger
        self.replace_by = replace_by
        self.notes: list[str] = []

    def resolve(self, name: str, value: float | None, rid: str | None, source: str | None,
                prefix: str, unit: str, definition: str, period: str,
                keywords: tuple[str, ...] = ()) -> tuple[float | None, str | None]:
        """(値, ID) を返す。値も ID もなければ (None, None)。
        keywords: ID で渡されたとき、台帳の定義に含まれているべき語（取り違えを防ぐ）"""
        if rid:
            row = self.ledger.get(rid)
            if row is None:
                sys.exit(f"エラー: {name} の ID {rid} が台帳にありません")
            if keywords and not any(k in row["definition"] for k in keywords):
                sys.exit(f"エラー: {name} に指定した {rid} の定義は「{row['definition']}」。{name}の ID か確かめる")
            if row["unit"] != unit:
                sys.exit(f"エラー: {name} に指定した {rid} の単位は {row['unit']}（期待は {unit}）。ID を確かめる")
            self.notes.append(f"{name}は台帳の {rid}（{row['definition']}、{row['period']}）を使った")
            try:
                return float(row["value"]), rid
            except ValueError:
                sys.exit(f"エラー: {rid} の値 {row['value']!r} は数値ではありません")
        if value is None:
            return None, None
        if source:
            new_id = self.ledger.register(prefix, raw(value, 4).rstrip("0").rstrip("."), unit, definition, period, "公開", source)
        else:
            new_id = self.ledger.register(prefix, raw(value, 4).rstrip("0").rstrip("."), unit, definition, period,
                                          "仮置き", "—", replace_by=self.replace_by)
            self.notes.append(f"{name} {fmt(value, 1)}{unit} [{new_id}] は出典がないため仮置きで登録した（差し替え期限 {self.replace_by}）")
        return value, new_id


def load_financials(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0}


def conv(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit or from_unit not in TO_OKU or to_unit not in TO_OKU:
        return value
    return value * TO_OKU[from_unit] / TO_OKU[to_unit]


def fin_lookup(rows: list[dict[str, str]], item: str, fy: str, unit: str) -> tuple[float, str] | None:
    for r in rows:
        if r["item"] == item and r["segment"] == "連結" and r["fiscal_year"] == fy:
            try:
                v = float(r["value"])
            except ValueError:
                return None
            if r["unit"] != unit and r["unit"] in TO_OKU and unit in TO_OKU:
                return None  # 単位が違うものは ID を使い回さず、値だけ使う場合は呼び出し側で conv
            return v, r["id"]
    return None


def fy_num(fy: str) -> int:
    m = re.search(r"(\d{4})", fy)
    if not m:
        sys.exit(f"エラー: 年度の書き方が読めません: {fy!r}（FY2025 のように書く）")
    return int(m.group(1))


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ---------------------------------------------------------------- 本体
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_argument_group("基準と目標")
    g.add_argument("--base", type=float, help="基準年の値（例: 2000）")
    g.add_argument("--base-id", help="基準値の台帳 ID")
    g.add_argument("--base-source", help="基準値の資料名とページ")
    g.add_argument("--base-year", required=True, help="基準年度（例: FY2025）")
    g.add_argument("--target", type=float, help="目標値（例: 5000）")
    g.add_argument("--target-id", help="目標値の台帳 ID")
    g.add_argument("--target-source", help="目標値の出典（説明会の書き起こしなど）")
    g.add_argument("--metric", default="連結売上高", help="目標の指標名（定義に書く。既定: 連結売上高）")
    g.add_argument("--unit", default="億円", choices=["億円", "百万円", "兆円"], help="金額の単位")
    g.add_argument("--horizons", default="5,7,10", help="期限の候補（年数、カンマ区切り）")
    g = ap.add_argument_group("市場成長（任意）")
    g.add_argument("--market-growth", type=float, help="市場成長率 %%/年")
    g.add_argument("--market-growth-id")
    g.add_argument("--market-growth-source")
    g = ap.add_argument_group("ベースレート")
    g.add_argument("--base-rate-mean", type=float, default=7.0)
    g.add_argument("--base-rate-sd", type=float, default=10.6)
    g.add_argument("--base-rate-source", default="Mauboussin & Callahan「Bayes and Base Rates」2026-02（売上 20〜50 億ドルで始まった米国上場企業の 5 年売上成長、1950-2024）")
    g.add_argument("--base-rate-class-usd", default="20-50", help="参照クラスの開始時売上（億ドル、下限-上限）")
    g.add_argument("--fx", type=float, help="円/ドル（参照クラスの規模と比べるため）")
    g.add_argument("--fx-id")
    g.add_argument("--fx-source")
    g = ap.add_argument_group("自社実績")
    g.add_argument("--financials", type=Path, help="facts/financials.csv（company-financials の出力）")
    g.add_argument("--history", help="売上の推移 FY2016=1350,FY2025=2000（financials.csv がないとき）")
    g.add_argument("--history-source", default="有価証券報告書 各期", help="--history の出典")
    g = ap.add_argument_group("資本効率（任意）")
    g.add_argument("--roe-target", type=float, help="ROE 目標 %%")
    g.add_argument("--roe-id")
    g.add_argument("--roe-source")
    g.add_argument("--equity", type=float, help="基準年の自己資本（純資産）")
    g.add_argument("--equity-id")
    g.add_argument("--equity-source")
    g.add_argument("--net-income", type=float, help="基準年の親会社株主に帰属する当期純利益")
    g.add_argument("--net-income-id")
    g.add_argument("--net-income-source")
    g.add_argument("--payout", type=float, help="配当性向 %%（内部留保で自己資本が増える前提を置くとき）")
    g.add_argument("--payout-id")
    g.add_argument("--payout-source")
    g = ap.add_argument_group("出力")
    g.add_argument("--ledger", type=Path, help="facts/facts.csv")
    g.add_argument("--append", action="store_true", help="台帳に新しい行を追記する（ないときは追記予定の行を表示するだけ）")
    g.add_argument("--today", default=dt.date.today().isoformat())
    g.add_argument("--replace-by", help="仮置きの差し替え期限（既定: 今日 + 14 日）")
    g.add_argument("--out", type=Path, help="Markdown の書き出し先")
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.today)
    replace_by = a.replace_by or (today + dt.timedelta(days=14)).isoformat()
    ledger = Ledger(a.ledger, a.today)
    inp = Inputs(ledger, replace_by)
    u = a.unit
    by = a.base_year
    by_n = fy_num(by)
    fin = load_financials(a.financials) if a.financials else []

    # 基準値（financials.csv があればその ID を使う）
    if a.base is None and not a.base_id and fin:
        hit = fin_lookup(fin, "売上高", by, u)
        if hit:
            a.base_id = hit[1]
    base, base_id = inp.resolve("基準値", a.base, a.base_id, a.base_source, "F", u, f"{a.metric}（基準年の実績）", by, ("売上", a.metric))
    target, target_id = inp.resolve("目標値", a.target, a.target_id, a.target_source, "T", u,
                                    f"{a.metric}の目標（期限・連結/単体・M&A込みかは未確定）", "—", ("目標",))
    if base is None or target is None:
        sys.exit("エラー: 基準値（--base か --base-id）と目標値（--target か --target-id）が要ります")
    if base <= 0:
        sys.exit("エラー: 基準値は正の数にしてください")

    horizons = [int(h) for h in a.horizons.split(",") if h.strip()]
    mg, mg_id = inp.resolve("市場成長率", a.market_growth, a.market_growth_id, a.market_growth_source, "F", "%",
                            "対象市場の年平均成長率", "—", ("成長",))
    mean_id = ledger.register("F", raw(a.base_rate_mean, 1), "%", "ベースレート: 5 年売上成長の年率平均（参照クラスは出典を参照）", "1950-2024", "公開", a.base_rate_source)
    sd_id = ledger.register("F", raw(a.base_rate_sd, 1), "%", "ベースレート: 5 年売上成長の年率の標準偏差（参照クラスは出典を参照）", "1950-2024", "公開", a.base_rate_source)

    out: list[str] = []
    notes: list[str] = []
    P = out.append

    P(f"# target-math の計算結果（{a.metric}）")
    P("")
    P(f"- 基準: {fmt(base)} {u} [{base_id}]")
    P(f"- 目標: {fmt(target)} {u} [{target_id}]")
    P(f"- 基準年度: {by}")
    P("")

    # 1. 必要年率
    P("## 1. 期限の候補ごとの必要年率")
    P("")
    hdr = "| 期限 | 年数 | 必要年率 |"
    sep = "|------|------|---------|"
    if mg is not None:
        hdr += " 市場成長に乗った到達値 | 市場成長への上乗せ年率 |"
        sep += "------------------------|----------------------|"
    P(hdr)
    P(sep)
    req: dict[int, tuple[float, str]] = {}
    for h in horizons:
        fy_t = f"FY{by_n + h}"
        r = ((target / base) ** (1.0 / h) - 1.0) * 100
        rid = ledger.register("T", raw(r, 2), "%", f"{a.metric}の必要年率（{h} 年で目標に届く CAGR）", f"{by}-{fy_t}",
                              "推定", f"({target_id}/{base_id})^(1/{h})-1")
        req[h] = (r, rid)
        row = f"| {fy_t} | {h} 年 | {fmt(r)}% [{rid}] |"
        if mg is not None:
            reach = base * (1 + mg / 100) ** h
            reach_id = ledger.register("T", raw(reach, 1), u, f"市場成長率で伸びた場合の{a.metric}（参考。成り行きの正本は gap-bridge）", fy_t,
                                       "推定", f"{base_id}×(1+{mg_id})^{h}")
            up = ((1 + r / 100) / (1 + mg / 100) - 1) * 100
            up_id = ledger.register("T", raw(up, 2), "%", f"市場成長に上乗せして要る年率（{h} 年、(1+必要年率)/(1+市場成長率)-1）", f"{by}-{fy_t}",
                                    "推定", f"(1+{rid})/(1+{mg_id})-1")
            row += f" {fmt(reach, 0)} {u} [{reach_id}] | {fmt(up)}% [{up_id}] |"
        P(row)
    P("")
    if mg is not None:
        P(f"市場成長率は {fmt(mg)}% [{mg_id}] で置いた。到達値は参考で、セグメント別の成り行きとギャップは gap-bridge で出す。")
        P("")

    # 2. ベースレート
    P("## 2. ベースレートとの照合")
    P("")
    P(f"- 参照クラス: {a.base_rate_source}")
    P(f"- 平均 {fmt(a.base_rate_mean)}% [{mean_id}]")
    P(f"- 標準偏差 {fmt(a.base_rate_sd)}% [{sd_id}]")
    P("")
    P("| 期限 | 必要年率 | 正規近似のパーセンタイル | 扱い |")
    P("|------|---------|------------------------|------|")
    for h in horizons:
        r, rid = req[h]
        z = (r - a.base_rate_mean) / a.base_rate_sd
        pct = norm_cdf(z) * 100
        pid = ledger.register("T", raw(pct, 1), "%", f"必要年率（{h} 年）がベースレートの分布で何パーセンタイルか（正規近似）", f"{by}-FY{by_n + h}",
                              "推定", f"Φ(({rid}-{mean_id})/{sd_id})")
        kind = "5 年の分布と同じ期間" if h == 5 else "参考（分布は 5 年。期間が違う）"
        P(f"| FY{by_n + h} | {fmt(r)}% [{rid}] | {fmt(pct)}% [{pid}] | {kind} |")
    P("")
    P("読み方の注意:")
    P("")
    P("- この分布は 5 年間の年率。7 年・10 年の年率はばらつきが小さくなるので、同じ標準偏差で測ると上位の度合いを甘く見る。5 年以外は参考にとどめる")
    P("- 実際の分布は右に裾が長い。正規分布での近似は目安で、上位の度合いを正確には表さない")
    P("- 参照クラスは米国上場企業。国・業種・時代が違う。規模・国・期間の合う参照クラスを選び直すこと")
    if a.fx is not None or a.fx_id:
        fx, fx_id = inp.resolve("為替", a.fx, a.fx_id, a.fx_source, "F", "円", "為替レート（円/ドル）", "—", ("為替", "円/ドル"))
        usd = conv(base, u, "億円") * 1e8 / fx / 1e8  # 億ドル
        usd_id = ledger.register("F", raw(usd, 1), "億ドル", f"{a.metric}（基準年）のドル換算", by, "推定", f"{base_id}/{fx_id}")
        lo, hi = (float(x) for x in a.base_rate_class_usd.split("-"))
        pos = "より小さい" if usd < lo else ("より大きい" if usd > hi else "の範囲内")
        P(f"- 規模: 基準年の売上は約 {fmt(usd)} 億ドル [{usd_id}]（{fmt(fx, 0)} 円/ドル [{fx_id}]）。参照クラスの開始時売上 {a.base_rate_class_usd} 億ドル{pos}")
        if pos != "の範囲内":
            notes.append(f"基準年の売上（約 {fmt(usd)} 億ドル [{usd_id}]）は参照クラスの規模の外にある。合う参照クラスに選び直すか、比べられない点を明記する")
    else:
        notes.append("為替（--fx）を渡していないため、参照クラスとの規模の比較をしていない")
    P("")

    # 3. 自社実績
    P("## 3. 自社の過去の売上成長との比較")
    P("")
    hist: list[tuple[int, float, str]] = []  # (年, 値, ID)
    if fin:
        for r in fin:
            if r["item"] == "売上高" and r["segment"] == "連結":
                try:
                    v = conv(float(r["value"]), r["unit"], u)
                except ValueError:
                    continue
                hist.append((fy_num(r["fiscal_year"]), v, r["id"]))
    elif a.history:
        for part in a.history.split(","):
            fy, v = part.split("=")
            fy = fy.strip()
            vid = ledger.register("F", v.strip(), u, f"{a.metric}（実績）", fy, "公開", f"{a.history_source}（{fy}）")
            hist.append((fy_num(fy), float(v), vid))
    hist.sort()
    own: list[tuple[str, float, str]] = []
    if len(hist) >= 2:
        last = hist[-1]
        windows = []
        first = hist[0]
        windows.append(first)
        five = next((h for h in hist if h[0] == last[0] - 5), None)
        if five and five != first:
            windows.append(five)
        P("| 期間 | 年数 | 実績の年率 | 必要年率（各期限）との比 |")
        P("|------|------|-----------|------------------------|")
        for st in windows:
            n = last[0] - st[0]
            c = ((last[1] / st[1]) ** (1.0 / n) - 1) * 100
            cid = ledger.register("F", raw(c, 2), "%", f"{a.metric}の実績 CAGR（{n} 年）", f"FY{st[0]}-FY{last[0]}",
                                  "推定", f"({last[2]}/{st[2]})^(1/{n})-1")
            own.append((f"FY{st[0]}-FY{last[0]}", c, cid))
            ratios = []
            for h in horizons:
                r, rid = req[h]
                if c > 0:
                    x = r / c
                    xid = ledger.register("T", raw(x, 2), "倍", f"必要年率（{h} 年）÷ 実績 CAGR（FY{st[0]}-FY{last[0]}）", f"{by}-FY{by_n + h}",
                                          "推定", f"{rid}/{cid}")
                    ratios.append(f"{h} 年: {fmt(x)}倍 [{xid}]")
                else:
                    ratios.append(f"{h} 年: —")
            P(f"| FY{st[0]}→FY{last[0]} | {n} 年 | {fmt(c)}% [{cid}] | {'、'.join(ratios)} |")
        P("")
        P("実績の年率は M&A・セグメント組み替え・会計基準の変更を含んだままの数字。不連続は company-financials の報告で確かめる。")
        if hist[0][0] != last[0] - 10 and len(hist) > 2:
            notes.append(f"売上の推移は FY{hist[0][0]}〜FY{last[0]}（{last[0] - hist[0][0]} 年分の伸び）。10 年 CAGR が要るなら FY{last[0] - 10} の値を足す")
    else:
        P("— （financials.csv か --history がないため計算していない）")
        notes.append("自社の過去の売上 CAGR を計算していない。company-financials の後に再実行する")
    P("")

    # 4. ROE
    P("## 4. 資本効率の目標との整合")
    P("")
    if a.roe_target is not None or a.roe_id:
        if fin:
            if a.equity is None and not a.equity_id:
                hit = fin_lookup(fin, "純資産", by, u)
                a.equity_id = hit[1] if hit else None
            if a.net_income is None and not a.net_income_id:
                hit = fin_lookup(fin, "親会社株主に帰属する当期純利益", by, u)
                a.net_income_id = hit[1] if hit else None
        roe, roe_id = inp.resolve("ROE 目標", a.roe_target, a.roe_id, a.roe_source, "T", "%", "ROE の目標（定義・期限は未確定）", "—", ("ROE",))
        eq, eq_id = inp.resolve("自己資本", a.equity, a.equity_id, a.equity_source, "F", u, "純資産（基準年末、連結）", by, ("純資産", "資本", "持分"))
        ni, ni_id = inp.resolve("純利益", a.net_income, a.net_income_id, a.net_income_source, "F", u, "親会社株主に帰属する当期純利益（連結）", by, ("利益",))
        if eq is None or ni is None:
            P("— （自己資本か純利益がないため計算していない）")
            notes.append("ROE との整合は、自己資本と純利益を渡してから計算する")
        else:
            roe_now = ni / eq * 100
            roe_now_id = ledger.register("F", raw(roe_now, 2), "%", "ROE（基準年、期末自己資本ベース）", by, "推定", f"{ni_id}/{eq_id}")
            m_now = ni / base * 100
            m_now_id = ledger.register("F", raw(m_now, 2), "%", "純利益率（基準年、純利益÷売上）", by, "推定", f"{ni_id}/{base_id}")
            ni_req0 = roe / 100 * eq
            ni_req0_id = ledger.register("T", raw(ni_req0, 1), u, "ROE 目標を基準年の自己資本で満たす純利益", by, "推定", f"{roe_id}×{eq_id}")
            P(f"- 基準年の ROE {fmt(roe_now)}% [{roe_now_id}]（期末自己資本ベース）、純利益率 {fmt(m_now, 2)}% [{m_now_id}]")
            P(f"- ROE 目標 {fmt(roe)}% [{roe_id}] を今の自己資本のまま満たす純利益: {fmt(ni_req0)} {u} [{ni_req0_id}]")
            P("")
            pay = pay_id = None
            if a.payout is not None or a.payout_id:
                pay, pay_id = inp.resolve("配当性向", a.payout, a.payout_id, a.payout_source, "F", "%", "配当性向", "—", ("配当性向",))
            P("| 期限 | 想定する自己資本 | ROE 目標に要る純利益 | 目標売上に対する純利益率 | 基準年の純利益率との差 | 基準年の純利益率のままの ROE |")
            P("|------|----------------|--------------------|----------------------|--------------------|--------------------------|")
            for h in horizons:
                r, rid = req[h]
                fy_t = f"FY{by_n + h}"
                if pay is not None:
                    # 売上が必要年率で伸び、純利益率は基準年のまま、配当性向で内部留保が積み上がる
                    eq_t = eq + sum(base * (1 + r / 100) ** t * m_now / 100 * (1 - pay / 100) for t in range(1, h + 1))
                    eq_t_id = ledger.register("T", raw(eq_t, 1), u, f"想定自己資本（売上が必要年率で伸び、純利益率は基準年のまま、配当性向で内部留保。{h} 年後）", fy_t,
                                              "推定", f"{eq_id}+Σ[t=1..{h}]({base_id}×(1+{rid})^t×{m_now_id}×(1-{pay_id}))")
                    eq_cell = f"{fmt(eq_t)} {u} [{eq_t_id}]"
                    eq_src = eq_t_id
                else:
                    eq_t = eq
                    eq_cell = f"{fmt(eq_t)} {u} [{eq_id}]（基準年のまま）"
                    eq_src = eq_id
                eq_note = "内部留保で積み上がる自己資本" if pay is not None else "自己資本は基準年のまま"
                ni_req = roe / 100 * eq_t
                ni_req_id = ledger.register("T", raw(ni_req, 1), u, f"ROE 目標に要る純利益（{h} 年後、{eq_note}）", fy_t, "推定", f"{roe_id}×{eq_src}")
                mreq = ni_req / target * 100
                mreq_id = ledger.register("T", raw(mreq, 2), "%", f"目標売上で ROE 目標を満たす純利益率（{h} 年後、{eq_note}）", fy_t, "推定", f"{ni_req_id}/{target_id}")
                d = mreq - m_now
                d_id = ledger.register("T", raw(d, 2), "pt", f"要る純利益率と基準年の純利益率の差（{h} 年後、{eq_note}）", fy_t, "推定", f"{mreq_id}-{m_now_id}")
                roe_keep = target * m_now / 100 / eq_t * 100
                roe_keep_id = ledger.register("T", raw(roe_keep, 2), "%", f"目標売上で純利益率が基準年のままのときの ROE（{h} 年後、期末自己資本ベース、{eq_note}）", fy_t,
                                              "推定", f"{target_id}×{m_now_id}/{eq_src}")
                P(f"| {fy_t} | {eq_cell} | {fmt(ni_req)} {u} [{ni_req_id}] | {fmt(mreq, 2)}% [{mreq_id}] | {fmt(d, 2)}pt [{d_id}] | {fmt(roe_keep)}% [{roe_keep_id}] |")
            P("")
            if pay is None:
                notes.append("自己資本を基準年のまま置いた。内部留保で増える分を入れるなら --payout を渡す")
            else:
                notes.append("想定自己資本は、売上が必要年率で伸び、純利益率が基準年のまま、配当性向が一定という単純化。自社株買い・M&A ののれん・増資は入れていない")
            notes.append("ROE は期末自己資本ベースで計算した。会社の開示が期中平均ベースなら、数字が少しずれる")
    else:
        P("— （ROE 目標を渡していないため計算していない）")
        notes.append("資本効率の目標（ROE・ROIC）が未確定。目標仕様で決める")
    P("")

    # 5. 前提と未確認事項
    P("## 前提と未確認事項（スクリプトが置いた前提）")
    P("")
    for n in inp.notes + notes + ledger.warnings:
        P(f"- {n}")
    P("- 目標の期限・連結か単体か・オーガニックか M&A 込みか・為替前提は、このスクリプトでは決めない。00-target-spec.md の定義チェックで確かめる")
    P("")

    text = "\n".join(out)
    print(text)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n", encoding="utf-8")
    if ledger.new:
        if a.append and a.ledger:
            ledger.write()
            print(f"\n<!-- 台帳 {a.ledger} に {len(ledger.new)} 行を追記した -->", file=sys.stderr)
        else:
            print("\n<!-- 台帳に追記する予定の行（--ledger と --append で追記） -->", file=sys.stderr)
            print(ledger.new_rows_csv(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
