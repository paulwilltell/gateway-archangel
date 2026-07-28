"""Head-to-head: does a stronger model or added context make bridges real?

For a fixed set of probe verses, show each variant's top bridges with their
z-scores. Two quantitative signals, no debatable ground truth needed:

- **top-z**: how far above the noise floor the single best bridge sits. A
  register-dominated geometry gives every bridge a low, similar z; a
  discriminating one lets a genuine connection stand out.
- **spread**: top-z minus the 5th bridge's z. A large spread means the geometry
  separates the real bridge from the also-rans.

Higher on both = a geometry that actually finds cross-vocabulary connections.
The verses printed are the qualitative check: are the top bridges thematically
apt, or just devotional-sounding filler?
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workbench.embed import build_embeddings  # noqa: E402
from workbench.semantic import bridges  # noqa: E402

PROBES = [
    "Psalms 23:1",        # keyword-carried; the hard case
    "Ecclesiastes 1:9",   # has a known real bridge (Ecc 3:15)
    "Matthew 7:12",       # golden rule; parallels exist in other words
    "Proverbs 16:18",     # pride before a fall
    "John 1:1",           # dense doctrine
]


def run(variants: list[str], show: int = 3) -> None:
    for variant in variants:
        print(f"\nBuilding / loading variant: {variant}")
        build_embeddings(variant, verbose=True)

    for probe in PROBES:
        print(f"\n{'=' * 78}\n{probe}\n{'=' * 78}")
        for variant in variants:
            result = bridges(probe, top=8, variant=variant)
            found = result["bridges"]
            if not found:
                print(f"  [{variant:10}] no bridges above threshold")
                continue
            top_z = found[0].z_score
            spread = round(top_z - found[min(4, len(found) - 1)].z_score, 1)
            print(f"\n  [{variant:10}]  top-z={top_z}  spread={spread}")
            for match in found[:show]:
                print(f"      z={match.z_score:>5}  {match.reference:<18} {match.text[:60]}")


if __name__ == "__main__":
    chosen = sys.argv[1:] or ["mini", "mpnet", "mpnet-ctx"]
    run(chosen)
