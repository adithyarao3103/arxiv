"""A deterministic "editor": no AI, no API, no network.

Papers are ranked with a few transparent signals, grouped into sections by keyword, and every piece of
text in the edition is a verbatim excerpt of the authors' own abstract. Nothing is paraphrased or invented.
"""
import math
import re

# ---- ranking signals (edit the weights here if you disagree with them) -----------------------------
VENUE = re.compile(
    r"\b(accepted|to appear|published in|appeared in|journal reference|jhep|prl|phys\.? ?rev|physical review|"
    r"nucl\.? ?phys|class\.? ?quantum|cqg|commun\.? ?math|annales|j\.? ?math\.? ?phys)", re.I)
LOW_PRIORITY = re.compile(r"\b(proceedings|lecture notes|lectures|talk|contribution to|summer school)\b", re.I)
RESULT_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bwe (?:show|prove|establish|derive|find|demonstrate|construct|solve|compute|report|obtain|determine)\b",
    r"\bfor the first time\b",
    r"\b(?:conjecture|counterexample|no-go|theorem)\b",
    r"\b(?:exact|closed[- ]form|analytic(?:al)?)\b",
    r"\b(?:bounds?|constraints?|upper limit|lower limit)\b",
)]
W_VENUE, W_PAGES, W_CROSS, W_RESULT, P_SHORT, P_LOW = 2.0, 1.0, 0.5, 0.5, 1.0, 2.0


def score(p):
    s, why = 0.0, []
    comment = p.get("comment", "")
    if VENUE.search(comment):
        s += W_VENUE
        why.append("a journal or acceptance is noted")
    m = re.search(r"(\d+)\s*pages", comment)
    if m and int(m.group(1)) >= 30:
        s += W_PAGES
        why.append(f"{m.group(1)} pages")
    extra = max(len(p.get("categories", [])) - 1, 0)
    s += W_CROSS * min(extra, 3)
    if extra >= 2:
        why.append(f"cross-listed to {extra} other categories")
    hits = sum(1 for r in RESULT_PATTERNS if r.search(p["abstract"]))
    s += W_RESULT * hits
    if hits >= 2:
        why.append("the abstract states concrete results")
    if len(p["abstract"].split()) < 40:
        s -= P_SHORT
    if LOW_PRIORITY.search(comment + " " + p["title"]):
        s -= P_LOW
    return s, why


def rank(papers):
    ps = sorted(papers, key=lambda p: p["published"], reverse=True)  # newest first, then stable sort by score
    for p in ps:
        p["_score"], p["_why"] = score(p)
    return sorted(ps, key=lambda p: -p["_score"])


# ---- text excerpts ---------------------------------------------------------------------------------
_ABBR = ["et al.", "e.g.", "i.e.", "cf.", "vs.", "Fig.", "Figs.", "Eq.", "Eqs.", "Ref.", "Refs.", "Sec.", "approx.", "resp.", "etc."]
_MATH = re.compile(r"\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\]", re.S)


def split_sentences(text):
    """Split an abstract into sentences without breaking inside LaTeX, abbreviations or decimals. Lossless."""
    stash = []

    def hold(m):
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"

    t = _MATH.sub(hold, text)
    for a in _ABBR:
        t = t.replace(a, a.replace(".", "\x01"))
    t = re.sub(r"(\d)\.(\d)", "\\1\x01\\2", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\x00(\u201c\"])", t)
    out = []
    for part in parts:
        part = part.replace("\x01", ".")
        part = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], part)
        if part.strip():
            out.append(part)
    return out


def excerpt(abstract, budget, per_par=2, max_sent=6):
    """Whole leading sentences until ~budget characters, grouped into short paragraphs."""
    out, n = [], 0
    for s in split_sentences(abstract)[:max_sent]:
        out.append(s)
        n += len(s)
        if n >= budget:
            break
    return [" ".join(out[i:i + per_par]) for i in range(0, len(out), per_par)]


def byline(p):
    a = p.get("authors") or []
    if len(a) <= 2:
        return " and ".join(a)
    return f"{a[0]} et al."


# ---- sections --------------------------------------------------------------------------------------
def assign_section(p, cfg):
    rules = cfg.get("sections") or []
    if not rules:
        return p["primary_category"]
    title, abstract = p["title"].lower(), p["abstract"].lower()
    best, best_hits = None, 0
    for r in rules:
        hits = sum(2 * title.count(k) + abstract.count(k) for k in r["keywords"])
        if hits > best_hits:
            best, best_hits = r["name"], hits
    return best or f"Also in {'/'.join(cfg['categories'])}"


def _story(p, budget):
    return {"headline": p["title"], "body": excerpt(p["abstract"], budget), "authors": byline(p), "arxiv_id": p["id"]}


def make_digest(papers, cfg):
    size, cats = cfg["size"], cfg["categories"]
    ranked = rank([dict(p) for p in papers])
    prim = [p for p in ranked if p["tier"] != "secondary"]
    sec = [p for p in ranked if p["tier"] == "secondary"]
    if not prim:
        prim, sec = sec, []
    for p in ranked:
        p["_section"] = assign_section(p, cfg)

    lead_p = prim[0]
    feats = prim[1:1 + size["features"]]
    rest = prim[1 + size["features"]:]
    stories = rest[:size["section_stories"]]
    leftovers = rest[size["section_stories"]:] + sec[size["secondary_stories"]:]
    sec_stories = sec[:size["secondary_stories"]]
    brief_ps = leftovers[:size["briefs"]]

    why = "; ".join(lead_p["_why"]) or "no standout signal"
    lead = _story(lead_p, 750)
    lead.update({
        "kicker": f"Lead Story · {lead_p['primary_category']}",
        "deck": lead_p.get("comment", ""),
        "why_label": "Why it leads.",
        "why_it_matters": f"Highest automatic score today ({lead_p['_score']:g}): {why}.",
    })

    features = []
    for p in feats:
        f = _story(p, 420)
        f["kicker"] = f"{p['_section']} · {p['primary_category']}"
        features.append(f)

    by_section, best = {}, {}
    for p in stories:
        by_section.setdefault(p["_section"], []).append(_story(p, 260))
        best[p["_section"]] = max(best.get(p["_section"], -math.inf), p["_score"])
    sections = [{"name": n, "stories": by_section[n]} for n in sorted(by_section, key=lambda n: -best[n])]
    if sec_stories:
        sections.append({
            "name": "Across the Border",
            "note": f"Papers primarily filed under {', '.join(cfg.get('cross_from', []))} and cross-listed to {', '.join(cats)}",
            "stories": [_story(p, 260) for p in sec_stories]})

    briefs = []
    for p in brief_ps:
        first = split_sentences(p["abstract"])[0]
        tag = f" (primary category {p['primary_category']})" if p["tier"] == "secondary" else ""
        briefs.append({"headline": p["title"], "text": first + tag, "arxiv_id": p["id"]})

    return {
        "lead": lead, "features": features, "sections": sections, "briefs": briefs,
        "editors_note": "No human or AI editor today: papers are ranked automatically by simple signals "
                        "(a journal or acceptance noted, page count, cross-listing breadth, stated results).",
        "footer": "Text is excerpted verbatim from the authors’ abstracts as posted on arXiv; stories are chosen by an "
                  "automatic ranking, not by an editor, and have not been peer reviewed. Follow the links for the full papers.",
    }
