# 見本案件：北辰工業（お題A）

> 会社、人物、数値、意思決定はすべて架空です。説明用に作った見本で、実在の企業とは関係ありません。意思決定（[decisions.md](decisions.md)）は架空のマネージャー、質問タイム（[reviews/question-time.md](reviews/question-time.md)）は架空の先輩とジュニアのものです。

[お題A のワークフロー](../../workflows/a-revenue-growth.md)の 10 段を、スキルの手順どおりに 2026-10-30 から 2026-11-13 の 2 週間で通した結果である。依頼は [brief.md](brief.md)、一次資料（架空）は [sources/](sources/) にある。数字はすべて [facts/facts.csv](facts/facts.csv) の 1 行に結び付き、本文では `[ID]` で引ける。

## 10 段の流れ

| 段 | スキル | 出力 | 鍵になる数字 | ゲートの決定 | 質問タイム |
|----|--------|------|------------|------------|----------|
| 1 目標を仕様にする | target-math、midterm-plan-reader、leadership-lens | [00-target-spec.md](00-target-spec.md)、[facts/midterm-plan.md](facts/midterm-plan.md)、[facts/leadership.md](facts/leadership.md) | FY2030 の必要年率 20.1% [T-002]、ベースレートの 89.2% [T-014] の位置。FY2033 なら 12.1% [T-008] | D-001 目標の解釈、D-002 譲れない線 | ① の後に D-001 |
| 2 論点と仮説 | issue-tree、workplan | [01-issue-tree.md](01-issue-tree.md)、[02-workplan.md](02-workplan.md) | 論点 Q-001〜Q-008 | D-003 仮説の優先順位、D-004 作業計画 | — |
| 3 現状と成長の内訳 | company-financials、financial-analysis、growth-decomposition、competitor-benchmark | [facts/financials.md](facts/financials.md)、[facts/financial-analysis.md](facts/financial-analysis.md)、[facts/growth-decomposition.md](facts/growth-decomposition.md)、[facts/competitor-benchmark.md](facts/competitor-benchmark.md) | 過去 9 年の年率 4.5% [F-009]、うち M&A 0.4pt [F-365]。ROIC 7.1% [F-276]。大和テクノHD は買収で年 9.9% [F-341] | — | — |
| 4 成り行き | market-sizing | [facts/market-sizing.md](facts/market-sizing.md) | 市場成長 3.5% [F-395]、5.0% [F-396]、8.5% [F-397] | D-005 成り行きの前提 | — |
| 5 ギャップ | gap-bridge | [03-gap-bridge.md](03-gap-bridge.md) | 成り行き 2,539 億円 [S-004]、ギャップ 2,461 億円 [G-001]。シェア 800 億円 [G-003] は年 5.9pt [G-007] で赤旗、平均なら 98 億円 [G-008] | D-006 レーン2 を FY2033 で組む | — |
| 6 打ち手 | option-longlist、initiative-sizing、option-evaluation | [04-options.md](04-options.md)（評価マトリクスつき）、[05-initiatives.md](05-initiatives.md) | 打ち手 16 件。見直し案の上乗せ 1,268.8 億円 [F-457] | D-007 sizing に回す打ち手、D-008 前提、D-009 確度 | — |
| 7 資本 | capital-capacity | [06-capital.md](06-capital.md) | 初回案は 657.6 億円 [C-007] 不足、ネット D/E 1.21倍 [C-008] → 打ち手に戻る。見直し案は 152.4 億円 [C-013] 余り、ネット D/E 0.50倍 [C-014] | D-010 打ち手に戻る、D-011 重み、D-012 追う打ち手 | ② は 1 回目に不通過、再確認で通過 |
| 8 KPI とモデル | kpi-tree、business-case-model、scenario-sensitivity | [07-kpi-tree.md](07-kpi-tree.md)、[model/model-summary.md](model/model-summary.md)、[model/scenarios.md](model/scenarios.md)、[model/business-case.xlsx](model/business-case.xlsx) | FY2030 の売上 3,809.2 億円 [F-468]、目標まで 1,190.8 億円 [F-491] 不足。下振れは 3,177.8 億円 [F-485] | D-013 ベースケース、D-014 モデルの旗、D-015 感応度の幅、D-016 管理する KPI | — |
| 9 ロードマップ | kpi-roadmap | [08-kpi-roadmap.md](08-kpi-roadmap.md) | ゲートは G1 から G4。閾値は仮置き（K-025〜K-028） | D-017 ゲートと撤退基準 | — |
| 10 ストーリー | storyline、number-audit | [deliverables/storyline.md](deliverables/storyline.md)、[reviews/number-audit.md](reviews/number-audit.md) | FY2033 の未割当 90 億円 [G-024] | D-018 レーン2 を前に出す | ③ の後に D-018 |

