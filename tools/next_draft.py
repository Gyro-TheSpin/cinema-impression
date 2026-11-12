#!/usr/bin/env python3
"""1日1本だけ、キューの下から次の映画の「概要・作品情報」下書きを作る。

設計（合意済み）:
- 投稿ペースは1日1本。大量生成はAdSense/検索の量産判定リスクがあるため、
  このスクリプトは1回の実行で BATCH 本（既定3）しか処理しない。
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
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 1回の実行で作る下書きの本数。2026-11-12 にユーザーの指示で 1日3本へ変更。
# ワークフロー側の旧 BATCH 環境変数は廃止（DAILY_BATCH で上書き可）。
BATCH = int(os.environ.get("DAILY_BATCH", "3"))


def find_queue():
    candidates = [
        os.path.join(ROOT, "data", "queue.csv"),
        os.path.join(ROOT, "..", "filmarks-queue", "filmarks_watched_queue.csv"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.normpath(c)
    raise SystemExit("queue CSV が見つかりません: " + " / ".join(candidates))


def _search_pages(title, limit=5, intro_only=True):
    """Wikipedia検索の候補ページを検索順で返す。"""
    api = "https://ja.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": "1",
        "inprop": "url",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{title} 映画",
        "gsrlimit": str(limit),
    }
    if intro_only:
        params["exintro"] = "1"
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "movie-blog-draft/1.0 (personal project)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    pages = (data.get("query") or {}).get("pages") or {}
    return sorted(pages.values(), key=lambda p: p.get("index", 99))


def _pick_page(pages, year, title=None):
    """候補ページの誤爆（同名の別作品・続編）を避けて選ぶ。

    優先順: ①ページタイトルが作品名と一致 ②リード文の最初の年が目標年±1
    （公開年の地域差を許容） ③検索順の先頭。
    """
    if title:
        for p in pages:
            if p.get("title") == title:
                return p
    for p in pages:
        m = re.search(r"(\d{4})年", p.get("extract") or "")
        if m and abs(int(m.group(1)) - int(year)) <= 1:
            return p
    return pages[0] if pages else None


def _page_by_title(title, intro_only=True):
    """タイトル完全一致でページを直接引く（曖昧さ回避ページは None）。"""
    api = "https://ja.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": "1",
        "inprop": "url",
        "format": "json",
        "titles": title,
        "redirects": "1",
    }
    if intro_only:
        params["exintro"] = "1"
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "movie-blog-draft/1.0 (personal project)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    for p in pages.values():
        if "missing" in p:
            return None
        ex = p.get("extract") or ""
        if not ex.strip() or "曖昧さ回避" in ex[:200]:
            return None
        return p
    return None


def wiki_summary(title, year):
    """日本語版 Wikipedia で作品ページを探し、リード文とURLと基本情報を返す。"""
    page = _page_by_title(title, intro_only=True)
    if page is None:
        pages = _search_pages(title, limit=5, intro_only=True)
        if not pages:
            return None
        page = _pick_page(pages, year, title)
    extract = (page.get("extract") or "").strip()
    return {"extract": extract, "url": page.get("fullurl", ""), "page_title": page.get("title", "")}


def _unwrap_templates(v):
    """データを持つテンプレートを先に展開する（中身ごと消えるのを防ぐ）。"""
    v = re.sub(r"\{\{仮リンク\|([^|{}]+)(?:\|[^{}]*)?\}\}", r"\1", v)
    def _ub(m):
        args = [a for a in m.group(1).split("|") if "=" not in a]
        return "\n".join(args)
    v = re.sub(r"\{\{(?:Unbulleted list|Plainlist|plainlist)\|([^{}]*)\}\}", _ub, v)
    return v


def _clean_wiki_value(v):
    v = _unwrap_templates(v)
    prev = None
    while prev != v:  # テンプレート除去（入れ子対応で内側から繰り返す）
        prev = v
        v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)  # [[a|b]]→b, [[a]]→a
    v = re.sub(r"<[^>]+>", "\n", v)  # <br> 等は区切りに
    v = re.sub(r"'{2,3}", "", v)
    parts = [p.strip(" *　") for p in v.split("\n")]
    parts = [p for p in parts if p]
    return parts


def wiki_facts(page_title):
    """Wikipedia の Infobox から作品情報（監督・出演など）を抽出する。失敗したら空リスト。"""
    api = "https://ja.wikipedia.org/w/api.php"
    params = {"action": "parse", "page": page_title, "prop": "wikitext", "format": "json", "redirects": "1"}
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "movie-blog-draft/1.0 (personal project)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        wikitext = ((data.get("parse") or {}).get("wikitext") or {}).get("*", "")
    except Exception:
        return []
    fields = {}
    for m in re.finditer(r"^\|[ \t]*([^=|\n]+?)[ \t]*=[ \t]*(.*)$", wikitext, re.M):
        fields[m.group(1).strip()] = m.group(2).strip()
    facts = []
    def add(label, keys, limit=None, joiner="、"):
        for k in keys:
            if k in fields:
                parts = _clean_wiki_value(fields[k])
                if limit:
                    parts = parts[:limit]
                if parts:
                    facts.append([label, joiner.join(parts)])
                return
    add("監督", ["監督"])
    add("脚本", ["脚本"])
    add("原作", ["原作"])
    add("出演", ["出演者", "出演"], limit=6)
    add("音楽", ["音楽"])
    if "公開" in fields:
        m = re.search(r"\{\{Film date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", fields["公開"]) or re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", fields["公開"])
        if m:
            facts.append(["公開", f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日"])
    if "上映時間" in fields:
        m = re.search(r"(\d+)\s*分", fields["上映時間"])
        if m:
            facts.append(["上映時間", f"{m.group(1)}分"])
    add("製作国", ["製作国"])
    return facts


NEXT_HEADINGS = ["登場人物", "キャスト", "声の出演", "スタッフ", "制作", "製作", "公開", "評価", "興行成績", "脚注", "出典", "関連項目", "外部リンク", "主題歌", "音楽"]


def wiki_plot(title, year=None):
    """Wikipedia全文から「あらすじ」セクション（結末まで含む）を切り出す。見つからなければ None。"""
    page = _page_by_title(title, intro_only=False)
    if page is None:
        try:
            pages = _search_pages(title, limit=5, intro_only=False)
        except Exception:
            return None
        if not pages:
            return None
        page = _pick_page(pages, year, title) if year else pages[0]
    text = page.get("extract") or ""
    lines = [ln.strip() for ln in text.splitlines()]

    def heading(ln):
        # Wikipediaのexplaintextは見出しを "== ストーリー ==" の形で返すため
        # "=" と空白を除いて見出し名だけを取り出す
        return ln.strip("= ").strip()

    start = None
    for i, ln in enumerate(lines):
        if heading(ln) in ("あらすじ", "ストーリー", "物語", "プロット"):
            start = i + 1
            break
    if start is None:
        return None
    body = []
    for ln in lines[start:]:
        if heading(ln) in NEXT_HEADINGS:
            break
        if ln:
            body.append(ln)
    plot = "".join(body).strip()
    return plot[:4000] if len(plot) >= 80 else None


def summarize_spoiler_with_gemini(title, plot):
    """GEMINI_API_KEY があるとき、結末まで含む詳しいあらすじを事実だけで整形する。"""
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not plot:
        return None
    prompt = (
        "次のWikipediaのあらすじをもとに、映画『"
        + title
        + "』の詳しいあらすじを600字程度の日本語で書いてください。"
        "結末まで含めてよい（ネタバレ記事用）。事実を変えたり、書かれていない内容を足したりしないこと。"
        "感想や評価は書かないこと。\n\n"
        + plot[:4000]
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  Gemini整形（ネタバレ）に失敗（原文で代替）: {e}", file=sys.stderr)
        return None


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
    # 週1回（月曜 JST）だけ Filmarks と差分同期する。失敗しても下書き作成は続ける。
    try:
        import datetime as _dt
        import subprocess as _sp
        _jst = _dt.timezone(_dt.timedelta(hours=9))
        if _dt.datetime.now(_jst).weekday() == 0 or os.environ.get("SYNC_FILMARKS"):
            _sp.run([sys.executable, os.path.join(ROOT, "tools", "sync_filmarks.py")],
                    timeout=900, check=False)
    except Exception as _e:
        print(f"[next_draft] Filmarks同期をスキップ: {_e}")
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
        draft = {
            "overview": overview,
            "facts": [["製作年", f"{t['year']}年"]] + wiki_facts(info["page_title"]),
            "source": [f"Wikipedia「{info['page_title']}」", info["url"]],
        }
        plot = wiki_plot(t["title"], t["year"])
        if plot:
            draft["spoiler_overview"] = (
                summarize_spoiler_with_gemini(t["title"], plot) or first_sentences(plot, limit=1500)
            )
        drafts[str(t["queue_no"])] = draft
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
