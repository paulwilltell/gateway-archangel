#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from sqlalchemy import select

from app.config import get_settings
from app.db import Database
from app.models import BibleVerse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a provenance-approved Scripture JSON file.")
    parser.add_argument("path", type=Path, help="JSON array using the same fields as app/data/kjv_seed.json")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--corpus-version", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--canonical", action="store_true", help="Mark this source as an approved canonical textual source")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    registry = json.loads(Path(settings.source_registry_path).read_text(encoding="utf-8"))
    known = {item["id"]: item for item in registry}
    if args.source_id not in known:
        raise SystemExit(f"Unknown source ID {args.source_id!r}; add it to the reviewed source registry first")
    if args.source_id == "community":
        raise SystemExit("Community discussions cannot be imported into the canonical corpus")

    records = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("Input must be a JSON array")

    database = Database(settings.database_url)
    database.create_all()
    imported = 0
    skipped = 0
    with database.session() as db:
        for item in records:
            required = {"reference", "book", "chapter", "verse", "text"}
            missing = required - item.keys()
            if missing:
                raise SystemExit(f"Record missing fields {sorted(missing)}: {item}")
            existing = db.scalar(
                select(BibleVerse).where(
                    BibleVerse.source_id == args.source_id,
                    BibleVerse.reference == item["reference"],
                )
            )
            if existing:
                skipped += 1
                continue
            db.add(
                BibleVerse(
                    source_id=args.source_id,
                    reference=item["reference"],
                    book=item["book"],
                    chapter=int(item["chapter"]),
                    verse=int(item["verse"]),
                    text=item["text"],
                    language=item.get("language", "unknown"),
                    original_language=item.get("original_language"),
                    license=args.license,
                    corpus_version=args.corpus_version,
                    is_canonical_source=args.canonical,
                )
            )
            imported += 1
    print(json.dumps({"imported": imported, "skipped": skipped, "source_id": args.source_id}, indent=2))


if __name__ == "__main__":
    main()
