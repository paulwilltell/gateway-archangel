from sqlalchemy import func, select

from app.analysis.engine import analyze_target
from app.analysis.retrieval import seed_corpus
from app.config import Settings
from app.db import Database
from app.models import Post, TrainingCandidate, User


def test_only_consented_aligned_non_sensitive_content_is_queued():
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=False,
        archangel_analyzer="heuristic",
    )
    database = Database(settings.database_url)
    database.create_all()

    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        user = User(display_name="Reviewer", normalized_name="reviewer")
        db.add(user)
        db.flush()
        eligible = Post(
            author_id=user.id,
            title="Forgive rather than avenge",
            body="Ephesians 4:32 teaches forgiveness and Romans 12:19 rejects revenge.",
            training_consent=True,
        )
        excluded = Post(
            author_id=user.id,
            title="Forgive without research consent",
            body="Ephesians 4:32 teaches forgiveness.",
            training_consent=False,
        )
        db.add_all([eligible, excluded])
        db.flush()
        analyze_target(db, settings, "post", eligible.id)
        analyze_target(db, settings, "post", excluded.id)
        count = db.scalar(select(func.count()).select_from(TrainingCandidate))
        assert count == 1
        candidate = db.scalar(select(TrainingCandidate))
        assert candidate is not None
        assert candidate.target_id == eligible.id
        assert candidate.review_state == "pending_theological_review"
