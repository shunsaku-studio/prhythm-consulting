#!/usr/bin/env python3
"""outline_check.py の自己テスト（標準ライブラリの unittest だけで動く）。

使い方:
  python3 skills/storyline/scripts/test_outline_check.py

フィクスチャの数字は説明用の値で、案件の結論ではない。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("outline_check", HERE / "outline_check.py")
oc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oc)
AUDIT = HERE.parent.parent / "number-audit" / "scripts" / "audit.py"
FIXTURE_ROOT = Path(os.environ.get("AUDIT_FIXTURE_DIR", tempfile.gettempdir()))

GOOD = """# ストーリーライン — テスト工業

## 統治メッセージ

5,000 億円 [T-001] には成り行きとの差 2,447 億円 [G-001] を M&A と市場の選び直しで埋める道筋が要る。

- 前に出すレーン: レーン2 [D-007]

## レーン2: 中計の外側の道筋 — ベースレートと資本の制約から見る

### 一言で

5,000 億円 [T-001] には成り行きとの差 2,447 億円 [G-001] を M&A と市場の選び直しで埋める道筋が要る。

### ピラミッド

- 主張: 一言でと同じ
  - 根拠1: 成り行きでは目標の半分にとどまる。
    - 事実: 成り行き 2,553 億円 [S-001]
  - 根拠2: シェア獲得だけで埋めるのは過去の例から外れる。
    - 事実: シェア獲得の平均は年 0.8% [F-201]
  - 根拠3: 買収の原資は借入余力の範囲で手当てできる。
    - 事実: 借入余力 [C-001]

### ゴーストデッキ

1. 5,000 億円 [T-001] には差 2,447 億円 [G-001] を中計の外側の道筋で埋める必要がある。
   - 根拠: [T-001] [G-001]
2. 市場が伸びても成り行きは 2,553 億円 [S-001] にとどまる。
3. シェア獲得で埋めるには年 5.9pt [G-002] が要り、平均の 0.8% [F-201] から大きく外れる。

## レーン1: 中計に則る — 目標に届くにはこれだけの打ち手が要る

### 一言で

中計の重点施策だけで 5,000 億円 [T-001] に届くには差 2,447 億円 [G-001] を埋める打ち手が要る。

### ピラミッド

- 主張: 一言でと同じ
  - 根拠1: 差の大半は自動車部品の外で生まれる。
    - 事実: 差 2,447 億円 [G-001]
  - 根拠2: 重点施策の積み上げでは差が残る。
    - 事実: 施策の積み上げ [I-001]

### ゴーストデッキ

1. 中計の重点施策だけで目標 [T-001] に届くには差 2,447 億円 [G-001] を埋める打ち手が要る。
2. 重点施策を満額で積んでも差の一部が残る [I-001]。
3. 残りを埋めるには買収か市場の選び直しを足すしかない [O-001]。

## 前提と未確認事項

