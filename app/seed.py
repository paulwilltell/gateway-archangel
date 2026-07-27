from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.engine import analyze_target
from app.analysis.retrieval import seed_corpus
from app.config import Settings
from app.models import ConsentEvent, Post, Reply, User


def seed_demo(db: Session, settings: Settings) -> None:
    seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)

    post_count = db.scalar(select(func.count()).select_from(Post)) or 0
    if post_count:
        return

    miriam = User(display_name="Miriam", normalized_name="miriam")
    jonah = User(display_name="Jonah", normalized_name="jonah")
    ruth = User(display_name="Ruth", normalized_name="ruth")
    db.add_all([miriam, jonah, ruth])
    db.flush()

    post1 = Post(
        author_id=miriam.id,
        title="Forgiveness and restored trust are not identical",
        body=(
            "Ephesians 4:32 calls Christians to forgive, but reconciliation also requires truth. "
            "I believe forgiveness rejects revenge while restored access can still require repentance and changed behavior."
        ),
        training_consent=True,
    )
    post2 = Post(
        author_id=jonah.id,
        title="When correction turns into humiliation",
        body=(
            "James 1:19 tells us to be swift to hear and slow to speak. Christian correction should seek restoration, "
            "not public embarrassment. Matthew 18:15 seems to begin privately rather than with a crowd."
        ),
        training_consent=False,
    )
    db.add_all([post1, post2])
    db.flush()

    reply1 = Reply(
        post_id=post1.id,
        author_id=ruth.id,
        body=(
            "Romans 12:19 also removes personal vengeance from the equation. A boundary can stop repeated harm "
            "without turning hatred into a virtue."
        ),
        training_consent=True,
    )
    db.add(reply1)
    db.flush()

    for user, target_type, target_id, consent in (
        (miriam, "post", post1.id, True),
        (jonah, "post", post2.id, False),
        (ruth, "reply", reply1.id, True),
    ):
        db.add(
            ConsentEvent(
                user_id=user.id,
                target_type=target_type,
                target_id=target_id,
                policy_version=settings.training_policy_version,
                consented=consent,
            )
        )
    db.flush()

    analyze_target(db, settings, "post", post1.id)
    analyze_target(db, settings, "post", post2.id)
    analyze_target(db, settings, "reply", reply1.id)
