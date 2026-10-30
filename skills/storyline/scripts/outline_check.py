#!/usr/bin/env python3
"""deliverables/storyline.md の骨組みを点検する（数字の点検は number-audit が行う）。

点検すること:
  1. 最初の節が「統治メッセージ」で、一文である（未決定の — は警告、--final ではエラー）
  2. 「前に出すレーン」の行があり、決まったら D- の ID が付いている
  3. レーン1 とレーン2 の両方がある
  4. 各レーンに「一言で」（一文）、「ピラミッド」（根拠 2〜5 個、各根拠に ID 付きの事実）、
     「ゴーストデッキ」（見出しの一覧）がある
  5. ゴーストデッキの各ページに [ID] が 1 つ以上ある
  6. 見出しが文になっている（「市場概要」のようなトピックラベルはエラー）
  7. 1 ページ目が「一言で」と同じ ID を含む（結論が先に来ているかの目安。警告）

使い方:
  python3 outline_check.py <storyline.md> [--final]

  --final  レーンと統治メッセージが決まった後の最終点検。未決定の — をエラーにする

終了コード: エラーが 1 件以上あれば 1、なければ 0。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ID_RE = r"[TQAFSGOICKD]-\d{3,}"
TAG_RE = re.compile(r"\[(" + ID_RE + r"(?:\s*[,、]\s*" + ID_RE + r")*)\]")
LANE_RE = re.compile(r"^##\s+レーン\s*([12１２])")
GOVERNING = "統治メッセージ"
LEAD_RE = re.compile(r"前に出すレーン\s*[:：]\s*(.*)")
REASON_RE = re.compile(r"^\s*[-*]\s*\**根拠\s*[0-9０-９]*\**\s*[:：]")
FACT_RE = re.compile(r"^\s*[-*]\s*\**事実\**\s*[:：]")
PAGE_RE = re.compile(r"^(\d+)[.．]\s+(.+)$")
# 見出しがこの語で終われば、文ではなくトピックラベルとみなす
LABEL_SUFFIXES = (
    "概要", "分析", "現状", "結果", "まとめ", "について", "比較", "一覧", "推移", "環境", "動向",
    "課題", "示唆", "方向性", "全体像", "背景", "目的", "論点", "前提", "打ち手", "施策", "ロードマップ",
    "結論", "提言", "はじめに", "目次", "アジェンダ", "次のステップ", "整理", "検討", "見通し", "内訳",
    "サマリー", "サマリ", "の比較", "の状況", "状況",
)
MIN_HEADLINE_CHARS = 15
PARTICLES = re.compile(r"[はがをにでともへ]")


class Result:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append((where, msg))


def ids_in(text: str) -> set[str]:
    out: set[str] = set()
    for m in TAG_RE.finditer(text):
        out.update(s.strip() for s in re.split(r"[,、]", m.group(1)))
    return out


def plain(text: str) -> str:
    """ID・強調・末尾の句点を落とした本文。"""
    t = TAG_RE.sub("", text).replace("**", "").strip()
    return t.rstrip("。. 　").strip()


def sentence_count(text: str) -> int:
    t = re.sub(r"「[^」]*」|『[^』]*』", "「」", TAG_RE.sub("", text))  # 引用の中の句点は数えない
    return len([s for s in re.split(r"[。]", t) if s.strip(" 　」』）)}]")])


def is_unknown(text: str) -> bool:
    return plain(text) in {"", "—", "-", "未決定", "—（未決定）"}


def headline_problem(text: str) -> str | None:
    """見出しがトピックラベルなら理由を返す。"""
    body = plain(text)
    for suf in LABEL_SUFFIXES:
        if body.endswith(suf):
            return f"「{suf}」で終わるトピックラベルです。主張を一文で書いてください"
    if len(body) < MIN_HEADLINE_CHARS:
        return f"{len(body)} 文字しかありません。トピックラベルではなく主張の一文にしてください"
    return None


def split_sections(lines: list[str], level: int) -> list[tuple[str, int, list[tuple[int, str]]]]:
    """見出しレベル level で区切る。(見出し, 行番号, 本文の行) の一覧。"""
    prefix = "#" * level + " "
    sections: list[tuple[str, int, list[tuple[int, str]]]] = []
    for no, line in lines:
        if line.startswith(prefix):
            sections.append((line[len(prefix):].strip(), no, []))
        elif sections:
            sections[-1][2].append((no, line))
    return sections


def first_text(body: list[tuple[int, str]]) -> tuple[int, str]:
    for no, line in body:
        s = line.strip()
        if s and not s.startswith(("<!--", ">")) and not LEAD_RE.search(s) and not s.startswith("- 聞き手"):
            return no, s
        if s.startswith(">"):
            return no, s.lstrip("> ").strip()
    return 0, ""


def check_lane(name: str, body: list[tuple[int, str]], res: Result) -> None:
    subs: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    for title, no, content in split_sections(body, 3):
        for key in ("一言で", "ピラミッド", "ゴーストデッキ"):
            if title.startswith(key) and key not in subs:
                subs[key] = (no, content)
    # 一言で
    key_ids: set[str] = set()
    if "一言で" not in subs:
        res.error(name, "「### 一言で」がありません")
    else:
        no, text = first_text(subs["一言で"][1])
        if not text or is_unknown(text):
            res.error(f"{name} 一言で", "一言でが空です")
        else:
            key_ids = ids_in(text)
            if sentence_count(text) != 1:
                res.error(f"line {no}", f"{name} の一言では一文にしてください（{sentence_count(text)} 文あります）")
            if not key_ids:
                res.warn(f"line {no}", f"{name} の一言でに [ID] がありません")
    # ピラミッド
    if "ピラミッド" not in subs:
        res.error(name, "「### ピラミッド」がありません")
    else:
        reasons: list[tuple[int, str, list[tuple[int, str]]]] = []
        for no, line in subs["ピラミッド"][1]:
            if REASON_RE.match(line):
                reasons.append((no, line, []))
            elif reasons and line.strip():
                reasons[-1][2].append((no, line))
        if not 2 <= len(reasons) <= 5:
            res.warn(f"{name} ピラミッド", f"根拠が {len(reasons)} 個です。3 個前後（2〜5 個）に絞ってください")
        for no, line, children in reasons:
            facts = [(n, c) for n, c in children if FACT_RE.match(c)]
            if not facts:
                res.error(f"line {no}", f"{name} の根拠に「事実:」の行がありません")
            for n, c in facts:
                if not ids_in(c):
                    res.error(f"line {n}", f"{name} の事実に [ID] がありません: {plain(FACT_RE.sub('', c))[:40]}")
    # ゴーストデッキ
    if "ゴーストデッキ" not in subs:
        res.error(name, "「### ゴーストデッキ」がありません")
        return
    pages: list[tuple[int, str, list[str]]] = []
    for no, line in subs["ゴーストデッキ"][1]:
        m = PAGE_RE.match(line)
        if m:
            pages.append((no, m.group(2), []))
        elif pages and line.startswith((" ", "\t")) and line.strip():
            pages[-1][2].append(line)
    if not pages:
        res.error(f"{name} ゴーストデッキ", "ページ（番号付きの見出し）がありません")
        return
    if len(pages) < 3:
        res.warn(f"{name} ゴーストデッキ", f"ページが {len(pages)} 枚です")
    for no, headline, children in pages:
        where = f"line {no}"
        if not ids_in(headline + " " + " ".join(children)):
            res.error(where, f"{name} の見出しに [ID] がありません: {plain(headline)[:40]}")
        problem = headline_problem(headline)
        if problem:
            res.error(where, f"{name}: {problem}（{plain(headline)[:40]}）")
            continue
        if not TAG_RE.sub("", headline).rstrip().endswith("。"):
            res.warn(where, f"{name}: 見出しが「。」で終わっていません。文になっているか確かめてください")
        if not PARTICLES.search(plain(headline)):
            res.warn(where, f"{name}: 見出しに助詞がありません。名詞の羅列になっていないか確かめてください")
        if sentence_count(headline) > 1:
            res.warn(where, f"{name}: 見出しが {sentence_count(headline)} 文あります。1 ページ 1 主張にしてください")
    if key_ids and not (ids_in(pages[0][1] + " " + " ".join(pages[0][2])) & key_ids):
        res.warn(f"line {pages[0][0]}", f"{name} の 1 ページ目が一言でと同じ ID を含みません。結論が最初に来ているか確かめてください")


def check(text: str, final: bool) -> Result:
    res = Result()
    raw = text.splitlines()
    lines: list[tuple[int, str]] = []
    in_code = False
    for no, line in enumerate(raw, start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append((no, line))
    if not any(line.startswith("# ") for _, line in lines):
        res.error("line 1", "表題（# 見出し）がありません")
    h2 = split_sections(lines, 2)
    if not h2:
        res.error("全体", "節（## 見出し）がありません")
        return res
    # 1. 統治メッセージが最初
    if GOVERNING not in h2[0][0]:
        res.error(f"line {h2[0][1]}", f"最初の節が「{GOVERNING}」ではありません（{h2[0][0]}）。結論を先頭に置いてください")
    gov = next((s for s in h2 if GOVERNING in s[0]), None)
    lead = ""
    if gov is None:
        res.error("全体", f"「## {GOVERNING}」がありません")
    else:
        no, msg = first_text(gov[2])
        if not msg or is_unknown(msg):
            (res.error if final else res.warn)(f"line {gov[1]}", "統治メッセージが未決定（—）です。レーンを決めてから書きます")
        elif sentence_count(msg) != 1:
            res.error(f"line {no}", f"統治メッセージは一文にしてください（{sentence_count(msg)} 文あります）")
        lead_line = next(((n, LEAD_RE.search(l)) for n, l in gov[2] if LEAD_RE.search(l)), None)
        if lead_line is None:
            res.error(f"line {gov[1]}", "「前に出すレーン:」の行がありません")
        else:
            n, m = lead_line
            value = m.group(1)
            lane = re.search(r"レーン\s*([12１２])", value)
            if not lane:
                (res.error if final else res.warn)(f"line {n}", "前に出すレーンが未決定です。マネージャーに決めてもらい D- に記録します")
            else:
                lead = lane.group(1).translate(str.maketrans("１２", "12"))
                if not re.search(r"D-\d{3,}", value):
                    res.error(f"line {n}", "前に出すレーンに決定の ID（[D-xxx]）がありません")
    # 3. 両レーン
    lanes: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    order: list[str] = []
    for title, no, body in h2:
        m = LANE_RE.match("## " + title)
        if m:
            key = m.group(1).translate(str.maketrans("１２", "12"))
            lanes[key] = (no, body)
            order.append(key)
    for key in ("1", "2"):
        if key not in lanes:
            res.error("全体", f"「## レーン{key}」がありません。二本のレーンで書きます")
    if lead and order and order[0] != lead:
        res.warn(f"line {lanes[order[0]][0]}", f"前に出すレーン{lead} を先に置いてください")
    for key in sorted(lanes):
        check_lane(f"レーン{key}", lanes[key][1], res)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyline")
    ap.add_argument("--final", action="store_true", help="未決定の — をエラーにする")
    args = ap.parse_args()
    path = Path(args.storyline)
    if not path.exists():
        print(f"{path} がありません", file=sys.stderr)
        return 1
    res = check(path.read_text(encoding="utf-8-sig"), args.final)
    out = [
        "# outline-check 結果",
        "",
        f"- ファイル: {path}" + ("（--final）" if args.final else ""),
        f"- **エラー: {len(res.errors)} 件** / 警告: {len(res.warnings)} 件",
        "",
    ]
    for title, items in (("## エラー", res.errors), ("## 警告", res.warnings)):
        if items:
            out += [title, "", "| 場所 | 内容 |", "|------|------|"]
            out += [f"| {w} | {m} |" for w, m in items]
            out.append("")
    print("\n".join(out))
    return 1 if res.errors else 0


if __name__ == "__main__":
    sys.exit(main())
