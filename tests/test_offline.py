"""Offline tests, no network and no key. Run with:  python tests/test_offline.py"""
import contextlib, io, json, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gazette import extractive as ex, run, authors, render  # noqa: E402

CFG = json.loads((ROOT / "config.json").read_text())


def test_split():
    t = r"Smith et al. report a bound $c \leq 1.5$. It holds for e.g. AdS$_5$ vacua, see Fig. 3. We find 0.85 of it. $\mathcal{N}=4$ theories are special."
    s = ex.split_sentences(t)
    assert len(s) == 4, s
    assert " ".join(s) == t, "splitting must be lossless"
    assert s[0].endswith("$.") and s[1].startswith("It holds") and s[3].startswith("$\\mathcal")
    print("split ok")


def paper(i, title, abstract, tier="primary", prim="hep-th", cats=None, comment="", day="2026-10-21T10:00:00Z"):
    return {"id": f"2610.{i:05d}", "title": title, "authors": ["A. Author", "B. Author", "C. Author"], "abstract": abstract,
            "primary_category": prim, "categories": cats or [prim], "published": day, "comment": comment,
            "url": f"https://arxiv.org/abs/2610.{i:05d}", "tier": tier}


RES = "We show that the bound holds exactly and prove a conjecture. We derive a closed-form constraint. The method is simple."
def fixture():
    ps = [paper(1, "Holographic entanglement in AdS", "We study entanglement in holographic CFT states. " + RES + " More detail follows here.",
                cats=["hep-th", "gr-qc", "math-ph"], comment="45 pages; accepted in JHEP"),
          paper(2, "Lecture notes on strings", "Short intro to string theory. " + RES, comment="Lectures at a summer school, 60 pages"),
          paper(3, "Black holes and de Sitter horizons", "We find that horizon entropy changes. " + RES, prim="gr-qc", cats=["gr-qc", "hep-th"], tier="secondary"),
          paper(4, "Tiny note", "Very short abstract.")]
    topics = ["Scattering amplitudes for supergravity", "Topological symmetry and anomalies", "Brane compactification moduli",
              "Chern-Simons field theory", "Inflation and cosmology", "Swampland string constraints", "Integrable operator spectra",
              "Entanglement and bulk reconstruction", "Quantum gravity spacetime", "Unrelated musings"]
    for k, t in enumerate(topics, start=10):
        ps.append(paper(k, t, f"{t} are studied here. We show a new relation. It has interesting consequences for the field.", day=f"2026-10-21T{k:02d}:00:00Z"))
    ps.append(paper(30, "Another cross-list", "A gr-qc paper. We show things. " + RES, prim="gr-qc", cats=["gr-qc", "hep-th"], tier="secondary"))
    return ps


def test_ranking_and_digest():
    ps = fixture()
    d = ex.make_digest(ps, CFG)
    assert d["lead"]["arxiv_id"] == "2610.00001", "accepted, long, cross-listed, results-rich paper leads"
    assert len({i["arxiv_id"] for i in [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]}) == len(ps), "no paper dropped"
    all_items = [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]
    ids = [i["arxiv_id"] for i in all_items]
    assert len(ids) == len(set(ids)), "no paper appears twice"
    border = [s for s in d["sections"] if s["name"] == "Across the Border"]
    assert border and {s["arxiv_id"] for s in border[0]["stories"]} <= {"2610.00003", "2610.00030"}
    assert all(i not in ("2610.00003", "2610.00030") for i in [d["lead"]["arxiv_id"]] + [f["arxiv_id"] for f in d["features"]]), "secondary papers never lead or feature"
    assert "2610.00002" not in [d["lead"]["arxiv_id"]], "lecture notes are demoted"
    names = [s["name"] for s in d["sections"]]
    assert any("Strings" in n for n in names) and any("Field Theory" in n for n in names), names
    assert len(d["features"]) <= CFG["size"]["features"]
    # nothing is invented: every body paragraph is verbatim abstract text, and headlines are real titles
    by = {p["id"]: p for p in ps}
    norm = lambda x: re.sub(r"\s+", " ", x)
    for it in all_items:
        p = by[it["arxiv_id"]]
        assert it["headline"] == p["title"]
        for para in it.get("body", []):
            assert norm(para) in norm(p["abstract"]), (it["arxiv_id"], para)
        if "text" in it:
            assert norm(it["text"].split(" (primary category")[0]) in norm(p["abstract"])
    print("ranking/digest ok:", d["lead"]["headline"], "|", names)


