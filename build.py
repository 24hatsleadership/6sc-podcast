#!/usr/bin/env python3
"""Static site builder. Reads content/posts/*.md and site.json, writes dist/. No dependencies."""
import os, re, html, shutil, glob, json
import urllib.request
import xml.etree.ElementTree as ET_XML
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "dist")
CFG = json.load(open(os.path.join(ROOT, "site.json"), encoding="utf-8"))
SITE = os.environ.get("SITE_BASE", CFG["base"]).rstrip("/")
ET = ZoneInfo("America/New_York")
E = html.escape
DAYS = "Mon Tue Wed Thu Fri Sat Sun".split()
MONS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

def inline(t):
    t = E(t, quote=False)
    def link(m):
        href, label = m.group(2), m.group(1)
        rel = ' rel="noopener"' if href.startswith("http") else ""
        return f'<a href="{href}"{rel}>{label}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    return t

def md(text):
    out, para, lst, kind = [], [], [], None
    def flush():
        nonlocal para, lst, kind
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if lst:
            klass = ' class="chapters"' if kind == "ul" else ""
            # chapters class is applied later, only on the Chapters list
            out.append(f"<{kind}{klass}>" + "".join(f"<li>{inline(i)}</li>" for i in lst) + f"</{kind}>")
            lst = []
            kind = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(#{2,4})\s+(.*)", s)
        if not s:
            flush()
            continue
        if m:
            flush()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        if s.startswith("> "):
            flush()
            out.append(f"<blockquote><p>{inline(s[2:])}</p></blockquote>")
            continue
        b = re.match(r"^[-*]\s+(.*)", s)
        o = re.match(r"^\d+\.\s+(.*)", s)
        if b or o:
            k = "ul" if b else "ol"
            if para or (kind and kind != k):
                flush()
            kind = k
            lst.append((b or o).group(1))
            continue
        if lst:
            flush()
        para.append(s)
    flush()
    html_out = "\n".join(out)
    html_out = html_out.replace("<h2>Chapters</h2>\n<ul class=\"chapters\">", "<h2>Chapters</h2>\n<ul class=\"chapters\">")
    # Only the list that follows the Chapters heading keeps the chapters class.
    parts = html_out.split("<ul class=\"chapters\">")
    if len(parts) > 1:
        rebuilt = [parts[0]]
        for chunk in parts[1:]:
            head = rebuilt[-1]
            if head.rstrip().endswith("<h2>Chapters</h2>"):
                rebuilt.append("<ul class=\"chapters\">" + chunk)
            else:
                rebuilt.append("<ul>" + chunk)
        html_out = "".join(rebuilt)
    return html_out

def safe_url(raw):
    raw = (raw or "").strip()
    low = raw.lower()
    if not raw or low.startswith("javascript:") or low.startswith("data:"):
        return ""
    return raw

def asset(path, prefix=""):
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return prefix + path.lstrip("/")

def abs_url(path):
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{SITE}/{path.lstrip('/')}"

def canon_for(path):
    path = (path or "").strip("/")
    return f"{SITE}/" if not path else f"{SITE}/{path}/"

def jsonld(obj):
    raw = json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{raw}</script>'

def youtube_id(raw):
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{6,})", raw)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", raw):
        return raw
    return ""

def parse_pub(date, time):
    time = (time or "").strip()
    if not time:
        time = "00:00"
    if len(time) == 5:
        time += ":00"
    naive = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=ET)

def clock():
    flag = os.environ.get("SHOW_FUTURE", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return datetime(9999, 1, 1, tzinfo=ET)
    raw = os.environ.get("BUILD_AS_OF", "").strip()
    if not raw:
        return datetime.now(ET)
    raw = raw.replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=ET)
        except ValueError:
            continue
    raise SystemExit(f"BUILD_AS_OF must be YYYY-MM-DD or YYYY-MM-DDTHH:MM, got {raw}")

def fwhen(p):
    dt = p["_dt"]
    date = f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    if not p.get("time"):
        return date
    h12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{date} at {h12}:{dt.minute:02d} {ampm} ET"

def rfc822(dt):
    u = dt.astimezone(timezone.utc)
    return f"{DAYS[u.weekday()]}, {u.day:02d} {MONS[u.month - 1]} {u.year} {u:%H:%M:%S} +0000"

