#!/usr/bin/env python3
"""記事ページ（articles/<番号>.html）を生成する。

- 対象は drafts.json に下書きがある作品だけ（概要のない作品の薄いページは作らない）
- 各記事が固有URLを持つ形にする（検索・AdSense・シェアのため）
- デザインは「案D改」（夜の野外シネマ＋ジャーナル）でトップと統一
- drafts.json に intro（紹介ボックス）がある記事は、アイキャッチ直下に
  ネタバレなしの紹介ボックスを出す
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
:root{--paper:#fffdf4;--cream:#fff8e6;--ink:#2b2b26;--muted:#7a7563;--yellow:#ffcf3f;--green:#58a05c;--green-d:#3d7a44;--red:#c22f2f;--curtain:#a02323;--night:#1d2440;--round:"M PLUS Rounded 1c",sans-serif;--sans:"Zen Kaku Gothic New",sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{background:#23263a;color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.85;-webkit-font-smoothing:antialiased}
a{color:var(--green-d)}
.sheet{max-width:960px;margin:0 auto;background:var(--paper);padding:0 clamp(20px,5vw,56px) 60px;box-shadow:0 4px 24px rgba(0,0,0,.45);min-height:100vh}
.js .rv{opacity:0;transform:translateY(22px);transition:opacity .7s ease,transform .7s ease}
.js .rv.in{opacity:1;transform:none}
header.site{display:flex;align-items:center;gap:14px;padding:20px 0 14px}
.logo{font-family:var(--round);font-weight:800;font-size:24px;color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:10px}
.logo .reel{width:34px;height:34px;flex:none;animation:spin 14s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
header.site nav{margin-left:auto;font-family:var(--round);font-weight:700;font-size:14px}
header.site nav a{color:var(--ink);text-decoration:none}
header.site nav .en{display:block;font-size:10px;letter-spacing:.22em;color:var(--muted);text-align:center}
.crumb{font-size:12.5px;color:var(--muted);padding-top:14px}
.crumb a{color:var(--muted)}
.j-head{margin-top:18px}
.j-head .row1{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px}
.j-head .spoiler{border:2px solid var(--red);color:var(--red);font-weight:900;font-size:12px;border-radius:999px;padding:2px 12px}
.j-head .date{color:var(--muted)}
.j-head h1{font-family:var(--round);font-weight:800;font-size:clamp(28px,4.8vw,40px);line-height:1.5;margin-top:12px;line-break:strict}
.j-head .meta{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin-top:10px}
.a-kv{margin-top:24px;border:2.5px solid var(--ink);border-radius:22px;overflow:hidden;position:relative;background:var(--night);line-height:0}
.a-kv img{width:100%;height:auto;display:block}
.a-kv iframe{width:100%;aspect-ratio:16/9;display:block;border:0;background:#000}
.trailer-note{font-size:11.5px;color:var(--muted);text-align:right;margin-top:6px}
article.body h2{font-family:var(--round);font-weight:800;font-size:22px;margin:42px 0 12px;display:flex;align-items:center;gap:11px}
article.body h2 .ic{width:26px;height:26px;flex:none}
article.body p{font-size:16.5px;line-height:1.95;color:#33322b;margin-bottom:14px}
article.body p strong{color:var(--ink)}
article.body h3{font-family:var(--round);font-weight:700;font-size:19px;margin:30px 0 8px;line-break:strict}
.src{font-size:12.5px;color:var(--muted)}
.src a{color:var(--muted)}
.factbox{background:#fff;border:2px solid var(--ink);border-radius:18px;padding:8px 22px}
.factbox .fr{display:grid;grid-template-columns:150px 1fr;gap:4px 16px;padding:9px 0;border-bottom:1.6px dashed #d8d2ba;font-size:14.5px}
.factbox .fr:last-child{border-bottom:none}
@media(max-width:640px){.factbox .fr{grid-template-columns:1fr}}
.factbox dt{color:var(--muted);font-size:13px;font-weight:700}
.spoil{margin:4px 0 14px;background:#fdeceb;border:2px solid var(--red);border-radius:14px;padding:12px 16px;font-size:14.5px;font-weight:700;color:#8c2d24}
.empty{border:2px dashed var(--green-d);border-radius:14px;padding:14px 16px;color:var(--green-d);font-size:14.5px;background:#eef6ee}
.introbox{background:#eef6ee;border:2.5px solid var(--green-d);border-radius:20px;padding:22px 24px;margin:28px 0 6px}
.introbox .ib-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.introbox .ib-head .t{font-family:var(--round);font-weight:800;font-size:18.5px}
.introbox .ns{margin-left:auto;background:#fff;border:1.6px solid var(--green-d);color:var(--green-d);border-radius:999px;font-size:11.5px;font-weight:900;padding:2px 11px}
.introbox .ib-lead{font-weight:900;font-size:16px;margin-top:9px;line-height:1.8}
.introbox .ib-cols{display:grid;grid-template-columns:1fr 1fr;gap:8px 26px;margin-top:14px}
@media(max-width:640px){.introbox .ib-cols{grid-template-columns:1fr}}
.introbox h4{font-size:12.5px;font-weight:900;letter-spacing:.08em;color:var(--green-d);margin-bottom:3px}
.introbox ul{list-style:none;font-size:14px;line-height:1.8}
.introbox li{padding:2px 0 2px 19px;position:relative}
.introbox li::before{content:"✓";position:absolute;left:0;color:var(--red);font-weight:900}
.introbox .ib-watch{margin-top:14px;border-top:1.6px dashed #b9cdb9;padding-top:11px;font-size:13.5px;color:var(--muted)}
.endnote{text-align:center;font-size:13px;color:var(--muted);margin-top:38px;font-family:var(--round);font-weight:700}
footer.site{margin-top:56px;text-align:center}
footer.site .fl{font-family:var(--round);font-weight:800;font-size:21px}
footer.site .fm{font-size:12.5px;color:var(--muted);margin-top:6px}
footer.site .fm a{color:var(--muted);text-decoration:underline}
#toTop{position:fixed;right:18px;bottom:18px;z-index:50;background:var(--night);color:#fff8e6;border:2px solid var(--yellow);border-radius:999px;font-family:var(--round);font-weight:800;font-size:12.5px;padding:9px 16px;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .4s ease}
#toTop.show{opacity:1;pointer-events:auto}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{animation:none !important;transition:none !important}.js .rv{opacity:1;transform:none}}
"""

