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
from app.models import Analysis, TrainingCandidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Export only human-approved training examples.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    exported = 0
    with database.session() as db, args.output.open("w", encoding="utf-8") as handle:
        candidates = db.scalars(
            select(TrainingCandidate).where(TrainingCandidate.review_state == "approved")
        ).all()
        for candidate in candidates:
            analysis = db.get(Analysis, candidate.analysis_id)
            if not analysis:
                continue
            record = {
                "candidate_id": candidate.id,
                "content_hash": candidate.content_hash,
                "community_text": candidate.redacted_text,
                "analysis": json.loads(analysis.result_json),
                "engine_version": analysis.engine_version,
                "corpus_version": analysis.corpus_version,
                "reviewer_id": candidate.reviewer_id,
                "review_notes": candidate.review_notes,
                "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
                "policy": settings.training_policy_version,
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            exported += 1
    print(json.dumps({"exported": exported, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