def load_posts():
    posts = []
    for f in glob.glob(os.path.join(ROOT, "content", "posts", "*.md")):
        raw = open(f, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        meta, body = {}, raw
        if m:
            for l in m.group(1).splitlines():
                l = l.strip()
                if not l or l.startswith("#") or ":" not in l:
                    continue
                k, v = l.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
            body = m.group(2)
        if meta.get("draft", "").lower() == "true":
            continue
        slug = meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", os.path.basename(f)[:-3])
        date = meta.get("date", "1970-01-01")
        time = meta.get("time", "")
        try:
            dt = parse_pub(date, time)
        except ValueError:
            print(f"skip unreadable date: {os.path.basename(f)}")
            continue
        posts.append(dict(
            slug=slug,
            title=meta.get("title", slug),
            date=date,
            time=time,
            _dt=dt,
            summary=meta.get("summary", ""),
            episode=meta.get("episode", ""),
            minutes=meta.get("minutes", ""),
            tag=meta.get("tag", ""),
            thumbnail=meta.get("thumbnail", ""),
            thumbnail_alt=meta.get("thumbnail_alt", ""),
            youtube_id=youtube_id(meta.get("youtube_id", "")),
            audio=safe_url(meta.get("audio", "")),
            spotify=safe_url(meta.get("spotify", "")),
            apple=safe_url(meta.get("apple", "")),
            disclosure=meta.get("disclosure", ""),
            body=md(body.strip()),
        ))
    posts.sort(key=lambda p: p["_dt"], reverse=True)
    return posts

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

def feed_audio():
    """Map episode number and title to the mp3 enclosure in the published podcast feed.
    Only published episodes are in the feed, so drafts get no player. Any failure means no players, not a failed build."""
    url = CFG.get("audio_feed", "")
    if not url:
        return {}, {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "podcast-site-build"})
        root = ET_XML.fromstring(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print(f"audio feed unavailable, building without feed audio: {e}")
        return {}, {}
    season = str(CFG.get("audio_feed_season", "1"))
    by_ep, by_title = {}, {}
    for item in root.iter("item"):
        enc = item.find("enclosure")
        src = safe_url(enc.get("url", "")) if enc is not None else ""
        if not src.startswith("https://"):
            continue
        ep = (item.findtext(ITUNES + "episode") or "").strip()
        se = (item.findtext(ITUNES + "season") or "").strip()
        if ep and se == season:
            by_ep.setdefault(ep, src)
        title = (item.findtext("title") or "").strip().lower()
        if title:
            by_title.setdefault(title, src)
    return by_ep, by_title

def attach_audio(posts):
    by_ep, by_title = feed_audio()
    for p in posts:
        if p["audio"]:
            continue
        src = by_ep.get(p["episode"], "")
        if not src:
            t = p["title"].lower()
            src = next((u for k, u in by_title.items() if k.endswith(t)), "")
        p["audio"] = src
        if src:
            print(f"audio from feed: episode {p['episode']}")
    return posts

def live_posts(posts):
    now = clock()
    live, skipped = [], []
    for p in posts:
        if p["_dt"] <= now:
            live.append(p)
        else:
            skipped.append(p)
    return live, skipped

def buttons(pairs, cls="btn"):
    out = []
    for label, url in pairs:
        url = safe_url(url)
        if not url:
            continue
        rel = ' rel="noopener"' if url.startswith("http") else ""
        out.append(f'<a class="{cls}" href="{E(url)}"{rel}>{E(label)}</a>')
    return "".join(out)

def hosts_html(prefix):
    items = []
    for h in CFG["hosts"]:
        sp = CFG["sprites"][h["sprite"]]
        items.append(
            f'<li><img class="sprite" src="{E(asset(sp, prefix))}" width="64" height="64" alt="">{E(h["name"])}</li>'
        )
    return f'<ul class="hosts">{"".join(items)}</ul>'

def meta_html(p, hero=False):
    rest = [fwhen(p)]
    if p["minutes"]:
        rest.append(f'{p["minutes"]} min')
    if p["tag"]:
        rest.append(p["tag"])
    pixel = f'<span class="pixel">Episode {E(p["episode"])}</span>' if p["episode"] else ""
    return f'<p class="meta">{pixel}<span class="meta-rest">{E(" · ".join(rest))}</span></p>'

def onair(p, live, prefix):
    if live:
        src = CFG["sprites"]["onair_on"]
        return f'<img class="onair live" src="{E(asset(src, prefix))}" width="140" height="60" alt="On air">'
    src = CFG["sprites"]["onair_off"]
    return f'<img class="onair" src="{E(asset(src, prefix))}" width="140" height="60" alt="">'

def card(p, prefix="", live=False):
    href = f'{prefix}{CFG["section"]}/{p["slug"]}/'
    media = ""
    if p["thumbnail"]:
        alt = p["thumbnail_alt"] or p["title"]
        media = (
            f'<a class="card-media" href="{href}" aria-label="{E(p["title"])}">'
            f'<img class="thumb" src="{E(asset(p["thumbnail"], prefix))}" alt="{E(alt)}" width="1920" height="1080" loading="lazy">'
            f'{onair(p, live, prefix)}</a>'
        )
    return (
        f'<article class="card">{media}<div class="card-body">{meta_html(p)}'
        f'<h3><a href="{href}">{E(p["title"])}</a></h3><p>{E(p["summary"])}</p>'
        f'<a class="more" href="{href}">{E(CFG["read_label"])}</a></div></article>'
    )

def subscribe_pairs():
    pairs = []
    for item in CFG.get("subscribe", []):
        url = safe_url(item.get("url", ""))
        label = (item.get("label") or "").strip()
        if label and url:
            pairs.append((label, url))
    return pairs

def subscribe_html():
    row = buttons(subscribe_pairs(), "btn")
    if row:
        return f'<div class="subscribe"><h2>Listen and subscribe</h2><p class="actions">{row}</p></div>'
    return (
        '<div class="subscribe"><h2>Listen and subscribe</h2>'
        f'<p class="pending">{E(CFG["subscribe_pending"])}</p></div>'
    )

def cta_html():
    return (
        f'<section class="cta"><div class="wrap"><h2>{E(CFG["cta_title"])}</h2>'
        f'<p>{E(CFG["cta_text"])}</p><p><a class="btn" href="{E(CFG["cta_url"])}">{E(CFG["cta_label"])}</a></p></div></section>'
    )

def series_ld():
    data = {
        "@context": "https://schema.org",
        "@type": "PodcastSeries",
        "name": CFG["name"],
        "description": CFG["desc"],
        "url": SITE + "/",
        "image": abs_url(CFG["cover"]),
        "inLanguage": "en",
        "webFeed": SITE + "/rss.xml",
        "author": {"@type": "Organization", "name": CFG["brand"], "url": "https://6stringcreative.com"},
        "publisher": {"@type": "Organization", "name": CFG["brand"], "url": "https://6stringcreative.com"},
    }
    same = [safe_url(item.get("url", "")) for item in CFG["subscribe"]]
    same = [u for u in same if u.startswith("http")]
    if same:
        data["sameAs"] = same
    return jsonld(data)

def episode_ld(p, url):
    data = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode",
        "name": p["title"],
        "description": p["summary"],
        "datePublished": p["_dt"].isoformat(),
        "url": url,
        "inLanguage": "en",
        "partOfSeries": {"@type": "PodcastSeries", "name": CFG["name"], "url": SITE + "/"},
        "publisher": {"@type": "Organization", "name": CFG["brand"], "url": "https://6stringcreative.com"},
    }
    if p["thumbnail"]:
        data["image"] = abs_url(p["thumbnail"])
    if p["episode"].isdigit():
        data["episodeNumber"] = int(p["episode"])
    if p["minutes"].isdigit():
        data["timeRequired"] = f'PT{p["minutes"]}M'
    media = []
    if p["youtube_id"]:
        media.append({
            "@type": "VideoObject",
            "name": p["title"],
            "embedUrl": f'https://www.youtube-nocookie.com/embed/{p["youtube_id"]}',
            "thumbnailUrl": abs_url(p["thumbnail"]) if p["thumbnail"] else None,
            "uploadDate": p["_dt"].isoformat(),
        })
    if p["audio"]:
        media.append({"@type": "AudioObject", "contentUrl": p["audio"], "name": p["title"]})
    media = [{k: v for k, v in item.items() if v} for item in media]
    if len(media) == 1:
        data["associatedMedia"] = media[0]
    elif media:
        data["associatedMedia"] = media
    return jsonld(data)

