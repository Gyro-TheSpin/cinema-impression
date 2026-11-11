#!/usr/bin/env python3
"""記事を公開状態にする。

公開の条件（ガード）:
- 概要の下書きがあること
- 編集済みの感想が入っていること（感想なしでは公開できない）

処理:
- drafts.json の該当エントリに published=true と公開日（JST、--date で上書き可）を付ける
- queue CSV の status を published に更新する
- drafts.js を再生成する

使い方:
  python3 tools/publish.py --no 571
  python3 tools/publish.py --no 571 --date 2026-11-12
"""
import argparse
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_queue():
    for c in [
        os.path.join(ROOT, "data", "queue.csv"),
        os.path.join(ROOT, "..", "filmarks-queue", "filmarks_watched_queue.csv"),
    ]:
        if os.path.exists(c):
            return os.path.normpath(c)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no", required=True)
    ap.add_argument("--date", default=None, help="公開日 YYYY-MM-DD（既定: 今日 JST）")
    args = ap.parse_args()
    date = args.date or datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d")

    drafts_path = os.path.join(ROOT, "drafts.json")
    with open(drafts_path, encoding="utf-8") as f:
        drafts = json.load(f)
    entry = drafts.get(str(args.no))
    if entry is None:
        sys.exit(f"#{args.no} の概要下書きがありません。公開できません。")
    if not entry.get("impression"):
        sys.exit(
            f"#{args.no} には編集済みの感想が入っていません。感想なしでは公開できません。"
            " impressions/<no>.md を編集して set_impression.py で反映してください。"
        )
    entry["published"] = True
    entry["date"] = date
    with open(drafts_path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "drafts.js"), "w", encoding="utf-8") as f:
        f.write(
            "// 記事の下書き（概要・作品情報・感想・考察）。tools が drafts.json から生成する。手で編集しない。\n"
        )
        f.write("const DRAFTS = " + json.dumps(drafts, ensure_ascii=False, indent=2) + ";\n")

    queue_path = find_queue()
    if queue_path:
        with open(queue_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            fieldnames = list(rows[0].keys())
        for r in rows:
            if r["queue_no"] == str(args.no):
                r["status"] = "published"
        with open(queue_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    import build_pages
    build_pages.build_all()
    print(f"#{args.no} を {date} 付で公開状態にしました")


if __name__ == "__main__":
    main()
