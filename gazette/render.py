"""Render a digest dict into a self-contained newspaper-style HTML page (plus the archive index)."""
import html
import json
import sys

CSS = """
:root{--paper:#f6f1e7;--ink:#1a1a1a;--muted:#5d574a;--rule:#1a1a1a;--soft:#d8cfba;--accent:#8b1a1a;--box:#eee6d3;
color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#16140f;--ink:#ece6d6;--muted:#a8a190;--rule:#ece6d6;--soft:#3b372b;--accent:#e58b74;--box:#1f1c14;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#16140f;--ink:#ece6d6;--muted:#a8a190;--rule:#ece6d6;--soft:#3b372b;--accent:#e58b74;--box:#1f1c14;color-scheme:dark}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Source Serif 4',Georgia,'Times New Roman',serif;line-height:1.55}
a{color:inherit;text-decoration:underline dotted;text-underline-offset:2px}a:hover{color:var(--accent)}
.sheet{max-width:1120px;margin:0 auto;padding:22px 28px 48px}
.dateline{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:5px 0}
.nameplate{font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:clamp(2.4rem,8.5vw,5.6rem);line-height:1;text-align:center;margin:.22em 0 .05em;letter-spacing:-.01em}
.tagline{text-align:center;font-style:italic;color:var(--muted);margin:0 0 12px;padding-bottom:12px;border-bottom:3px double var(--rule)}
.hd{font-family:'Playfair Display',Georgia,serif;font-weight:900;line-height:1.08;margin:0}
.kicker{font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:700;margin-bottom:.4em}
.front{display:grid;grid-template-columns:minmax(0,2.3fr) minmax(0,1fr);gap:28px;padding:20px 0;border-bottom:1px solid var(--rule)}
.lead h2{font-size:clamp(1.9rem,4.6vw,3.2rem);margin:0 0 .25em}
.deck{font-size:1.15rem;font-style:italic;color:var(--muted);margin:0 0 .6em;line-height:1.35}
.source{font-size:.78rem;color:var(--muted);font-style:italic;margin:.4em 0 0}
.lead .text{column-count:2;column-gap:28px;column-rule:1px solid var(--soft);text-align:justify;hyphens:auto}
.lead .text p{margin:0 0 .8em}
.lead .text p:first-child::first-letter{float:left;font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:3.6em;line-height:.8;padding:.06em .08em 0 0}
.whymatters{background:var(--box);border-left:3px solid var(--accent);padding:10px 14px;margin:14px 0 0;font-size:.95rem}
.rail{border-left:1px solid var(--soft);padding-left:24px}
.box{margin-bottom:22px}
.box h3{font-family:'Playfair Display',Georgia,serif;font-size:.85rem;letter-spacing:.16em;text-transform:uppercase;margin:0 0 8px;padding-bottom:5px;border-bottom:1px solid var(--rule)}
.box dl{margin:0;display:grid;grid-template-columns:1fr auto;gap:4px 12px;font-size:.92rem}
.box dt{color:var(--muted)}.box dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums}
.box ol{margin:0;padding-left:1.2em;font-size:.92rem}
.note{font-size:.92rem;font-style:italic}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));border-bottom:1px solid var(--rule)}
.feature{padding:18px 22px;border-left:1px solid var(--soft)}
.feature:first-child{border-left:0;padding-left:0}.feature:last-child{padding-right:0}
.feature h3{font-size:1.45rem;margin:0 0 .3em}
.feature p{margin:.4em 0;font-size:.97rem}
.section-title{font-family:'Playfair Display',Georgia,serif;font-weight:900;text-transform:uppercase;letter-spacing:.2em;font-size:1rem;text-align:center;border-top:3px double var(--rule);border-bottom:1px solid var(--rule);padding:.4em 0;margin:30px 0 16px}
.section-note{text-align:center;font-style:italic;color:var(--muted);font-size:.88rem;margin:-6px 0 14px}
.columns{column-width:290px;column-gap:28px;column-rule:1px solid var(--soft)}
.story{break-inside:avoid;margin:0 0 20px}
.story h4{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:1.2rem;line-height:1.15;margin:0 0 .3em}
.story p{margin:.3em 0;font-size:.95rem;text-align:justify;hyphens:auto}
blockquote.pull{font-family:'Playfair Display',Georgia,serif;font-style:italic;font-size:clamp(1.3rem,3vw,1.8rem);line-height:1.3;text-align:center;margin:30px 6%;padding:14px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
blockquote.pull cite{display:block;font:normal .78rem 'Source Serif 4',Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-top:8px}
.briefs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0 28px}
.brief{padding:10px 0;border-bottom:1px solid var(--soft);font-size:.9rem}
.brief b{font-family:'Playfair Display',Georgia,serif;font-size:1rem}
.nav{margin:.6em 0 0}.nav a{margin:0 .7em}
.archive{list-style:none;margin:0;padding:0}.archive li{display:grid;grid-template-columns:minmax(11em,16em) 1fr;gap:12px;padding:9px 0;border-bottom:1px solid var(--soft)}.archive span{color:var(--muted);font-style:italic}
@media (max-width:820px){.archive li{grid-template-columns:1fr;gap:2px}}
footer{margin-top:36px;padding-top:10px;border-top:3px double var(--rule);font-size:.78rem;color:var(--muted);text-align:center}
@media (max-width:820px){
.sheet{padding:16px 16px 40px}
.front{grid-template-columns:1fr}
.rail{border-left:0;padding-left:0;border-top:1px solid var(--soft);padding-top:16px}
.lead .text{column-count:1}
.feature,.feature:first-child,.feature:last-child{border-left:0;padding:14px 0;border-top:1px solid var(--soft)}
.feature:first-child{border-top:0}
}
mjx-container{max-width:100%}
mjx-container[display="true"]{overflow-x:auto;overflow-y:hidden;margin:.7em 0!important}
.hd mjx-container,.deck mjx-container{font-size:inherit}
@media print{:root{--paper:#fff;--ink:#000}.sheet{max-width:none;padding:0}.story,.feature{break-inside:avoid}}
"""