def test_authors():
    P = authors.ProminentAuthors()
    assert len(P) > 500, len(P)
    yes = ["Edward Witten", "E. Witten", "J. M. Maldacena", "Juan Martin Maldacena", "Dieter Lüst", "Yu-Tin Huang",
           "Gerard 't Hooft", "G. 't Hooft", "J. de Boer", "Eric D'Hoker", "Iñaki García Etxebarria", "Xi Yin", "A. Strominger"]
    no = ["Y. Wang", "Yi Wang", "S. Kim", "B. Strominger", "Edwin Witten", "A. N. Other", "Madonna"]
    for n in yes:
        assert P.match(n), n
    for n in no:
        assert not P.match(n), n
    assert P.match("E. Witten")[1] == 10 and P.match("Seok Kim")[1] == 8
    s_two, hits = P.paper_score({"authors": ["Edward Witten", "Seok Kim", "Z. Nobody"]})
    assert hits[0][0] == "Edward Witten" and s_two == 10, "paper score is the best author's score, never a sum"
    assert P.paper_score({"authors": ["Z. Nobody"]}) == (0.0, [])
    x = authors.ProminentAuthors(["Ada Lovelace | 9", "Charles Babbage"])
    assert x.match("A. Lovelace")[1] == 9 and x.match("Charles Babbage")[1] == 4
    print("authors ok:", len(P), "entries")


def test_ranking_and_digest():
    ps = fixture()
    d = ex.make_digest(ps, CFG)
    assert d["lead"]["arxiv_id"] == "2610.00001", "accepted, long, cross-listed, results-rich paper leads"
    assert len({i["arxiv_id"] for i in [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]}) == len(ps), "no paper dropped"
    all_items = [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]
    ids = [i["arxiv_id"] for i in all_items]
    assert len(ids) == len(set(ids)), "no paper appears twice"
    border = [s for s in d["sections"] if s["name"] == "Across the Border"]
    assert border and {s["arxiv_id"] for s in border[0]["stories"]} <= {"2610.00003", "2610.00030"}
    assert all(i not in ("2610.00003", "2610.00030") for i in [d["lead"]["arxiv_id"]] + [f["arxiv_id"] for f in d["features"]]), "secondary papers never lead or feature"
    assert "2610.00002" not in [d["lead"]["arxiv_id"]], "lecture notes are demoted"
    names = [s["name"] for s in d["sections"]]
    assert any("Strings" in n for n in names) and any("Field Theory" in n for n in names), names
    assert len(d["features"]) <= CFG["size"]["features"]
    # nothing is invented: every body paragraph is verbatim abstract text, and headlines are real titles
    by = {p["id"]: p for p in ps}
    norm = lambda x: re.sub(r"\s+", " ", x)
    for it in all_items:
        p = by[it["arxiv_id"]]
        assert it["headline"] == p["title"]
        for para in it.get("body", []):
            assert norm(para) in norm(p["abstract"]), (it["arxiv_id"], para)
        if "text" in it:
            assert norm(it["text"].split(" (primary category")[0]) in norm(p["abstract"])
    print("ranking/digest ok:", d["lead"]["headline"], "|", names)


def test_authors():
    P = authors.ProminentAuthors()
    assert len(P) > 500, len(P)
    yes = ["Edward Witten", "E. Witten", "J. M. Maldacena", "Juan Martin Maldacena", "Dieter Lüst", "Yu-Tin Huang",
           "Gerard 't Hooft", "G. 't Hooft", "J. de Boer", "Eric D'Hoker", "Iñaki García Etxebarria", "Xi Yin", "A. Strominger"]
    no = ["Y. Wang", "Yi Wang", "S. Kim", "B. Strominger", "Edwin Witten", "A. N. Other", "Madonna"]
    for n in yes:
        assert P.match(n), n
    for n in no:
        assert not P.match(n), n
    assert authors.ProminentAuthors(["Ada Lovelace"]).match("A. Lovelace")
    print("authors ok:", len(P), "entries")