ICON_LEAF = '<svg class="ic" viewBox="0 0 26 26" aria-hidden="true"><path d="M13 24 C4 18 3 8 6 2 C14 3 23 6 24 12 C25 19 19 23 13 24Z" fill="#58a05c" stroke="#2b2b26" stroke-width="1.8"/></svg>'
ICON_REEL = '<svg class="ic" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="10" fill="#ffcf3f" stroke="#2b2b26" stroke-width="1.8"/><circle cx="13" cy="13" r="3.4" fill="#2b2b26"/></svg>'
ICON_BANG = '<svg class="ic" viewBox="0 0 26 26" aria-hidden="true"><rect x="4" y="4" width="18" height="18" rx="4" fill="#c22f2f" stroke="#2b2b26" stroke-width="1.8"/><text x="13" y="18.5" text-anchor="middle" font-size="12" font-weight="900" fill="#fff">!</text></svg>'
ICON_CROWN = '<svg class="ic" viewBox="0 0 26 26" aria-hidden="true"><path d="M5 21 L8 13 L13 18 L17 9 L21 21Z" fill="#f59a3c" stroke="#2b2b26" stroke-width="1.8" stroke-linejoin="round"/></svg>'
ICON_SCOPE = '<svg class="ic" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="10" fill="#aedce8" stroke="#2b2b26" stroke-width="1.8"/><path d="M8.5 17.5 L17.5 8.5" stroke="#2b2b26" stroke-width="2.2" stroke-linecap="round"/></svg>'
REEL_LOGO = '<svg class="reel" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="16.5" fill="#fffdf4" stroke="#2b2b26" stroke-width="2.6"/><circle cx="20" cy="20" r="3.6" fill="#2b2b26"/><g fill="#2b2b26"><circle cx="20" cy="10.5" r="3.4"/><circle cx="28.2" cy="24.8" r="3.4"/><circle cx="11.8" cy="24.8" r="3.4"/></g></svg>'

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}（{year}）の感想と考察｜山田太郎シネマ</title>
<meta name="description" content="{title}（{year}年）のあらすじ、作品情報、感想と考察。">
<meta property="og:type" content="article">
<meta property="og:site_name" content="山田太郎シネマ">
<meta property="og:title" content="{title}（{year}）の感想と考察｜山田太郎シネマ">
<meta property="og:description" content="{title}（{year}年）のあらすじ、作品情報、感想と考察。">
<meta property="og:url" content="https://gyro-thespin.github.io/cinema-impression/articles/{no}.html">
<script>document.documentElement.className += ' js';</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@500;700;800&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="sheet">
<header class="site">
  <a class="logo" href="../index.html">{reel_logo}山田太郎シネマ</a>
  <nav><a href="../index.html"><span class="en">TOP</span>トップへ戻る</a></nav>