def layout(title, desc, path, body, prefix="", og_type="website", image=None, extra_head=""):
    nav = "".join(
        f'<a href="{href if href.startswith("http") else prefix + href}">{E(label)}</a>'
        for label, href in CFG["nav"]
    )
    sub = "".join(f'<a href="{E(u)}" rel="noopener">{E(l)}</a>' for l, u in subscribe_pairs())
    soc = sub + "".join(f'<a href="{E(u)}" rel="noopener">{E(l)}</a>' for l, u in CFG["social"])
    canon = canon_for(path)
    full_title = title if title == CFG["name"] else f'{title} | {CFG["name"]}'
    desc = " ".join((desc or "").split())
    og = ""
    if image and image.get("src"):
        img = abs_url(image["src"])
        og = (
            f'<meta property="og:image" content="{E(img)}">'
            f'<meta property="og:image:alt" content="{E(image.get("alt", ""))}">'
            f'<meta name="twitter:image" content="{E(img)}">'
            f'<meta name="twitter:image:alt" content="{E(image.get("alt", ""))}">'
        )
        if image.get("width"):
            og += f'<meta property="og:image:width" content="{int(image["width"])}">'
            og += f'<meta property="og:image:height" content="{int(image["height"])}">'
    logo = asset(CFG["logo"], prefix)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(full_title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canon)}"><meta name="theme-color" content="{E(CFG['theme_color'])}">