def test_author_scores_rank_papers():
    P = authors.ProminentAuthors()
    ps = fixture()
    assert ex.make_digest(ps, CFG)["lead"]["arxiv_id"] == "2610.00001"        # no listed author: simple signals decide
    # a modest paper by Witten leads, even though another paper has far stronger signals
    ps[-2] = dict(ps[-2], authors=["Z. Nobody", "Edward Witten"])             # 2610.00019, "Unrelated musings"
    assert ex.make_digest(ps, CFG)["lead"]["arxiv_id"] == ps[-2]["id"]
    # scores are NOT added: one score-10 author beats a paper with many score-8 authors, and beats two score-6 authors
    many = [n for n, s in P.in_paper({"authors": ["Seok Kim", "Xi Yin", "Hong Liu", "Zohar Komargodski", "Hirosi Ooguri", "Shiraz Minwalla"]})]
    assert len(many) == 6 and P.paper_score({"authors": many})[0] == 8 == max(s for _, s in P.in_paper({"authors": many}))
    qs = fixture()
    qs[-2] = dict(qs[-2], authors=["Edward Witten"])                          # 10 alone
    qs[-3] = dict(qs[-3], authors=many)                                       # six 8s, plus every other signal equal or better
    qs[-3]["comment"] = "60 pages; accepted in JHEP"
    assert ex.make_digest(qs, CFG)["lead"]["arxiv_id"] == qs[-2]["id"], "one 10 beats any number of 8s"
    # ties on author score fall back to the simple signals
    qt = fixture()
    qt[-2] = dict(qt[-2], authors=["Seok Kim"]); qt[-3] = dict(qt[-3], authors=["Xi Yin"], comment="60 pages; accepted in JHEP")
    assert ex.make_digest(qt, CFG)["lead"]["arxiv_id"] == qt[-3]["id"]
    # tiers: 10 > 8 > 4 > unlisted
    assert [P.paper_score({"authors": [n]})[0] for n in ("Edward Witten", "Seok Kim", "Kallol Sen", "Z. Nobody")] == [10, 8, 4, 0]
    # secondary (cross-listed) papers never lead, even with a score-10 author
    ps2 = fixture()
    ps2[2] = dict(ps2[2], authors=["Juan Maldacena"])
    assert ex.make_digest(ps2, CFG)["lead"]["arxiv_id"] == "2610.00001"
    print("author ranking ok")


def test_nothing_dropped():
    ps = fixture()
    for k in range(100, 400):                                  # a realistic hep-th day: ~300 papers
        ps.append(paper(k, f"Paper number {k} on strings", "We show a result about strings. More text follows here.",
                        tier=("primary" if k % 3 else "crosslist"), prim=("hep-th" if k % 3 else "math-ph"), cats=["hep-th"] if k % 3 else ["math-ph", "hep-th"]))
    d = ex.make_digest(ps, CFG)
    items = [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]
    assert sorted(i["arxiv_id"] for i in items) == sorted(p["id"] for p in ps), "every paper appears exactly once"
    assert len(d["briefs"]) > 200 and all(b.get("section") for b in d["briefs"])
    html = render.build(dict(d, title="T", date="d", edition="e", categories=["hep-th"], stats={}, nav=[]))
    for p in ps:
        assert f"arxiv.org/abs/{p['id']}" in html, p["id"]
    assert "brief-group" in html
    print("nothing dropped ok:", len(ps), "papers ->", len(items))


def test_render_light_and_layout():
    d = ex.make_digest(fixture(), CFG)
    d.update({"title": "T", "date": "d", "edition": "No. 1", "categories": ["hep-th"], "stats": {"a": "1"}})
    d["lead"]["body"] = [r"$\\mathcal{N}=4$ theory. We show things."]
    d["lead"]["deck"] = "v2: 45 pages, 12 figures"
    html = render.build(dict(d, nav=[]))
    assert "prefers-color-scheme" not in html and "data-theme" not in html and "dark" not in html.lower().replace("darkness", "")
    assert 'name="color-scheme" content="light"' in html and "color-scheme:light only" in html
    assert 'class="text drop"' not in html, "no drop cap when the abstract starts with LaTeX"
    low = html.lower()
    for bad in ("why it leads", "from the desk", "score", "ranked", "ranking", "★", "lower-ranked", "automatic"):
        assert bad not in low, bad
    assert "Authors’ note: v2: 45 pages" in html and 'class="deck"' not in html
    d["lead"]["body"] = ["We show things."]
    assert 'class="text drop"' in render.build(dict(d, nav=[]))
    assert html.count('class="section"') == len(d["sections"])
    print("render ok")


