# intake — 何を聞いてから始めるか

足りないものだけを聞く。分からない値は — のまま残し、前提と未確認事項に書く。

## 最初に確かめること

| 聞くこと | なぜ | 答えがないとき |
|----------|------|----------------|
| 目標の定義（連結か、M&A 込みか、期限） | モデルの売上と目標を同じ定義で比べるため | `00-target-spec.md` を読む。なければ target-math に戻る |
| 基準年の実績がどの ID か | 基準年を再現できないモデルは先へ進めない | company-financials を先に回す |
| 成り行きの成長率はどこで決まったか | 成り行きはモデルで決めるものではない | market-sizing / gap-bridge の段のゲートに戻る |
| 施策の一覧と確度 | どれをベースケースに入れるかを決めるため | 施策なしで回し、成り行きだけと明記する |
| 資本の対照（06-capital.md）の結論 | 現預金の線と照らすため | モデルの旗だけを示し、資本の段に戻すか聞く |
| 財務規律（ネット D/E の上限、配当性向） | 旗の基準にするため | 開示から取る。なければ — |

## ドライバーの集め方

| key | ふつうの出どころ | 置き方の目安 |
|-----|------------------|--------------|
| base_revenue, base_op, base_equity, base_debt, base_cash | 有報（`facts/financials.csv`） | `公開` |
| base_growth | gap-bridge の成り行き（S-）か market-sizing | `推定`。根拠のない値を置かない |
| base_margin | 基準年の営業利益 ÷ 売上 | `推定`（計算式に ID） |
| init_margin | 競合の利益率、施策カード | `推定` か `仮置き` |
| da_rate | 基準年の減価償却費 ÷ 売上 | `推定` |
| maint_capex_rate | 過去の設備投資と減価償却の差 | `仮置き` が多い。期限を付ける |
| dep_life | 有報の耐用年数の記載 | 5 年以上にする（スクリプトが止める） |
| nwc_rate | 売上債権・棚卸資産・仕入債務の売上比 | `推定` か `仮置き` |
| tax_rate | 有報の税効果注記 | `公開` か `仮置き` |
| interest_rate | 支払利息 ÷ 有利子負債 | `推定` |
| payout_ratio | 中計・説明会の方針 | `公開` |
| wacc | 資本コストの開示 | `公開`。なければ — にして ROIC と比べない |

## 始める前に揃っているべきファイル

- `facts/facts.csv`（基準年の実績が載っている）
- `05-initiatives.csv`（`id,initiative,year,revenue,investment,unit,confidence`）
- `model/inputs.csv`（`templates/inputs.csv` から）