<meta property="og:title" content="{E(full_title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:type" content="{E(og_type)}"><meta property="og:url" content="{E(canon)}"><meta property="og:site_name" content="{E(CFG['name'])}"><meta property="og:locale" content="en_US">
{og}<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(full_title)}"><meta name="twitter:description" content="{E(desc)}">
<link rel="alternate" type="application/rss+xml" title="{E(CFG['name'])}" href="{SITE}/rss.xml">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{E(CFG['font_url'])}">
<link rel="stylesheet" href="{prefix}assets/style.css">
{extra_head}</head><body><a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="{prefix}index.html" aria-label="{E(CFG['name'])} home"><img src="{E(logo)}" alt="{E(CFG['brand'])}" width="100" height="40"></a>
<nav aria-label="Main">{nav}</nav><a class="btn btn-sm hdr-cta" href="{E(CFG['cta_url'])}">{E(CFG['cta_label'])}</a></div></header>
<main id="main">{body}</main>
<footer class="site"><div class="wrap"><div class="cols"><p>{E(CFG['footer_blurb'])}</p><a href="{E(CFG['main_url'])}" aria-label="{E(CFG['brand'])}"><img src="{E(logo)}" alt="{E(CFG['brand'])}" width="110" height="44"></a></div>
<div class="soc">{soc}</div><p class="fine">{E(CFG['copyright'])}</p></div></footer></body></html>"""

def home_html(posts):
    cards = []
    for i, p in enumerate(posts):
        cards.append(card(p, live=(i == 0 and bool(p["thumbnail"]))))
    grid = "".join(cards) if cards else f'<p class="empty">{E(CFG["empty_episodes"])}</p>'
    hero = f"""<section class="hero"><div class="wrap">
