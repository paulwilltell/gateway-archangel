#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from datetime import datetime, timezone

from app.config import get_settings
from app.db import Database
from app.models import TrainingCandidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve or reject a queued training candidate.")
    parser.add_argument("candidate_id")
    parser.add_argument("state", choices=["approved", "rejected"])
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--confirm-biblical-alignment", action="store_true")
    parser.add_argument("--confirm-rights", action="store_true")
    parser.add_argument("--confirm-privacy", action="store_true")
    args = parser.parse_args()

    if args.state == "approved" and not all(
        [args.confirm_biblical_alignment, args.confirm_rights, args.confirm_privacy]
    ):
        raise SystemExit(
            "Approval requires --confirm-biblical-alignment --confirm-rights --confirm-privacy"
        )

    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    with database.session() as db:
        candidate = db.get(TrainingCandidate, args.candidate_id)
        if not candidate:
            raise SystemExit("Candidate not found")
        candidate.review_state = args.state
        candidate.reviewer_id = args.reviewer_id
        candidate.review_notes = args.notes
        candidate.reviewed_at = datetime.now(timezone.utc)
    print(f"{args.state}: {args.candidate_id}")


if __name__ == "__main__":
    main()
