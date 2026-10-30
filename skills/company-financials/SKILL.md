---
name: company-financials
description: >-
  Collect a listed company's PL, BS, CF and segment figures from public filings
  (有価証券報告書 via EDINET API v2 CSV, or a hand-made long-form CSV from 有報 and
  決算短信), normalize them into facts/financials.csv with ledger IDs and source
  pages, and report discontinuities: segment reorganizations, accounting-basis
  changes, M&A years, YoY jumps and segment totals that do not reconcile.
  「この会社の数字、10年分並べといて」「有報から PL と BS 取っといて」
  「セグメント別の推移出して」「EDINET から財務データ落として」「財務の時系列作って」
disable-model-invocation: false
verb: investigate
categories:
  - finance
autonomy: solo
maturity: formal
workflows:
  - A
  - B
  - D
---

# company-financials

Lay out a company's numbers over time, with a source for every value and a list of the places where the series is not comparable.
The output file `facts/financials.csv` is the input for financial-analysis, growth-decomposition, capital-capacity and business-case-model.

Human guide (Japanese): [README.md](README.md)

## When to use

- Step 3 of workflow A (現状と成長の内訳), and the first data step of B and D
- Whenever another skill needs a time series and `facts/financials.csv` does not exist yet
- When a new 有報 or 短信 comes out (re-run; existing IDs are kept)

Do NOT use for: interpreting the numbers (financial-analysis), splitting growth into market / share / M&A (growth-decomposition), competitor tables (competitor-benchmark).

## Intake (ask before collecting)

Details: [references/intake.md](references/intake.md).

| Input | Example | If unknown |
|-------|---------|-----------|
| Company name and 証券コード or EDINET コード | `<社名>` / — | Ask. Needed to find filings |
| Years | FY2016–FY2025 (10 periods) | Default: 10 periods |
| Items | PL, BS, CF basics + segment sales and profit | Default list in method.md |
| Source available | EDINET API key? hand-made CSV? | Without a key, build the long-form CSV by hand from 有報 PDFs |
| Unit | 億円 or 百万円 | Keep the source unit; EDINET values are converted from 円 to 百万円 |

## Steps

Method and reasons: [references/method.md](references/method.md).

1. **Get the filings.**
   - With an EDINET API key: `scripts/fetch_edinet.py list` to find docIDs, then `get` to download the CSV zip (type=5)
   - Without a key, or for years EDINET no longer holds: write the long-form CSV by hand from 有報 / 短信 PDFs (columns below), one row per value, with page numbers
2. **Normalize** with `scripts/normalize.py` into `facts/financials.csv` and append ledger rows (`source_tag` 公開, source = document and page).
3. **Read the discontinuity report** the script prints (and writes to `facts/financials.md`). For every 不連続 / 非連続 / 要確認 line, open the filing note (セグメント情報, 会計方針の変更, 企業結合) and write the cause in 前提と未確認事項. A jump the script flags is not a discontinuity until a note says so; a series the script does not flag is not proven continuous.
4. **Add restated values** where the filing gives them (e.g. 組み替え後の前期数値 in 比較情報) as separate items like `売上高（組み替え後・参考）`, then re-run. The script then reports like-for-like YoY.
5. **Hand off.** No gate in this skill (autonomy: solo). Tell the user which discontinuities later skills must handle.

## Output (always these three parts)

1. **Body** — `facts/financials.csv` (schema below) and `facts/financials.md` (discontinuity table, consolidated and segment series, segment-total reconciliation). Template: [templates/financials.md](templates/financials.md)
2. **Facts** — every row of financials.csv has an `id` that is also a row in `facts/facts.csv` with the same value and unit
3. **前提と未確認事項** — causes of flagged discontinuities (or — if not yet found), missing years, items not disclosed, data-source limits

`facts/financials.csv` schema (CONVENTIONS §9), long form:

```csv
id,fiscal_year,item,segment,value,unit,basis,source,note
F-188,FY2025,売上高,連結,2000,億円,日本基準,有価証券報告書 FY2025 p.40,
```

- `segment` is `連結`, a segment name, or `調整額`
- `basis` is `日本基準` / `IFRS` / `米国基準`
- Item names: use the filing's own names (日本基準 `売上高`, IFRS `売上収益`). financial-analysis maps the common aliases
- Hand-made input CSV columns: `fiscal_year,item,segment,value,unit,basis,source_page,note`

