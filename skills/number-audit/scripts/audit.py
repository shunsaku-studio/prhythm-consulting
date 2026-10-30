#!/usr/bin/env python3
"""案件フォルダの数字を、ファクト台帳 facts/facts.csv と突き合わせて点検する。

点検すること:
  1. 台帳の各行: 出典タグが 4 種のいずれか / 必須情報（出典・計算式・差し替え期限）がある
  2. 仮置きの差し替え期限が過ぎていないか
  3. 推定の計算式が参照する ID が台帳にあるか
  4. Markdown と CSV に書かれた [ID] が台帳にあるか
  5. [ID] の直前の数字が台帳の値と一致するか（単位の換算と表示の丸めを許容）
  6. 出典 ID の付いていない数字（deliverables/ ではエラー、それ以外は警告）
  7. 社外に出す成果物（deliverables/）に社外秘の値が入っていないか

使い方:
  python3 audit.py <case-dir> [--today YYYY-MM-DD] [--out report.md]

終了コード: エラーが 1 件以上あれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

SOURCE_TAGS = {"公開", "クライアント提供", "推定", "仮置き"}
CONFIDENTIALITY = {"公開", "社外秘"}
ID_RE = r"[TQAFSGOICKD]-\d{3,}"
TAG_RE = re.compile(r"\[(" + ID_RE + r"(?:\s*[,、]\s*" + ID_RE + r")*)\]")
BARE_ID_RE = re.compile(ID_RE)
NUM_RE = re.compile(r"[-−▲]?\d[\d,]*(?:\.\d+)?")
# 出典が要る「数字」とみなす単位
UNIT_NUM_RE = re.compile(r"[-−▲]?\d[\d,]*(?:\.\d+)?\s*(?:億円|百万円|兆円|万円|円|%|％|pt|ポイント|倍)")
EXEMPT_DIRS = {"sources", "reviews"}  # 一次資料の写しと、質問タイムの記録は対象外
STRICT_DIR = "deliverables"

# 単位ごとの「億円」への換算係数
TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0, "万円": 0.0001}


def parse_number(text: str) -> float | None:
    t = text.replace(",", "").replace("−", "-").replace("▲", "-").strip()
    try:
        return float(t)
    except ValueError:
        return None


def decimals(text: str) -> int:
    t = text.replace(",", "")
    return len(t.split(".")[1]) if "." in t else 0


class Report:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append((where, msg))


def load_ledger(path: Path, today: dt.date, rep: Report) -> dict[str, dict[str, str]]:
    ledger: dict[str, dict[str, str]] = {}
    if not path.exists():
        rep.error(str(path), "ファクト台帳がありません")
        return ledger
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = ["id", "value", "unit", "definition", "period", "source_tag", "source",
                    "retrieved_at", "confidentiality", "replace_by"]
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            rep.error(path.name, f"台帳の列が足りません: {', '.join(missing)}")
            return ledger
        for line_no, row in enumerate(reader, start=2):
            where = f"facts.csv:{line_no}"
            rid = (row["id"] or "").strip()
            if not re.fullmatch(ID_RE, rid):
                rep.error(where, f"ID の形式が不正です: {rid!r}")
                continue
            if rid in ledger:
                rep.error(where, f"{rid} が重複しています")
            ledger[rid] = row
            tag = (row["source_tag"] or "").strip()
            src = (row["source"] or "").strip()
            if tag not in SOURCE_TAGS:
                rep.error(where, f"{rid}: 出典タグ {tag!r} は 公開/クライアント提供/推定/仮置き のいずれでもありません")
            if tag in {"公開", "クライアント提供"} and src in {"", "—"}:
                rep.error(where, f"{rid}: {tag} の値に資料名がありません")
            if tag == "推定":
                if src in {"", "—"}:
                    rep.error(where, f"{rid}: 推定の値に計算式がありません")
                else:
                    for ref in BARE_ID_RE.findall(src):
                        if ref == rid:
                            rep.error(where, f"{rid}: 計算式が自分自身を参照しています")
            if tag == "クライアント提供" and (row["confidentiality"] or "").strip() != "社外秘":
                rep.error(where, f"{rid}: クライアント提供の値は confidentiality=社外秘 にしてください")
            if (row["confidentiality"] or "").strip() not in CONFIDENTIALITY:
                rep.error(where, f"{rid}: confidentiality は 公開/社外秘 のいずれかです")
            if tag == "仮置き":
                rb = (row["replace_by"] or "").strip()
                if not rb:
                    rep.error(where, f"{rid}: 仮置きに差し替え期限 replace_by がありません")
                else:
                    try:
                        if dt.date.fromisoformat(rb) < today:
                            rep.error(where, f"{rid}: 仮置きの差し替え期限 {rb} を過ぎています（{row['definition']}）")
                    except ValueError:
                        rep.error(where, f"{rid}: replace_by の日付が不正です: {rb!r}")
    # 推定の計算式の参照先
    for rid, row in ledger.items():
        if (row["source_tag"] or "").strip() == "推定":
            for ref in BARE_ID_RE.findall(row["source"] or ""):
                if ref != rid and ref not in ledger:
                    rep.error(f"facts.csv ({rid})", f"計算式が参照する {ref} が台帳にありません")
    return ledger


def value_matches(shown: str, shown_unit: str, row: dict[str, str]) -> bool:
    """表示された数字が台帳の値と一致するか。単位の換算と表示の丸めを許容する。"""
    v_shown = parse_number(shown)
    v_ledger = parse_number(row["value"] or "")
    if v_shown is None or v_ledger is None:
        return True  # 比べられないものは問わない（— など）
    ledger_unit = (row["unit"] or "").strip()
    candidates = [v_ledger]
    if shown_unit in TO_OKU and ledger_unit in TO_OKU:
        candidates.append(v_ledger * TO_OKU[ledger_unit] / TO_OKU[shown_unit])
    if ledger_unit in {"%", "％"} and shown_unit in {"%", "％", "pt", "ポイント", ""}:
        candidates.append(v_ledger)
    if ledger_unit == "倍" and shown_unit in {"%", "％"}:
        candidates.append(v_ledger * 100)
    if ledger_unit in {"%", "％"} and shown_unit == "倍":
        candidates.append(v_ledger / 100)
    # 符号の表し方（▲ や 「減」）の違いは許容する
    candidates += [-c for c in candidates]
    tol = 0.5 * 10 ** (-decimals(shown))
    return any(abs(round(c, 10) - v_shown) <= tol + 1e-9 for c in candidates)


def unit_after(text: str, end: int) -> str:
    m = re.match(r"\s*(億円|百万円|兆円|万円|円|%|％|pt|ポイント|倍)", text[end:])
    return m.group(1) if m else ""


def strip_code(lines: list[str]) -> list[tuple[int, str]]:
    out, in_code = [], False
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            out.append((i, re.sub(r"`[^`]*`", "", line)))
    return out


def check_markdown(path: Path, rel: str, ledger: dict, rep: Report, strict: bool) -> int:
    count = 0
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, line in strip_code(lines):
        where = f"{rel}:{line_no}"
        cells = line.split("|") if line.lstrip().startswith("|") else [line]
        for cell in cells:
            tags = list(TAG_RE.finditer(cell))
            for m in tags:
                ids = [s.strip() for s in re.split(r"[,、]", m.group(1))]
                for rid in ids:
                    count += 1
                    if rid not in ledger:
                        rep.error(where, f"[{rid}] が台帳にありません")
                    elif strict and (ledger[rid]["confidentiality"] or "").strip() == "社外秘":
                        rep.error(where, f"[{rid}] は社外秘です。社外に出す成果物に載せられません")
                # 直前の数字と台帳の値を比べる（ID が 1 つのときだけ）
                if len(ids) == 1 and ids[0] in ledger:
                    before = cell[: m.start()]
                    prev_end = max((t.end() for t in tags if t.end() <= m.start()), default=0)
                    window = before[prev_end:]
                    nums = list(NUM_RE.finditer(window))
                    if nums:
                        last = nums[-1]
                        # 数字と ID の間が離れすぎていれば比べない
                        gap = window[last.end():]
                        if len(gap) <= 6:
                            u = unit_after(window, last.end())
                            if not value_matches(last.group(), u, ledger[ids[0]]):
                                rep.error(where, f"{last.group()}{u} [{ids[0]}] が台帳の値 {ledger[ids[0]]['value']}{ledger[ids[0]]['unit']} と一致しません")
            # 出典のない数字（文や句ごとに見る。ID が同じ句にあれば出典ありとみなす）
            for clause in re.split(r"[。、；;]|と(?=\s*\d)", cell):
                if BARE_ID_RE.search(clause):
                    continue
                stripped = re.sub(r"FY\d{4}(?:-FY\d{4})?|\d{4}-\d{2}-\d{2}|\d{4}\s*年(?:度)?", "", clause)
                for m in UNIT_NUM_RE.finditer(stripped):
                    msg = f"出典 ID のない数字: {m.group().strip()}"
                    (rep.error if strict else rep.warn)(where, msg)
    return count


def check_csv(path: Path, rel: str, ledger: dict, rep: Report) -> int:
    count = 0
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "id" not in reader.fieldnames:
            return 0
        for line_no, row in enumerate(reader, start=2):
            rid = (row.get("id") or "").strip()
            if not rid:
                continue
            count += 1
            where = f"{rel}:{line_no}"
            if rid not in ledger:
                rep.error(where, f"{rid} が台帳にありません")
                continue
            if "value" in row and row["value"] not in (None, "", "—"):
                unit = (row.get("unit") or ledger[rid]["unit"] or "").strip()
                if not value_matches(row["value"], unit, ledger[rid]):
                    rep.error(where, f"{rid} の値 {row['value']} が台帳の値 {ledger[rid]['value']} と一致しません")
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_dir")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", help="レポートを書き出す Markdown のパス")
    args = ap.parse_args()

    case = Path(args.case_dir)
    today = dt.date.fromisoformat(args.today)
    rep = Report()
    ledger_path = case / "facts" / "facts.csv"
    ledger = load_ledger(ledger_path, today, rep)

    refs = 0
    files = 0
    for path in sorted(case.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(case).as_posix()
        top = rel.split("/")[0]
        if top in EXEMPT_DIRS or path == ledger_path or rel == "brief.md":
            continue
        if args.out and path.resolve() == Path(args.out).resolve():
            continue
        if path.suffix == ".md":
            files += 1
            refs += check_markdown(path, rel, ledger, rep, strict=(top == STRICT_DIR))
        elif path.suffix == ".csv":
            files += 1
            refs += check_csv(path, rel, ledger, rep)

    by_tag: dict[str, int] = {}
    for row in ledger.values():
        by_tag[row["source_tag"]] = by_tag.get(row["source_tag"], 0) + 1

    out = [
        "# number-audit レポート",
        "",
        f"- 点検日: {today.isoformat()}",
        f"- 台帳: {len(ledger)} 件（" + "、".join(f"{k} {v}" for k, v in sorted(by_tag.items())) + "）",
        f"- 点検したファイル: {files} 件、ID 参照: {refs} 件",
        f"- **エラー: {len(rep.errors)} 件** / 警告: {len(rep.warnings)} 件",
        "",
    ]
    if rep.errors:
        out += ["## エラー（直してから上に出す）", "", "| 場所 | 内容 |", "|------|------|"]
        out += [f"| {w} | {m} |" for w, m in rep.errors]
        out.append("")
    if rep.warnings:
        out += ["## 警告（作業中の成果物。デッキに載せる前に ID を付ける）", "", "| 場所 | 内容 |", "|------|------|"]
        out += [f"| {w} | {m} |" for w, m in rep.warnings]
        out.append("")
    text = "\n".join(out)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
