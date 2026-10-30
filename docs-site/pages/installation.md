# インストール

[GitHub CLI](https://cli.github.com/) の `gh skill` で、全体または個別のスキルをインストールする。

## 全体

```bash
gh skill install shunsaku-studio/prhythm-consulting --all
```

## 個別スキル

各スキルページ上部のタブから、エージェント別のコマンドをコピーできる。

```bash
gh skill install shunsaku-studio/prhythm-consulting <skill-name>
gh skill install shunsaku-studio/prhythm-consulting <skill-name> --agent claude-code --scope user
```

## Claude Code のプラグインとして

```bash
claude plugin marketplace add shunsaku-studio/prhythm-consulting
claude plugin install prhythm-consulting@prhythm-consulting
```

## 動かすのに必要なもの

- 計算スクリプトは **Python 3.10 以上の標準ライブラリだけ**で動く。追加のパッケージは要らない
- 実在企業の有価証券報告書を取る [company-financials](/skills/company-financials/) の EDINET 取得には、EDINET API v2 の API キー（無料で登録）が要る。環境変数 `EDINET_API_KEY` に入れる

## 案件フォルダを始める

スキルは案件フォルダ（`case/`）の中で使う。最初に台帳の見出し行だけを置いておくとよい。

```bash
mkdir -p case/facts case/client case/reviews case/deliverables case/model
echo "id,value,unit,definition,period,source_tag,source,retrieved_at,confidentiality,replace_by" > case/facts/facts.csv
```

フォルダの構成は[共通の決まり](/guide/conventions/)にある。
