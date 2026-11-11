#!/usr/bin/env python3
"""1日1本だけ、キューの下から次の映画の「概要・作品情報」下書きを作る。

設計（合意済み）:
- 投稿ペースは1日1本。大量生成はAdSense/検索の量産判定リスクがあるため、
  このスクリプトは1回の実行で BATCH 本（既定1）しか処理しない。
- 対象は queue CSV のうち status=pending で queue_no が最大のもの（＝キューの下）。
- 概要は Wikipedia API のリード文（extract）を取得し、
  GEMINI_API_KEY があれば Gemini で「事実を変えずに短くまとめた概要」に整形、
  なければ extract の冒頭文をそのまま下書きにする（どちらも出典を明記）。
- 感想・考察は生成しない。本人が書く。
- 処理した作品は queue CSV の status を drafted に更新し、drafts.json に追加、
  サイト表示用の drafts.js を再生成する。

使い方:
  python3 tools/next_draft.py             # 次の1本を処理
  python3 tools/next_draft.py --dry-run   # 次の対象を表示するだけ（取得・書き込みなし）
  BATCH=1 python3 tools/next_draft.py     # 1回の処理本数（既定1、増やすのは非推奨）

ファイル配置（リポジトリ化したときの想定）:
  data/queue.csv   … キュー（なければ ../filmarks-queue/filmarks_watched_queue.csv を探す）
  drafts.json      … このスクリプトと同じ階層（サイトルート）
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = int(os.environ.get("BATCH", "1"))


def find_queue():
    candidates = [
        os.path.join(ROOT, "data", "queue.csv"),
        os.path.join(ROOT, "..", "filmarks-queue", "filmarks_watched_queue.csv"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.normpath(c)
    raise SystemExit("queue CSV が見つかりません: " + " / ".join(candidates))


def wiki_summary(title, year):
    """日本語版 Wikipedia で作品ページを探し、リード文とURLと基本情報を返す。"""
    api = "https://ja.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": "1",
        "exintro": "1",
        "inprop": "url",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{title} 映画",
        "gsrlimit": "1",
    }
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "movie-blog-draft/1.0 (personal project)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    pages = (data.get("query") or {}).get("pages") or {}
    if not pages:
        return None
    page = next(iter(pages.values()))
    extract = (page.get("extract") or "").strip()
    return {"extract": extract, "url": page.get("fullurl", ""), "page_title": page.get("title", "")}


def summarize_with_gemini(title, extract):
    """GEMINI_API_KEY があるときだけ、事実を変えずに概要を短く整形する。失敗したら None。"""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not extract:
        return None
    prompt = (
        "次のWikipediaのリード文をもとに、映画『"
        + title
        + "』のあらすじ・概要を200字程度の日本語で書いてください。"
        "事実（人名・設定・結末の有無）を変えたり、書かれていない内容を足したりしないこと。"
        "ネタバレになる結末には触れないこと。感想や評価は書かないこと。\n\n"
        + extract[:3000]
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="
        + key,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # 整形に失敗しても下書き自体は止めない
        print(f"  Gemini整形に失敗（extractで代替）: {e}", file=sys.stderr)
        return None


def first_sentences(text, limit=350):
    out = ""
    for part in text.replace("\n", " ").split("。"):
        if not part.strip():
            continue
        out += part.strip() + "。"
        if len(out) >= limit:
            break
    return out


def main():
    dry_run = "--dry-run" in sys.argv
    queue_path = find_queue()
    drafts_path = os.path.join(ROOT, "drafts.json")

    with open(queue_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())
    drafts = {}
    if os.path.exists(drafts_path):
        with open(drafts_path, encoding="utf-8") as f:
            drafts = json.load(f)

    pending = [
        r
        for r in rows
        if r["status"] == "pending" and str(r["queue_no"]) not in drafts
    ]
    pending.sort(key=lambda r: -int(r["queue_no"]))  # キューの下から
    targets = pending[:BATCH]
    if not targets:
        print("対象なし（キューは全て処理済み）")
        return
    for t in targets:
        print(f"対象: #{t['queue_no']} {t['title']} ({t['year']})")
    if dry_run:
        print("--dry-run のため取得・書き込みはしません")
        return

    for t in targets:
        info = wiki_summary(t["title"], t["year"])
        if not info or not info["extract"]:
            print(f"  Wikipediaで見つからず、スキップ（status据え置き）: {t['title']}")
            continue
        overview = summarize_with_gemini(t["title"], info["extract"]) or first_sentences(
            info["extract"]
        )
        drafts[str(t["queue_no"])] = {
            "overview": overview,
            "facts": [["製作年", f"{t['year']}年"]],
            "source": [f"Wikipedia「{info['page_title']}」", info["url"]],
        }
        t["status"] = "drafted"
        print(f"  下書きを作成: {t['title']}")

    with open(queue_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    with open(drafts_path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "drafts.js"), "w", encoding="utf-8") as f:
        f.write(
            "// 記事の下書き（概要・作品情報）。tools/next_draft.py が drafts.json から生成する。手で編集しない。\n"
        )
        f.write("const DRAFTS = " + json.dumps(drafts, ensure_ascii=False, indent=2) + ";\n")
    print("drafts.json / drafts.js / queue を更新しました")
    import build_pages
    made = build_pages.build_all()
    print(f"記事ページを生成しました: {len(made)}本")


if __name__ == "__main__":
    main()