HEAD_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700'
    '&family=Source+Serif+4:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">'
)


MATHJAX = r"""<script>window.MathJax={tex:{inlineMath:[['$','$'],['\\(','\\)']],displayMath:[['$$','$$'],['\\[','\\]']],processEscapes:true},svg:{fontCache:'global'},options:{skipHtmlTags:['script','noscript','style','textarea','pre','code']}};</script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.js"></script>"""


def needs_math(d):
    """Load MathJax only when the digest contains LaTeX (or math is forced on/off)."""
    if "math" in d:
        return bool(d["math"])
    blob = json.dumps(d, ensure_ascii=False)
    return "$" in blob or "\\\\(" in blob or "\\\\[" in blob


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def paras(body):
    if isinstance(body, str):
        body = [p for p in body.split("\n\n") if p.strip()]
    return "".join(f"<p>{e(p)}</p>" for p in body)


def source(s):
    bits = []
    if s.get("authors"):
        bits.append(e(s["authors"]))
    if s.get("arxiv_id"):
        i = e(s["arxiv_id"])
        bits.append(f'<a href="https://arxiv.org/abs/{i}" target="_blank" rel="noopener">arXiv:{i}</a>')
    return f'<p class="source">{" · ".join(bits)}</p>' if bits else ""


def kicker(s):
    k = s.get("kicker")
    return f'<div class="kicker">{e(k)}</div>' if k else ""


def render_lead(s):
    why = f'<div class="whymatters"><b>{e(s.get("why_label", "Why it matters."))}</b> {e(s["why_it_matters"])}</div>' if s.get("why_it_matters") else ""
    deck = f'<p class="deck">{e(s["deck"])}</p>' if s.get("deck") else ""
    return (f'<article class="lead">{kicker(s)}<h2 class="hd">{e(s["headline"])}</h2>{deck}'
            f'<div class="text">{paras(s.get("body", []))}</div>{why}{source(s)}</article>')


def render_rail(d):
    out = []
    stats = d.get("stats") or {}
    if stats:
        rows = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in stats.items())
        out.append(f'<div class="box"><h3>By the numbers</h3><dl>{rows}</dl></div>')
    names = [sec["name"] for sec in d.get("sections", [])]
    if d.get("briefs"):
        names.append("In Brief")
    if names:
        items = "".join(f"<li>{e(n)}</li>" for n in names)
        out.append(f'<div class="box"><h3>In this edition</h3><ol>{items}</ol></div>')
    if d.get("editors_note"):
        out.append(f'<div class="box"><h3>From the desk</h3><p class="note">{e(d["editors_note"])}</p></div>')
    return f'<aside class="rail">{"".join(out)}</aside>'


