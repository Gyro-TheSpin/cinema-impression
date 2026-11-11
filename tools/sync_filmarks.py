#!/usr/bin/env python3
"""Filmarksの公開「観た映画」一覧とキューの差分同期（週1回想定）。

- https://filmarks.com/users/movie_taro_/marks をページ送りで全件取得し、
  タイトル＋製作年が data/queue.csv にないものを末尾（新しい queue_no）に追加する。
- 追加分は queue_no が最大側になるため、投稿順（降順）では先に下書きされる。
- data.js（サイトの一覧データ）もキューから作り直す。
- 取得や解析に失敗した場合はキューを変更せず、警告だけ出して正常終了する
  （毎日の下書き作成を止めないため）。
"""
import csv
import html as h
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER = "movie_taro_"
BASE = f"https://filmarks.com/users/{USER}/marks"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
CARD_RE = re.compile(r'<h3 class="c-content-card__title"><a href="/movies/\d+#mark-\d+">(.*?)<span>\((\d{4})年製作の映画\)</span></a></h3>', re.S)
MAX_PAGES = 60


def match_key(title, year):
    """表記ゆれ（全角/半角スペース、HTMLエンティティ、波ダッシュ）を吸収した照合キー"""
    s = h.unescape(str(title))
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("〜", "~")
    s = re.sub(r"\s+", "", s)
    return (s, int(year))


def fetch_page(page):
    req = urllib.request.Request(f"{BASE}?page={page}", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_all():
    films = []  # (title, year, page)
    for page in range(1, MAX_PAGES + 1):
        html = fetch_page(page)
        cards = CARD_RE.findall(html)
        if not cards:
            break
        for title, year in cards:
            films.append((re.sub(r"<[^>]+>", "", title).strip(), int(year), page))
        if len(cards) < 36:
            break
        time.sleep(1)
    return films


def rebuild_data_js(rows):
    ordered = sorted(rows, key=lambda r: -int(r["queue_no"]))
    films = [
        {"no": int(r["queue_no"]), "title": r["title"], "year": int(r["year"]), "order": i + 1}
        for i, r in enumerate(ordered)
    ]
    body = "// Filmarksキュー（data/queue.csv）から生成。下から＝queue_no降順が投稿順。\n"
    body += "const FILMS = " + json.dumps(films, ensure_ascii=False, indent=1) + ";\n"
    with open(os.path.join(ROOT, "data.js"), "w", encoding="utf-8") as f:
        f.write(body)


def main():
    queue_path = os.path.join(ROOT, "data", "queue.csv")
    with open(queue_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())
    try:
        films = fetch_all()
    except Exception as e:
        print(f"[sync_filmarks] 取得に失敗したため同期をスキップ: {e}")
        return 0
    if len(films) < 100:
        print(f"[sync_filmarks] 取得件数が想定より少ない ({len(films)}件) ため同期をスキップ")
        return 0
    known = {match_key(r["title"], r["year"]) for r in rows}
    next_no = max(int(r["queue_no"]) for r in rows)
    added = []
    seen_new = set()
    for title, year, page in films:
        title = h.unescape(title)
        key = match_key(title, year)
        if key in known or key in seen_new:
            continue
        seen_new.add(key)
        next_no += 1
        row = {k: "" for k in fields}
        row.update({"queue_no": str(next_no), "title": title, "year": str(year),
                    "status": "pending", "source_page": str(page)})
        rows.append(row)
        added.append(row)
    if added:
        with open(queue_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        rebuild_data_js(rows)
        for r in added:
            print(f"[sync_filmarks] 追加: #{r['queue_no']} {r['title']} ({r['year']})")
    print(f"[sync_filmarks] Filmarks全{len(films)}件 / 新規追加 {len(added)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
