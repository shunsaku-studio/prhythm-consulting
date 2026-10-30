#!/usr/bin/env python3
"""EDINET API v2 から書類一覧を引き、有報の CSV（type=5 の zip）を取ってくる。

【未検証】このスクリプトは API キーのない環境で書いたため、実際の API には一度も通していない。
引数の解釈（--help）だけを確かめてある。初めて使うときは、1 日分の一覧取得から試し、
返ってきた JSON の項目名（docID, secCode, docTypeCode, csvFlag など）が下のコードと合うか確かめること。

準備:
  - EDINET の API キー（無料。利用登録が要る）を環境変数 EDINET_API_KEY に入れる
    キーはコマンドラインに書かない。このスクリプトもキーを画面に出さない
  - エンドポイント:
      書類一覧  https://api.edinet-fsa.go.jp/api/v2/documents.json?date=YYYY-MM-DD&type=2&Subscription-Key=...
      書類取得  https://api.edinet-fsa.go.jp/api/v2/documents/{docID}?type=5&Subscription-Key=...（CSV の zip）

データの限り（SKILL.md にも書いた）:
  - EDINET で取れる過去書類には保持期間の限りがある（期間は EDINET の案内で要確認）。10 年分を並べるなら、
    古い期は最新の有報の「経営指標等の推移」（5 期分）を二つ重ねるなどで補う
  - 四半期報告書は 2024 年に廃止された。四半期の数字は決算短信（TDnet）から取る
  - TDnet の API は法人向けが有料。短信は会社の IR ページの PDF から手で取る

使い方:
  export EDINET_API_KEY=...
  python3 fetch_edinet.py list --from 2026-06-20 --to 2026-06-30 --sec-code 7203
  python3 fetch_edinet.py get --doc-id S100XXXX --out case/sources/edinet/
  → 展開した CSV を normalize.py に渡す（--fiscal-year と --doc-name を付ける）

標準ライブラリだけで動く。Python 3.10 以上。
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.edinet-fsa.go.jp/api/v2"
DOC_TYPES = {"120": "有価証券報告書", "130": "訂正有価証券報告書", "140": "四半期報告書（2024 年廃止）",
             "160": "半期報告書", "170": "訂正半期報告書"}


def api_key() -> str:
    key = os.environ.get("EDINET_API_KEY", "").strip()
    if not key:
        sys.exit("エラー: 環境変数 EDINET_API_KEY がありません。EDINET の API キーを入れてから実行する")
    return key


def fetch(url_path: str, params: dict[str, str], timeout: float) -> bytes:
    q = dict(params)
    q["Subscription-Key"] = api_key()
    url = f"{API}{url_path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "prhythm-consulting/company-financials"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read()
    except urllib.error.HTTPError as e:
        # URL にキーが入るので、URL は表示しない
        sys.exit(f"エラー: EDINET API が {e.code} を返した（{url_path}）。キー・日付・docID を確かめる")
    except urllib.error.URLError as e:
        sys.exit(f"エラー: EDINET API に接続できない（{e.reason}）")


def cmd_list(a: argparse.Namespace) -> int:
    start = dt.date.fromisoformat(a.date_from)
    end = dt.date.fromisoformat(a.date_to or a.date_from)
    if (end - start).days > 366:
        sys.exit("エラー: 期間は 1 年以内にする（1 日ずつ API を呼ぶため）")
    types = set(a.doc_types.split(","))
    sec = a.sec_code
    if sec and len(sec) == 4:
        sec = sec + "0"  # EDINET の証券コードは 5 桁
    hits = []
    d = start
    while d <= end:
        body = fetch("/documents.json", {"date": d.isoformat(), "type": "2"}, a.timeout)
        data = json.loads(body.decode("utf-8"))
        status = str(data.get("metadata", {}).get("status", ""))
        if status and status != "200":
            print(f"警告: {d} の一覧で status={status}（{data.get('metadata', {}).get('message', '')}）", file=sys.stderr)
        for r in data.get("results") or []:
            if r.get("docTypeCode") not in types:
                continue
            if sec and r.get("secCode") != sec:
                continue
            if a.edinet_code and r.get("edinetCode") != a.edinet_code:
                continue
            hits.append(r)
        d += dt.timedelta(days=1)
        time.sleep(a.sleep)
    print("| 提出日時 | docID | 提出者 | 書類 | 期末 | CSV |")
    print("|---------|-------|--------|------|------|-----|")
    for r in hits:
        print(f"| {r.get('submitDateTime', '—')} | {r.get('docID', '—')} | {r.get('filerName', '—')} | "
              f"{r.get('docDescription') or DOC_TYPES.get(r.get('docTypeCode', ''), '—')} | {r.get('periodEnd', '—')} | "
              f"{'あり' if str(r.get('csvFlag')) == '1' else 'なし'} |")
    if not hits:
        print("| — | — | — | 該当なし | — | — |")
    return 0


def cmd_get(a: argparse.Namespace) -> int:
    body = fetch(f"/documents/{a.doc_id}", {"type": "5"}, a.timeout)
    if body[:2] != b"PK":
        # エラーのときは JSON が返る
        try:
            msg = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            msg = body[:200]
        sys.exit(f"エラー: zip ではない応答が返った: {msg}")
    out = Path(a.out) / a.doc_id
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        z.extractall(out)
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
    print(f"{out} に展開した。CSV:")
    for n in names:
        print(f"  {out / n}")
    print("次: normalize.py <CSV> --fiscal-year FYxxxx --doc-name \"有価証券報告書 FYxxxx（EDINET "
          f"{a.doc_id}）\" --out facts/financials.csv ...")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="期間内の書類一覧から対象企業の書類を探す")
    p.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", help="YYYY-MM-DD（省略時は --from の 1 日だけ）")
    p.add_argument("--sec-code", help="証券コード（4 桁か 5 桁）")
    p.add_argument("--edinet-code", help="EDINET コード（E から始まる）")
    p.add_argument("--doc-types", default="120,130", help="書類種別コード（既定: 120 有報, 130 訂正有報）")
    p.add_argument("--sleep", type=float, default=1.0, help="API を呼ぶ間隔（秒）")
    p.add_argument("--timeout", type=float, default=30.0)
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("get", help="書類の CSV（type=5 の zip）を取って展開する")
    p.add_argument("--doc-id", required=True)
    p.add_argument("--out", required=True, help="展開先のディレクトリ")
    p.add_argument("--timeout", type=float, default=60.0)
    p.set_defaults(func=cmd_get)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
