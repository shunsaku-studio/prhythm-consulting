# 作業計画 — <会社名>

- 作成: YYYY-MM-DD / 作成者: —
- 期間: YYYY-MM-DD 〜 YYYY-MM-DD（提案: <会議名> YYYY-MM-DD）
- モード: <アウトサイドイン（公開情報のみ） / インサイドアウト（社内データ）>
- 入力: 01-issue-tree.md、decisions.md（検証する仮説の優先順位 D-xxx）
- チーム: <アナリスト>、<先輩（質問役）>、<マネージャー>

<!--
ID の書き方: Q-xxx、A-xxx、D-xxx は角括弧で囲まない。数字を書くときだけ台帳の ID を角括弧で付ける
担当と締め切りは案。決めるのはマネージャー
-->

## 1. 作業表

| 順 | 論点 / 仮説 | 分析 | データの出所 | スキル | 出力ファイル | 担当 | 締め切り | 状態 |
|---|---|---|---|---|---|---|---|---|
| 1 | — / — | 目標を仕様にする（期限・定義・必要年率） | 中計、決算説明会、資本コストの開示 | target-math | 00-target-spec.md | — | 1 日目 | 未着手 |
| 2 | — / — | 論点と仮説 | 00-target-spec.md | issue-tree | 01-issue-tree.md | — | 2 日目 | 未着手 |
| 3 | Q-___ / A-___ | <例: 10 年分の財務とセグメントの推移> | 有報、短信 | company-financials | facts/financials.csv | — | — | 未着手 |
| 4 | Q-___ / A-___ | <例: 過去の成長の内訳> | facts/financials.csv | growth-decomposition | facts/growth-decomposition.md | — | — | 未着手 |
| 5 | Q-___ / A-___ | <例: 競合との比較> | 競合の有報、統合報告書 | competitor-benchmark | facts/competitor-benchmark.md | — | — | 未着手 |
| 6 | Q-___ / A-___ | <例: 市場の成り行き> | 業界統計 | market-sizing | facts/market-sizing.md | — | — | 未着手 |
| 7 | Q-___ / A-___ | <例: 成り行きとギャップ> | facts.csv | gap-bridge | 03-gap-bridge.md | — | 1 週目末 | 未着手 |
| 8 | Q-___ / A-___ | <例: 打ち手の網羅と見積もり> | 03-gap-bridge.md | option-longlist, initiative-sizing | 04-options.md, 05-initiatives.md | — | — | 未着手 |
| 9 | Q-___ / A-___ | <例: 資本の手当て> | 05-initiatives.csv、financials.csv | capital-capacity | 06-capital.md | — | — | 未着手 |
| 10 | Q-___ / A-___ | <例: KPI とモデル、ロードマップ> | — | kpi-tree, business-case-model, kpi-roadmap | 07-kpi-tree.md, model/, 08-kpi-roadmap.md | — | — | 未着手 |
| 11 | — / — | ストーリーと数字の点検 | 成果物一式 | storyline, number-audit | deliverables/storyline.md | — | — | 未着手 |

<!-- 状態: 未着手 / 作業中 / レビュー待ち / 完了 / 取り下げ。仮説に結び付かない行は置かない -->

## 2. ゲートと質問タイムの日程

| 日付 | 種類 | 中身 | 参加 | 決めること / 記録先 |
|---|---|---|---|---|
| YYYY-MM-DD | 質問タイム① | 目標の解釈の前（15〜20 分） | 先輩、マネージャー | reviews/question-time.md |
| YYYY-MM-DD | ゲート | 目標の解釈を合意 | マネージャー | decisions.md D-___ |
| YYYY-MM-DD | ゲート | 検証する仮説の優先順位 | マネージャー | decisions.md D-___ |
| YYYY-MM-DD | ゲート | 成り行きの前提を確定 | マネージャー | decisions.md D-___ |
| YYYY-MM-DD | 質問タイム② | 追う打ち手を選ぶ前（資本の見積もりの後） | 先輩、マネージャー | reviews/question-time.md |
| YYYY-MM-DD | ゲート | 追う打ち手を選ぶ | マネージャー | decisions.md D-___ |
| YYYY-MM-DD | ゲート | ゲートと撤退基準を確定 | マネージャー | decisions.md D-___ |
| YYYY-MM-DD | 質問タイム③ | 最終メッセージの前 | 先輩、マネージャー | reviews/question-time.md |
| YYYY-MM-DD | ゲート | 最終メッセージとレーンを確定 | マネージャー | decisions.md D-___ |

各質問タイムの前に、半日の手戻りの余裕を取る。

## 3. 週ごとの見取り図

| 週 | 前半 | 後半 |
|---|---|---|
| 1 週目 | 目標の仕様、論点と仮説、財務の収集 | 成長の内訳、競合比較、市場の成り行き、ギャップ |
| 2 週目 | 打ち手、資本、KPI とモデル | ロードマップ、ストーリー、数字の点検 |

## 4. 前提と未確認事項

- 担当が決まっていない行: —
- 期間内に手に入らないデータ: —
- 戻りが起きたときに削る行の順番: —

## 5. 人に返す判断

- 担当と締め切り、ゲートと質問タイムの日程
- 決めたことは decisions.md に D-xxx で残す
