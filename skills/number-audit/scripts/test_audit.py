#!/usr/bin/env python3
"""audit.py の自己テスト（標準ライブラリの unittest だけで動く）。

使い方:
  python3 skills/number-audit/scripts/test_audit.py
  AUDIT_FIXTURE_DIR=/path/to/tmp python3 ...   # 一時フィクスチャの置き場所（既定は OS の一時フォルダ）

案件フォルダは使わない。テストごとに一時フォルダへ小さな案件を作って点検する。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audit", HERE / "audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

HEADER = "id,value,unit,definition,period,source_tag,source,retrieved_at,confidentiality,replace_by"
BASE_ROWS = [
    "T-001,5000,億円,連結売上目標,FY2030,公開,決算説明会 2026-05-15 p.12,2026-10-20,公開,",
    "F-012,200000,百万円,連結売上高,FY2025,公開,有価証券報告書 FY2025 p.45,2026-10-20,公開,",
    "F-031,5.0,%,対象市場の年成長率,FY2025-FY2030,仮置き,—,2026-10-22,公開,2026-11-05",
    "S-001,2553,億円,FY2030 成り行き売上,FY2030,推定,F-012 × (1+F-031)^5,2026-10-22,公開,",
    "F-090,120,億円,社内計画の設備投資,FY2026,クライアント提供,経営会議資料 p.3,2026-10-22,社外秘,",
]
TODAY = "2026-10-30"
FIXTURE_ROOT = Path(os.environ.get("AUDIT_FIXTURE_DIR", tempfile.gettempdir()))


class CaseDir:
    """一時の案件フォルダ。"""

    def __init__(self, base: Path, rows: list[str] | None = None) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="case-", dir=base))
        self.write("facts/facts.csv", "\n".join([HEADER] + (BASE_ROWS if rows is None else rows)) + "\n")

    def write(self, rel: str, text: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run(self, *extra: str) -> tuple[int, str]:
        argv = ["audit.py", str(self.root), "--today", TODAY, *extra]
        buf = io.StringIO()
        old = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(buf):
                code = audit.main()
        finally:
            sys.argv = old
        return code, buf.getvalue()


def section(report: str, title: str) -> str:
    """レポートから見出し title の節だけを取り出す。"""
    if title not in report:
        return ""
    body = report.split(title, 1)[1]
    return body.split("\n## ", 1)[0]


def errors(report: str) -> str:
    return section(report, "## エラー")


def warnings(report: str) -> str:
    return section(report, "## 警告")


def make_xlsx(path: Path, sheets: dict[str, str], shared: list[str] | None) -> None:
    """最小の xlsx を手で組む。sheets はシート名 → <sheetData> の中身。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        sheet_xml, rel_xml = [], []
        # 名前の順とファイル番号をわざとずらす（sheet1.xml = inputs と決めつけないことの確認）
        for i, name in enumerate(reversed(list(sheets)), start=1):
            rid = f"rId{i}"
            sheet_xml.append(f'<sheet name="{name}" sheetId="{i}" r:id="{rid}"/>')
            rel_xml.append(f'<Relationship Id="{rid}" Type="worksheet" Target="worksheets/sheet{i}.xml"/>')
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                       f'<?xml version="1.0"?><worksheet {ns}><sheetData>{sheets[name]}</sheetData></worksheet>')
        z.writestr("xl/workbook.xml",
                   f'<?xml version="1.0"?><workbook {ns} {rns}><sheets>{"".join(sheet_xml)}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(rel_xml) + "</Relationships>")
        if shared is not None:
            sis = "".join(f"<si><t>{s}</t></si>" for s in shared)
            z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0"?><sst {ns}>{sis}</sst>')


def s(ref: str, idx: int) -> str:
    return f'<c r="{ref}" t="s"><v>{idx}</v></c>'


def n(ref: str, v: str) -> str:
    return f'<c r="{ref}"><v>{v}</v></c>'


def f(ref: str, formula: str, v: str) -> str:
    return f'<c r="{ref}"><f>{formula}</f><v>{v}</v></c>'


def istr(ref: str, text: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


class AuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
        cls.base = Path(tempfile.mkdtemp(prefix="audit-test-", dir=FIXTURE_ROOT))

    def case(self, rows: list[str] | None = None) -> CaseDir:
        return CaseDir(self.base, rows)

    # ---- 台帳 ----
    def test_clean_case_passes(self):
        c = self.case()
        c.write("03-gap-bridge.md", "連結売上 2,000 億円 [F-012] から成り行き 2,553 億円 [S-001] へ。\n")
        code, out = c.run()
        self.assertEqual(code, 0, out)
        self.assertIn("エラー: 0 件", out)
        self.assertIn("このスクリプトが見ないこと", out)

    def test_missing_ledger(self):
        c = self.case()
        (c.root / "facts/facts.csv").unlink()
        code, out = c.run()
        self.assertEqual(code, 1)
        self.assertIn("ファクト台帳がありません", out)

    def test_missing_columns(self):
        c = self.case()
        c.write("facts/facts.csv", "id,value\nF-001,1\n")
        code, out = c.run()
        self.assertEqual(code, 1)
        self.assertIn("台帳の列が足りません", out)

    def test_bad_tag_id_and_duplicates(self):
        c = self.case(BASE_ROWS + [
            "F-100,1,%,x,FY2025,ネット,記事,2026-10-20,公開,",
            "X-1,1,%,x,FY2025,公開,資料,2026-10-20,公開,",
            "F-012,200000,百万円,重複,FY2025,公開,資料,2026-10-20,公開,",
            "F-101,1,%,x,FY2025,公開,—,2026-10-20,公開,",
            "F-102,1,%,x,FY2025,公開,資料,2026-10-20,秘密,",
            "F-103,1,%,x,FY2025,クライアント提供,資料,2026-10-20,公開,",
        ])
        code, out = c.run()
        e = errors(out)
        self.assertEqual(code, 1)
        self.assertIn("出典タグ 'ネット'", e)
        self.assertIn("ID の形式が不正です: 'X-1'", e)
        self.assertIn("F-012 が重複しています", e)
        self.assertIn("F-101: 公開 の値に資料名がありません", e)
        self.assertIn("F-102: confidentiality", e)
        self.assertIn("F-103: クライアント提供の値は confidentiality=社外秘", e)

    def test_placeholder_deadline(self):
        rows = [r for r in BASE_ROWS if not r.startswith("F-031")] + [
            "F-031,5.0,%,対象市場の年成長率,FY2025-FY2030,仮置き,—,2026-10-22,公開,2026-10-01",
            "F-032,1,%,x,FY2025,仮置き,—,2026-10-22,公開,",
            "F-033,1,%,x,FY2025,仮置き,—,2026-10-22,公開,11/05",
        ]
        code, out = self.case(rows).run()
        e = errors(out)
        self.assertIn("F-031: 仮置きの差し替え期限 2026-10-01 を過ぎています", e)
        self.assertIn("F-032: 仮置きに差し替え期限 replace_by がありません", e)
        self.assertIn("F-033: replace_by の日付が不正です", e)

    def test_estimate_formula(self):
        code, out = self.case(BASE_ROWS + [
            "S-002,1,億円,x,FY2030,推定,F-999 × 2,2026-10-22,公開,",
            "S-003,1,億円,x,FY2030,推定,—,2026-10-22,公開,",
            "S-004,1,億円,x,FY2030,推定,S-004 + 1,2026-10-22,公開,",
        ]).run()
        e = errors(out)
        self.assertIn("計算式が参照する F-999 が台帳にありません", e)
        self.assertIn("S-003: 推定の値に計算式がありません", e)
        self.assertIn("S-004: 計算式が自分自身を参照しています", e)

    def test_non_numeric_value_warns(self):
        code, out = self.case(BASE_ROWS + ["F-110,約2000,億円,x,FY2025,公開,資料,2026-10-20,公開,"]).run()
        self.assertIn("F-110: 値 '約2000' が数値でも — でもありません", warnings(out))

    def test_bom_ledger(self):
        c = self.case()
        p = c.root / "facts/facts.csv"
        p.write_bytes("﻿".encode("utf-8") + p.read_bytes())
        c.write("03.md", "売上 2,000 億円 [F-012]。\n")
        code, out = c.run()
        self.assertEqual(code, 0, out)

    # ---- Markdown ----
    def test_unknown_id(self):
        c = self.case()
        c.write("03.md", "売上 2,000 億円 [F-777]。\n")
        code, out = c.run()
        self.assertIn("[F-777] が台帳にありません", errors(out))

    def test_value_mismatch_and_unit_conversion(self):
        c = self.case()
        c.write("03.md", "\n".join([
            "売上 2,000 億円 [F-012]。",       # 百万円 → 億円 の換算で一致
            "売上 200,000 百万円 [F-012]。",   # 同じ単位
            "売上 0.2 兆円 [F-012]。",         # 兆円
            "売上 2,100 億円 [F-012]。",       # 不一致
            "市場は年 5% [F-031] で伸びる。",  # 表示の丸め（5.0 と 5）
            "| 成り行き | 2,553 億円 [S-001] |",
        ]) + "\n")
        code, out = c.run()
        e = errors(out)
        self.assertEqual(e.count("一致しません"), 1, out)
        self.assertIn("2,100億円 [F-012] が台帳の値 200000百万円 と一致しません", e)

    def test_fiscal_year_before_id_is_not_compared(self):
        c = self.case()
        c.write("03.md", "成り行きは FY2030 [S-001] の値を使う。期限は 2026-11-05 [F-031]。\n")
        code, out = c.run()
        self.assertNotIn("一致しません", out)

    def test_multi_id_tag(self):
        c = self.case()
        c.write("03.md", "成り行きの根拠 [F-012, F-031]、目標 [T-001、F-777]。\n")
        code, out = c.run()
        e = errors(out)
        self.assertIn("[F-777] が台帳にありません", e)
        self.assertNotIn("[F-012] が台帳", e)

    def test_unsourced_number_warning_vs_deliverables_error(self):
        c = self.case()
        c.write("03.md", "シェア獲得は年 0.8% にとどまる。\n")
        c.write("deliverables/storyline.md", "シェア獲得は年 0.8% にとどまる。\n")
        code, out = c.run()
        self.assertEqual(code, 1)
        self.assertIn("deliverables/storyline.md:1 | 出典 ID のない数字: 0.8%", errors(out))
        self.assertIn("03.md:1 | 出典 ID のない数字: 0.8%", warnings(out))

    def test_years_and_code_are_ignored(self):
        c = self.case()
        c.write("deliverables/storyline.md", "\n".join([
            "FY2030 までに、2030 年度の目標を置く。",
            "`5%` はコードの中なので見ない。",
            "```",
            "20.1% もコードブロックの中",
            "```",
        ]) + "\n")
        code, out = c.run()
        self.assertEqual(code, 0, out)

    def test_confidential_in_deliverables(self):
        c = self.case()
        c.write("06-capital.md", "設備投資 120 億円 [F-090]。\n")
        c.write("deliverables/storyline.md", "設備投資 120 億円 [F-090]。\n")
        code, out = c.run()
        e = errors(out)
        self.assertIn("deliverables/storyline.md:1 | [F-090] は社外秘です", e)
        self.assertNotIn("06-capital.md:1 | [F-090] は社外秘", e)

    def test_exempt_dirs_brief_and_out(self):
        c = self.case()
        c.write("sources/midterm.md", "売上 9,999 億円 [F-777]。\n")
        c.write("reviews/question-time.md", "ROE 8% は？\n")
        c.write("brief.md", "連結売上 2,000 億円\n")
        out_path = c.root / "notes-audit.md"
        out_path.write_text("前回のレポート 12% [F-888]\n", encoding="utf-8")
        code, out = c.run("--out", str(out_path))
        self.assertEqual(code, 0, out)
        self.assertIn("# number-audit レポート", out_path.read_text(encoding="utf-8"))

    def test_out_into_missing_reviews_dir(self):
        c = self.case()
        out_path = c.root / "reviews" / "number-audit.md"
        self.assertFalse(out_path.parent.exists())
        code, out = c.run("--out", str(out_path))
        self.assertEqual(code, 0, out)
        self.assertTrue(out_path.exists())
        code, out = c.run("--out", str(out_path))  # 2 回目: レポート自身は点検されない
        self.assertEqual(code, 0, out)
        self.assertIn("点検したファイル: 0 件", out)

    def test_non_numeric_ids_defined_in_case(self):
        c = self.case()
        c.write("decisions.md", "## D-001 目標の解釈（2026-10-31）\n- 根拠: [T-001]\n")
        c.write("01-issue-tree.md", "| Q-003 | 何で伸びるか |\n- A-003 自動車が牽引する\n")
        c.write("deliverables/storyline.md", "前に出すレーン: レーン2 [D-001]。論点 [Q-003] と仮説 [A-003]、未定義 [O-009]。\n")
        code, out = c.run()
        e = errors(out)
        self.assertNotIn("[D-001]", e)
        self.assertNotIn("[Q-003]", e)
        self.assertNotIn("[A-003]", e)
        self.assertIn("[O-009] が台帳にありません", e)

    def test_numeric_prefix_must_be_in_ledger_even_if_defined(self):
        c = self.case()
        c.write("05-initiatives.md", "## I-001 EV 熱マネジメントの拡販\n")
        c.write("deliverables/storyline.md", "打ち手 [I-001] で埋める。\n")
        code, out = c.run()
        self.assertIn("[I-001] が台帳にありません", errors(out))

    def test_dependency_on_placeholder_in_deliverables(self):
        c = self.case()
        c.write("deliverables/storyline.md", "成り行きは 2,553 億円 [S-001] にとどまる。\n")
        code, out = c.run()
        self.assertEqual(code, 0, out)
        self.assertIn("deliverables (S-001) | 仮置きか — に依存しています: F-031", warnings(out))

    # ---- CSV ----
    def test_csv_ids_values_units_and_tags(self):
        c = self.case()
        c.write("facts/financials.csv", "\n".join([
            "id,fiscal_year,item,segment,value,unit,basis,source,note",
            "F-012,FY2025,売上高,連結,2000,億円,日本基準,有報,",     # 換算で一致
            "F-012,FY2025,売上高,連結,2100,億円,日本基準,有報,",     # 不一致
            "F-555,FY2025,売上高,連結,1,億円,日本基準,有報,",        # 台帳にない
            "F-031,FY2025,成長率,連結,—,%,—,—,",                      # — は比べない
        ]) + "\n")
        c.write("model/inputs.csv", "id,label,value,unit,source_tag\nF-031,市場成長率,5,%,公開\n")
        c.write("other.csv", "name,value\nx,1\n")  # id 列のない CSV は見ない
        code, out = c.run()
        e = errors(out)
        self.assertIn("financials.csv:3 | F-012 の値 2100億円", e)
        self.assertNotIn("financials.csv:2 |", e)
        self.assertIn("F-555 が台帳にありません", e)
        self.assertNotIn("financials.csv:5", e)
        self.assertIn("model/inputs.csv:2 | F-031 の出典タグ 公開 が台帳の 仮置き と一致しません", e)

    def test_csv_without_unit_uses_ledger_unit(self):
        c = self.case()
        c.write("model/inputs.csv", "id,value\nF-012,200000\n")
        code, out = c.run()
        self.assertEqual(code, 0, out)

    # ---- xlsx ----
    def test_xlsx_inputs_and_hardcoded(self):
        c = self.case()
        shared = ["id", "label", "value", "unit", "source_tag", "F-012", "連結売上", "百万円", "公開",
                  "F-031", "市場成長率", "%", "F-404", "年度"]
        inputs = (
            f'<row r="1">{s("A1",0)}{s("B1",1)}{s("C1",2)}{s("D1",3)}{s("E1",4)}</row>'
            f'<row r="2">{s("A2",5)}{s("B2",6)}{n("C2","200000")}{s("D2",7)}{s("E2",8)}</row>'
            f'<row r="3">{s("A3",9)}{s("B3",10)}{n("C3","6")}{s("D3",11)}{s("E3",8)}</row>'
            f'<row r="4">{s("A4",12)}{s("B4",10)}{n("C4","1")}{s("D4",11)}{s("E4",8)}</row>'
        )
        calc = (
            f'<row r="1">{s("A1",13)}{n("B1","2026")}{n("C1","2027")}</row>'
            f'<row r="2">{istr("A2","売上")}{f("B2","inputs!C2*(1+inputs!C3/100)","210000")}'
            f'<c r="C2"><f t="shared" si="0"/><v>220500</v></c></row>'
            f'<row r="3">{istr("A3","投資")}{n("B3","120")}{f("C3","B3","120")}</row>'
        )
        make_xlsx(c.root / "model/business-case.xlsx", {"inputs": inputs, "calc": calc}, shared)
        code, out = c.run()
        e = errors(out)
        self.assertNotIn("inputs:2", e)
        self.assertIn("inputs:3 | F-031 の値 6% が台帳の値 5.0% と一致しません", e)
        self.assertIn("inputs:3 | F-031 の出典タグ 公開 が台帳の 仮置き と一致しません", e)
        self.assertIn("inputs:4 | F-404 が台帳にありません", e)
        self.assertIn("calc | 数式のない数値セル（直打ち）: B3。", e)
        self.assertNotIn("B1", e)   # 1 行目は見出し
        self.assertNotIn("C2", e)   # 共有数式の従属セル

    def test_xlsx_without_shared_strings_and_missing_inputs(self):
        c = self.case()
        calc = f'<row r="2">{istr("A2","売上")}{n("B2","2000")}</row>'
        make_xlsx(c.root / "model/business-case.xlsx", {"calc": calc}, None)
        code, out = c.run()
        e = errors(out)
        self.assertIn("inputs シートがありません", e)
        self.assertIn("calc | 数式のない数値セル（直打ち）: B2", e)

    def test_xlsx_inline_inputs_ok(self):
        c = self.case()
        inputs = (
            f'<row r="1">{istr("A1","id")}{istr("B1","value")}{istr("C1","unit")}</row>'
            f'<row r="2">{istr("A2","F-012")}{n("B2","2000")}{istr("C2","億円")}</row>'
        )
        make_xlsx(c.root / "model/business-case.xlsx", {"inputs": inputs}, None)
        code, out = c.run()
        self.assertEqual(code, 0, out)

    def test_broken_xlsx(self):
        c = self.case()
        c.write("model/business-case.xlsx", "not a zip")
        code, out = c.run()
        self.assertIn("xlsx を読めません", errors(out))

    # ---- --strict ----
    def test_strict_promotes_warnings(self):
        c = self.case()
        c.write("03.md", "シェア獲得は年 0.8% にとどまる。\n")
        code, _ = c.run()
        self.assertEqual(code, 0)
        code, out = c.run("--strict")
        self.assertEqual(code, 1)
        self.assertIn("（--strict）出典 ID のない数字: 0.8%", errors(out))
        self.assertNotIn("## 警告", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
