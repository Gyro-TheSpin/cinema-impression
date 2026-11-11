#!/usr/bin/env python3
"""編集済みの感想・考察を記事（drafts.json）に反映する。

入力ファイル（Markdown）の形式:
    ## 感想
    （編集済みの感想テキスト）

    ## 考察
    （編集済みの考察テキスト。なければ省略可）

ルール:
- ここに入れるのは「編集済み」の文章だけ。音声の文字起こし原文は入れない
  （原文は impressions/<no>.raw.txt に別保存する）。
- 対象の映画に概要の下書き（drafts.json のエントリ）が無い場合はエラーにする。

使い方:
  python3 tools/set_impression.py --no 571 --file impressions/571.md
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_sections(text):
    sections = {}
    current = None
    buf = []
    for line in text.splitlines():
        m = re.match(r"^##\s*(感想|考察)\s*$", line)
        if m:
            if current:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1)
            buf = []
        elif current:
            if line.strip().startswith("<!--"):
                continue
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


def emit_js(drafts):
    with open(os.path.join(ROOT, "drafts.js"), "w", encoding="utf-8") as f:
        f.write(
            "// 記事の下書き（概要・作品情報・感想・考察）。tools が drafts.json から生成する。手で編集しない。\n"
        )
        f.write("const DRAFTS = " + json.dumps(drafts, ensure_ascii=False, indent=2) + ";\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no", required=True, help="キュー番号（例: 571）")
    ap.add_argument("--file", required=True, help="編集済みMarkdownのパス")
    args = ap.parse_args()

    drafts_path = os.path.join(ROOT, "drafts.json")
    with open(drafts_path, encoding="utf-8") as f:
        drafts = json.load(f)
    entry = drafts.get(str(args.no))
    if entry is None:
        sys.exit(
            f"#{args.no} の概要下書きがまだありません。先に next_draft.py で概要を作ってください。"
        )
    with open(args.file, encoding="utf-8") as f:
        sections = parse_sections(f.read())
    if not sections.get("感想"):
        sys.exit("「## 感想」セクションが空です。編集済みの感想を入れてください。")
    entry["impression"] = sections["感想"]
    if sections.get("考察"):
        entry["analysis"] = sections["考察"]
    with open(drafts_path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)
    emit_js(drafts)
    import build_pages
    build_pages.build_all()
    print(f"#{args.no} に感想（{len(entry['impression'])}字）"
          + (f"・考察（{len(entry['analysis'])}字）" if entry.get("analysis") else "")
          + "を反映しました")


if __name__ == "__main__":
    main()
