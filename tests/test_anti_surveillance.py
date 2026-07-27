"""Anti-surveillance invariants.

Archangel analyzes content, never people. These tests pin the structural
guarantees that keep the platform from becoming a spiritual-scoring tool:
analyses attach to a post or reply, carry no author identity, and expose no
per-user rollup surface. If any of these fail, the feature that broke them
must be redesigned, not the test.
"""

from __future__ import annotations

import json

from app.analysis.engine import analysis_to_dict, analyze_target
from app.analysis.retrieval import seed_corpus
from app.config import Settings
from app.db import Database
from app.models import Analysis, Post, User
from app.routers import api, web


def _make_db(settings: Settings) -> Database:
    database = Database(settings.database_url)
    database.create_all()
    return database


def test_analysis_table_carries_no_user_identity():
    columns = {column.name for column in Analysis.__table__.columns}
    forbidden = {"user_id", "author_id", "owner_id", "member_id"}
    assert not (columns & forbidden), (
        "Analysis rows must attach to content, never to a person: "
        f"found {columns & forbidden}"
    )


def test_analysis_payload_exposes_no_author():
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=False,
        archangel_analyzer="heuristic",
    )
    database = _make_db(settings)
    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        user = User(display_name="Member", normalized_name="member")
        db.add(user)
        db.flush()
        post = Post(
            author_id=user.id,
            title="Forgiveness",
            body="Ephesians 4:32 teaches forgiveness.",
            training_consent=False,
        )
        db.add(post)
        db.flush()
        analysis = analyze_target(db, settings, "post", post.id)
        payload = analysis_to_dict(analysis)

    serialized = json.dumps(payload)
    assert user.id not in serialized
    assert "author_id" not in payload
    assert "author_name" not in payload
    assert "Member" not in serialized


def test_no_router_exposes_per_user_analysis_aggregation():
    for module in (api, web):
        for route in module.router.routes:
            path = getattr(route, "path", "")
            assert not (
                "/analysis" in path and ("user" in path or "member" in path or "author" in path)
            ), f"Route {path} looks like a per-user analysis rollup"
