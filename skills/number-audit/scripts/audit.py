#!/usr/bin/env python3
"""案件フォルダの数字を、ファクト台帳 facts/facts.csv と突き合わせて点検する。

点検すること:
  1. 台帳の各行: 出典タグが 4 種のいずれか / 必須情報（出典・計算式・差し替え期限）がある
  2. 仮置きの差し替え期限が過ぎていないか
  3. 推定の計算式が参照する ID が台帳にあるか
  4. Markdown と CSV に書かれた [ID] が台帳にあるか
     （Q・A・O・D は数字を持たないので、案件内の Markdown で定義されていればよい）
  5. [ID] の直前の数字が台帳の値と一致するか（単位の換算と表示の丸めを許容）
  6. 出典 ID の付いていない数字（deliverables/ ではエラー、それ以外は警告）
  7. 社外に出す成果物（deliverables/）に社外秘の値が入っていないか
  8. deliverables/ が参照する推定値が、計算式をたどって仮置きや — に依存していないか（警告）
  9. model/business-case.xlsx の inputs シートが台帳と一致するか、
     計算シートに数値の直打ち（数式のない数値セル）がないか

使い方:
  python3 audit.py <case-dir> [--today YYYY-MM-DD] [--out report.md] [--strict]

  --strict  警告もエラーとして数える（上に出す直前の最終点検用）

終了コード: エラーが 1 件以上あれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_TAGS = {"公開", "クライアント提供", "推定", "仮置き"}
CONFIDENTIALITY = {"公開", "社外秘"}
ID_RE = r"[TQAFSGOICKD]-\d{3,}"
TAG_RE = re.compile(r"\[(" + ID_RE + r"(?:\s*[,、]\s*" + ID_RE + r")*)\]")
BARE_ID_RE = re.compile(ID_RE)
NUM_RE = re.compile(r"[-−▲]?\d[\d,]*(?:\.\d+)?")
# 出典が要る「数字」とみなす単位
UNIT_NUM_RE = re.compile(r"[-−▲]?\d[\d,]*(?:\.\d+)?\s*(?:億円|百万円|兆円|万円|円|%|％|pt|ポイント|倍)")
# 値の比較で数字とみなさないもの（年度・日付・ID の連番）
NOT_VALUE_RE = re.compile(r"FY\d{4}(?:-FY\d{4})?|\d{4}-\d{2}-\d{2}|" + ID_RE)
EXEMPT_DIRS = {"sources", "reviews"}  # 一次資料の写しと、質問タイム・点検の記録は対象外
STRICT_DIR = "deliverables"
# 数字を持たず、台帳ではなく各成果物で定義される ID の接頭辞
NON_NUMERIC_PREFIXES = {"Q", "A", "O", "D"}
# Markdown で ID を「定義」している行: 見出し、表の先頭セル、箇条書きの先頭
DEF_LINE_RE = re.compile(r"^\s*(?:#{1,6}\s+|\|\s*|[-*]\s+|\d+\.\s+)\**(" + ID_RE + r")\b")
XLSX_PATH = PurePosixPath("model/business-case.xlsx")
INPUT_SHEET = "inputs"

# 単位ごとの「億円」への換算係数
TO_OKU = {"億円": 1.0, "百万円": 0.01, "兆円": 10000.0, "万円": 0.0001}

NOT_CHECKED = [
    "定義の食い違い（連結とセグメント、オーガニックと M&A 込み など）。値が同じでも定義が違えば別の数字である",
    "単位の付かない数字（表の中の素の数字など）の出典",
    "計算式そのものの正しさ（参照先の ID があるかだけを見る）",
    "ID から離れた場所（7 文字以上前）にある数字と台帳の値の一致",
    "sources/ と reviews/ と brief.md の中身",
]


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
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = ["id", "value", "unit", "definition", "period", "source_tag", "source",
                    "retrieved_at", "confidentiality", "replace_by"]
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            rep.error(path.name, f"台帳の列が足りません: {', '.join(missing)}")
            return ledger
        for line_no, row in enumerate(reader, start=2):
            row = {k: (v or "") for k, v in row.items() if k is not None}
            where = f"facts.csv:{line_no}"
            rid = row["id"].strip()
            if not re.fullmatch(ID_RE, rid):
                rep.error(where, f"ID の形式が不正です: {rid!r}")
                continue
            if rid in ledger:
                rep.error(where, f"{rid} が重複しています")
            ledger[rid] = row
            value = row["value"].strip()
            if value != "—" and parse_number(value) is None:
                rep.warn(where, f"{rid}: 値 {value!r} が数値でも — でもありません（比べられません）")
            tag = row["source_tag"].strip()
            src = row["source"].strip()
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
            if tag == "クライアント提供" and row["confidentiality"].strip() != "社外秘":
                rep.error(where, f"{rid}: クライアント提供の値は confidentiality=社外秘 にしてください")
            if row["confidentiality"].strip() not in CONFIDENTIALITY:
                rep.error(where, f"{rid}: confidentiality は 公開/社外秘 のいずれかです")
            if tag == "仮置き":
                rb = row["replace_by"].strip()
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
        if row["source_tag"].strip() == "推定":
            for ref in BARE_ID_RE.findall(row["source"]):
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


def collect_defined_ids(case: Path) -> set[str]:
    """Q・A・O・D のように数字を持たない ID の定義を、案件内の Markdown から集める。"""
    defined: set[str] = set()
    for path in case.rglob("*.md"):
        rel = path.relative_to(case).as_posix()
        if rel.split("/")[0] in EXEMPT_DIRS:
            continue
        for _, line in strip_code(path.read_text(encoding="utf-8-sig").splitlines()):
            m = DEF_LINE_RE.match(line)
            if m and m.group(1)[0] in NON_NUMERIC_PREFIXES:
                defined.add(m.group(1))
    return defined


def check_markdown(path: Path, rel: str, ledger: dict, rep: Report, strict: bool,
                   defined: set[str] | None = None, used: set[str] | None = None) -> int:
    count = 0
    defined = defined or set()
    lines = path.read_text(encoding="utf-8-sig").splitlines()
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
                        if rid[0] in NON_NUMERIC_PREFIXES and rid in defined:
                            continue
                        rep.error(where, f"[{rid}] が台帳にありません")
                        continue
                    if used is not None:
                        used.add(rid)
                    if strict and (ledger[rid]["confidentiality"] or "").strip() == "社外秘":
                        rep.error(where, f"[{rid}] は社外秘です。社外に出す成果物に載せられません")
                # 直前の数字と台帳の値を比べる（ID が 1 つのときだけ）
                if len(ids) == 1 and ids[0] in ledger:
                    before = cell[: m.start()]
                    prev_end = max((t.end() for t in tags if t.end() <= m.start()), default=0)
                    window = NOT_VALUE_RE.sub("", before[prev_end:])
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
    with path.open(encoding="utf-8-sig") as f:
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
            if "value" in row and (row["value"] or "").strip() not in ("", "—"):
                unit = (row.get("unit") or ledger[rid]["unit"] or "").strip()
                if not value_matches(row["value"], unit, ledger[rid]):
                    rep.error(where, f"{rid} の値 {row['value']}{unit} が台帳の値 {ledger[rid]['value']}{ledger[rid]['unit']} と一致しません")
            tag = (row.get("source_tag") or "").strip()
            if tag and tag != (ledger[rid]["source_tag"] or "").strip():
                rep.error(where, f"{rid} の出典タグ {tag} が台帳の {ledger[rid]['source_tag']} と一致しません")
    return count


def check_dependencies(used: set[str], ledger: dict, rep: Report) -> None:
    """deliverables/ が参照する値が、推定の計算式をたどって仮置きや — に行き着かないか。"""
    for rid in sorted(used):
        seen: set[str] = set()
        stack = [rid]
        weak: list[str] = []
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in ledger:
                continue
            seen.add(cur)
            row = ledger[cur]
            tag = (row["source_tag"] or "").strip()
            if tag == "仮置き":
                weak.append(f"{cur}（仮置き、期限 {row['replace_by'] or '—'}）")
            elif (row["value"] or "").strip() == "—":
                weak.append(f"{cur}（値が —）")
            if tag == "推定":
                stack += [r for r in BARE_ID_RE.findall(row["source"] or "") if r != cur]
        if weak:
            rep.warn(f"deliverables ({rid})", "仮置きか — に依存しています: " + "、".join(sorted(weak)))


# ---------- xlsx ----------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _text(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter() if _local(t.tag) == "t")


def _col_row(ref: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else ("", 0)


def read_xlsx(path: Path) -> dict[str, list[dict]]:
    """シート名 → セルの一覧（ref, row, col, type, value, has_formula）。"""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root if _local(si.tag) == "si"]
        rels: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
                target = r.get("Target", "")
                target = target.lstrip("/") if target.startswith("/") else "xl/" + target
                rels[r.get("Id", "")] = target
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets: dict[str, list[dict]] = {}
        for sheets_el in wb.iter():
            if _local(sheets_el.tag) != "sheet":
                continue
            rid = next((v for k, v in sheets_el.attrib.items() if _local(k) == "id"), "")
            target = rels.get(rid, "")
            if target not in names:
                continue
            cells = []
            for c in ET.fromstring(z.read(target)).iter():
                if _local(c.tag) != "c":
                    continue
                ref = c.get("r", "")
                col, row = _col_row(ref)
                ctype = c.get("t", "n")
                has_f = bool(_children(c, "f"))
                v_el = _children(c, "v")
                raw = v_el[0].text if v_el and v_el[0].text is not None else None
                if ctype == "s" and raw is not None:
                    value = shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
                elif ctype == "inlineStr":
                    is_el = _children(c, "is")
                    value = _text(is_el[0]) if is_el else ""
                else:
                    value = raw
                cells.append({"ref": ref, "col": col, "row": row, "type": ctype,
                              "value": value, "has_formula": has_f})
            sheets[sheets_el.get("name", "")] = cells
    return sheets


def check_xlsx(path: Path, rel: str, ledger: dict, rep: Report) -> int:
    """inputs シートと台帳の一致、計算シートの直打ちを点検する。戻り値は ID 参照の数。"""
    try:
        sheets = read_xlsx(path)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        rep.error(rel, f"xlsx を読めません: {e}")
        return 0
    count = 0
    if INPUT_SHEET not in sheets:
        rep.error(rel, f"{INPUT_SHEET} シートがありません（入力と計算を分けてください）")
    else:
        rows: dict[int, dict[str, dict]] = {}
        for c in sheets[INPUT_SHEET]:
            rows.setdefault(c["row"], {})[c["col"]] = c
        header_row = min(rows) if rows else 0
        header = {c["col"]: str(c["value"] or "").strip() for c in rows.get(header_row, {}).values()}
        col_of = {name: col for col, name in header.items()}
        if "id" not in col_of or "value" not in col_of:
            rep.error(f"{rel}!{INPUT_SHEET}", "見出し行に id と value の列がありません")
        else:
            for r in sorted(rows):
                if r == header_row:
                    continue
                cells = rows[r]
                get = lambda name: str((cells.get(col_of.get(name, ""), {}) or {}).get("value") or "").strip()
                rid = get("id")
                if not rid:
                    continue
                count += 1
                where = f"{rel}!{INPUT_SHEET}:{r}"
                if rid not in ledger:
                    rep.error(where, f"{rid} が台帳にありません")
                    continue
                value = get("value")
                unit = get("unit") or (ledger[rid]["unit"] or "").strip()
                if value not in ("", "—") and not value_matches(value, unit, ledger[rid]):
                    rep.error(where, f"{rid} の値 {value}{unit} が台帳の値 {ledger[rid]['value']}{ledger[rid]['unit']} と一致しません")
                tag = get("source_tag")
                if tag and tag != (ledger[rid]["source_tag"] or "").strip():
                    rep.error(where, f"{rid} の出典タグ {tag} が台帳の {ledger[rid]['source_tag']} と一致しません")
    for name, cells in sheets.items():
        if name == INPUT_SHEET:
            continue
        hard = [c["ref"] for c in cells
                if c["type"] == "n" and c["value"] not in (None, "") and not c["has_formula"]
                and c["row"] != 1]  # 1 行目は年度などの見出しとみなす
        if hard:
            shown = ", ".join(hard[:10]) + (f" ほか {len(hard) - 10} 件" if len(hard) > 10 else "")
            rep.error(f"{rel}!{name}", f"数式のない数値セル（直打ち）: {shown}。inputs シートを参照してください")
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_dir")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", help="レポートを書き出す Markdown のパス")
    ap.add_argument("--strict", action="store_true", help="警告もエラーとして数える")
    args = ap.parse_args()

    case = Path(args.case_dir)
    today = dt.date.fromisoformat(args.today)
    rep = Report()
    ledger_path = case / "facts" / "facts.csv"
    ledger = load_ledger(ledger_path, today, rep)
    defined = collect_defined_ids(case)

    refs = 0
    files = 0
    used_in_deliverables: set[str] = set()
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
            strict = top == STRICT_DIR
            refs += check_markdown(path, rel, ledger, rep, strict=strict, defined=defined,
                                   used=used_in_deliverables if strict else None)
        elif path.suffix == ".csv":
            files += 1
            refs += check_csv(path, rel, ledger, rep)
        elif PurePosixPath(rel) == XLSX_PATH:
            files += 1
            refs += check_xlsx(path, rel, ledger, rep)
    check_dependencies(used_in_deliverables, ledger, rep)

    if args.strict:
        rep.errors += [(w, f"（--strict）{m}") for w, m in rep.warnings]
        rep.warnings = []

    by_tag: dict[str, int] = {}
    for row in ledger.values():
        by_tag[row["source_tag"]] = by_tag.get(row["source_tag"], 0) + 1

    out = [
        "# number-audit レポート",
        "",
        f"- 点検日: {today.isoformat()}" + ("（--strict: 警告もエラーとして数える）" if args.strict else ""),
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
        out += ["## 警告（作業中は許す。デッキに載せる前に ID を付けるか、仮置きと — を差し替える）", "", "| 場所 | 内容 |", "|------|------|"]
        out += [f"| {w} | {m} |" for w, m in rep.warnings]
        out.append("")
    out += ["## このスクリプトが見ないこと（人が確かめる）", ""]
    out += [f"- {s}" for s in NOT_CHECKED]
    out.append("")
    text = "\n".join(out)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
