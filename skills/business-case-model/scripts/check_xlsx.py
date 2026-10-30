#!/usr/bin/env python3
"""build_model.py が書いた business-case.xlsx を点検する。

点検すること:
  1. xlsx として必要な部品（[Content_Types].xml、rels、workbook.xml、styles.xml、各シート）が揃い、XML として読めるか
  2. calc シートに数式のない数値セル（直打ち）がないか
  3. calc シートの数式に、1 以外の数値の直打ちがないか（(1+g) の 1 だけを認める）
  4. calc シートの数式が inputs と calc 以外のシートを参照していないか
  5. 数式を Python で計算し直した値が、キャッシュ値と model.csv に一致するか（数式そのものの検算）
  6. LibreOffice（soffice）があれば、キャッシュ値を消した写しを再計算させ、結果が一致するか（--soffice）

使い方:
  python3 check_xlsx.py --case case
  python3 check_xlsx.py --case case --soffice

終了コード: 問題が 1 件以上あれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED = ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml"]
TOKEN = re.compile(
    r"(?P<range>(?:(?P<rs>\w+)!)?\$?(?P<c1>[A-Z]+)\$?(?P<r1>\d+):\$?(?P<c2>[A-Z]+)\$?(?P<r2>\d+))"
    r"|(?P<ref>(?:(?P<s>\w+)!)?\$?(?P<c>[A-Z]+)\$?(?P<r>\d+))"
    r"|(?P<func>SUM|AVERAGE)\("
    r"|(?P<num>\d+(?:\.\d+)?)"
    r"|(?P<op>[-+*/(),%])"
    r"|(?P<sp>\s+)"
)


def col_num(c: str) -> int:
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def col_name(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_book(path: Path) -> tuple[dict[str, dict[str, dict]], list[str], dict[str, str]]:
    problems: list[str] = []
    sheets: dict[str, dict[str, dict]] = {}
    targets: dict[str, str] = {}
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            problems.append(f"zip の中身が壊れています: {bad}")
        names = set(z.namelist())
        for n in REQUIRED:
            if n not in names:
                problems.append(f"部品がありません: {n}")
        for n in names:
            if n.endswith(".xml") or n.endswith(".rels"):
                try:
                    ET.fromstring(z.read(n))
                except ET.ParseError as e:
                    problems.append(f"{n} を XML として読めません: {e}")
        ct = z.read("[Content_Types].xml").decode("utf-8")
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for sh in wb.find("m:sheets", NS):
            rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = "xl/" + rels.get(rid, "")
            targets[sh.get("name")] = target
            if target not in names:
                problems.append(f"シート {sh.get('name')} の実体 {target} がありません")
                continue
            if f'PartName="/{target}"' not in ct:
                problems.append(f"[Content_Types].xml に {target} の登録がありません")
            cells: dict[str, dict] = {}
            for c in ET.fromstring(z.read(target)).iter(f"{{{NS['m']}}}c"):
                f = c.find("m:f", NS)
                v = c.find("m:v", NS)
                t = c.get("t", "n")
                cells[c.get("r")] = {
                    "f": f.text if f is not None else None,
                    "v": float(v.text) if (v is not None and t == "n" and v.text) else None,
                    "t": t,
                    "s": "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t")),
                }
            sheets[sh.get("name")] = cells
        if "fullCalcOnLoad" not in z.read("xl/workbook.xml").decode("utf-8"):
            problems.append("workbook.xml に fullCalcOnLoad がありません（開いたときに再計算されない）")
    return sheets, problems, targets


class Evaluator:
    def __init__(self, sheets: dict[str, dict[str, dict]], home: str) -> None:
        self.sheets, self.home, self.cache = sheets, home, {}

    def value(self, sheet: str, ref: str) -> float:
        key = (sheet, ref)
        if key in self.cache:
            return self.cache[key]
        cell = self.sheets.get(sheet, {}).get(ref)
        if cell is None or (cell["f"] is None and cell["v"] is None):
            v = 0.0  # 空セルは 0
        elif cell["f"] is None:
            v = cell["v"]
        else:
            v = self.eval(cell["f"], sheet)
        self.cache[key] = v
        return v

    def rng(self, sheet: str, a: str, b: str) -> list[float]:
        ca, ra = re.fullmatch(r"([A-Z]+)(\d+)", a).groups()
        cb, rb = re.fullmatch(r"([A-Z]+)(\d+)", b).groups()
        return [self.value(sheet, f"{col_name(c)}{r}")
                for c in range(col_num(ca), col_num(cb) + 1) for r in range(int(ra), int(rb) + 1)]

    def eval(self, formula: str, sheet: str) -> float:
        py = translate(formula)
        env = {"V": lambda s, r: self.value(s or sheet, r), "R": lambda s, a, b: self.rng(s or sheet, a, b),
               "_sum": lambda *xs: sum(sum(x) if isinstance(x, list) else x for x in xs),
               "_avg": lambda *xs: (lambda fl: sum(fl) / len(fl))([y for x in xs for y in (x if isinstance(x, list) else [x])])}
        return float(eval(py, {"__builtins__": {}}, env))  # noqa: S307 （自前で翻訳した式だけを評価する）


def translate(formula: str) -> str:
    out, pos = [], 0
    while pos < len(formula):
        m = TOKEN.match(formula, pos)
        if not m:
            raise ValueError(f"読めない数式: {formula!r}（位置 {pos}）")
        pos = m.end()
        if m["range"]:
            out.append(f"R({m['rs']!r}, '{m['c1']}{m['r1']}', '{m['c2']}{m['r2']}')")
        elif m["ref"]:
            out.append(f"V({m['s']!r}, '{m['c']}{m['r']}')")
        elif m["func"]:
            out.append("_sum(" if m["func"] == "SUM" else "_avg(")
        elif m["num"]:
            out.append(m["num"])
        elif m["op"]:
            out.append("/100" if m["op"] == "%" else m["op"])
    return "".join(out)


def literals(formula: str) -> list[str]:
    found = []
    pos = 0
    while pos < len(formula):
        m = TOKEN.match(formula, pos)
        if not m:
            break
        pos = m.end()
        if m["num"]:
            found.append(m["num"])
    return found


def foreign_sheets(formula: str) -> set[str]:
    return {s for s in re.findall(r"(\w+)!", formula)} - {"inputs", "calc"}


def load_model_csv(path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    out = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[(r["item"], r["fiscal_year"])] = (r["value"], r["unit"])
    return out


def find_soffice() -> str | None:
    for c in ("soffice", "libreoffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        p = shutil.which(c) or (c if Path(c).exists() else None)
        if p:
            return p
    return None


def soffice_recalc(xlsx: Path, calc_target: str, sheet_index: int) -> tuple[dict[str, float] | None, str]:
    exe = find_soffice()
    if not exe:
        return None, "soffice が見つからない。表計算ソフトでの再計算は確かめていない"
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        blank = tdp / "nocache.xlsx"
        with zipfile.ZipFile(xlsx) as zin, zipfile.ZipFile(blank, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == calc_target:
                    data = re.sub(rb"(</f>)<v>[^<]*</v>", rb"\1", data)  # 数式セルのキャッシュ値を消す
                zout.writestr(item, data)
        filt = f"csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,false,false,false,false,{sheet_index}"
        cmd = [exe, "--headless", f"-env:UserInstallation=file://{tdp}/profile", "--convert-to", filt,
               "--outdir", str(tdp / "out"), str(blank)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        except (subprocess.SubprocessError, OSError) as e:
            return None, f"soffice の実行に失敗した（{e}）。表計算ソフトでの再計算は確かめていない"
        outs = list((tdp / "out").glob("*.csv"))
        if not outs:
            return None, "soffice が CSV を書かなかった。表計算ソフトでの再計算は確かめていない"
        vals: dict[str, float] = {}
        with outs[0].open(encoding="utf-8") as f:
            for ri, row in enumerate(csv.reader(f), start=1):
                for ci, cell in enumerate(row, start=1):
                    t = cell.strip()
                    pct = t.endswith("%")
                    try:
                        x = float(t.rstrip("%").replace(",", ""))
                    except ValueError:
                        continue
                    vals[f"{col_name(ci)}{ri}"] = x / 100 if pct else x
        return vals, f"soffice（{exe}）でキャッシュ値を消した写しを再計算させた"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="案件フォルダ。<case>/model/business-case.xlsx を点検する")
    ap.add_argument("--xlsx", help="xlsx のパス（--case より優先）")
    ap.add_argument("--soffice", action="store_true", help="LibreOffice で再計算して照合する")
    a = ap.parse_args()
    if not (a.case or a.xlsx):
        ap.error("--case か --xlsx を指定する")
    xlsx = Path(a.xlsx) if a.xlsx else Path(a.case) / "model" / "business-case.xlsx"
    model_csv = xlsx.parent / "model.csv"
    problems: list[str] = []
    sheets, p, targets = read_book(xlsx)
    problems += p
    if "inputs" not in sheets or "calc" not in sheets:
        problems.append("inputs と calc の両方のシートが要る")
        print("\n".join(f"- {x}" for x in problems))
        return 1
    calc = sheets["calc"]
    n_formula = 0
    for ref, c in calc.items():
        if c["f"] is None:
            if c["t"] == "n" and c["v"] is not None:
                problems.append(f"calc!{ref}: 数式のない数値（直打ち）")
            continue
        n_formula += 1
        bad = [x for x in literals(c["f"]) if x != "1"]
        if bad:
            problems.append(f"calc!{ref}: 数式に数値の直打ち {', '.join(bad)}（{c['f']}）")
        fs = foreign_sheets(c["f"])
        if fs:
            problems.append(f"calc!{ref}: inputs/calc 以外のシートを参照 {', '.join(sorted(fs))}")

    ev = Evaluator(sheets, "calc")
    mism_cache = 0
    recomputed: dict[str, float] = {}
    for ref, c in calc.items():
        if c["f"] is None:
            continue
        v = ev.value("calc", ref)
        recomputed[ref] = v
        if c["v"] is not None and abs(v - c["v"]) > 1e-6 * max(1.0, abs(v)):
            mism_cache += 1
            problems.append(f"calc!{ref}: 数式の再計算 {v:.4f} とキャッシュ値 {c['v']:.4f} が違う")

    # model.csv との照合（行ラベルと年度の見出しで突き合わせる）
    model = load_model_csv(model_csv)
    labels = {int(re.sub(r"\D", "", r)): c["s"] for r, c in calc.items() if r.startswith("A")}
    years = {re.match(r"[A-Z]+", r).group(): re.match(r"FY\d{4}", c["s"]).group()
             for r, c in calc.items() if re.fullmatch(r"[A-Z]+1", r) and re.match(r"FY\d{4}", c["s"])}
    n_cmp = 0
    for ref, v in recomputed.items():
        cl, rw = re.fullmatch(r"([A-Z]+)(\d+)", ref).groups()
        key = (labels.get(int(rw), ""), years.get(cl, ""))
        if key not in model:
            continue
        shown, unit = model[key]
        x = v * 100 if unit == "%" else v
        dec = len(shown.split(".")[1]) if "." in shown else 0
        n_cmp += 1
        if abs(round(x, dec) - float(shown)) > 0.5 * 10 ** (-dec) + 1e-9:
            problems.append(f"calc!{ref}（{key[0]} {key[1]}）: 数式の値 {x:.4f} が model.csv の {shown} と違う")

    print("# business-case.xlsx の点検\n")
    print(f"- ファイル: {xlsx}")
    print(f"- calc シートの数式: {n_formula} 件。Python で再計算してキャッシュ値と照合、model.csv の {n_cmp} 件と照合")
    if a.soffice:
        sheet_index = list(sheets).index("calc") + 1
        vals, msg = soffice_recalc(xlsx, targets["calc"], sheet_index)
        print(f"- {msg}")
        if vals is not None:
            n_ok = 0
            for ref, v in recomputed.items():
                got = vals.get(ref)
                if got is None:
                    problems.append(f"soffice: calc!{ref} の値が出力にない（再計算されていない可能性）")
                elif abs(got - v) > 1e-6 * max(1.0, abs(v)):
                    problems.append(f"soffice: calc!{ref} = {got} が Python の再計算 {v} と違う")
                else:
                    n_ok += 1
            print(f"- soffice の再計算と一致: {n_ok} / {len(recomputed)} 件")
    else:
        print("- 表計算ソフトでの再計算は確かめていない（--soffice で確かめる）")
    if problems:
        print(f"\n## 問題 {len(problems)} 件\n")
        print("\n".join(f"- {x}" for x in problems))
        return 1
    print("\n問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
