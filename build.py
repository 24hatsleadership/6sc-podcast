#!/usr/bin/env python3
"""Static site builder. Reads content/posts/*.md, writes dist/. No dependencies."""
import os, re, html, shutil, glob, json
from datetime import datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "site.json")))
SITE = os.environ.get("SITE_BASE", CFG["base"]).rstrip("/")
E = html.escape

def inline(t):
    t = E(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    return t

def md(text):
    out, para, lst, kind = [], [], [], None
    def flush():
        nonlocal para, lst, kind
        if para: out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
        if lst: out.append(f"<{kind}>" + "".join(f"<li>{inline(i)}</li>" for i in lst) + f"</{kind}>"); lst = []; kind = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(#{2,4})\s+(.*)", s)
        if not s: flush(); continue
        if m: flush(); n = len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); continue
        if s.startswith("> "): flush(); out.append(f"<blockquote><p>{inline(s[2:])}</p></blockquote>"); continue
        b = re.match(r"^[-*]\s+(.*)", s); o = re.match(r"^\d+\.\s+(.*)", s)
        if b or o:
            k = "ul" if b else "ol"
            if para or (kind and kind != k): flush()
            kind = k; lst.append((b or o).group(1)); continue
        if lst: flush()
        para.append(s)
    flush()
    return "\n".join(out)

def load_posts():
    posts = []
    for f in glob.glob(os.path.join(ROOT, "content", "posts", "*.md")):
        raw = open(f, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        meta, body = {}, raw
        if m:
            for l in m.group(1).splitlines():
                if ":" in l: k, v = l.split(":", 1); meta[k.strip()] = v.strip().strip('"')
            body = m.group(2)
        slug = meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", os.path.basename(f)[:-3])
        if meta.get("draft", "").lower() == "true": continue
        posts.append(dict(slug=slug, title=meta.get("title", slug), date=meta.get("date", "1970-01-01"),
            summary=meta.get("summary", ""), episode=meta.get("episode", ""), minutes=meta.get("minutes", ""),
            tag=meta.get("tag", ""), listen=meta.get("listen", ""), watch=meta.get("watch", ""), body=md(body)))
    return sorted(posts, key=lambda p: p["date"], reverse=True)

def fdate(d):
    try: return datetime.strptime(d, "%Y-%m-%d").strftime("%B %-d, %Y")
    except Exception: return d

def layout(title, desc, path, body, prefix="", og_type="website"):
    nav = "".join(f'<a href="{href if href.startswith("http") else prefix + href}">{E(label)}</a>' for label, href in CFG["nav"])
    soc = "".join(f'<a href="{u}" rel="noopener">{E(l)}</a>' for l, u in CFG["social"])
    canon = f"{SITE}/{path}".rstrip("/") + ("/" if path else "")
    full_title = title if title == CFG["name"] else f"{title} | {CFG['name']}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(full_title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="{canon}"><meta name="theme-color" content="{CFG['theme_color']}">
<meta property="og:title" content="{E(full_title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:type" content="{og_type}"><meta property="og:url" content="{canon}"><meta property="og:site_name" content="{E(CFG['name'])}">
<link rel="alternate" type="application/rss+xml" title="{E(CFG['name'])}" href="{SITE}/rss.xml">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{CFG['font_url']}">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="{prefix}index.html" aria-label="{E(CFG['name'])} home"><img src="{CFG['logo']}" alt="{E(CFG['brand'])}"></a>
<nav aria-label="Main">{nav}</nav><a class="btn btn-sm hdr-cta" href="{CFG['cta_url']}">{E(CFG['cta_label'])}</a></div></header>
<main id="main">{body}</main>
<footer class="site"><div class="wrap"><div class="cols"><p>{CFG['footer_blurb']}</p><a href="{CFG['main_url']}" aria-label="{E(CFG['brand'])}"><img src="{CFG['logo']}" alt="{E(CFG['brand'])}"></a></div>
<div class="soc">{soc}</div><p class="fine">{CFG['copyright']}</p></div></footer></body></html>"""

def card(p, prefix=""):
    meta = " · ".join(x for x in [
        (f"Episode {p['episode']}" if p["episode"] else fdate(p["date"])),
        (f"{p['minutes']} min" if p["minutes"] else ""), p["tag"]] if x)
    return f'<article class="card"><p class="eyebrow">{E(meta)}</p><h3><a href="{prefix}{CFG["section"]}/{p["slug"]}/">{E(p["title"])}</a></h3><p>{E(p["summary"])}</p><a class="more" href="{prefix}{CFG["section"]}/{p["slug"]}/">{E(CFG["read_label"])}</a></article>'

def write(path, content):
    full = os.path.join(OUT, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(content)

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    posts = load_posts()
    sec = CFG["section"]
    cards = "\n".join(card(p) for p in posts) or "<p>New posts are on the way.</p>"
    hero = f"""<section class="hero"><div class="wrap"><p class="eyebrow">{E(CFG['hero_eyebrow'])}</p><h1>{E(CFG['hero_title'])}</h1><p class="lede">{E(CFG['hero_lede'])}</p>
<p class="actions"><a class="btn" href="{sec}/">{E(CFG['hero_btn1'])}</a><a class="btn btn-ghost" href="{CFG['hero_btn2_url']}">{E(CFG['hero_btn2'])}</a></p></div></section>"""
    latest = f'<section class="band"><div class="wrap"><p class="eyebrow">{E(CFG["latest_eyebrow"])}</p><h2>{E(CFG["latest_title"])}</h2><div class="grid">{"".join(card(p) for p in posts[:3])}</div><p class="allp"><a class="more" href="{sec}/">{E(CFG["all_label"])}</a></p></div></section>'
    cta = f'<section class="cta"><div class="wrap"><h2>{E(CFG["cta_title"])}</h2><p>{E(CFG["cta_text"])}</p><p><a class="btn" href="{CFG["cta_url"]}">{E(CFG["cta_label"])}</a></p></div></section>'
    write("index.html", layout(CFG["name"], CFG["desc"], "", hero + latest + cta))
    write(f"{sec}/index.html", layout(CFG["section_title"], CFG["desc"], f"{sec}", f'<section class="page"><div class="wrap"><p class="eyebrow">{E(CFG["name"])}</p><h1>{E(CFG["section_title"])}</h1><div class="grid">{cards}</div></div></section>', prefix="../"))
    about = "".join(f"<p>{E(t)}</p>" for t in CFG["about"])
    write("about/index.html", layout("About", CFG["desc"], "about", f'<section class="page"><div class="wrap narrow"><p class="eyebrow">{E(CFG["name"])}</p><h1>About</h1><div class="prose">{about}</div></div></section>' + cta, prefix="../"))
    for p in posts:
        listen = ""
        if p["listen"] or p["watch"]:
            b = (f'<a class="btn" href="{p["listen"]}">Listen</a>' if p["listen"] else "") + (f'<a class="btn btn-ghost" href="{p["watch"]}">Watch on YouTube</a>' if p["watch"] else "")
            listen = f'<p class="actions">{b}</p>'
        meta = " · ".join(x for x in [(f"Episode {p['episode']}" if p["episode"] else ""), fdate(p["date"]), (f"{p['minutes']} min" if p["minutes"] else ""), p["tag"]] if x)
        body = f'<article class="page"><div class="wrap narrow"><p class="eyebrow">{E(meta)}</p><h1>{E(p["title"])}</h1><p class="lede">{E(p["summary"])}</p>{listen}<div class="prose">{p["body"]}</div><p class="back"><a class="more" href="../">{E(CFG["back_label"])}</a></p></div></article>' + cta
        write(f"{sec}/{p['slug']}/index.html", layout(p["title"], p["summary"], f"{sec}/{p['slug']}", body, prefix="../../", og_type="article"))
    write("404.html", layout("Page not found", CFG["desc"], "404", '<section class="page"><div class="wrap narrow"><h1>Page not found</h1><p class="lede">That page moved or never existed.</p><p><a class="btn" href="/">Back home</a></p></div></section>'))
    items = "".join(f'<item><title>{E(p["title"])}</title><link>{SITE}/{sec}/{p["slug"]}/</link><guid>{SITE}/{sec}/{p["slug"]}/</guid><pubDate>{datetime.strptime(p["date"], "%Y-%m-%d").strftime("%a, %d %b %Y 08:00:00 +0000")}</pubDate><description>{E(p["summary"])}</description></item>' for p in posts)
    write("rss.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{E(CFG["name"])}</title><link>{SITE}/</link><description>{E(CFG["desc"])}</description>{items}</channel></rss>')
    urls = ["", f"{sec}/", "about/"] + [f"{sec}/{p['slug']}/" for p in posts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{SITE}/{u}</loc></url>" for u in urls) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(OUT, "CNAME"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"Built {len(posts)} post(s) to dist/")

if __name__ == "__main__": main()
