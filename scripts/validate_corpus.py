#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import re
from collections import Counter

from sqlalchemy import select

from app.config import get_settings
from app.db import Database
from app.models import BibleVerse
from app.analysis.retrieval import seed_corpus

REFERENCE = re.compile(r"^.+\s\d{1,3}:\d{1,3}$")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate imported corpus records.")
    # The canonical corpus is the full KJV 1769 built by
    # scripts/build_kjv_corpus.py, whose records carry source_id "kjv_1769".
    parser.add_argument("--source-id", default="kjv_1769")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        rows = db.scalars(select(BibleVerse).where(BibleVerse.source_id == args.source_id)).all()

    errors: list[str] = []
    seen = Counter(row.reference for row in rows)
    duplicates = [ref for ref, count in seen.items() if count > 1]
    if duplicates:
        errors.append(f"duplicate references: {duplicates[:20]}")
    malformed = [row.reference for row in rows if not REFERENCE.match(row.reference)]
    if malformed:
        errors.append(f"malformed references: {malformed[:20]}")
    empty = [row.reference for row in rows if not row.text.strip()]
    if empty:
        errors.append(f"empty text: {empty[:20]}")
    if not args.allow_partial and len(rows) < 30_000:
        errors.append(f"source contains only {len(rows)} verses; expected a full Bible corpus")

    report = {
        "source_id": args.source_id,
        "verse_count": len(rows),
        "book_count": len({row.book for row in rows}),
        "corpus_versions": sorted({row.corpus_version for row in rows}),
        "errors": errors,
        "valid": not errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