def call(*argv):
    sys.argv = ["run"] + list(argv)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run.main()
    return rc, buf.getvalue().strip()


def test_pipeline():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        pf = t / "papers.json"
        pf.write_text(json.dumps(fixture()))
        base = ["--papers-file", str(pf), "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data"), "--root-dir", str(t / "root")]
        rc, out = call(*base, "--now", "2026-10-22T11:30"); print(" ", out)
        html = (t / "docs" / "index.html").read_text()
        assert "No. 1" in html and "Past editions" in html and "verbatim" in html and "Why it leads" not in html
        assert (t / "docs" / "archive" / "2026-10-22.html").exists()
        top = (t / "root" / "index.html").read_text()
        assert 'href="docs/archive/"' in top and 'href="archive/"' not in top and 'href="archive/"' in html, "root and docs copies differ only in the archive link"
        assert top.replace('href="docs/archive/"', 'href="archive/"') == html
        assert (t / "root" / ".nojekyll").exists()
        before = html
        rc, out = call(*base, "--now", "2026-10-23T11:30"); print(" ", out)
        assert "current edition was kept" in out and (t / "docs" / "index.html").read_text() == before
        newp = fixture()
        for p in newp: p["id"] = "2611" + p["id"][4:]
        pf.write_text(json.dumps(newp))
        rc, out = call(*base, "--now", "2026-10-26T11:30"); print(" ", out)
        idx = (t / "docs" / "archive" / "index.html").read_text()
        assert "No. 2" in (t / "docs" / "index.html").read_text() and idx.index("Monday, October 26") < idx.index("Thursday, October 22")
        rc, out = call("--not-before-hour", "11", "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data"), "--now", "2026-10-27T10:05")
        assert "skipping this trigger" in out
        rc, out = call("--not-before-hour", "11", "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data"), "--now", "2026-10-26T11:40")
        assert "already exists" in out
        (t / "docs" / "index.html").unlink()
        (t / "root" / "index.html").unlink()
        call("--rerender", "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data"), "--root-dir", str(t / "root"))
        assert (t / "docs" / "index.html").exists() and (t / "root" / "index.html").exists()
    print("pipeline ok")


# ---------------------------------------------------------------- announcement window / fetch filtering
def test_announcement_window():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from gazette import fetch
    AMS = ZoneInfo("Europe/Amsterdam")
    def win(t):
        a, b, d = fetch.announcement_window(datetime.fromisoformat(t).replace(tzinfo=AMS))
        return a.strftime("%a %H:%M"), b.strftime("%a %H:%M"), (b - a).total_seconds() / 3600, d.strftime("%a")
    assert win("2026-10-23T11:00") == ("Wed 18:00", "Thu 18:00", 24, "Thu"), win("2026-10-23T11:00")
    assert win("2026-10-24T11:00")[2:] == (24, "Thu") and win("2026-10-25T11:00")[3] == "Thu", "weekend mornings reuse Thursday's batch"
    assert win("2026-10-26T11:00") == ("Thu 18:00", "Fri 18:00", 24, "Sun"), win("2026-10-26T11:00")
    assert win("2026-10-27T11:00")[2:] == (72, "Mon"), "Monday's announcement covers the weekend (arXiv does the same)"
    assert win("2026-11-04T11:00")[:2] == ("Mon 19:00", "Tue 19:00"), "after US daylight saving ends, 14:00 ET is 19:00 UTC"
    print("announcement window ok")


ATOM = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">{}</feed>"""
ENTRY = """<entry><id>http://arxiv.org/abs/{id}v1</id><published>{pub}</published><updated>{pub}</updated>
<title>{id} title</title><summary>An abstract.</summary><author><name>A B</name></author>
<arxiv:primary_category term="{prim}"/>{cats}</entry>"""


