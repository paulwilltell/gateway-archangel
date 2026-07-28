"""Verse embeddings — the semantic geometry of Scripture.

The lexical tools (echo, novelty) find where the same *words* recur. This finds
where *meaning* recurs, even across entirely different vocabulary — a verse
about a shepherd guarding sheep and a verse about a king shielding his people,
no shared words, deep kinship.

It runs a local sentence-transformer on the machine. No API, no key, nothing
sent anywhere: the whole KJV is embedded offline and cached. That is both a
privacy property and a reproducibility one — the same corpus always yields the
same geometry.

Multiple *variants* are supported so the quality of the geometry can be tuned
and, crucially, *measured* rather than guessed. Each variant is a (model,
context-window) pair with its own cache:

- ``mini``       — all-MiniLM-L6-v2, verse alone (small, fast baseline)
- ``mpnet``      — all-mpnet-base-v2, verse alone (stronger model)
- ``mpnet-ctx``  — all-mpnet-base-v2, verse plus one neighbour each side
                   (gives short verses enough content to place well)

Honest limits, stated up front. These embeddings encode meaning as a general
model learned it from modern English, applied to 1611 English — one step
removed from the Hebrew and Greek, and shaped by a model that never studied
theology. They also cluster partly by *surface style* as much as by meaning.
That is exactly why nothing here is reported without a null test and without
showing the lexical overlap.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from workbench.corpus import load_verses

VARIANTS: dict[str, dict] = {
    "mini": {"provider": "local", "model": "sentence-transformers/all-MiniLM-L6-v2", "context": 0},
    "mpnet": {"provider": "local", "model": "sentence-transformers/all-mpnet-base-v2", "context": 0},
    "mpnet-ctx": {"provider": "local", "model": "sentence-transformers/all-mpnet-base-v2", "context": 1},
    "openai": {"provider": "openai", "model": "text-embedding-3-large", "context": 0},
    "openai-ctx": {"provider": "openai", "model": "text-embedding-3-large", "context": 1},
}
# The tuning experiment (workbench/compare_variants.py, docs/RELIABILITY.md)
# named 'openai' the winner: it roughly doubled bridge signal AND its top
# bridges are genuinely thematic. 'openai-ctx' scored higher still but was
# rejected — the context window leaks, so its bridges degrade to adjacent
# verses. Higher numbers, worse tool; the discipline of reading the actual
# verses caught it. 'mini' remains the free, local, key-free fallback.
DEFAULT_VARIANT = "openai"

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
KEY_FILE = Path(__file__).resolve().parent / "openai_key.txt"


def _paths(variant: str) -> tuple[Path, Path]:
    return CACHE_DIR / f"emb_{variant}.npy", CACHE_DIR / f"emb_{variant}.stamp"


def _corpus_stamp(variant: str, verses: list[dict]) -> str:
    spec = VARIANTS[variant]
    hasher = hashlib.sha256()
    hasher.update(f"{spec['model']}|ctx{spec['context']}".encode())
    hasher.update(str(len(verses)).encode())
    hasher.update(verses[0]["text"].encode("utf-8"))
    hasher.update(verses[-1]["text"].encode("utf-8"))
    return hasher.hexdigest()


@lru_cache(maxsize=4)
def _model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


def _openai_key() -> str:
    import os
    import re

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        # Find the key wherever it was pasted in the file (robust to landing on
        # a comment line). A real key is a long sk- token, not the placeholder.
        for token in re.findall(r"sk-[A-Za-z0-9_\-]{20,}", KEY_FILE.read_text(encoding="utf-8")):
            if "xxxx" not in token.lower():
                key = token
                break
    if not key:
        raise RuntimeError(
            "No OpenAI key found. Paste it into workbench/openai_key.txt or set OPENAI_API_KEY."
        )
    return key


def _openai_embed(texts: list[str], model: str, verbose: bool, checkpoint: Path | None = None) -> np.ndarray:
    """Embed via the OpenAI REST endpoint — batched, retried, and resumable.

    A single transient read-timeout must not discard thousands of already-paid
    embeddings, so each batch retries with backoff and completed batches are
    checkpointed to disk. A re-run resumes where it stopped."""
    import time

    import httpx

    key = _openai_key()
    batch = 256

    done: list[list[float]] = []
    if checkpoint and checkpoint.exists():
        done = [row.tolist() for row in np.load(checkpoint)]
        if verbose and done:
            print(f"  resuming from checkpoint at {len(done)}/{len(texts)}")

    with httpx.Client(timeout=httpx.Timeout(30.0, read=90.0)) as client:
        for start in range(len(done), len(texts), batch):
            chunk = texts[start : start + batch]
            for attempt in range(6):
                try:
                    response = client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": model, "input": chunk},
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.HTTPError(f"retryable {response.status_code}")
                    if response.status_code >= 400:
                        raise RuntimeError(
                            f"OpenAI embeddings error {response.status_code}: {response.text[:300]}"
                        )
                    data = sorted(response.json()["data"], key=lambda d: d["index"])
                    done.extend(d["embedding"] for d in data)
                    break
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    if attempt == 5:
                        if checkpoint:
                            np.save(checkpoint, np.asarray(done, dtype=np.float32))
                        raise RuntimeError(
                            f"OpenAI batch failed after retries at {start}/{len(texts)}: {exc}. "
                            "Progress checkpointed — re-run to resume."
                        ) from exc
                    time.sleep(2 ** attempt)
            if checkpoint and (start // batch) % 10 == 0:
                np.save(checkpoint, np.asarray(done, dtype=np.float32))
            if verbose:
                print(f"  embedded {min(start + batch, len(texts))}/{len(texts)}")

    arr = np.asarray(done, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
    if checkpoint and checkpoint.exists():
        checkpoint.unlink()
    return arr


def _windowed_texts(verses: list[dict], context: int) -> list[str]:
    """Each verse's text, optionally padded with `context` neighbours on each
    side from the same book, so short verses carry enough signal to place."""
    if context <= 0:
        return [v["text"] for v in verses]
    by_book: dict[str, list[int]] = {}
    for i, v in enumerate(verses):
        by_book.setdefault(v["book"], []).append(i)
    position = {i: (book, k) for book, idxs in by_book.items() for k, i in enumerate(idxs)}

    texts = []
    for i, v in enumerate(verses):
        book, k = position[i]
        idxs = by_book[book]
        lo, hi = max(0, k - context), min(len(idxs), k + context + 1)
        texts.append(" ".join(verses[idxs[j]]["text"] for j in range(lo, hi)))
    return texts


def build_embeddings(variant: str = DEFAULT_VARIANT, force: bool = False, verbose: bool = True) -> np.ndarray:
    """Compute (or load) L2-normalized embeddings for a variant, in corpus
    order. The vector for each verse still *represents* that verse; context, if
    any, only enriches how it is placed."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; choose from {list(VARIANTS)}")
    verses = load_verses()
    stamp = _corpus_stamp(variant, verses)
    emb_path, stamp_path = _paths(variant)

    if not force and emb_path.exists() and stamp_path.exists():
        if stamp_path.read_text(encoding="utf-8").strip() == stamp:
            return np.load(emb_path)

    spec = VARIANTS[variant]
    if verbose:
        print(f"Embedding {len(verses)} verses — variant {variant} "
              f"({spec['model']}, context {spec['context']}), one-time...")
    texts = _windowed_texts(verses, spec["context"])
    if spec["provider"] == "openai":
        checkpoint = CACHE_DIR / f"emb_{variant}.partial.npy"
        CACHE_DIR.mkdir(exist_ok=True)
        vectors = _openai_embed(texts, spec["model"], verbose, checkpoint=checkpoint)
    else:
        vectors = _model(spec["model"]).encode(
            texts, batch_size=128, normalize_embeddings=True,
            show_progress_bar=verbose, convert_to_numpy=True,
        ).astype(np.float32)

    CACHE_DIR.mkdir(exist_ok=True)
    np.save(emb_path, vectors)
    stamp_path.write_text(stamp, encoding="utf-8")
    if verbose:
        print(f"Cached {emb_path.name} ({vectors.shape[0]}x{vectors.shape[1]}).")
    return vectors


@lru_cache(maxsize=4)
def embeddings(variant: str = DEFAULT_VARIANT) -> np.ndarray:
    return build_embeddings(variant, verbose=False)


def embed_text(text: str, variant: str = DEFAULT_VARIANT) -> np.ndarray:
    spec = VARIANTS[variant]
    if spec["provider"] == "openai":
        return _openai_embed([text], spec["model"], verbose=False)[0]
    return _model(spec["model"]).encode(
        [text], normalize_embeddings=True, convert_to_numpy=True
    )[0].astype(np.float32)
