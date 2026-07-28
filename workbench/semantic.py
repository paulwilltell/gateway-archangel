"""Semantic discovery over the verse geometry.

Three lenses, each null-tested:

- **neighbors(ref)** — verses closest in meaning to a given verse.
- **bridges(ref)** — verses close in meaning but sharing NO significant words.
  This is where discovery lives: a concordance cannot find these, and a reader
  would take a lifetime to. High meaning-similarity with zero lexical overlap
  is a connection you could not reach through words.
- **outliers()** — verses least like everything else in Scripture: unusual
  imagery, singular theology, foreign vocabulary.

Every result carries a z-score against a random-pair baseline, and its lexical
overlap, so a genuine cross-vocabulary bridge is distinguishable from a reworded
quotation or an embedding style-artifact. Numbers point somewhere to look; they
never establish that a connection means anything.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from workbench.corpus import load_verses, resolve, tokens
from workbench.embed import DEFAULT_VARIANT, embeddings


@lru_cache(maxsize=8)
def _null_stats(variant: str, samples: int = 20000, seed: int = 0) -> tuple[float, float]:
    """Similarity of random verse pairs — the baseline every score is read
    against. Two verses picked at random are the definition of 'no signal'.
    Computed per variant, since each geometry has its own scale."""
    emb = embeddings(variant)
    rng = random.Random(seed)
    n = emb.shape[0]
    sims = []
    for _ in range(samples):
        i, j = rng.randrange(n), rng.randrange(n)
        if i != j:
            sims.append(float(emb[i] @ emb[j]))
    arr = np.array(sims)
    return float(arr.mean()), float(arr.std() or 1e-9)


def _z(sim: float, variant: str) -> float:
    mean, sd = _null_stats(variant)
    return round((sim - mean) / sd, 1)


def _content_stems(text: str) -> set[str]:
    return {stem for stem, _ in tokens(text)}


def _lexical_overlap(a: str, b: str) -> list[str]:
    a_map = {stem: surface for stem, surface in tokens(a)}
    return sorted({a_map[stem] for stem, _ in tokens(b) if stem in a_map})


@dataclass
class Match:
    reference: str
    text: str
    similarity: float
    z_score: float
    shared_words: list[str]


def neighbors(reference: str, top: int = 12, variant: str = DEFAULT_VARIANT) -> dict:
    verse = resolve(reference)
    emb = embeddings(variant)
    query = emb[verse["_index"]]
    sims = emb @ query
    order = np.argsort(-sims)
    verses = load_verses()

    matches = []
    for idx in order:
        if idx == verse["_index"]:
            continue
        other = verses[idx]
        matches.append(
            Match(
                reference=other["reference"],
                text=other["text"],
                similarity=round(float(sims[idx]), 3),
                z_score=_z(float(sims[idx]), variant),
                shared_words=_lexical_overlap(verse["text"], other["text"]),
            )
        )
        if len(matches) >= top:
            break
    return {"query": verse["reference"], "text": verse["text"], "matches": matches}


def bridges(reference: str, top: int = 12, min_similarity: float = 0.4,
            scan: int = 400, variant: str = DEFAULT_VARIANT) -> dict:
    """Semantically close, lexically disjoint — the surprising connections."""
    verse = resolve(reference)
    emb = embeddings(variant)
    query = emb[verse["_index"]]
    query_stems = _content_stems(verse["text"])
    sims = emb @ query
    order = np.argsort(-sims)
    verses = load_verses()

    found = []
    for idx in order[: scan + 1]:
        if idx == verse["_index"]:
            continue
        sim = float(sims[idx])
        if sim < min_similarity:
            break
        other = verses[idx]
        shared = query_stems & _content_stems(other["text"])
        if shared:
            continue  # not a bridge — it shares words
        found.append(
            Match(
                reference=other["reference"],
                text=other["text"],
                similarity=round(sim, 3),
                z_score=_z(sim, variant),
                shared_words=[],
            )
        )
        if len(found) >= top:
            break
    return {"query": verse["reference"], "text": verse["text"], "bridges": found,
            "note": "close in meaning, sharing no significant words"}


@lru_cache(maxsize=4)
def _mean_neighbor_similarity(variant: str, k: int = 10) -> np.ndarray:
    """For each verse, its average similarity to its k nearest neighbours.
    Low = the verse sits alone in the geometry."""
    emb = embeddings(variant)
    # Chunked to keep the 31k x 31k similarity matrix off the heap.
    n = emb.shape[0]
    scores = np.empty(n, dtype=np.float32)
    chunk = 512
    for start in range(0, n, chunk):
        block = emb[start : start + chunk] @ emb.T  # (chunk, n)
        block[np.arange(block.shape[0]), np.arange(start, start + block.shape[0])] = -1.0
        part = np.partition(block, -k, axis=1)[:, -k:]
        scores[start : start + block.shape[0]] = part.mean(axis=1)
    return scores


def outliers(top: int = 20, min_words: int = 4, variant: str = DEFAULT_VARIANT) -> list[dict]:
    """Verses least like the rest of Scripture. Filtered to verses with real
    content so the list is not dominated by three-word fragments."""
    verses = load_verses()
    scores = _mean_neighbor_similarity(variant)
    ranked = sorted(
        (
            (float(scores[v["_index"]]), v)
            for v in verses
            if len(_content_stems(v["text"])) >= min_words
        ),
        key=lambda s: s[0],
    )
    return [
        {"isolation": round(1 - score, 3), "reference": v["reference"], "text": v["text"]}
        for score, v in ranked[:top]
    ]