<figure class="studio"><img src="{E(asset(CFG['hero']))}" alt="{E(CFG['hero_alt'])}" width="1920" height="1080" fetchpriority="high"></figure>
<div class="hero-grid">
<img class="hero-cover" src="{E(asset(CFG['cover']))}" alt="{E(CFG['cover_alt'])}" width="1400" height="1400">
<div class="hero-copy">
<p class="pixel">A 6 String Creative podcast</p>
<h1>{E(CFG['name'])}</h1>
<p class="tagline">{E(CFG['tagline'])}</p>
<p class="lede">{E(CFG['desc'])}</p>
{hosts_html("")}
{subscribe_html()}
</div></div></div></section>"""
    player = ""
    if posts and posts[0]["audio"]:
        p = posts[0]
        player = (f'<figure class="audio"><figcaption>Listen to the latest episode: {E(p["title"])}</figcaption>'
                  f'<audio controls preload="none" src="{E(p["audio"])}"></audio></figure>')
    latest = f'<section class="band" id="episodes"><div class="wrap"><p class="pixel">Newest first</p><h2>Episodes</h2>{player}<div class="grid">{grid}</div></div></section>'
    return hero + latest + cta_html()

def episode_html(p, live, prefix):
    media = ""
    if p["youtube_id"]:
        media = (
            f'<div class="frame"><iframe src="https://www.youtube-nocookie.com/embed/{E(p["youtube_id"])}" '
            f'title="{E(p["title"])}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            f'allowfullscreen></iframe></div>'
        )
    elif p["thumbnail"]:
        alt = p["thumbnail_alt"] or p["title"]
        media = (
            f'<div class="frame"><img src="{E(asset(p["thumbnail"], prefix))}" alt="{E(alt)}" width="1920" height="1080"></div>'
        )
    audio = ""
    if p["audio"]:
        audio = f'<figure class="audio"><figcaption>Listen</figcaption><audio controls preload="none" src="{E(p["audio"])}"></audio></figure>'
    links = buttons([
        ("YouTube", f'https://www.youtube.com/watch?v={p["youtube_id"]}' if p["youtube_id"] else ""),
        ("Spotify", p["spotify"]),
        ("Apple Podcasts", p["apple"]),
    ])
    if links:
        listen = f'<p class="actions">{links}</p>'
    elif not p["youtube_id"] and not p["audio"]:
        listen = f'<p class="pending">{E(CFG["episode_pending"])}</p>'
    else:
        listen = ""
    note = f'<p class="ai-note">{E(p["disclosure"])}</p>' if p["disclosure"] else ""
    badge = onair(p, live, prefix)
    return (
        f'<article class="page"><div class="wrap episode">{meta_html(p)}<h1>{E(p["title"])}</h1>'
        f'{hosts_html(prefix)}{note}<p class="lede">{E(p["summary"])}</p>'
        f'<div class="stage">{media}{badge}</div>{audio}{listen}'
        f'<div class="prose">{p["body"]}</div>'
        f'<p class="back"><a class="more" href="../">{E(CFG["back_label"])}</a></p></div></article>'
        + cta_html()
    )

def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(content)

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    posts, skipped = live_posts(load_posts())
    attach_audio(posts)
    sec = CFG["section"]
    cover = {"src": CFG["cover"], "alt": CFG["cover_alt"], "width": 1400, "height": 1400}
    write("index.html", layout(CFG["name"], CFG["desc"], "", home_html(posts), image=cover, extra_head=series_ld()))
    cards = "".join(card(p, "../", live=(i == 0 and bool(p["thumbnail"]))) for i, p in enumerate(posts))
    if not cards:
        cards = f'<p class="empty">{E(CFG["empty_episodes"])}</p>'
    listing = f'<section class="page"><div class="wrap"><p class="pixel">{E(CFG["name"])}</p><h1>{E(CFG["section_title"])}</h1><div class="grid">{cards}</div></div></section>'
    write(f"{sec}/index.html", layout(CFG["section_title"], CFG["desc"], sec, listing, prefix="../", image=cover, extra_head=series_ld()))
    about = hosts_html("../") + "".join(f"<p>{E(t)}</p>" for t in CFG["about"])
    write("about/index.html", layout("About", CFG["desc"], "about", f'<section class="page"><div class="wrap narrow"><p class="pixel">{E(CFG["name"])}</p><h1>About</h1><div class="prose">{about}</div></div></section>' + cta_html(), prefix="../", image=cover))
    for i, p in enumerate(posts):
        image = None
        if p["thumbnail"]:
            image = {"src": p["thumbnail"], "alt": p["thumbnail_alt"] or p["title"], "width": 1920, "height": 1080}
        url = canon_for(f"{sec}/{p['slug']}")
        body = episode_html(p, live=(i == 0 and bool(p["thumbnail"])), prefix="../../")
        write(f"{sec}/{p['slug']}/index.html", layout(p["title"], p["summary"] or CFG["desc"], f"{sec}/{p['slug']}", body, prefix="../../", og_type="article", image=image, extra_head=episode_ld(p, url)))
    write("404.html", layout("Page not found", CFG["desc"], "404", '<section class="page"><div class="wrap narrow"><h1>Page not found</h1><p class="lede">That page does not exist.</p><p><a class="btn" href="/">Back home</a></p></div></section>', image=cover))
    items = []
    for p in posts:
        link = f"{SITE}/{sec}/{p['slug']}/"
        enc = f'<enclosure url="{E(p["audio"])}" type="audio/mpeg" />' if p["audio"].startswith("http") else ""
        items.append(
            f'<item><title>{E(p["title"])}</title><link>{link}</link><guid>{link}</guid>'
            f'<pubDate>{rfc822(p["_dt"])}</pubDate><description>{E(p["summary"])}</description>{enc}</item>'
        )
    write("rss.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{E(CFG["name"])}</title><link>{SITE}/</link><description>{E(CFG["desc"])}</description><language>en</language>{"".join(items)}</channel></rss>')
    urls = [("", posts[0]["date"] if posts else "")] + [(f"{sec}/", posts[0]["date"] if posts else ""), ("about/", "")]
    urls += [(f"{sec}/{p['slug']}/", p["date"]) for p in posts]
    body = []
    for path, last in urls:
        loc = canon_for(path)
        extra = f"<lastmod>{E(last)}</lastmod>" if last else ""
        body.append(f"<url><loc>{loc}</loc>{extra}</url>")
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(body) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(OUT, "CNAME"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"Built {len(posts)} post(s), skipped {len(skipped)} future, to dist/")
    for p in skipped:
        print(f"  later: {p['slug']} ({p['_dt'].isoformat()})")

if __name__ == "__main__":
    main()