def test_fetch_window_and_crosslists():
    from datetime import datetime, timezone
    from gazette import fetch
    def e(i, pub, prim, *extra):
        cats = "".join(f'<category term="{c}"/>' for c in (prim,) + extra)
        return ENTRY.format(id=f"2610.{i:05d}", pub=pub, prim=prim, cats=cats)
    entries = [
        e(1, "2026-10-22T17:00:00Z", "hep-th"),                       # in the Thursday batch
        e(2, "2026-10-22T17:59:58Z", "hep-th", "math-ph"),            # in (hep-th primary, cross-listed elsewhere)
        e(3, "2026-10-22T10:00:00Z", "gr-qc", "hep-th"),              # in: gr-qc cross-list
        e(4, "2026-10-22T10:30:00Z", "hep-ph", "hep-th"),             # in the window but an unwanted cross-list
        e(5, "2026-10-22T18:00:01Z", "hep-th"),                       # after the cutoff -> next batch
        e(6, "2026-10-21T17:59:00Z", "hep-th"),                       # before the window -> previous batch
        e(7, "2026-10-20T12:00:00Z", "hep-th"),                       # two days earlier
    ]
    xml = ATOM.format("".join(entries)).encode()
    orig = fetch._get
    fetch._get = lambda url, retries=4: xml
    try:
        win = (datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc), datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc))
        papers, meta = fetch.fetch_papers(["hep-th"], ["gr-qc"], False, 600, 48, window=win)
        got = {p["id"][-1]: p["tier"] for p in papers}
        assert got == {"1": "primary", "2": "primary", "3": "secondary"}, got
        assert meta["dropped_crosslists"] == 1 and meta["possibly_truncated"] == []
        papers, _ = fetch.fetch_papers(["hep-th"], ["gr-qc"], True, 600, 48, window=win)
        assert {p["id"][-1] for p in papers} == {"1", "2", "3", "4"}, "include_other_crosslists keeps hep-ph"
        # old behaviour (no window) is still available and shows why 48h was too wide: it pulls in several days
        papers, _ = fetch.fetch_papers(["hep-th"], ["gr-qc"], False, 600, 48)
        assert {"5", "6"} <= {p["id"][-1] for p in papers}
        # config: other cross-lists are off
        assert CFG["include_other_crosslists"] is False and CFG["window_mode"] == "announcement"
    finally:
        fetch._get = orig
    print("fetch window/cross-list filtering ok")


def test_force_and_fresh_start():
    place = "<html><body>The first edition appears after the workflow runs for the first time.</body></html>"
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); docs, data, pf = t / "docs", t / "data", t / "p.json"
        pf.write_text(json.dumps(fixture()))
        g = ["--papers-file", str(pf), "--docs-dir", str(docs), "--data-dir", str(data)]
        call(*g, "--now", "2026-10-23T11:00")
        assert "No. 1" in (docs / "index.html").read_text()
        # the same papers again are not news: the edition is kept (normal weekend behaviour)...
        assert "current edition was kept" in call(*g, "--now", "2026-10-24T11:00")[1]
        assert "Friday, October 23" in (docs / "index.html").read_text()
        # ...but FORCE rebuilds from them anyway, so running the workflow with force always changes the page
        out = call(*g, "--force", "--now", "2026-10-24T11:00")[1]
        assert "written" in out and "Saturday, October 24" in (docs / "index.html").read_text(), out
        # leftover state + placeholder front page (e.g. after a manual reset) is a fresh start, even without force
        (docs / "index.html").write_text(place)
        out = call(*g, "--now", "2026-10-25T11:00")[1]
        assert "written" in out and "first edition appears" not in (docs / "index.html").read_text(), out
        # saved editions whose pages were deleted are forgotten instead of blocking the next run
        import shutil; shutil.rmtree(docs)
        out = call(*g, "--now", "2026-10-26T11:00")[1]
        st = json.loads((data / "state.json").read_text())["editions"]
        assert "written" in out and len(st) == 1 and "No. 1" in (docs / "index.html").read_text(), (out, st)
        # rerender with nothing saved says so instead of silently doing nothing
        with tempfile.TemporaryDirectory() as t2:
            r = call("--rerender", "--docs-dir", str(Path(t2) / "d"), "--data-dir", str(Path(t2) / "x"))[1]
            assert "nothing to re-render" in r, r
    print("force / fresh start ok")


if __name__ == "__main__":
    test_split(); test_authors(); test_ranking_and_digest(); test_author_scores_rank_papers(); test_nothing_dropped(); test_render_light_and_layout(); test_pipeline(); test_announcement_window(); test_fetch_window_and_crosslists(); test_force_and_fresh_start(); print("ALL PASSED")
