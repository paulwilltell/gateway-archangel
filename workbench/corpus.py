"""Shared corpus access and tokenization for the Workbench.

Tokenization is deliberately transparent — no neural embeddings, no opaque
model. Content words only, lightly normalized so KJV verb forms match
(forgiveth/forgive), with the original surface words kept so a match can always
be shown to the reader in the words that actually overlapped. If you cannot see
why two verses were linked, the link is worthless.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "kjv_full.json"

# Modern + KJV-archaic function words. These carry no thematic weight and would
# otherwise dominate every overlap ("thou", "unto", "hath").
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are art as at be because
    been before being below between both but by came can concerning did do doth
    down during each even every for from further had hast hath have having he her
    here hers herself him himself his how i if in into is it its itself let like
    lo may me might mine more most much my myself neither no nor not now o of off
    on once only or other otherwise our ours ourselves out over own said saith
    same shall shalt she should since so some such than that the thee their theirs
    them themselves then thence there therefore these they thine thing things this
    those thou though thy thyself till to too under unto up upon us was wast we
    were what when whence where which while who whom whose why will with within
    without ye yea yet you your yours yourself yourselves
    behold came come cometh doeth done forth go goeth hence made make maketh put
    thus verily whether
    """.split()
)

_WORD = re.compile(r"[a-z]+")


def _normalize(word: str) -> str:
    """Light, transparent stemming for KJV forms.

    Correctness matters less than *consistency*: both "forgive" and
    "forgiveth" must reach the same token or they will not match. Endings are
    stripped in order, then a trailing 'e' is removed to canonicalize e-stem
    verbs (love/loveth/loved all become "lov"). Surface words are always kept
    and shown, so a reader can see the real basis of any match.
    """
    for suffix in ("eth", "est", "edst"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    else:
        if word.endswith("ing") and len(word) > 5:
            word = word[:-3]
        elif word.endswith("ed") and len(word) > 4:
            word = word[:-2]
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            word = word[:-1]
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def tokens(text: str) -> list[tuple[str, str]]:
    """(stem, surface) content-word pairs, in order. Surface is kept so the
    reader always sees the real word behind a stemmed match."""
    out = []
    for match in _WORD.finditer(text.lower()):
        surface = match.group(0)
        if len(surface) < 3 or surface in STOPWORDS:
            continue
        out.append((_normalize(surface), surface))
    return out


@lru_cache(maxsize=1)
def load_verses() -> list[dict]:
    verses = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    for index, verse in enumerate(verses):
        verse["_index"] = index
    return verses


@lru_cache(maxsize=1)
def by_reference() -> dict[str, dict]:
    return {verse["reference"]: verse for verse in load_verses()}


def resolve(reference: str) -> dict:
    verse = by_reference().get(reference.strip())
    if verse is None:
        raise KeyError(f"{reference!r} is not a verse in the corpus")
    return verse
