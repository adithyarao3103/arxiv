"""Fetch recent arXiv papers via the official API and tag them with tiers.

Tiers: "primary" (primary category is one of `categories`), "secondary" (primary category is one of
`cross_from` and cross-listed into `categories`), "crosslist" (anything else cross-listed in).
Standard library only. arXiv asks clients to wait ~3 seconds between requests.
"""
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API = "https://export.arxiv.org/api/query"
US_EASTERN = ZoneInfo("America/New_York")
_ANNOUNCE_WEEKDAYS = {6, 0, 1, 2, 3}  # arXiv announces Sunday to Thursday at 20:00 ET
NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def _get(url, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arxiv-gazette-site/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except Exception as exc:  # network error, 429/5xx, timeout
            last = exc
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"arXiv request failed after {retries} tries: {last}")


def _clean(text):
    return " ".join((text or "").split())


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    papers = []
    for e in root.findall("a:entry", NS):
        arxiv_id = e.findtext("a:id", "", NS).rsplit("/abs/", 1)[-1]
        base = arxiv_id.rsplit("v", 1)[0] if "v" in arxiv_id else arxiv_id
        prim = e.find("x:primary_category", NS)
        papers.append({
            "id": base,
            "title": _clean(e.findtext("a:title", "", NS)),
            "authors": [_clean(a.findtext("a:name", "", NS)) for a in e.findall("a:author", NS)],
            "abstract": _clean(e.findtext("a:summary", "", NS)),
            "primary_category": prim.get("term") if prim is not None else "",
            "categories": [c.get("term") for c in e.findall("a:category", NS)],
            "published": e.findtext("a:published", "", NS),
            "comment": _clean(e.findtext("x:comment", "", NS)),
            "url": f"https://arxiv.org/abs/{base}",
        })
    return papers


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def classify(papers, cats, cross_from, keep_other=False):
    for p in papers:
        if p["primary_category"] in cats:
            p["tier"] = "primary"
        elif cross_from and p["primary_category"] in cross_from and any(c in cats for c in p["categories"]):
            p["tier"] = "secondary"
        else:
            p["tier"] = "crosslist"
    if cross_from and not keep_other:
        papers = [p for p in papers if p["tier"] != "crosslist"]
    order = {"primary": 0, "secondary": 1, "crosslist": 2}
    papers.sort(key=lambda p: p["published"], reverse=True)
    papers.sort(key=lambda p: order[p["tier"]])
    return papers


def _cutoff(day):
    """End of the submission window announced on `day`: 14:00 ET that day (Friday 14:00 ET for Sunday's)."""
    d = day - timedelta(days=2) if day.weekday() == 6 else day
    return datetime(d.year, d.month, d.day, 14, 0, tzinfo=US_EASTERN)


def announcement_window(now=None):
    """The submission window of the latest arXiv announcement made before `now`.

    arXiv announces new papers Sun-Thu at 20:00 ET; each announcement contains what was submitted between the
    previous 14:00 ET cutoff and this one (Monday's announcement therefore covers the whole weekend).
    Returns (start, end, announcement_date) with start/end as UTC datetimes.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(US_EASTERN)
    day = now.date()
    while not (day.weekday() in _ANNOUNCE_WEEKDAYS and now >= datetime(day.year, day.month, day.day, 20, 15, tzinfo=US_EASTERN)):
        day -= timedelta(days=1)
    prev = day - timedelta(days=1)
    while prev.weekday() not in _ANNOUNCE_WEEKDAYS:
        prev -= timedelta(days=1)
    return _cutoff(prev).astimezone(timezone.utc), _cutoff(day).astimezone(timezone.utc), day


def fetch_papers(categories, cross_from=(), keep_other=False, max_per_category=200, window_hours=48, window=None):
    """Return (papers, meta). Raises RuntimeError if nothing could be fetched.

    `window=(start, end)` (UTC datetimes, see announcement_window) keeps exactly the papers first submitted in
    that interval; without it the last `window_hours` before the newest paper are kept (older behaviour).
    """
    seen, found, truncated_at = set(), [], {}
    for i, cat in enumerate(categories):
        if i:
            time.sleep(3)
        q = urllib.parse.urlencode({
            "search_query": f"cat:{cat}", "sortBy": "submittedDate", "sortOrder": "descending",
            "start": 0, "max_results": max_per_category,
        })
        batch = parse(_get(f"{API}?{q}"))
        if len(batch) >= max_per_category:
            truncated_at[cat] = min(_ts(p["published"]) for p in batch)
        for p in batch:
            if p["id"] not in seen:
                seen.add(p["id"])
                found.append(p)
    if not found:
        raise RuntimeError("arXiv returned no papers")
    if window:
        cutoff, newest = window
        papers = [p for p in found if cutoff < _ts(p["published"]) <= newest]
    else:
        newest = max(_ts(p["published"]) for p in found)
        cutoff = newest - timedelta(hours=window_hours)
        papers = [p for p in found if _ts(p["published"]) >= cutoff]
    in_window = len(papers)
    papers = classify(papers, list(categories), list(cross_from), keep_other)
    meta = {
        "window_start": cutoff.isoformat(timespec="seconds"),
        "window_end": newest.isoformat(timespec="seconds"),
        "dropped_crosslists": in_window - len(papers),
        "possibly_truncated": [c for c, t in truncated_at.items() if t >= cutoff],
    }
    return papers, meta