## Scripts

All Python 3.10+, standard library only. `--help` shows every option.

```bash
# (a) long-form CSV (e.g. お題A)
python3 skills/company-financials/scripts/normalize.py case/sources/yuho-excerpt.csv \
  --company 対象会社 --out <case>/facts/financials.csv \
  --ledger <case>/facts/facts.csv --append --report <case>/facts/financials.md

# (b) EDINET (needs EDINET_API_KEY in the environment)
python3 skills/company-financials/scripts/fetch_edinet.py list --from 2026-06-20 --to 2026-06-30 --sec-code 7203
python3 skills/company-financials/scripts/fetch_edinet.py get --doc-id S100XXXX --out <case>/sources/edinet/
python3 skills/company-financials/scripts/normalize.py <case>/sources/edinet/S100XXXX/XBRL_TO_CSV/<file>.csv \
  --fiscal-year FY2025 --doc-name "有価証券報告書 FY2025（EDINET S100XXXX）" --company <name> \
  --segment-map AutomotiveReportableSegmentMember=自動車部品 \
  --out <case>/facts/financials.csv --ledger <case>/facts/facts.csv --append --report <case>/facts/financials.md
```

- `normalize.py` auto-detects EDINET CSV (UTF-16, tab-separated; columns 要素ID, 項目名, コンテキストID, 相対年度, 連結・個別, 期間・時点, ユニットID, 単位, 値). It keeps only the elements in its map (add more with `--element-map`), consolidated only unless `--include-nonconsolidated`, and maps 当期/前期/前々期 to fiscal years from `--fiscal-year`
- Re-running keeps existing IDs (same fiscal year, item, segment, basis). A changed value is reported, never silently overwritten in the ledger
- If another skill already registered the same fact (e.g. target-math on day 1 registered FY2025 売上高 2,000 as `連結売上高（基準年の実績）`), normalize.py reuses that ID instead of minting a second one: same fiscal year, unit and value, source tag 公開, and a definition that contains the item name and the segment (`連結` for consolidated rows). Each reuse is listed in 前提と未確認事項. After this, re-run target-math with `--financials`; it then adds no new rows
- Item names matter downstream: financial-analysis, capital-capacity and business-case-model read `売上高`, `営業利益`, `親会社株主に帰属する当期純利益`, `総資産`, `純資産`, `現金及び預金`, `有利子負債`, `営業活動によるキャッシュ・フロー`, `設備投資額`, `減価償却費`, `子会社株式の取得による支出`, `配当金の支払額` (IFRS names such as `売上収益` are also read). Keep the filing's names; if the filing has only 短期借入金 / 長期借入金 / 社債, financial-analysis registers their sum as 有利子負債 and capital-capacity takes that ID through `06-capital-inputs.csv`
- Thresholds: `--jump` (YoY %, default 20), `--tolerance` (segment total vs consolidated, %, default 0.5)
- **`fetch_edinet.py` is untested**: it was written without an API key. Try one day of `list` first and check the JSON field names. The EDINET element map in normalize.py is a starting list; check element IDs against the actual filing. normalize.py's EDINET path was tested only on a synthetic UTF-16 file

## Data limits (write them in 前提と未確認事項 when they apply)

- EDINET keeps past filings only for a limited period (check EDINET's guidance for the exact span). For 10 periods, combine the 経営指標等の推移 (5 periods) of two 有報, or type older years from PDFs
- 四半期報告書 was abolished in 2024. Quarterly figures come from 決算短信
- TDnet API is a paid corporate service; J-Quants' TDnet add-on is for individuals and cannot be used by a firm. Take 短信 from the company's IR page by hand
- Segment assets and liabilities are often not disclosed; segment ROIC is then —

## Pitfalls

Full list: [references/pitfalls.md](references/pitfalls.md). Most important: missing a segment reorganization or accounting-basis change and comparing across it as if continuous.

Senior question seeds: [references/questions.md](references/questions.md).
Evaluation: [references/eval-scenarios.md](references/eval-scenarios.md), [references/eval-rubric.md](references/eval-rubric.md).
