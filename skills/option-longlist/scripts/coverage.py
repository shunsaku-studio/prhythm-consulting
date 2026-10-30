#!/usr/bin/env python3
"""打ち手のロングリストの網羅を点検する（option-longlist）。

04-options.md の「打ち手候補」の表と「該当なしの判断」の表を読み、
網羅グリッド（6 行 × 3 列）に O-xxx を並べる。空いているマスは埋めずに「空欄」と出す。
空欄は「検討していない」のか「検討して該当なし」なのかを人が書き分ける。

打ち手候補の表の列（見出しの名前で読む。順番は問わない）:
  ID | 打ち手 | 類型 | 市場 | 製品 | 進め方 | 対象ギャップ | レーン | 根拠
  - 類型: 成長 / 価格・ミックス / ポートフォリオ
  - 市場・製品: 既存 / 新規（類型が成長のときに必須）
  - 進め方: 自前 / 提携 / 買収 / 売却（売却は 3 列目に入れる）
  - 対象ギャップ: G-001 など（複数は「、」区切り）
  - レーン: 1（中計に則る）/ 2（中計の外側）

該当なしの判断の表の列: 行 | 列 | 理由 | 判断した人

使い方:
  python3 coverage.py 04-options.md [--gaps 03-gap-bridge.md] [--write]
  --write を付けると、04-options.md の <!-- COVERAGE:BEGIN --> と <!-- COVERAGE:END --> の間を書き換える。
終了コード: 空欄・未対応のギャップ・列の不備があれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROWS = [
    ("市場浸透（既存市場 × 既存製品）", ("成長", "既存", "既存")),
    ("製品開発（既存市場 × 新規製品）", ("成長", "既存", "新規")),
    ("市場開拓（新規市場 × 既存製品）", ("成長", "新規", "既存")),
    ("多角化（新規市場 × 新規製品）", ("成長", "新規", "新規")),
    ("価格・ミックス", ("価格・ミックス", None, None)),
    ("ポートフォリオ（撤退・売却・縮小）", ("ポートフォリオ", None, None)),
]
COLS = ["自前", "提携", "買収・売却"]
COL_OF = {"自前": 0, "提携": 1, "買収": 2, "売却": 2, "買収・売却": 2}
BEGIN, END = "<!-- COVERAGE:BEGIN -->", "<!-- COVERAGE:END -->"


def tables_under(text: str, heading_kw: str) -> list[dict[str, str]]:
    """heading_kw を含む見出しの直後にある最初の Markdown 表を辞書のリストで返す。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and heading_kw in line:
            start = i + 1
            break
    if start is None:
        return []
    rows, header = [], None
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("#"):
            break
        if not s.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def norm_col(v: str) -> int | None:
    v = v.strip()
    for k, i in COL_OF.items():
        if k in v:
            return i
    return None


def row_index(t: str, m: str, p: str) -> int | None:
    for i, (_, (tt, mm, pp)) in enumerate(ROWS):
        if tt == t and (mm is None or (mm == m and pp == p)):
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("options_md")
    ap.add_argument("--gaps", help="03-gap-bridge.md。G-xxx を拾い、打ち手のないギャップを出す")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    path = Path(args.options_md)
    text = path.read_text(encoding="utf-8")
    opts = [r for r in tables_under(text, "打ち手候補") if re.match(r"O-\d{3,}", r.get("ID", ""))]
    nones = tables_under(text, "該当なしの判断")
    problems: list[str] = []
    if not opts:
        print("打ち手候補の表が見つからないか、O-xxx の行がありません", file=sys.stderr)
        return 2

    grid = [[[] for _ in COLS] for _ in ROWS]
    lanes = {"1": 0, "2": 0}
    covered_gaps: set[str] = set()
    for o in opts:
        oid = o["ID"]
        t = o.get("類型", "").strip()
        m, p = o.get("市場", "").strip(), o.get("製品", "").strip()
        r = row_index(t, m, p)
        c = norm_col(o.get("進め方", ""))
        if r is None:
            problems.append(f"{oid}: 類型・市場・製品からマスが決まらない（類型={t or '空'}, 市場={m or '空'}, 製品={p or '空'}）")
        if c is None:
            problems.append(f"{oid}: 進め方が 自前/提携/買収/売却 のどれでもない（{o.get('進め方', '') or '空'}）")
        if r is not None and c is not None:
            grid[r][c].append(oid)
        gs = re.findall(r"G-\d{3,}", o.get("対象ギャップ", ""))
        if not gs:
            problems.append(f"{oid}: 対象ギャップ（G-xxx）が書かれていない")
        covered_gaps.update(gs)
        lane = o.get("レーン", "").strip()
        found = False
        for k in lanes:
            if k in lane:
                lanes[k] += 1
                found = True
        if not found:
            problems.append(f"{oid}: レーン（1 / 2）が書かれていない")

    judged = {}
    for n in nones:
        rn, cn = n.get("行", ""), n.get("列", "")
        ri = next((i for i, (label, _) in enumerate(ROWS) if rn and (rn in label or label.startswith(rn))), None)
        ci = norm_col(cn)
        if ri is not None and ci is not None and n.get("理由", "").strip() not in {"", "—"}:
            judged[(ri, ci)] = n

    L = [BEGIN, "", "## 網羅グリッド（coverage.py の出力）", "",
         "| 類型 | " + " | ".join(COLS) + " |", "|------|" + "|".join("------" for _ in COLS) + "|"]
    empty = []
    for ri, (label, _) in enumerate(ROWS):
        cells = []
        for ci in range(len(COLS)):
            if grid[ri][ci]:
                cells.append(", ".join(grid[ri][ci]))
            elif (ri, ci) in judged:
                cells.append("該当なし（判断済み）")
            else:
                cells.append("**空欄**")
                empty.append(f"{label} × {COLS[ci]}")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L.append("")
    L.append(f"- 打ち手 {len(opts)} 件（レーン 1: {lanes['1']} 件、レーン 2: {lanes['2']} 件）")
    if empty:
        L.append(f"- 空欄 {len(empty)} マス。埋めずに、検討していないのか該当なしなのかを人が書き分ける:")
        L += [f"  - {e}" for e in empty]
    if lanes["2"] == 0:
        L.append("- レーン 2（中計の外側）の打ち手がない。M&A、市場の選び直し、撤退も検討したか確かめる")
    if lanes["1"] == 0:
        L.append("- レーン 1（中計に則る）の打ち手がない。中計の重点施策を拾えているか確かめる")
    if args.gaps:
        gtext = Path(args.gaps).read_text(encoding="utf-8")
        all_gaps = sorted(set(re.findall(r"G-\d{3,}", gtext)))
        miss = [g for g in all_gaps if g not in covered_gaps]
        unknown = sorted(g for g in covered_gaps if g not in all_gaps)
        if miss:
            L.append(f"- 打ち手が 1 つもないギャップ: {', '.join(miss)}")
        if unknown:
            L.append(f"- 03-gap-bridge.md にないギャップ ID: {', '.join(unknown)}")
        problems += [f"打ち手のないギャップ {g}" for g in miss] + [f"不明なギャップ ID {g}" for g in unknown]
    for pr in problems:
        L.append(f"- 不備: {pr}")
    L += ["", END]
    block = "\n".join(L)

    if args.write:
        if BEGIN in text and END in text:
            new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
        else:
            new = text.rstrip() + "\n\n" + block + "\n"
        path.write_text(new, encoding="utf-8")
    print(block)
    return 1 if (empty or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
