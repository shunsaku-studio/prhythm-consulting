#!/usr/bin/env python3
"""ファクト台帳 facts/facts.csv に 1 行を足す（公開・クライアント提供・推定・仮置きのどれでも）。

スクリプトの計算結果ではない数字（WACC の開示値、工業会の市場規模、議論のための仮置きなど）を
手で台帳に載せるときに使う。台帳を直接編集すると列の抜けや ID の重複が起きやすいので、ここを通す。

- ID は接頭辞ごとに使われていない最小の番号を振る（--id で指定もできる）
- 定義・期間・出典タグ・値が同じ行がすでにあれば、新しい行を作らずその ID を返す
- 台帳の決まり（CONVENTIONS.md 2 節）に合わない行は書かずに止まる

例:
  python3 add_fact.py case/facts/facts.csv --value 6.0 --unit % \\
    --definition "WACC（会社開示）" --period FY2025 --tag 公開 \\
    --source "資本コストや株価を意識した経営の実現に向けた対応 p.2"
  python3 add_fact.py case/facts/facts.csv --value 30 --unit % \\
    --definition "実効税率" --period FY2025-FY2030 --tag 仮置き --replace-by 2026-11-27
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

COLUMNS = ["id", "value", "unit", "definition", "period", "source_tag", "source",
           "retrieved_at", "confidentiality", "replace_by"]
SOURCE_TAGS = {"公開", "クライアント提供", "推定", "仮置き"}


def next_id(rows: list[dict[str, str]], prefix: str) -> str:
    used = {int(m.group(1)) for r in rows if (m := re.fullmatch(prefix + r"-(\d+)", r["id"]))}
    n = 1
    while n in used:
        n += 1
    return f"{prefix}-{n:03d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ledger", help="facts/facts.csv のパス（なければ見出し行から作る）")
    ap.add_argument("--prefix", default="F", help="ID の接頭辞（既定 F）")
    ap.add_argument("--id", help="ID を指定するとき")
    ap.add_argument("--value", required=True, help="数値。分からなければ —")
    ap.add_argument("--unit", required=True)
    ap.add_argument("--definition", required=True)
    ap.add_argument("--period", required=True)
    ap.add_argument("--tag", required=True, choices=sorted(SOURCE_TAGS))
    ap.add_argument("--source", default="—", help="資料名とページ、または計算式と入力 ID")
    ap.add_argument("--retrieved-at", default=dt.date.today().isoformat())
    ap.add_argument("--confidentiality", choices=["公開", "社外秘"])
    ap.add_argument("--replace-by", default="", help="仮置きの差し替え期限 YYYY-MM-DD")
    args = ap.parse_args()

    problems = []
    if args.tag in {"公開", "クライアント提供", "推定"} and args.source in {"", "—"}:
        problems.append(f"{args.tag} の値には --source（資料名か計算式）が要る")
    if args.tag == "仮置き" and not args.replace_by:
        problems.append("仮置きには --replace-by（差し替え期限）が要る")
    if args.value != "—":
        try:
            float(args.value.replace(",", ""))
        except ValueError:
            problems.append(f"--value は数値か — にする: {args.value!r}")
    conf = args.confidentiality or ("社外秘" if args.tag == "クライアント提供" else "公開")
    if args.tag == "クライアント提供" and conf != "社外秘":
        problems.append("クライアント提供の値は社外秘にする")
    if problems:
        for p in problems:
            print(f"エラー: {p}", file=sys.stderr)
        return 2

    path = Path(args.ledger)
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    value = args.value.replace(",", "")
    for r in rows:
        if (r["definition"], r["period"], r["source_tag"], r["value"]) == (args.definition, args.period, args.tag, value):
            print(r["id"])
            print(f"既にある行を使う: {r['id']}", file=sys.stderr)
            return 0

    rid = args.id or next_id(rows, args.prefix)
    if any(r["id"] == rid for r in rows):
        print(f"エラー: {rid} は台帳にすでにある", file=sys.stderr)
        return 2
    row = {
        "id": rid, "value": value, "unit": args.unit, "definition": args.definition,
        "period": args.period, "source_tag": args.tag, "source": args.source,
        "retrieved_at": args.retrieved_at, "confidentiality": conf,
        "replace_by": args.replace_by if args.tag == "仮置き" else "",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        if new_file:
            w.writeheader()
        w.writerow(row)
    print(rid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