- 前提: 市場成長率は仮置き [F-031]
"""

LEDGER = """id,value,unit,definition,period,source_tag,source,retrieved_at,confidentiality,replace_by
T-001,5000,億円,連結売上目標,FY2030,公開,決算説明会 p.12,2026-10-20,公開,
F-012,2000,億円,連結売上高,FY2025,公開,有報 p.45,2026-10-20,公開,
F-031,5.0,%,市場成長率,FY2025-FY2030,仮置き,—,2026-10-22,公開,2026-11-05
S-001,2553,億円,成り行き売上,FY2030,推定,F-012 × (1+F-031)^5,2026-10-22,公開,
G-001,2447,億円,ギャップ,FY2030,推定,T-001 − S-001,2026-10-22,公開,
G-002,5.9,pt,シェア由来の必要成長,FY2025-FY2030,推定,G-001 と F-012 から,2026-10-22,公開,
F-201,0.8,%,シェア獲得による成長の平均,—,公開,McKinsey 2017-08,2026-10-22,公開,
C-001,—,億円,借入余力,FY2025,推定,F-012 から,2026-10-22,公開,
I-001,—,億円,重点施策の積み上げ,FY2030,推定,F-012 から,2026-10-22,公開,
"""


def run(text: str, *extra: str) -> tuple[int, str]:
    d = Path(tempfile.mkdtemp(prefix="outline-", dir=FIXTURE_ROOT))
    p = d / "storyline.md"
    p.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["outline_check.py", str(p), *extra]
    try:
        with contextlib.redirect_stdout(buf):
            code = oc.main()
    finally:
        sys.argv = old
    return code, buf.getvalue()


def errors(out: str) -> str:
    return out.split("## エラー", 1)[1].split("## 警告")[0] if "## エラー" in out else ""


def warnings(out: str) -> str:
    return out.split("## 警告", 1)[1] if "## 警告" in out else ""


class OutlineCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)

    def test_good_passes_final(self):
        code, out = run(GOOD, "--final")
        self.assertEqual(code, 0, out)
        self.assertIn("エラー: 0 件", out)

    def test_governing_message_must_come_first(self):
        text = GOOD.replace("## 統治メッセージ", "## 背景\n\n市場は伸びている。\n\n## 統治メッセージ", 1)
        code, out = run(text)
        self.assertEqual(code, 1)
        self.assertIn("最初の節が「統治メッセージ」ではありません", errors(out))

    def test_governing_message_one_sentence(self):
        text = GOOD.replace("埋める道筋が要る。\n\n- 前に", "埋める道筋が要る。資本も足りる。\n\n- 前に", 1)
        code, out = run(text)
        self.assertIn("統治メッセージは一文にしてください（2 文", errors(out))

    def test_closing_quote_is_not_a_second_sentence(self):
        self.assertEqual(oc.sentence_count("社長は「M&A は選択肢として持つ。」と述べた [F-300]。"), 1)
        self.assertEqual(oc.sentence_count("差は打ち手で埋める必要がある。」"), 1)

    def test_undecided_lane_warns_then_fails_final(self):
        text = GOOD.replace("- 前に出すレーン: レーン2 [D-007]", "- 前に出すレーン: —", 1)
        code, out = run(text)
        self.assertEqual(code, 0, out)
        self.assertIn("前に出すレーンが未決定", warnings(out))
        code, out = run(text, "--final")
        self.assertEqual(code, 1)
        self.assertIn("前に出すレーンが未決定", errors(out))

    def test_undecided_governing_message(self):
        lines = GOOD.splitlines()
        i = lines.index("## 統治メッセージ")
        lines[i + 2] = "—"
        code, out = run("\n".join(lines), "--final")
        self.assertIn("統治メッセージが未決定", errors(out))

    def test_lane_without_decision_id(self):
        code, out = run(GOOD.replace("レーン2 [D-007]", "レーン2", 1))
        self.assertIn("決定の ID（[D-xxx]）がありません", errors(out))

    def test_both_lanes_required(self):
        text = GOOD.split("## レーン1")[0] + "## 前提と未確認事項\n"
        code, out = run(text)
        self.assertIn("「## レーン1」がありません", errors(out))

    def test_lead_lane_order(self):
        code, out = run(GOOD.replace("レーン2 [D-007]", "レーン1 [D-007]", 1))
        self.assertIn("前に出すレーン1 を先に置いてください", warnings(out))

    def test_headline_without_id(self):
        text = GOOD.replace("3. 残りを埋めるには買収か市場の選び直しを足すしかない [O-001]。",
                            "3. 残りを埋めるには買収か市場の選び直しを足すしかない。", 1)
        code, out = run(text)
        self.assertIn("見出しに [ID] がありません", errors(out))

    def test_id_in_child_line_counts(self):
        code, out = run(GOOD)
        self.assertNotIn("line 33", errors(out))

    def test_topic_labels(self):
        text = GOOD.replace("2. 市場が伸びても成り行きは 2,553 億円 [S-001] にとどまる。", "2. 市場概要 [S-001]", 1)
        text = text.replace("2. 重点施策を満額で積んでも差の一部が残る [I-001]。", "2. 重点施策の積み上げ [I-001]", 1)
        text = text.replace("3. 残りを埋めるには買収か市場の選び直しを足すしかない [O-001]。", "3. まとめ [O-001]", 1)
        code, out = run(text)
        e = errors(out)
        self.assertIn("「概要」で終わるトピックラベル", e)
        self.assertIn("文字しかありません", e)
        self.assertIn("「まとめ」で終わるトピックラベル", e)

    def test_sentence_heuristics_warn(self):
        text = GOOD.replace("2. 市場が伸びても成り行きは 2,553 億円 [S-001] にとどまる。",
                            "2. 市場が伸びても成り行きは 2,553 億円 [S-001] にとどまる", 1)
        code, out = run(text)
        self.assertEqual(code, 0, out)
        self.assertIn("「。」で終わっていません", warnings(out))

    def test_pyramid_reasons(self):
        text = GOOD.replace("    - 事実: 借入余力 [C-001]", "    - 事実: 借入余力は大きい", 1)
        code, out = run(text)
        self.assertIn("事実に [ID] がありません", errors(out))
        text = GOOD.replace("    - 事実: 借入余力 [C-001]\n", "", 1)
        code, out = run(text)
        self.assertIn("根拠に「事実:」の行がありません", errors(out))

    def test_pyramid_reason_count_warns(self):
        lane1 = GOOD.split("## レーン1")[1]
        text = GOOD.replace("  - 根拠2: 重点施策の積み上げでは差が残る。\n    - 事実: 施策の積み上げ [I-001]\n", "", 1)
        self.assertNotEqual(text, GOOD, lane1)
        code, out = run(text)
        self.assertIn("レーン1 ピラミッド | 根拠が 1 個です", warnings(out))

    def test_conclusion_first_heuristic(self):
        text = GOOD.replace("1. 中計の重点施策だけで目標 [T-001] に届くには差 2,447 億円 [G-001] を埋める打ち手が要る。",
                            "1. 前中計は売上と利益のどちらの目標にも届かなかった [F-012]。", 1)
        code, out = run(text)
        self.assertIn("レーン1 の 1 ページ目が一言でと同じ ID を含みません", warnings(out))

    def test_missing_subsections(self):
        text = GOOD.replace("### ゴーストデッキ", "### デッキ", 1)
        code, out = run(text)
        self.assertIn("「### ゴーストデッキ」がありません", errors(out))

    def test_good_storyline_passes_number_audit(self):
        """良い例を案件に置くと、number-audit の deliverables/ の点検をエラーなしで通る。
        --strict では、仮置き（F-031）と — への依存が残るのでエラーになる（対応表に残す前提）。"""
        import subprocess
        case = Path(tempfile.mkdtemp(prefix="case-story-", dir=FIXTURE_ROOT))
        (case / "facts").mkdir()
        (case / "facts/facts.csv").write_text(LEDGER, encoding="utf-8")
        (case / "deliverables").mkdir()
        (case / "deliverables/storyline.md").write_text(GOOD, encoding="utf-8")
        (case / "04-options.md").write_text("| O-001 | 買収 |\n", encoding="utf-8")
        (case / "decisions.md").write_text("## D-007 前に出すレーン（2026-11-10）\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(AUDIT), str(case), "--today", "2026-10-30"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        r = subprocess.run([sys.executable, str(AUDIT), str(case), "--today", "2026-10-30", "--strict"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("仮置きか — に依存しています: F-031", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
