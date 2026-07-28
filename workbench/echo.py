"""Intertextual echo finder.

For any verse, which other verses across the whole canon echo it — ranked by
shared vocabulary, weighted so a shared rare word ("propitiation",
"lovingkindness") counts far more than a shared common one. This is the
Workbench's most useful primitive: it surfaces allusions, quotations, and
thematic cousins a reader would take years to notice.

The honesty discipline: a raw similarity score means nothing on its own,
because some verses are lexically generic and match many things weakly. Every
result is therefore reported against the verse's OWN null baseline — how
similar it is to random verses — so you can tell a real echo (many standard
deviations above this verse's typical similarity) from a mundane overlap. A
strong number is only strong relative to what chance gives *this* verse.

Pure Python, transparent weights, no embeddings. If you cannot see the shared
words that produced a link, do not trust the link — so they are always shown.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from workbench.corpus import load_verses, resolve, tokens


@lru_cache(maxsize=1)
def _index() -> dict:
    """Build IDF weights and per-verse stem sets once."""
    verses = load_verses()
    document_frequency: dict[str, int] = {}
    verse_stems: list[set[str]] = []
    for verse in verses:
        stems = {stem for stem, _ in tokens(verse["text"])}
        verse_stems.append(stems)
        for stem in stems:
            document_frequency[stem] = document_frequency.get(stem, 0) + 1

    total = len(verses)
    idf = {stem: math.log(total / freq) for stem, freq in document_frequency.items()}
    # Vector norm per verse, for cosine similarity.
    norms = [
        math.sqrt(sum(idf[stem] ** 2 for stem in stems)) or 1.0
        for stems in verse_stems
    ]
    return {"idf": idf, "verse_stems": verse_stems, "norms": norms}


def _similarity(a_stems: set[str], a_norm: float, b_index: int, index: dict) -> float:
    shared = a_stems & index["verse_stems"][b_index]
    if not shared:
        return 0.0
    idf = index["idf"]
    dot = sum(idf[stem] ** 2 for stem in shared)
    return dot / (a_norm * index["norms"][b_index])


@dataclass
class Echo:
    reference: str
    text: str
    similarity: float
    z_score: float
    shared_words: list[str]


def _shared_surfaces(query_text: str, other_text: str, limit: int = 8) -> list[str]:
    q = {stem: surface for stem, surface in tokens(query_text)}
    out = []
    for stem, surface in tokens(other_text):
        if stem in q and surface not in out:
            out.append(surface)
        if len(out) >= limit:
            break
    return out


def find_echoes(reference: str, top: int = 12, null_samples: int = 400, seed: int = 0) -> dict:
    """Echoes of one verse, each scored against the verse's own null baseline."""
    verse = resolve(reference)
    index = _index()
    query_stems = index["verse_stems"][verse["_index"]]
    query_norm = index["norms"][verse["_index"]]
    verses = load_verses()

    if not query_stems:
        return {"query": verse["reference"], "text": verse["text"],
                "note": "This verse has no distinctive content words to match on.",
                "echoes": [], "null": None}

    # Null baseline: how similar is THIS verse to random other verses? A real
    # echo must stand out against that, not against an absolute scale.
    rng = random.Random(seed)
    sample_indexes = rng.sample(range(len(verses)), min(null_samples, len(verses)))
    null = [
        _similarity(query_stems, query_norm, i, index)
        for i in sample_indexes
        if i != verse["_index"]
    ]
    null_mean = sum(null) / len(null)
    null_sd = (sum((x - null_mean) ** 2 for x in null) / len(null)) ** 0.5 or 1e-9

    scored = []
    for other in verses:
        if other["_index"] == verse["_index"]:
            continue
        sim = _similarity(query_stems, query_norm, other["_index"], index)
        if sim <= 0:
            continue
        scored.append((sim, other))
    scored.sort(key=lambda s: s[0], reverse=True)

    echoes = [
        Echo(
            reference=other["reference"],
            text=other["text"],
            similarity=round(sim, 3),
            z_score=round((sim - null_mean) / null_sd, 1),
            shared_words=_shared_surfaces(verse["text"], other["text"]),
        )
        for sim, other in scored[:top]
    ]
    return {
        "query": verse["reference"],
        "text": verse["text"],
        "echoes": echoes,
        "null": {"mean": round(null_mean, 3), "sd": round(null_sd, 3),
                 "reading": "z is standard deviations above this verse's similarity to random verses"},
    }
