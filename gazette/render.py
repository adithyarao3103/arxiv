"""Render a digest dict into a self-contained newspaper-style HTML page (plus the archive index)."""
import html
import json
import sys

CSS = """
:root{--page:#ebe4d2;--paper:#f6f1e7;--ink:#1a1a1a;--muted:#5d574a;--rule:#1a1a1a;--soft:#d8cfba;--accent:#8b1a1a;--box:#eee6d3;
color-scheme:light only;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
html{scroll-padding-top:env(safe-area-inset-top,0px);background:var(--page);-webkit-text-size-adjust:100%}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:'Source Serif 4',Georgia,'Times New Roman',serif;line-height:1.55;overflow-wrap:break-word}
a{color:inherit;text-decoration:underline dotted;text-underline-offset:2px}a:hover{color:var(--accent)}
.sheet{max-width:1120px;margin:0 auto;padding:22px 36px 48px;background:var(--paper);min-height:100vh;box-shadow:0 0 0 1px var(--soft),0 10px 40px rgba(60,45,20,.12)}
.dateline{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:6px 0}
.dateline span:first-child{text-align:left}.dateline span:nth-child(2){text-align:center}.dateline span:last-child{text-align:right}
.nameplate{font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:clamp(2.3rem,8vw,5.2rem);line-height:1.02;text-align:center;margin:.24em 0 .06em;letter-spacing:-.01em}
.tagline{text-align:center;font-style:italic;color:var(--muted);margin:0 0 18px;padding-bottom:12px;border-bottom:3px double var(--rule)}
.hd{font-family:'Playfair Display',Georgia,serif;font-weight:900;line-height:1.12;margin:0}
.kicker{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:700;margin-bottom:.45em;line-height:1.35}
/* front page: lead story + sidebar */
.front{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(0,1fr);gap:0;border-bottom:1px solid var(--rule);margin-bottom:0}
.lead{padding:4px 30px 24px 0}
.lead h2{font-size:clamp(1.8rem,4.2vw,2.9rem);margin:0 0 .35em}
.lead .meta{font-size:.82rem;letter-spacing:.02em;color:var(--muted);margin:0 0 1em;padding:.35em 0;border-top:1px solid var(--soft);border-bottom:1px solid var(--soft)}
.lead .text{font-size:1.06rem;line-height:1.6}
.lead .text p{margin:0 0 .85em}
.lead .text.drop p:first-child::first-letter{float:left;font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:3.5em;line-height:.82;padding:.05em .09em 0 0}
.source{font-size:.8rem;color:var(--muted);font-style:italic;margin:.7em 0 0}
.rail{border-left:1px solid var(--soft);padding:4px 0 24px 26px}
.box{margin-bottom:24px}.box:last-child{margin-bottom:0}
.box h3{font-family:'Playfair Display',Georgia,serif;font-size:.8rem;letter-spacing:.16em;text-transform:uppercase;margin:0 0 9px;padding-bottom:5px;border-bottom:1px solid var(--rule)}
.box dl{margin:0;display:grid;grid-template-columns:1fr auto;gap:5px 14px;font-size:.9rem}
.box dt{color:var(--muted)}.box dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums;text-align:right}
.box ol{margin:0;padding-left:1.25em;font-size:.9rem}.box li{margin:0 0 .15em}
.note{font-size:.88rem;font-style:italic;margin:0;line-height:1.5}
/* features: one row of equal columns */
.features{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);border-bottom:1px solid var(--rule)}
.feature{padding:20px 24px 22px;border-left:1px solid var(--soft)}
.feature:first-child{border-left:0;padding-left:0}.feature:last-child{padding-right:0}
.feature h3{font-size:1.32rem;margin:0 0 .4em}
.feature p{margin:.4em 0;font-size:.95rem}
/* sections: each section is a block; blocks flow into two balanced newspaper columns */
.section-title{font-family:'Playfair Display',Georgia,serif;font-weight:900;text-transform:uppercase;letter-spacing:.18em;font-size:.92rem;text-align:center;border-top:3px double var(--rule);border-bottom:1px solid var(--rule);padding:.45em 0;margin:0 0 14px}
.section-title.wide{margin:32px 0 16px}
.section-note{text-align:center;font-style:italic;color:var(--muted);font-size:.85rem;margin:-6px 0 14px}
.sections{column-count:2;column-gap:56px;column-rule:1px solid var(--soft);margin-top:30px}
.section{break-inside:avoid;margin:0 0 30px}
.story{padding:0 0 16px;margin:0 0 16px;border-bottom:1px solid var(--soft)}
.story:last-child{border-bottom:0;margin-bottom:0;padding-bottom:0}
.story h4{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:1.15rem;line-height:1.2;margin:0 0 .35em}
.story p{margin:.35em 0;font-size:.94rem}
blockquote.pull{font-family:'Playfair Display',Georgia,serif;font-style:italic;font-size:clamp(1.3rem,3vw,1.8rem);line-height:1.3;text-align:center;margin:30px 6%;padding:14px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
blockquote.pull cite{display:block;font:normal .78rem 'Source Serif 4',Georgia,serif;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-top:8px}
.briefs{column-count:2;column-gap:56px;column-rule:1px solid var(--soft)}
.brief{break-inside:avoid;padding:0 0 11px;margin:0 0 11px;border-bottom:1px solid var(--soft);font-size:.9rem;line-height:1.5}
.brief b{font-family:'Playfair Display',Georgia,serif;font-size:.98rem}
.brief .by{display:block;font-size:.76rem;color:var(--muted);font-style:italic;margin-top:2px}
.brief-group{font-family:'Playfair Display',Georgia,serif;font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;margin:22px 0 10px;padding-bottom:4px;border-bottom:1px solid var(--rule)}
.brief-group small,.section-title small{font-weight:400;letter-spacing:.06em;color:var(--muted);text-transform:none}
.nav{margin:.8em 0 0}.nav a{margin:0 .7em}
.archive{list-style:none;margin:0;padding:0}.archive li{display:grid;grid-template-columns:minmax(11em,16em) 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--soft)}.archive span{color:var(--muted);font-style:italic}
footer{margin-top:40px;padding-top:12px;border-top:3px double var(--rule);font-size:.78rem;line-height:1.5;color:var(--muted);text-align:center}
mjx-container{max-width:100%}
mjx-container[display="true"]{overflow-x:auto;overflow-y:hidden;margin:.7em 0!important}
.hd mjx-container{font-size:inherit}
@media (max-width:900px){
.sheet{padding:16px 18px 40px}
.dateline{grid-template-columns:1fr;gap:2px;text-align:center}
.dateline span,.dateline span:first-child,.dateline span:nth-child(2),.dateline span:last-child{text-align:center}
.front{grid-template-columns:1fr}
.lead{padding-right:0}
.rail{border-left:0;border-top:1px solid var(--soft);padding:18px 0 0}
.features{grid-auto-flow:row;grid-auto-columns:auto}
.feature,.feature:first-child,.feature:last-child{border-left:0;padding:16px 0;border-top:1px solid var(--soft)}
.feature:first-child{border-top:0}
.sections,.briefs{column-count:1;column-rule:0}
.archive li{grid-template-columns:1fr;gap:2px}
}
@media print{:root{--page:#fff;--paper:#fff;--ink:#000}.sheet{max-width:none;padding:0;box-shadow:none}.story,.feature,.section{break-inside:avoid}}
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
    note = (s.get("deck") or "").strip()
    meta = f'<p class="meta">Authors’ note: {e(note[:200])}{"…" if len(note) > 200 else ""}</p>' if note else ""
    body = s.get("body", [])
    first = (body[0] if body and not isinstance(body, str) else str(body)).lstrip()[:1]
    drop = " drop" if first.isalpha() else ""   # a drop cap on "$" or a digit looks broken, especially before MathJax runs
    return (f'<article class="lead">{kicker(s)}<h2 class="hd">{e(s["headline"])}</h2>{meta}'
            f'<div class="text{drop}">{paras(body)}</div>{source(s)}</article>')


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
    return f'<section class="section"><h2 class="section-title">{e(sec["name"])}</h2>{note}{stories}</section>'


def render_pull(q):
    if not q:
        return ""
    cite = f"<cite>{e(q['attribution'])}</cite>" if q.get("attribution") else ""
    return f'<blockquote class="pull">{e(q["text"])}{cite}</blockquote>'


def _brief(b):
    i = e(b["arxiv_id"]) if b.get("arxiv_id") else ""
    sep = "" if b["headline"][-1:] in ".?!" else "."
    who = []
    if b.get("authors"):
        who.append(e(b["authors"]))
    if i:
        who.append(f'<a href="https://arxiv.org/abs/{i}" target="_blank" rel="noopener">{i}</a>')
    by = f'<span class="by">{" · ".join(who)}</span>' if who else ""
    return f'<div class="brief"><b>{e(b["headline"])}{sep}</b> {e(b.get("text", ""))}{by}</div>'


def render_briefs(items):
    """All papers not given a story, grouped by topic (groups ordered by their best-ranked paper)."""
    if not items:
        return ""
    groups = {}
    for b in items:
        groups.setdefault(b.get("section", ""), []).append(b)
    out = [f'<h2 class="section-title wide">In Brief</h2>']
    for name, bs in groups.items():
        head = f'<h3 class="brief-group">{e(name)} <small>({len(bs)})</small></h3>' if name else ""
        out.append(f'{head}<div class="briefs">{"".join(_brief(b) for b in bs)}</div>')
    return "".join(out)


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
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#f6f1e7">
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
    body, run = [], []
    for idx, sec in enumerate(sections):
        run.append(render_section(sec))
        if d.get("pullquote") and idx == min(pull_after, len(sections) - 1):
            body.append(f'<div class="sections">{"".join(run)}</div>' + render_pull(d["pullquote"]))
            run = []
    if run:
        body.append(f'<div class="sections">{"".join(run)}</div>')
    footer = ("Text is excerpted verbatim from the authors’ abstracts as posted on arXiv and has not been peer reviewed. "
              "Follow the links for the full papers.")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#f6f1e7">
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


