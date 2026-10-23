# The arXiv Gazette (self-updating, no AI, no API keys)

Every morning a GitHub Action fetches the day's new arXiv papers, ranks them with a few transparent rules, lays them out as a newspaper page in `docs/`, commits it, and GitHub Pages serves it. The page is static HTML, so it loads instantly all day. There is no AI model, no paid API and no secret to manage.

```
arXiv (free public API) --> gazette/fetch.py --> gazette/extractive.py --> gazette/render.py --> docs/index.html
                                                  (rank + verbatim excerpts)                    docs/archive/DATE.html
```

## Setup (about 5 minutes)

1. **Create a GitHub repo** and push this folder to it (branch `main`). GitHub Pages is free for public repos; for a private repo you need a paid GitHub plan, so check GitHub's current terms.
2. **Turn on Pages**: repo → Settings → Pages → Source: *Deploy from a branch* → Branch `main`, folder `/docs`.
3. **Generate the first edition**: repo → Actions → *Daily gazette* → Run workflow (tick *force*). After a minute your site is live at `https://<your-user>.github.io/<repo>/`.

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

The top **primary** paper leads, the next ones become features and section stories, and the rest become briefs. Sections are chosen by keyword matching (`sections` in config.json). Papers from `cross_from` categories form a separate "Across the Border" section and never lead. The lead box says exactly why it leads, and the footer says that the selection is automatic.

**Be aware of the limits.** These signals are a rough proxy for importance: a famous author or a short, brilliant paper is not rewarded, and "accepted in JHEP" says nothing about quality. The excerpt is the abstract's opening sentences, which often set up background before stating the result. There is no summary, no "why it matters" and no caveats. If a day's lead looks odd, that is the ranking, not an editorial judgement.

## Configure: `config.json`

| key | meaning |
|---|---|
| `categories` | arXiv categories to cover, e.g. `["hep-th"]` or `["cs.AI","cs.LG"]` |
| `cross_from` | papers with these *primary* categories that are cross-listed into `categories` form the secondary section. Use `[]` to disable it |
| `include_other_crosslists` | keep cross-lists from other fields as well (hep-ph, math-ph, ...) |
| `sections` | list of `{"name", "keywords"}`; a paper goes to the section whose keywords match most (title counts double). Remove the key to group by arXiv category instead |
| `size` | how many features, section stories, secondary stories and briefs |
| `timezone` | used for the edition date and the 11:00 rule |

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
