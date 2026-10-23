# The arXiv Gazette (self-updating, no AI, no API keys)

Every morning a GitHub Action fetches the day's new arXiv papers, ranks them with a few transparent rules, lays them out as a newspaper page in `docs/`, commits it, and GitHub Pages serves it. The page is static HTML, so it loads instantly all day. There is no AI model, no paid API and no secret to manage.

```
arXiv (free public API) --> gazette/fetch.py --> gazette/extractive.py --> gazette/render.py --> index.html  and  docs/index.html
                                                  (rank + verbatim excerpts)                    docs/archive/DATE.html
```

## Setup (about 5 minutes)

1. **Create a GitHub repo** and push this folder to it (branch `main`). GitHub Pages is free for public repos; for a private repo you need a paid GitHub plan, so check GitHub's current terms.
2. **Turn on Pages**: repo → Settings → Pages → Source: *Deploy from a branch* → Branch `main`, folder `/ (root)` or `/docs`. Every run writes the front page to **both** `index.html` (repo root) and `docs/index.html`, so `https://<your-user>.github.io/<repo>/` and `.../<repo>/docs/` both work; with the `/docs` folder option only the first one is not served.
3. **Generate the first edition**: repo → Actions → *Daily gazette* → Run workflow (tick *force*). After a minute your site is live at `https://<your-user>.github.io/<repo>/`.

After changing `gazette/render.py` (the look), run the workflow with **rerender** ticked: it rebuilds every page from the saved editions and fetches nothing. Set `"root_index": false` in `config.json` to stop writing the root copy.

If the workflow fails to push, check repo → Settings → Actions → General → Workflow permissions is set to *Read and write*.

## Schedule

GitHub cron is UTC and ignores daylight saving, so the workflow has two triggers (09:00 and 10:00 UTC) and the script only generates once it is 11:00 or later in `timezone` (config.json, default `Europe/Amsterdam`), and only once per day. GitHub can start scheduled jobs several minutes late, so expect "around 11".

arXiv announces new papers Sunday to Thursday evenings (US Eastern), so there is no new batch for Saturday or Sunday morning. On those days nothing new is found and the previous edition stays up. Papers shown in an earlier edition are never repeated.

## How the "editor" works (no AI)

Every word on the page is either a paper's title or a **verbatim excerpt of the authors' abstract** (whole leading sentences). Nothing is paraphrased, so nothing can be misreported. What the code decides is *which* papers go where.

Each paper gets a score (weights are at the top of `gazette/extractive.py`):

| signal | effect |
|---|---|
| comment field mentions a journal or acceptance | +2 |
| 30 or more pages | +1 |
| cross-listed to other categories | +0.5 each, up to 3 |
| abstract contains "we show/prove/derive...", "conjecture", "closed-form", "bound", ... | +0.5 per kind of phrase |
| very short abstract | -1 |
| proceedings, lecture notes, talks | -2 |

**Author scores.** `gazette/hep_th_authors.txt` is a fixed list of well-known hep-th authors, one `Given Family | score` per line (score 1-10; 10 = field-defining, 8 = leading senior researchers, 6 = very well known, 4 = established, which is also the default when no score is given). The scores are a subjective, hand-made judgement: edit freely, or add names under `extra_prominent_authors` in `config.json` (also as `"Given Family | score"`). A paper's **author score** is its best listed author's score plus 0.2 times the next few listed authors' scores, and that number is added to the paper's ranking (weight `W_AUTHOR` in `gazette/extractive.py`, default 1.0, which makes the authors the strongest single signal; set it lower to let the other signals count more). Listed authors are marked ★ on the page. Names match on family name plus given name, ignoring accents and hyphens; a bare initial ("E. Witten") matches too, except for very common family names ("Y. Wang"), which need the full given name.

**No paper is dropped.** The ranked list is split by position: the lead, a few features, a set of section stories (with abstract excerpts), and then *every remaining paper* as an In Brief entry (title, first sentence of the abstract, authors, link), grouped by topic. `size.briefs` no longer exists; only `features`, `section_stories` and `secondary_stories` limit the longer entries. Cross-lists from other fields are included (`include_other_crosslists: true`) under "Across the Border". The code asserts that every fetched paper appears exactly once. `max_per_category` is 600 so a busy two-day window is not cut off; the run warns if it ever is.

The top-ranked **primary** paper leads, the next ones become features and section stories, and the rest become briefs. Sections are chosen by keyword matching (`sections` in config.json). Papers from `cross_from` categories form a separate "Across the Border" section and never lead. The lead box says exactly why it leads, and the footer says that the selection is automatic.

**Be aware of the limits.** The author list and its scores were compiled by hand from memory, not exported from a database: it will miss people and may contain errors, and being on it says nothing about the quality of a particular paper. These signals are a rough proxy for importance: a short, brilliant paper by an unlisted author is not rewarded, and "accepted in JHEP" says nothing about quality. The excerpt is the abstract's opening sentences, which often set up background before stating the result. There is no summary, no "why it matters" and no caveats. If a day's lead looks odd, that is the ranking, not an editorial judgement.

## Configure: `config.json`

| key | meaning |
|---|---|
| `categories` | arXiv categories to cover, e.g. `["hep-th"]` or `["cs.AI","cs.LG"]` |
| `cross_from` | papers with these *primary* categories that are cross-listed into `categories` form the secondary section. Use `[]` to disable it |
| `include_other_crosslists` | keep cross-lists from other fields as well (hep-ph, math-ph, ...) |
| `sections` | list of `{"name", "keywords"}`; a paper goes to the section whose keywords match most (title counts double). Remove the key to group by arXiv category instead |
| `size` | how many features, section stories and secondary stories get a longer entry; everything else becomes a brief |
| `timezone` | used for the edition date and the 11:00 rule |
| `extra_prominent_authors` | optional list of extra `"Given Family"` names to add to the built-in prominent list |
| `root_index` | `true` (default) also writes `index.html` in the repo root; `false` writes only `docs/index.html` |

The page is always light: there is no dark theme, whatever the visitor's system setting.

When you change `categories`, also update `sections` and set `cross_from` to `[]` unless the cross-list idea still applies.

## Run or test locally

```bash
python -m gazette.run --force      # real run (needs internet), writes docs/ and data/
python tests/test_offline.py       # offline tests
python -m gazette.run --rerender   # rebuild all pages from saved editions after editing render.py
```

`data/digests/*.json` keeps each day's edition, and `data/state.json` records which papers each edition covered.

## Cost and data

Free: the arXiv API needs no key, and the job takes seconds of GitHub Actions time (public repos get free minutes; check GitHub's limits for private ones). Please keep the schedule modest, as arXiv asks API users to be gentle.
