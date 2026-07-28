"""Disciplined lexical novelty.

The naive compression-anomaly score (see the project history) was dominated by
two artifacts: the first verse of every book scored high because its context
was empty, and name-dense verses scored high because names are lexically rare.
A shuffle test showed the raw score tracked verse *form*, not meaning.

This version controls for both:

- Context is the preceding N content words within the book, but the first few
  verses of each book are excluded from ranking rather than being handed an
  empty context and spiking. Book openers are not a discovery.
- Novelty is IDF-weighted: a verse scores for introducing words that are rare
  in the *whole canon*, and each novel word's contribution is its IDF, so a
  cluster of proper names (each individually rare) does not automatically beat
  a genuine conceptual shift.
- The `--null` mode shuffles verse order and re-ranks, so you can see for
  yourself whether the top of the list is signal or the same artifacts.

Even disciplined, this finds LEXICAL novelty — a verse whose vocabulary is
surprising given its neighbours. That often coincides with an intertextual
reach (Luke 17:32, "Remember Lot's wife"), which is the point. It never
establishes theological significance on its own; it points somewhere to look.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

from workbench.corpus import load_verses, tokens

WINDOW = 40  # preceding content words used as local context
SKIP_OPENING = 3  # verses at each book start excluded from ranking


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    verses = load_verses()
    df: dict[str, int] = {}
    for verse in verses:
        for stem in {stem for stem, _ in tokens(verse["text"])}:
            df[stem] = df.get(stem, 0) + 1
    total = len(verses)
    return {stem: math.log(total / freq) for stem, freq in df.items()}


def _score_stream(verses: list[dict]) -> list[tuple[float, dict]]:
    idf = _idf()
    scored: list[tuple[float, dict]] = []
    by_book: dict[str, list[dict]] = {}
    for verse in verses:
        by_book.setdefault(verse["book"], []).append(verse)

    for book_verses in by_book.values():
        seen: dict[str, int] = {}  # stem -> content-word position last seen
        position = 0
        for order, verse in enumerate(book_verses):
            verse_tokens = tokens(verse["text"])
            novel_weight = 0.0
            content = 0
            for stem, _ in verse_tokens:
                content += 1
                last = seen.get(stem)
                if last is None or position - last > WINDOW:
                    novel_weight += idf.get(stem, 0.0)
                seen[stem] = position
                position += 1
            if content and order >= SKIP_OPENING:
                scored.append((novel_weight / content, verse))
    scored.sort(key=lambda s: s[0], reverse=True)
    return scored


def most_novel(top: int = 20) -> list[tuple[float, dict]]:
    return _score_stream(load_verses())[:top]


def null_comparison(top: int = 100, seed: int = 1) -> dict:
    """Top-N under real order vs shuffled order. If they look alike, the score
    is tracking form, not meaning."""
    verses = load_verses()
    real = _score_stream(verses)[:top]

    shuffled = [dict(v) for v in verses]
    texts = [v["text"] for v in shuffled]
    random.Random(seed).shuffle(texts)
    for verse, text in zip(shuffled, texts):
        verse["text"] = text
    fake = _score_stream(shuffled)[:top]

    return {
        "real_mean_score": round(sum(s for s, _ in real) / len(real), 3),
        "shuffled_mean_score": round(sum(s for s, _ in fake) / len(fake), 3),
        "real_top": [(round(s, 3), v["reference"]) for s, v in real[:10]],
    }
