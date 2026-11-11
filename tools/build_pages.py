#!/usr/bin/env python3
"""記事ページ（articles/<番号>.html）を生成する。

- 対象は drafts.json に下書きがある作品だけ（概要のない作品の薄いページは作らない）
- 各記事が固有URLを持つ形にする（検索・AdSense・シェアのため）
- next_draft.py / set_impression.py / publish.py の末尾からも呼ばれる

使い方:
  python3 tools/build_pages.py
"""
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
:root{--bg:#0d0c0a;--bg2:#14120e;--panel:#191611;--line:#2c2618;--ink:#f2ecdc;--muted:#a89e83;--faint:#6f6752;--accent:#e2a458;--accent2:#8a6a35;--serif:"Hiragino Mincho ProN","Yu Mincho",serif;--sans:"Hiragino Kaku Gothic ProN","Hiragino Sans","Noto Sans JP",sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:17px;line-height:1.95}
a{color:var(--accent)}
header.site{border-bottom:1px solid var(--line);padding:16px 20px}
.brand{font-family:var(--serif);font-weight:800;font-size:21px;color:var(--ink);text-decoration:none}
.brand b{color:var(--accent)}
.wrap{max-width:760px;margin:0 auto;padding:36px 20px 70px}
.back{font-size:14px;color:var(--muted);text-decoration:none}
.date{font-size:12px;letter-spacing:.2em;color:var(--accent);font-weight:900;margin-top:26px}
h1{font-family:var(--serif);font-size:36px;font-weight:800;line-height:1.45;margin:8px 0 4px}
.meta{color:var(--muted);font-size:15px;margin-bottom:10px}
h2{font-family:var(--serif);font-size:22px;margin:30px 0 10px;padding-left:10px;border-left:3px solid var(--accent)}
p{color:#d8d1bf;font-size:17px;margin-bottom:15px}
p strong{color:var(--ink)}
.src{font-size:13px;color:var(--faint);margin-top:8px}
.facts{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 20px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;font-size:15px}
.facts dt{color:var(--faint);font-size:13px}
.facts dd{color:var(--ink)}
.empty{border:1px dashed var(--accent2);border-radius:12px;padding:16px 18px;color:var(--accent);font-size:15px;background:rgba(226,164,88,.05)}
.warn{color:#d98c8c;font-size:14px;margin-bottom:10px}
h2.spaced{margin-top:58px}
.hero{width:100%;height:auto;border-radius:16px;border:1px solid var(--line);margin:16px 0 4px;display:block}
.divider{display:block;width:230px;max-width:60%;margin:38px auto 2px;opacity:.85}
footer.site{border-top:1px solid var(--line);padding:30px 20px 40px;text-align:center;color:var(--faint);font-size:14px}
@media(max-width:640px){h1{font-size:29px}.facts{grid-template-columns:1fr}}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}（{year}）の感想と考察｜シネマインプレッション</title>
<meta name="description" content="{title}（{year}年）のあらすじ、感想と考察。">
<style>{css}</style>
</head>
<body>
<header class="site"><a class="brand" href="../index.html">シネマ<b>インプレッション</b></a></header>
<main class="wrap">
<a class="back" href="../index.html">← トップへ戻る</a>
<div class="date">{date}</div>
<h1>{title}</h1>
<div class="meta">{year}年製作</div>
{hero}
<h2>あらすじ・概要</h2>
<p>{overview}</p>
<div class="src">出典：<a href="{source_url}">{source_name}</a>（事実情報を整理して記載）</div>
<h2>作品情報</h2>
<dl class="facts">{facts}</dl>
<h2 class="spaced">ネタバレあり｜詳しいあらすじ</h2>
<p class="warn">※ここから先は結末まで含むネタバレです。未見の方はご注意ください。</p>
{spoiler}
<div class="src">あらすじの出典：<a href="{source_url}">{source_name}</a>（事実情報を整理して記載）</div>
<img class="divider" src="../images/divider.svg" alt="">
<h2>感想</h2>
{impression}
{analysis_block}
</main>
<footer class="site">シネマインプレッション<br>映画の感想と考察を、1日1本ずつ。</footer>
</body>
</html>
"""


def esc(s):
    return html.escape(str(s), quote=True)


def para(text):
    if not text:
        return '<div class="empty">準備中です。</div>'
    body = esc(text)
    body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return "\n".join("<p>" + p.replace("\n", "<br>") + "</p>" for p in paras)


def load_films():
    with open(os.path.join(ROOT, "data.js"), encoding="utf-8") as f:
        raw = f.read()
    m = re.search(r"const FILMS = (\[.*\]);?\s*$", raw, re.S)
    return {str(f["no"]): f for f in json.loads(m.group(1))}


def build_all():
    films = load_films()
    with open(os.path.join(ROOT, "drafts.json"), encoding="utf-8") as f:
        drafts = json.load(f)
    outdir = os.path.join(ROOT, "articles")
    os.makedirs(outdir, exist_ok=True)
    made = []
    for no, d in drafts.items():
        film = films.get(no)
        if not film:
            continue
        facts = "".join(
            f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in d.get("facts", [])
        )
        hero = ""
        if os.path.exists(os.path.join(ROOT, "images", f"{no}.svg")):
            hero = f'<img class="hero" src="../images/{no}.svg" alt="{esc(film["title"])}のイラスト">'
        page = TEMPLATE.format(
            hero=hero,
            title=esc(film["title"]),
            year=film["year"],
            css=CSS,
            date=esc(d["date"] + " 公開") if d.get("date") else "REVIEW",
            overview=esc(d.get("overview", "")),
            source_name=esc(d["source"][0]) if d.get("source") else "",
            source_url=esc(d["source"][1]) if d.get("source") else "#",
            facts=facts,
            impression=para(d.get("impression")),
            analysis_block=("<h2>考察</h2>\n" + para(d.get("analysis"))) if (d.get("analysis") or "").strip() else "",
            spoiler=para(d.get("spoiler_overview")),
        )
        with open(os.path.join(outdir, f"{no}.html"), "w", encoding="utf-8") as f:
            f.write(page)
        made.append(no)
    return made


def main():
    made = build_all()
    print(f"記事ページを生成しました: {', '.join(sorted(made))}（{len(made)}本）")


if __name__ == "__main__":
    main()
