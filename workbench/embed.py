"""Verse embeddings — the semantic geometry of Scripture.

The lexical tools (echo, novelty) find where the same *words* recur. This finds
where *meaning* recurs, even across entirely different vocabulary — a verse
about a shepherd guarding sheep and a verse about a king shielding his people,
no shared words, deep kinship.

It runs a local sentence-transformer on the machine. No API, no key, nothing
sent anywhere: the whole KJV is embedded offline and cached. That is both a
privacy property and a reproducibility one — the same corpus always yields the
same geometry.

Honest limits, stated up front. These embeddings encode meaning as a general
model learned it from modern English, applied to 1611 English — one step
removed from the Hebrew and Greek, and shaped by a model that never studied
theology. They also cluster partly by *surface style* (genealogies group with
genealogies) as much as by meaning. That is exactly why nothing here is
reported without a null test and without showing the lexical overlap, so a real
cross-vocabulary connection can be told from a reworded quotation or a
style artifact.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from workbench.corpus import load_verses

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
EMB_PATH = CACHE_DIR / "verse_embeddings.npy"
STAMP_PATH = CACHE_DIR / "verse_embeddings.stamp"


def _corpus_stamp(verses: list[dict]) -> str:
    """Identifies the corpus + model, so a changed corpus rebuilds the cache."""
    hasher = hashlib.sha256()
    hasher.update(MODEL_NAME.encode())
    hasher.update(str(len(verses)).encode())
    hasher.update(verses[0]["text"].encode("utf-8"))
    hasher.update(verses[-1]["text"].encode("utf-8"))
    return hasher.hexdigest()


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def build_embeddings(force: bool = False, verbose: bool = True) -> np.ndarray:
    """Compute (or load) L2-normalized embeddings for every verse, in corpus
    order. Normalized so cosine similarity is a plain dot product."""
    verses = load_verses()
    stamp = _corpus_stamp(verses)

    if not force and EMB_PATH.exists() and STAMP_PATH.exists():
        if STAMP_PATH.read_text(encoding="utf-8").strip() == stamp:
            return np.load(EMB_PATH)

    if verbose:
        print(f"Embedding {len(verses)} verses with {MODEL_NAME} (one-time, CPU)...")
    texts = [verse["text"] for verse in verses]
    vectors = _model().encode(
        texts,
        batch_size=256,
        normalize_embeddings=True,
        show_progress_bar=verbose,
        convert_to_numpy=True,
    ).astype(np.float32)

    CACHE_DIR.mkdir(exist_ok=True)
    np.save(EMB_PATH, vectors)
    STAMP_PATH.write_text(stamp, encoding="utf-8")
    if verbose:
        print(f"Cached to {EMB_PATH.name} ({vectors.shape[0]}x{vectors.shape[1]}).")
    return vectors


@lru_cache(maxsize=1)
def embeddings() -> np.ndarray:
    return build_embeddings(verbose=False)


def embed_text(text: str) -> np.ndarray:
    """Embed an arbitrary query string into the same space."""
    return _model().encode([text], normalize_embeddings=True, convert_to_numpy=True)[0].astype(np.float32)