def render_features(items):
    if not items:
        return ""
    cards = "".join(
        f'<article class="feature">{kicker(f)}<h3 class="hd">{e(f["headline"])}</h3>{paras(f.get("body", []))}{source(f)}</article>'
        for f in items
    )
    return f'<section class="features">{cards}</section>'


def render_section(sec):
    stories = "".join(
        f'<article class="story"><h4>{e(s["headline"])}</h4>{paras(s.get("body", []))}{source(s)}</article>'
        for s in sec.get("stories", [])
    )
    note = f'<p class="section-note">{e(sec["note"])}</p>' if sec.get("note") else ""
    return f'<h2 class="section-title">{e(sec["name"])}</h2>{note}<div class="columns">{stories}</div>'


def render_pull(q):
    if not q:
        return ""
    cite = f"<cite>{e(q['attribution'])}</cite>" if q.get("attribution") else ""
    return f'<blockquote class="pull">{e(q["text"])}{cite}</blockquote>'


def render_briefs(items):
    if not items:
        return ""
    cells = []
    for b in items:
        link = ""
        if b.get("arxiv_id"):
            i = e(b["arxiv_id"])
            link = f' <a href="https://arxiv.org/abs/{i}" target="_blank" rel="noopener">[{i}]</a>'
        sep = "" if b["headline"][-1:] in ".?!" else "."
        cells.append(f'<div class="brief"><b>{e(b["headline"])}{sep}</b> {e(b.get("text", ""))}{link}</div>')
    return f'<h2 class="section-title">In Brief</h2><div class="briefs">{"".join(cells)}</div>'


def render_nav(items):
    if not items:
        return ""
    links = "".join(f'<a href="{e(i["href"])}">{e(i["label"])}</a>' for i in items)
    return f'<p class="nav">{links}</p>'


def build_archive(title, editions, home_href="../index.html"):
    """editions: list of {"date": "YYYY-MM-DD", "label": str, "headline": str}, any order."""
    rows = "".join(
        f'<li><a href="{e(ed["date"])}.html"><b>{e(ed["label"])}</b></a><span>{e(ed.get("headline", ""))}</span></li>'
        for ed in sorted(editions, key=lambda x: x["date"], reverse=True)
    ) or "<li><span>No editions yet.</span></li>"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)} — Past editions</title>{HEAD_LINKS}<style>{CSS}</style></head>
<body><div class="sheet">
<h1 class="nameplate">{e(title)}</h1>
<p class="tagline">Past editions</p>
<ul class="archive">{rows}</ul>
<footer>{render_nav([{"label": "Today’s edition", "href": home_href}])}</footer>
</div></body></html>"""


def build(d):
    title = d.get("title", "The arXiv Gazette")
    date = d.get("date", "")
    cats = " · ".join(d.get("categories", []))
    pull_after = d.get("pullquote_position", 0)  # insert pullquote after Nth section
    sections = d.get("sections", [])
    body = []
    for idx, sec in enumerate(sections):
        body.append(render_section(sec))
        if d.get("pullquote") and idx == min(pull_after, len(sections) - 1):
            body.append(render_pull(d["pullquote"]))
    footer = d.get("footer") or (
        "Compiled from arXiv listings. Summaries are based on paper abstracts and have not been peer reviewed; "
        "results are as reported by the authors. Follow the links for the full papers."
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)} — {e(date)}</title>{HEAD_LINKS}<style>{CSS}</style>{MATHJAX if needs_math(d) else ''}</head>
<body><div class="sheet">
<div class="dateline"><span>{e(date)}</span><span>{e(d.get("edition", ""))}</span><span>{e(cats)}</span></div>
<h1 class="nameplate">{e(title)}</h1>
<p class="tagline">{e(d.get("tagline", "All the preprints fit to print"))}</p>
<section class="front">{render_lead(d["lead"])}{render_rail(d)}</section>
{render_features(d.get("features"))}
{"".join(body)}
{render_briefs(d.get("briefs"))}
<footer>{e(footer)}{render_nav(d.get("nav"))}</footer>
</div></body></html>"""


