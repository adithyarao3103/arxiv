"""Hard-coded, scored list of prominent hep-th authors, and a matcher for arXiv author strings.

The list lives in hep_th_authors.txt, one "Given Family | score" per line (score 1-10, default 4). Each paper
gets an *author score* from the listed authors it contains (see paper_score), and that score is added to the
paper's ranking in extractive.py. An arXiv author matches an entry on family name AND given name:

  * if the arXiv name spells the given name out ("Edward Witten"), the given names must agree;
  * if it only has initials ("E. Witten", "J. M. Maldacena"), the first initial must agree, but only for
    family names that are not very common (for "Wang", "Kim", "Li", ... a bare initial proves nothing, so a
    full given name is required there).

Accents, hyphens, apostrophes and case are ignored, so "Dieter Lüst" == "Dieter Lust" and
"Yu-tin Huang" == "Yu-Tin Huang". Extra names can be added via "extra_prominent_authors" in config.json.
"""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

LIST_FILE = Path(__file__).with_name("hep_th_authors.txt")
DEFAULT_SCORE = 4.0
# author score of a paper = best author's score + this fraction of the next few listed authors' scores
EXTRA_AUTHOR_WEIGHT, EXTRA_AUTHORS_COUNTED = 0.2, 5

# Family names so common that an initial alone ("Y. Wang") is not evidence of identity.
COMMON_FAMILY = {
    "wang", "li", "zhang", "chen", "liu", "lee", "kim", "yang", "wu", "lin", "huang", "zhou", "zhao", "xu",
    "sun", "ma", "zhu", "hu", "guo", "he", "gao", "park", "choi", "jung", "kang", "cho", "son", "singh",
    "kumar", "sharma", "patel", "gupta", "smith", "jones", "brown", "wilson", "taylor", "davis", "miller",
    "martin", "garcia", "rodriguez", "lopez", "gonzalez", "hernandez", "perez", "sanchez", "santos", "silva",
    "costa", "rossi", "russo", "ferrari", "romano", "mueller", "schmidt", "schneider", "fischer", "weber",
    "meyer", "wagner", "becker", "nguyen", "tran", "pham", "song", "yin", "xie", "yan", "pan", "cheng",
    "green", "king", "wright", "walker", "white", "wall", "young", "allen", "scott", "moore", "ross",
}
# Very common family name + very short given name (e.g. "Yi Wang") would match many unrelated people, so such
# entries are ignored unless the person is listed here.
ALLOW_COMMON = {"Xi Yin", "Hong Liu", "Seok Kim", "Dam Thanh Son"}
_ASCII = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss", "æ": "ae", "Æ": "AE", "đ": "d", "Đ": "D", "ı": "i"})


def _fold(s):
    s = unicodedata.normalize("NFKD", s.translate(_ASCII))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return s.replace("’", "'").replace("`", "'")


def parse(name):
    """-> (family, given_first, is_initial). Returns None if the name cannot be used."""
    toks = _fold(name).replace(",", " ").split()
    toks = [t for t in toks if re.search(r"[a-z]", t)]
    if len(toks) < 2:
        return None
    # "Family, Given" never appears in arXiv's API output, so the family name is the last token
    family = re.sub(r"[^a-z]", "", re.split(r"-", toks[-1])[-1])
    first_raw = toks[0]
    letters = re.sub(r"[^a-z]", "", first_raw)
    if not family or not letters:
        return None
    is_initial = len(letters) == 1 or "." in first_raw
    given = letters[0] if is_initial else letters
    return family, given, is_initial


@lru_cache(maxsize=1)
def _load_file():
    names = []
    if LIST_FILE.exists():
        for line in LIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return tuple(names)


def split_entry(line):
    """'Edward Witten | 10' -> ('Edward Witten', 10.0); no score -> DEFAULT_SCORE."""
    name, _, sc = line.partition("|")
    try:
        score = float(sc) if sc.strip() else DEFAULT_SCORE
    except ValueError:
        score = DEFAULT_SCORE
    return name.strip(), score


def build_index(extra=()):
    """family -> {given: score}; display[(family, given)] = name. `extra` entries may carry '| score' too."""
    index, display = {}, {}
    for line in list(_load_file()) + list(extra or ()):
        name, score = split_entry(line)
        p = parse(name)
        if not p or p[2]:
            continue
        family, given, _ = p
        if family in COMMON_FAMILY and len(given) <= 4 and name not in ALLOW_COMMON:
            continue
        index.setdefault(family, {})
        index[family][given] = max(score, index[family].get(given, 0.0))
        display[(family, given)] = name
    return index, display


class ProminentAuthors:
    def __init__(self, extra=()):
        self.index, self.display = build_index(extra)

    def __len__(self):
        return sum(len(v) for v in self.index.values())

    def match(self, author):
        """(name, score) of the list entry this arXiv author string refers to, or None."""
        p = parse(author)
        if not p:
            return None
        family, given, is_initial = p
        known = self.index.get(family)
        if not known:
            return None
        if is_initial:
            if family in COMMON_FAMILY:
                return None
            hits = [k for k in known if k[0] == given]
            if not hits:
                return None
            k = max(hits, key=lambda g: known[g])
        elif given in known:
            k = given
        else:
            return None
        return self.display[(family, k)], known[k]

    def in_paper(self, paper):
        """Distinct (name, score) pairs among the paper's authors, best score first."""
        found = {}
        for a in paper.get("authors") or []:
            m = self.match(a)
            if m:
                found[m[0]] = m[1]
        return sorted(found.items(), key=lambda kv: -kv[1])

    def paper_score(self, paper):
        """-> (author_score, [(name, score), ...]). 0 when no author is on the list."""
        hits = self.in_paper(paper)
        if not hits:
            return 0.0, []
        rest = [s for _, s in hits[1:1 + EXTRA_AUTHORS_COUNTED]]
        return hits[0][1] + EXTRA_AUTHOR_WEIGHT * sum(rest), hits


def names_in_file():
    return _load_file()