</header>
<div class="crumb"><a href="../index.html">トップ</a> ＞ 感想ジャーナル ＞ {title}</div>
<div class="j-head">
  <div class="row1"><span class="spoiler">ネタバレあり</span><span class="date">{date}</span></div>
  <h1>{title}</h1>
  <div class="meta"><span>{year}年製作{runtime}</span><span>書いた人：山田太郎</span></div>
</div>
{hero}
<article class="body">
{intro_block}
<h2>{icon_leaf}あらすじ・概要</h2>
{overview}
<div class="src">出典：<a href="{source_url}" target="_blank" rel="noopener">{source_name}</a>（事実情報を整理して記載）</div>
<h2>{icon_reel}作品情報</h2>
<div class="factbox">{facts}</div>
<h2>{icon_bang}ネタバレあり｜詳しいあらすじ</h2>
<div class="spoil">ここから先は結末まで含むネタバレです。未見の方はご注意ください。</div>
{spoiler}
<div class="src">あらすじの出典：<a href="{source_url}" target="_blank" rel="noopener">{source_name}</a>（事実情報を整理して記載）</div>
<h2>{icon_crown}感想</h2>
{impression}
{analysis_block}
<div class="endnote">— 最後まで読んでくれて、ありがとうございました —</div>
</article>
<footer class="site">
  <div class="fl">山田太郎シネマ</div>
  <div class="fm">映画の感想と考察を、1日1本ずつ。 ・ <a href="../privacy.html">プライバシーポリシー</a></div>
