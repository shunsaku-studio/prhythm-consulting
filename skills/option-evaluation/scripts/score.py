#!/usr/bin/env python3
"""評価マトリクスの加重合計を出す（option-evaluation）。順位は付けない。

重みは人が決める。--weights がなければ計算しない。
出力は入力と同じ順に並べ、加重合計と「重みを少し動かすと上下が入れ替わる組」を示す。
どれを追うかは人が決める（decisions.md に D-xxx）。

入力 CSV の列:
  id,option,impact,feasibility,capital_need,time_to_effect,risk,fit,red_line,note
  - 点数は 1〜5。どの軸も「大きいほど良い」にそろえる
    （capital_need は 5 = 必要資本が小さい、time_to_effect は 5 = 効果が早い、risk は 5 = リスクが小さい）
  - 分からない点数は —。その案の加重合計は — になる
  - red_line: 経営者の譲れない線に触れるか。○（触れない）/ ×（触れる）/ —（未確認）。× でも消さずに示す

使い方:
  python3 score.py matrix.csv --weights impact=30,feasibility=20,capital_need=15,time_to_effect=10,risk=15,fit=10 \\
      [--shift 10] [--out-md evaluation.tables.md]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

CRITERIA = ["impact", "feasibility", "capital_need", "time_to_effect", "risk", "fit"]
LABEL = {"impact": "効果", "feasibility": "実現性", "capital_need": "必要資本（小さいほど高い）",
         "time_to_effect": "効果が出る早さ", "risk": "リスク（小さいほど高い）", "fit": "中計・経営者との整合"}


def parse_weights(text: str) -> dict[str, float]:
    w = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        k = k.strip()
        if k not in CRITERIA:
            raise SystemExit(f"入力エラー: 軸 {k!r} はありません（{', '.join(CRITERIA)}）")
        w[k] = float(v)
    miss = [c for c in CRITERIA if c not in w]
    if miss:
        raise SystemExit(f"入力エラー: 重みのない軸があります: {', '.join(miss)}（使わない軸は 0 と書く）")
    if sum(w.values()) <= 0:
        raise SystemExit("入力エラー: 重みの合計が 0 です")
    return w


def total(row: dict, w: dict[str, float]) -> float | None:
    s = sum(w.values())
    acc = 0.0
    for c in CRITERIA:
        if w[c] == 0:
            continue
        v = (row.get(c) or "").strip()
        if v in {"", "—"}:
            return None
        x = float(v)
        if not 1 <= x <= 5:
            raise SystemExit(f"入力エラー: {row['id']} の {c} が 1〜5 の外です: {v}")
        acc += x * w[c] / s
    return acc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("matrix")
    ap.add_argument("--weights", help="人が決めた重み。例 impact=30,feasibility=20,...")
    ap.add_argument("--shift", type=float, default=10.0, help="感応度で各軸の重みを動かす幅（既定 10）")
    ap.add_argument("--out-md")
    args = ap.parse_args()
    if not args.weights:
        print("重みが指定されていません。重みは人が決める。決まったら --weights で渡す", file=sys.stderr)
        return 2
    w = parse_weights(args.weights)
    with Path(args.matrix).open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("id") or "").strip()]

    tot = {r["id"]: total(r, w) for r in rows}
    flips = set()
    for c in CRITERIA:
        for d in (-args.shift, args.shift):
            w2 = dict(w)
            w2[c] = max(0.0, w2[c] + d)
            t2 = {r["id"]: total(r, w2) for r in rows}
            for a, b in itertools.combinations([r["id"] for r in rows], 2):
                if None in (tot[a], tot[b], t2[a], t2[b]):
                    continue
                if (tot[a] - tot[b]) * (t2[a] - t2[b]) < 0:
                    flips.add((a, b, f"{LABEL[c]} {'+' if d > 0 else '−'}{abs(d):g}"))

    L = ["## 評価マトリクスの加重合計（入力順。順位は付けない）", "",
         "| 軸 | " + " | ".join(LABEL[c] for c in CRITERIA) + " |",
         "|----|" + "|".join("----:" for _ in CRITERIA) + "|",
         "| 重み（人が決めた値） | " + " | ".join(f"{w[c]:g}" for c in CRITERIA) + " |", "",
         "| ID | 打ち手 | " + " | ".join(LABEL[c] for c in CRITERIA) + " | 加重合計（1〜5） | 譲れない線 |",
         "|----|--------|" + "|".join("----:" for _ in CRITERIA) + "|-----:|:----:|"]
    for r in rows:
        t = tot[r["id"]]
        L.append(f"| {r['id']} | {r['option']} | " + " | ".join((r.get(c) or "—").strip() or "—" for c in CRITERIA)
                 + f" | {'—' if t is None else f'{t:.2f}'} | {(r.get('red_line') or '—').strip() or '—'} |")
    L += ["", "## 重みを動かすと上下が入れ替わる組", ""]
    if flips:
        for a, b, why in sorted(flips):
            L.append(f"- {a} と {b}: {why} で入れ替わる")
    else:
        L.append(f"- 各軸の重みを ±{args.shift:g} 動かしても入れ替わる組はない")
    L += ["", "## 前提と未確認事項（スクリプトが拾ったもの）", ""]
    for r in rows:
        if tot[r["id"]] is None:
            L.append(f"- {r['id']}: 点数に — があり、加重合計は出していない")
        if (r.get("red_line") or "").strip() == "×":
            L.append(f"- {r['id']}: 経営者の譲れない線に触れる。外すかどうかは人が決める")
        if (r.get("red_line") or "").strip() in {"", "—"}:
            L.append(f"- {r['id']}: 譲れない線に触れるかが未確認")
    L.append("- 加重合計は議論の材料。差が小さい案どうしは同じ扱いにする")
    text = "\n".join(L) + "\n"
    if args.out_md:
        Path(args.out_md).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
