"""Verify every reference in the curated indexes exists in the corpus.

A mistyped reference in the counterpassage or topical index fails silently:
the lookup returns nothing and the tension simply never surfaces. Since these
indexes are the platform's editorial contribution, a silent hole in one is a
claim the system promised to challenge and quietly did not.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.analysis.retrieval import (  # noqa: E402
    COUNTERPASSAGES,
    COUNTERPASSAGE_VERSION,
    THEME_INDEX_VERSION,
    THEME_REFERENCES,
    seed_corpus,
)
from app.config import get_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.models import BibleVerse  # noqa: E402


def main() -> int:
    settings = get_settings()
    database = Database("sqlite://")
    database.create_all()

    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        known = set(db.scalars(select(BibleVerse.reference)).all())

    missing: list[tuple[str, str]] = []

    theme_refs = {ref for _, refs in THEME_REFERENCES for ref in refs}
    for reference in sorted(theme_refs):
        if reference not in known:
            missing.append(("theme index", reference))

    counter_refs = set()
    for side_a, side_b, _ in COUNTERPASSAGES:
        counter_refs.update(side_a)
        counter_refs.update(side_b)
    for reference in sorted(counter_refs):
        if reference not in known:
            missing.append(("counterpassage index", reference))

    print(f"corpus:              {len(known)} verses")
    print(f"theme index:         {THEME_INDEX_VERSION} — {len(theme_refs)} references")
    print(f"counterpassage index: {COUNTERPASSAGE_VERSION} — {len(COUNTERPASSAGES)} tensions, "
          f"{len(counter_refs)} references")

    if missing:
        print(f"\n{len(missing)} MISSING references (these tensions can never fire):")
        for index_name, reference in missing:
            print(f"  {index_name}: {reference}")
        return 1

    print("\nAll index references exist in the corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