</footer>
</div>
<button id="toTop" type="button">↑ トップへ</button>
<script>
(function(){
  var els = document.querySelectorAll('.rv');
  if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } });
    },{threshold:.12});
    els.forEach(function(e){io.observe(e);});
  } else { els.forEach(function(e){e.classList.add('in');}); }
  var btn = document.getElementById('toTop');
  addEventListener('scroll',function(){ btn.classList.toggle('show', scrollY > 600); },{passive:true});
  btn.addEventListener('click',function(){ scrollTo({top:0,behavior:'smooth'}); });
})();
</script>
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
    out = []
    for p in paras:
        if p.startswith("### "):
            out.append("<h3>" + p[4:].strip() + "</h3>")
        else:
            out.append("<p>" + p.replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def sentences(text):
    parts = re.split(r"(?<=。)", text)
    return [p for p in (x.strip() for x in parts) if p]


def regroup(text, per=2, min_split=0):
    """長い1段落を文単位で束ね直して段落に分ける（意味は変えない、改行だけ）"""
    if not text:
        return text
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if len(block) <= min_split:
            out.append(block)
            continue
        sents = sentences(block)
        if len(sents) <= per:
            out.append(block)
            continue
        for i in range(0, len(sents), per):
            out.append("".join(sents[i:i + per]))
    return "\n\n".join(out)


def impression_html(no, text):
    if not text:
        return para(text)
    blocks = [b.strip() for b in regroup(text, per=2, min_split=230).split("\n\n") if b.strip()]
    return "\n".join(para(b) for b in blocks)


def intro_block(d):
    intro = d.get("intro")
    if not intro or not intro.get("lead"):
        return ""
    rec = "\n".join(f"<li>{esc(x)}</li>" for x in intro.get("recommend", []))
    high = "\n".join(f"<li>{esc(x)}</li>" for x in intro.get("highlights", []))
    cols = ""
    if rec:
        cols += f'<div><h4>こんな人におすすめ</h4><ul>{rec}</ul></div>'
    if high:
        cols += f'<div><h4>見どころ</h4><ul>{high}</ul></div>'
    watch = ""
    links = intro.get("watch") or []
    if links:
        items = " ／ ".join(
            f'<a href="{esc(x.get("url", "#"))}" target="_blank" rel="noopener sponsored">{esc(x.get("label", ""))}</a>'
            for x in links
        )
        watch = f'<div class="ib-watch">観るなら：{items}</div>'
    return (
        '<div class="introbox rv">'
        '<div class="ib-head"><span class="t">この映画、こんな作品です</span>'
        '<span class="ns">ネタバレなし</span></div>'
        f'<div class="ib-lead">{esc(intro["lead"])}</div>'
        f'<div class="ib-cols">{cols}</div>'
        f"{watch}</div>"
    )


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
            f'<div class="fr"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in d.get("facts", [])
        )
        runtime = ""
        for k, v in d.get("facts", []):
            if k == "上映時間":
                runtime = f" ・ {esc(v)}"
        hero = ""
        trailer = (d.get("trailer") or "").strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", trailer):
            hero = (
                f'<figure class="a-kv rv"><iframe src="https://www.youtube-nocookie.com/embed/{esc(trailer)}" '
                f'title="{esc(film["title"])} 公式予告編" loading="lazy" '
                'allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen></iframe></figure>'
                '<div class="trailer-note">公式予告編（YouTube）</div>'
            )
        elif os.path.exists(os.path.join(ROOT, "images", f"{no}.svg")):
            hero = f'<figure class="a-kv rv"><img src="../images/{no}.svg" alt="{esc(film["title"])}のイラスト"></figure>'
        date = esc(d["date"].replace("-", ".") + " 掲載") if d.get("date") else "感想ジャーナル"
        # CSS/JS の波括弧と衝突しないよう、format ではなくトークン置換で埋め込む
        tokens = {
            "{no}": no,
            "{hero}": hero,
            "{reel_logo}": REEL_LOGO,
            "{icon_leaf}": ICON_LEAF,
            "{icon_reel}": ICON_REEL,
            "{icon_bang}": ICON_BANG,
            "{icon_crown}": ICON_CROWN,
            "{title}": esc(film["title"]),
            "{year}": str(film["year"]),
            "{runtime}": runtime,
            "{css}": CSS,
            "{date}": date,
            "{intro_block}": intro_block(d),
            "{overview}": para(regroup(d.get("overview", ""), per=2, min_split=0)),
            "{source_name}": esc(d["source"][0]) if d.get("source") else "",
            "{source_url}": esc(d["source"][1]) if d.get("source") else "#",
            "{facts}": facts,
            "{impression}": impression_html(no, d.get("impression")),
            "{analysis_block}": ("<h2>" + ICON_SCOPE + "考察</h2>\n" + para(d.get("analysis"))) if (d.get("analysis") or "").strip() else "",
            "{spoiler}": para(regroup(d.get("spoiler_overview"), per=2, min_split=0)),
        }
        page = TEMPLATE
        for k, v in tokens.items():
            page = page.replace(k, v)
        with open(os.path.join(outdir, f"{no}.html"), "w", encoding="utf-8") as f:
            f.write(page)
        made.append(no)
    base = "https://gyro-thespin.github.io/cinema-impression/"
    urls = [base, base + "privacy.html"] + [base + f"articles/{n}.html" for n in sorted(made)]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{u}</loc></url>" for u in urls]
    sm.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sm) + "\n")
    return made


def main():
    made = build_all()
    print(f"記事ページを生成しました: {', '.join(sorted(made))}（{len(made)}本）")


if __name__ == "__main__":
    main()
