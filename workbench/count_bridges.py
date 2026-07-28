"""Count the Bible's cross-vocabulary bridges, at every strength.

A *bridge* is a pair of verses close in meaning that share no significant
words. "How many are there" has no single answer: it depends on how strong a
connection must be to count. So this reports the whole spectrum — how many
bridge-pairs exist at each z-level above the random-pair noise floor — and
surfaces the strongest cross-book bridges, the genuinely surprising ones.

Same-passage pairs (Psalm 23:1 and 23:5) are technically bridges but trivial,
so cross-book pairs are counted and ranked separately: those are the
connections no reader would reach by concordance.

Pure computation over cached embeddings. No API calls, no cost.
"""

from __future__ import annotations

import heapq
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workbench.corpus import load_verses, tokens  # noqa: E402
from workbench.embed import DEFAULT_VARIANT, embeddings  # noqa: E402


def is_name_list(text: str) -> bool:
    """A genealogy / name-list / place-list verse. The embedding model treats
    these as a distinctive genre, so they bridge to each other with high scores
    that mean 'both are name-lists', not a real connection. Detected by a high
    density of mid-sentence capitalized words."""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
    if len(words) < 3:
        return False
    mid_caps = sum(1 for w in words[1:] if w[0].isupper())
    return mid_caps / len(words) > 0.35

Z_LEVELS = (3, 4, 5, 6, 7, 8)
BASE_Z = 3          # only pairs at least this strong are examined
KEEP_TOP = 40       # strongest cross-book bridges to surface
TOP_MIN_Z = 5       # a bridge must be at least this strong to be "top"


def main(variant: str = DEFAULT_VARIANT) -> None:
    emb = embeddings(variant)
    verses = load_verses()
    n = emb.shape[0]
    print(f"variant {variant}: {n} verses, {emb.shape[1]}-dim\n")

    stems = [frozenset(s for s, _ in tokens(v["text"])) for v in verses]
    books = np.array([v["book"] for v in verses])
    namelist = np.array([is_name_list(v["text"]) for v in verses])
    print(f"excluding {int(namelist.sum())} name-list / genealogy verses "
          f"({100 * namelist.mean():.1f}% of the corpus)\n")

    # Null baseline: random-pair cosine → z-scale.
    rng = np.random.default_rng(0)
    a = rng.integers(0, n, 60000)
    b = rng.integers(0, n, 60000)
    keep = a != b
    rand = np.einsum("ij,ij->i", emb[a[keep]], emb[b[keep]])
    mean, sd = float(rand.mean()), float(rand.std())
    base_cos = mean + BASE_Z * sd
    top_min_cos = mean + TOP_MIN_Z * sd
    print(f"noise floor: mean cos={mean:.3f}, sd={sd:.3f}; examining pairs with z>={BASE_Z}\n")

    total = {z: 0 for z in Z_LEVELS}
    crossbook = {z: 0 for z in Z_LEVELS}
    top: list[tuple[float, int, int]] = []
    examined = 0

    chunk = 400
    start_time = time.time()
    for start in range(0, n, chunk):
        block = emb[start : start + chunk] @ emb.T  # (chunk, n)
        for r in range(block.shape[0]):
            i = start + r
            if namelist[i]:
                continue
            sims = block[r]
            cand = np.where(sims >= base_cos)[0]
            cand = cand[cand > i]  # i<j only; skips self
            if cand.size == 0:
                continue
            si = stems[i]
            bi = books[i]
            for j in cand:
                if namelist[j]:
                    continue  # skip genealogy / name-list artifacts
                if si & stems[j]:
                    continue  # shares words → echo, not bridge
                examined += 1
                z = (float(sims[j]) - mean) / sd
                cross = bi != books[j]
                for zt in Z_LEVELS:
                    if z >= zt:
                        total[zt] += 1
                        if cross:
                            crossbook[zt] += 1
                if cross and sims[j] >= top_min_cos:
                    if len(top) < KEEP_TOP:
                        heapq.heappush(top, (z, i, int(j)))
                    elif z > top[0][0]:
                        heapq.heapreplace(top, (z, i, int(j)))
        if (start // chunk) % 10 == 0:
            done = start + block.shape[0]
            print(f"  {done}/{n} verses  ({time.time() - start_time:.0f}s)")

    print(f"\n=== BRIDGE SPECTRUM (all cross-vocabulary pairs, {time.time()-start_time:.0f}s) ===")
    print(f"{'z >=':>6}  {'all bridges':>14}  {'cross-book':>14}")
    for z in Z_LEVELS:
        print(f"{z:>6}  {total[z]:>14,}  {crossbook[z]:>14,}")

    print(f"\n=== {len(top)} STRONGEST CROSS-BOOK BRIDGES ===")
    for z, i, j in sorted(top, reverse=True):
        print(f"\n  z={z:.1f}")
        print(f"    {verses[i]['reference']:<18} {verses[i]['text'][:70]}")
        print(f"    {verses[j]['reference']:<18} {verses[j]['text'][:70]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VARIANT)
