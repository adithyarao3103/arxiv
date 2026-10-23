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
    assert "journal or acceptance" in d["lead"]["why_it_matters"] and "45 pages" in d["lead"]["why_it_matters"]
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
    assert P.match("E. Witten")[1] == 10 and P.match("Seok Kim")[1] >= 4
    s_two, hits = P.paper_score({"authors": ["Edward Witten", "Seok Kim", "Z. Nobody"]})
    assert hits[0][0] == "Edward Witten" and abs(s_two - (10 + 0.2 * P.match("Seok Kim")[1])) < 1e-9
    assert P.paper_score({"authors": ["Z. Nobody"]}) == (0.0, [])
    x = authors.ProminentAuthors(["Ada Lovelace | 9", "Charles Babbage"])
    assert x.match("A. Lovelace")[1] == 9 and x.match("Charles Babbage")[1] == 4
    print("authors ok:", len(P), "entries")


def test_ranking_and_digest():
    ps = fixture()
    d = ex.make_digest(ps, CFG)
    assert d["lead"]["arxiv_id"] == "2610.00001", "accepted, long, cross-listed, results-rich paper leads"
    assert "journal or acceptance" in d["lead"]["why_it_matters"] and "45 pages" in d["lead"]["why_it_matters"]
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
    ps = fixture()
    assert ex.make_digest(ps, CFG)["lead"]["arxiv_id"] == "2610.00001"
    # a modest paper by a score-10 author overtakes the previous lead
    ps[-2] = dict(ps[-2], authors=["Z. Nobody", "Edward Witten"])          # 2610.00019, "Unrelated musings"
    d = ex.make_digest(ps, CFG)
    assert d["lead"]["arxiv_id"] == ps[-2]["id"] and d["lead"]["notable"] == ["Edward Witten"]
    assert "Edward Witten" in d["lead"]["why_it_matters"] and "author score 10" in d["lead"]["why_it_matters"]
    # same paper with authors of different scores: tier 10 > tier 8 > tier 4 > unlisted
    P = authors.ProminentAuthors()
    def paper_score_with(name):
        q = dict(fixture()[-2], authors=[name])
        q["_author_score"], q["_authors_hit"] = P.paper_score(q)
        return ex.score(q)[0]
    s10, s8, s4, s0 = (paper_score_with(n) for n in ("Edward Witten", "Seok Kim", "Kallol Sen", "Z. Nobody"))
    assert s10 > s8 > s4 > s0, (s10, s8, s4, s0)
    assert P.match("Kallol Sen")[1] == 4 and P.match("Seok Kim")[1] == 8
    # secondary (cross-listed) papers never lead, even with a score-10 author
    ps2 = fixture()
    ps2[2] = dict(ps2[2], authors=["Juan Maldacena"])
    assert ex.make_digest(ps2, CFG)["lead"]["arxiv_id"] == "2610.00001"
    print("author-score ranking ok")


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
    assert "more papers" in html and "brief-group" in html
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
        assert "No. 1" in html and "Past editions" in html and "verbatim" in html and "Why it leads." in html
        assert (t / "docs" / "archive" / "2026-10-22.html").exists()
        top = (t / "root" / "index.html").read_text()
        assert 'href="docs/archive/"' in top and 'href="archive/"' not in top and 'href="archive/"' in html, "root and docs copies differ only in the archive link"
        assert top.replace('href="docs/archive/"', 'href="archive/"') == html
        assert (t / "root" / ".nojekyll").exists()
        before = html
        rc, out = call(*base, "--now", "2026-10-23T11:30"); print(" ", out)
        assert "keeping the current edition" in out and (t / "docs" / "index.html").read_text() == before
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


if __name__ == "__main__":
    test_split(); test_authors(); test_ranking_and_digest(); test_author_scores_rank_papers(); test_nothing_dropped(); test_render_light_and_layout(); test_pipeline(); print("ALL PASSED")
