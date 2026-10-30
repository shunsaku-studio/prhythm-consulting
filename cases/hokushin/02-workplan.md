# 作業計画 — 北辰工業

- 作成: 2026-11-02 / 作成者: アナリスト 佐藤（見本。架空の人物）。状態の列は作成時点のもの
- 期間: 2026-10-30 〜 2026-11-13（提案: 経営会議 2026-11-13）
- モード: アウトサイドイン（公開情報のみ）
- 入力: 01-issue-tree.md、decisions.md（検証する仮説の優先順位 D-003）
- チーム: アナリスト 佐藤、先輩（質問役）田中、マネージャー 山本（いずれも架空）

<!--
ID の書き方: Q-xxx、A-xxx、D-xxx は角括弧で囲まないのが基本。数字を書くときだけ台帳の ID を角括弧で付ける
担当と締め切りは案。決めるのはマネージャー（D-004）
-->

## 1. 作業表

| 順 | 論点 / 仮説 | 分析 | データの出所 | スキル | 出力ファイル | 担当 | 締め切り | 状態 |
|---|---|---|---|---|---|---|---|---|
| 1 | — / — | 目標を仕様にする（期限・定義・必要年率） | 決算説明会の書き起こし、中計、資本コストの開示 | target-math、midterm-plan-reader、leadership-lens | 00-target-spec.md、facts/midterm-plan.md、facts/leadership.md | 佐藤 | 2026-10-30 | 完了 |
| 2 | — / — | 論点と仮説、作業計画 | 00-target-spec.md | issue-tree、workplan | 01-issue-tree.md、02-workplan.md | 佐藤 | 2026-11-02 | 完了 |
| 3 | Q-006 / A-006 | 10 年分の財務とセグメントの推移、不連続 | 有報（抜粋） | company-financials | facts/financials.csv、facts/financials.md | 佐藤 | 2026-11-03 | 未着手 |
| 4 | Q-008 / A-008 | 収益性・ROE の分解・ROIC | facts/financials.csv | financial-analysis | facts/financial-analysis.md | 佐藤 | 2026-11-03 | 未着手 |
| 5 | Q-006 / A-006 | 過去の成長の内訳 | facts/financials.csv | growth-decomposition | facts/growth-decomposition.md | 佐藤 | 2026-11-04 | 未着手 |
| 6 | Q-007 / A-007 | 競合との比較 | 競合 3 社の有報・統合報告書 | competitor-benchmark | facts/competitor-benchmark.md | 佐藤 | 2026-11-04 | 未着手 |
| 7 | Q-001 / A-001 | 市場の成り行き | 業界団体の見通し | market-sizing | facts/market-sizing.md | 佐藤 | 2026-11-04 | 未着手 |
| 8 | Q-001 / A-001、Q-005 / A-005 | 成り行きとギャップ（FY2030、FY2033） | facts/facts.csv | gap-bridge | 03-gap-bridge.md | 佐藤 | 2026-11-05 | 未着手 |
| 9 | Q-002 / A-002 | 打ち手の網羅と見積もり | 03-gap-bridge.md | option-longlist、initiative-sizing | 04-options.md、05-initiatives.md | 佐藤（確度は田中・山本と） | 2026-11-09 | 未着手 |
| 10 | Q-003 / A-003 | 資本の手当て | 05-initiatives.csv、facts/financials.csv | capital-capacity | 06-capital.md | 佐藤 | 2026-11-09 | 未着手 |
| 11 | Q-002 / A-002 | 打ち手の評価 | 05-initiatives.md、06-capital.md | option-evaluation | 04-options.md（評価マトリクス） | 佐藤（重みは山本） | 2026-11-10 | 未着手 |
| 12 | Q-008 / A-008、Q-004 / A-004 | KPI ツリー、モデル、感応度 | 05-initiatives.csv、facts/facts.csv | kpi-tree、business-case-model、scenario-sensitivity | 07-kpi-tree.md、model/ | 佐藤 | 2026-11-11 | 未着手 |
| 13 | Q-004 / A-004 | ロードマップ、ゲートと撤退基準 | model/model.csv、model/sensitivity.md | kpi-roadmap | 08-kpi-roadmap.md | 佐藤（閾値は山本と） | 2026-11-11 | 未着手 |
| 14 | — / — | ストーリーと数字の点検 | 成果物一式 | storyline、number-audit | deliverables/storyline.md、reviews/number-audit.md | 佐藤 | 2026-11-12 | 未着手 |

## 2. ゲートと質問タイムの日程

| 日付 | 種類 | 中身 | 参加 | 決めること / 記録先 |
|---|---|---|---|---|
| 2026-11-02 | 質問タイム① | 目標の解釈の前（15〜20 分） | 田中、山本 | reviews/question-time.md |
| 2026-11-02 | ゲート | 目標の解釈を合意 | 山本 | decisions.md D-001 |
| 2026-11-02 | ゲート | 検証する仮説の優先順位 | 山本 | decisions.md D-003 |
| 2026-11-04 | ゲート | 成り行きの前提を確定 | 山本 | decisions.md D-005 の予定 |
| 2026-11-10 | 質問タイム② | 追う打ち手を選ぶ前（資本の見積もりの後） | 田中、山本 | reviews/question-time.md |
| 2026-11-10 | ゲート | 追う打ち手を選ぶ | 山本 | decisions.md |
| 2026-11-11 | ゲート | ゲートと撤退基準を確定 | 山本 | decisions.md |
| 2026-11-12 | 質問タイム③ | 最終メッセージの前 | 田中、山本 | reviews/question-time.md |
| 2026-11-12 | ゲート | 最終メッセージとレーンを確定 | 山本 | decisions.md |

各質問タイムの前に、半日の手戻りの余裕を取る（11-09 の午後、11-11 の午後）。

## 3. 週ごとの見取り図

| 週 | 前半 | 後半 |
|---|---|---|
| 1 週目（10-30〜11-06） | 目標の仕様、論点と仮説、財務の収集 | 成長の内訳、競合比較、市場の成り行き、ギャップ、打ち手の洗い出し |
| 2 週目（11-09〜11-13） | 打ち手の見積もり、資本、評価、KPI とモデル | ロードマップ、ストーリー、数字の点検、経営会議 |

## 4. 前提と未確認事項

- 担当が決まっていない行: なし（確度・重み・閾値はマネージャーと一緒に決める）
- 期間内に手に入らないデータ: 受注残、稼働率、顧客別の採用件数（受注後のインサイドアウトで取る）
- 戻りが起きたときに削る行の順番: 12 の感応度の変数を減らす → 6 の競合比較を財務だけにする

## 5. 人に返す判断

- 担当と締め切り、ゲートと質問タイムの日程 → D-004 で決めた
- 決めたことは decisions.md に D-004 で残した