段 8 は、kpi-tree をモデルの後に回した。ツリーの値を model/model.csv から取るためである。

## ID をたどる

ストーリーのレーン1 の 2 ページ目「成り行きは 2,539 億円 [S-004] で、ギャップは 2,461 億円 [G-001] ある」を、一次資料までたどる。

1. [facts/facts.csv](facts/facts.csv) の S-004 は推定で、計算式は「S-001 + S-002 + S-003」
2. S-001 は 1,247.1 億円 [S-001]（自動車部品の成り行き）。計算式は「F-236 × (1+F-395)^5」で、gap-bridge のスクリプトが書いた
3. F-236 は公開で、有価証券報告書 FY2025 p.90（セグメント情報）の自動車部品の売上高 1,050 億円 [F-236]。company-financials が [sources/yuho-excerpt.csv](sources/yuho-excerpt.csv) から登録した
4. F-395 は公開で、日本精密部品工業会「精密部品市場の見通し 2026」p.5 の自動車向け精密部品の成長率 3.5% [F-395]。成り行きに使うことは D-005 で決めた

どの数字も、この順に「推定なら計算式の ID、公開なら資料とページ」をたどれば元に戻れる。

## 通して直したこと

通すたびにスキルを直す（企画書 §8 ステップ 5）。今回、段と段のつなぎ目で直したもの。

- **ROIC の定義をそろえた**: financial-analysis の ratios.py は投下資本から「余剰現金」だけを引いていた。CONVENTIONS の共通の定義（純資産 + 有利子負債 − 現金及び預金）を既定にし、余剰現金の定義は `--cash-months` を渡したときだけ使う形にした。capital-capacity と business-case-model はもともと共通の定義だった
- **同じ事実を二重に載せない**: target-math が 1 日目に登録した売上・純資産・純利益を、company-financials が後から別の ID で登録していた。normalize.py が同じ期間・単位・値・科目の公開の行を見つけたら、その ID を使い回すようにした（FY2025 の売上高は [F-001] の 1 行だけ）。target-math の基準年の売上も、推移の行と二重に登録しないようにした。midterm-plan-reader は `@F-001` で台帳の ID を指定できるようにした。ratios.py、competitor-benchmark、growth-decomposition、gap-bridge、market-sizing は、同じ計算式の推定の行があればその ID を使う
- **financial-analysis のセグメント表に ID を付けた**: 6 節の利益率と構成比に、`--register` の年度だけ ID を付けた。減価償却費 ÷ 売上高と設備投資額 ÷ 売上高を足し、business-case-model の入力にそのまま使えるようにした
- **Q・A・O・D の括弧の書き方をそろえた**: number-audit は案件内で定義された `[Q-]` `[O-]` `[D-]` を通す。issue-tree・workplan・competitor-benchmark のテンプレートと CONVENTIONS を、この挙動に合わせて書き直した（A- は表の 4 列目にあるので括弧で囲まない）
- **科目名と年度の書き方**: capital-capacity が IFRS の科目名も読むようにし、有利子負債の内訳しかないときの直し方をエラーに書いた。年度は FY2027 の形で書くと各スキルの説明をそろえた
- **案を比べられるようにした**: capital-capacity に `--label` を足した。初回案と見直し案の C- 行が上書きされずに両方残り、decisions.md から引ける。合計と過不足の計算式は C- の ID で書くようにした
- **日付を案件の日にそろえた**: business-case-model、scenario-sensitivity、kpi-roadmap に `--today` を足した（kpi-roadmap は仮置きの閾値の `--replace-by` と `replace_by` 列も読む）
- **出力に ID を付けた**: market-sizing の定義に合う割合の列、business-case-model のネット D/E の最大と現預金の最小、scenario-sensitivity の目標との差を台帳に載せ、本文に `[ID]` を付けた
- **網羅の点検の誤検出**: option-longlist の coverage.py が 03-gap-bridge.md の G- をすべて「埋めるギャップ」とみなしていた。04-options.md の「埋めるギャップ」の表にある G- だけを見るようにした
- **gap-bridge の必要年率**: target-math が同じ目標・期間の必要年率を登録済みなら、その T- を使う（この案件では G-002 が先に登録されていたので残っている）

## 残っていること

- 仮置きは 48 件ある（期限は 2026-11-27 と 2026-12-25）。デッキに出す数字のうち 15 件が仮置きに依って立つ（[reviews/number-audit-triage.md](reviews/number-audit-triage.md)）
- capital-capacity とモデルでネット D/E の最大が違う（0.50倍 [C-014] と 0.61倍 [F-494]）。運転資本の置き方の差で、受注後に実績で確かめる（D-014）
- FY2031 以降の資本（2 件目の買収の資金）は見積もっていない
