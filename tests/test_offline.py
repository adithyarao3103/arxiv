"""Offline tests, no network and no key. Run with:  python tests/test_offline.py"""
import contextlib, io, json, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gazette import extractive as ex, run  # noqa: E402

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
    all_items = [d["lead"]] + d["features"] + [s for sec in d["sections"] for s in sec["stories"]] + d["briefs"]
    ids = [i["arxiv_id"] for i in all_items]
    assert len(ids) == len(set(ids)), "no paper appears twice"
    border = [s for s in d["sections"] if s["name"] == "Across the Border"]
    assert border and {s["arxiv_id"] for s in border[0]["stories"]} <= {"2610.00003", "2610.00030"}
    assert all(i not in ("2610.00003", "2610.00030") for i in [d["lead"]["arxiv_id"]] + [f["arxiv_id"] for f in d["features"]]), "secondary papers never lead or feature"
    assert "2610.00002" not in [d["lead"]["arxiv_id"]], "lecture notes are demoted"
    names = [s["name"] for s in d["sections"]]
    assert any("Strings" in n for n in names) and any("Field Theory" in n for n in names), names
    assert len(d["features"]) <= CFG["size"]["features"] and len(d["briefs"]) <= CFG["size"]["briefs"]
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
        base = ["--papers-file", str(pf), "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data")]
        rc, out = call(*base, "--now", "2026-10-22T11:30"); print(" ", out)
        html = (t / "docs" / "index.html").read_text()
        assert "No. 1" in html and "Past editions" in html and "verbatim" in html and "Why it leads." in html
        assert (t / "docs" / "archive" / "2026-10-22.html").exists()
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
        call("--rerender", "--docs-dir", str(t / "docs"), "--data-dir", str(t / "data"))
        assert (t / "docs" / "index.html").exists()
    print("pipeline ok")


if __name__ == "__main__":
    test_split(); test_ranking_and_digest(); test_pipeline(); print("ALL PASSED")
