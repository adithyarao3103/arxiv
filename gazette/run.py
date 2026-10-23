"""Generate today's edition.

  python -m gazette.run                      # normal run (skips if today's edition exists)
  python -m gazette.run --force              # regenerate today's edition
  python -m gazette.run --not-before-hour 11 # used by the scheduled workflow (see README)
  python -m gazette.run --rerender           # rebuild every page from saved digests (after editing the template)
  python -m gazette.run ... --root-dir DIR   # also write DIR/index.html (default: repo root, so /<repo>/ works as well as /<repo>/docs/)
  python -m gazette.run --papers-file p.json --docs-dir /tmp/out --data-dir /tmp/data   # offline testing

No API key or AI is involved: the edition is built from verbatim abstract excerpts (see gazette/extractive.py).
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import extractive, fetch, render

ROOT = Path(__file__).resolve().parent.parent


def load_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def write_pages(docs, cfg, digest, date, latest, root=None):
    """Write the archived edition and, for the latest one, the front page.

    The front page is written to docs/index.html and, when `root` is given, also to <root>/index.html so that
    https://<user>.github.io/<repo>/ works as well as .../<repo>/docs/. The two copies differ only in the
    relative link to the archive (archive/ from docs/, docs/archive/ from the repo root).
    """
    (docs / "archive").mkdir(parents=True, exist_ok=True)
    archived = dict(digest, nav=[{"label": "Past editions", "href": "./"}, {"label": "Latest edition", "href": "../index.html"}])
    (docs / "archive" / f"{date}.html").write_text(render.build(archived), encoding="utf-8")
    if latest:
        home = dict(digest, nav=[{"label": "Past editions", "href": "archive/"}])
        (docs / "index.html").write_text(render.build(home), encoding="utf-8")
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)
            top = dict(digest, nav=[{"label": "Past editions", "href": "docs/archive/"}])
            (root / "index.html").write_text(render.build(top), encoding="utf-8")
            (root / ".nojekyll").touch()


def write_archive_index(docs, cfg, editions):
    (docs / "archive" / "index.html").write_text(render.build_archive(cfg["title"], editions), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--not-before-hour", type=int, default=None)
    ap.add_argument("--rerender", action="store_true")
    ap.add_argument("--papers-file")
    ap.add_argument("--docs-dir")
    ap.add_argument("--root-dir", help="where to also write the root index.html (default: the repo root, but only when --docs-dir is not given)")
    ap.add_argument("--data-dir")
    ap.add_argument("--now", help="override the current time, ISO format (testing)")
    args = ap.parse_args()

    cfg = load_json(ROOT / "config.json", None)
    docs = Path(args.docs_dir) if args.docs_dir else ROOT / "docs"
    data = Path(args.data_dir) if args.data_dir else ROOT / "data"
    if args.root_dir:
        root_index = Path(args.root_dir)
    else:
        root_index = ROOT if (not args.docs_dir and cfg.get("root_index", True)) else None
    state = load_json(data / "state.json", {"editions": []})
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.fromisoformat(args.now).replace(tzinfo=tz) if args.now else datetime.now(tz)
    today = now.date().isoformat()
    date_label = f"{now:%A}, {now:%B} {now.day}, {now.year}"

    if args.rerender:
        eds = sorted(state["editions"], key=lambda e: e["date"])
        for i, ed in enumerate(eds):
            d = load_json(data / "digests" / f"{ed['date']}.json", None)
            if d:
                write_pages(docs, cfg, d, ed["date"], latest=(i == len(eds) - 1), root=root_index)
        write_archive_index(docs, cfg, eds)
        print(f"re-rendered {len(eds)} editions")
        return 0

    if not (args.force or args.papers_file):
        if args.not_before_hour is not None and now.hour < args.not_before_hour:
            print(f"it is {now:%H:%M} in {cfg['timezone']}, before {args.not_before_hour}:00; skipping this trigger")
            return 0
        if any(e["date"] == today for e in state["editions"]):
            print(f"edition for {today} already exists; nothing to do")
            return 0

    others = [e for e in state["editions"] if e["date"] != today]
    covered = {i for e in others[-14:] for i in e.get("ids", [])}

    if args.papers_file:
        raw = load_json(args.papers_file, [])
        papers, meta = (raw["papers"] if isinstance(raw, dict) else raw), {}
    else:
        papers, meta = fetch.fetch_papers(
            cfg["categories"], cfg.get("cross_from", []), cfg.get("include_other_crosslists", False),
            cfg["max_per_category"], cfg["window_hours"])
        if meta["possibly_truncated"]:
            print(f"warning: {meta['possibly_truncated']} may have hit max_per_category; consider raising it")
    fresh = [p for p in papers if p["id"] not in covered]
    if len(fresh) < cfg["min_new_papers"]:
        print(f"only {len(fresh)} papers not already covered (minimum {cfg['min_new_papers']}); keeping the current edition")
        return 0

    digest = extractive.make_digest(fresh, cfg)

    n_stories = 1 + len(digest["features"]) + sum(len(s["stories"]) for s in digest["sections"]) + len(digest["briefs"])
    tiers = {t: sum(1 for p in fresh if p["tier"] == t) for t in ("primary", "secondary", "crosslist")}
    stats = {"Papers scanned": str(len(fresh)), f"{'/'.join(cfg['categories'])} primary": str(tiers["primary"])}
    if tiers["secondary"]:
        stats[f"{'/'.join(cfg['cross_from'])} cross-lists"] = str(tiers["secondary"])
    stats["Items selected"] = str(n_stories)
    digest.update({
        "title": cfg["title"], "tagline": cfg.get("tagline", ""), "date": date_label,
        "edition": f"No. {len(others) + 1} · Morning Edition",
        "categories": list(cfg["categories"]) + [f"{c} (cross-lists)" for c in cfg.get("cross_from", [])],
        "stats": stats,
    })

    entry = {"date": today, "label": date_label, "headline": digest["lead"]["headline"],
             "ids": [p["id"] for p in fresh], "newest": meta.get("window_end", "")}
    editions = sorted(others + [entry], key=lambda e: e["date"])
    # everything is computed; only now touch the files, so a failure never leaves a half-written site
    save_json(data / "digests" / f"{today}.json", digest)
    write_pages(docs, cfg, digest, today, latest=True, root=root_index)
    write_archive_index(docs, cfg, editions)
    save_json(data / "state.json", {"editions": editions})
    print(f"edition {today}: {n_stories} items from {len(fresh)} papers; lead: {digest['lead']['headline']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
