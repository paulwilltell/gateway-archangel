"""Anonymous ownership: control over your own words without an account."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ownership import hash_token, new_token, token_matches


def _app():
    return create_app(
        Settings(app_env="test", database_url="sqlite://", seed_demo_data=False, archangel_analyzer="heuristic")
    )


def _post(client) -> dict:
    return client.post(
        "/api/v1/posts",
        json={
            "author_name": "Sojourner",
            "title": "A question I may want to withdraw",
            "body": "Ephesians 4:32 has been on my mind and I am not sure I want this public forever.",
            "training_consent": True,
        },
    ).json()


def test_token_is_random_and_verified_by_hash():
    token_a, hash_a = new_token()
    token_b, _ = new_token()
    assert token_a != token_b
    assert len(token_a) >= 24
    assert token_matches(token_a, hash_a)
    assert not token_matches(token_b, hash_a)
    assert not token_matches("", hash_a)
    assert not token_matches(token_a, None)


def test_only_the_hash_is_stored():
    """A seized database must not yield usable tokens."""
    from app.db import Database
    from app.models import Post

    app = _app()
    with TestClient(app) as client:
        created = _post(client)
        token = created["owner_token"]
    db: Database = app.state.db
    with db.session() as session:
        row = session.get(Post, created["id"])
        assert row.owner_token_hash == hash_token(token)
        assert token not in (row.owner_token_hash or "")


def test_correct_token_withdraws_and_wrong_token_is_refused():
    app = _app()
    with TestClient(app) as client:
        created = _post(client)
        post_id, token = created["id"], created["owner_token"]

        refused = client.post(
            f"/api/v1/ownership/post/{post_id}/withdraw",
            json={"owner_token": "not-the-right-token", "action": "delete"},
        )
        assert refused.status_code == 403
        assert post_id in [p["id"] for p in client.get("/api/v1/posts").json()]

        ok = client.post(
            f"/api/v1/ownership/post/{post_id}/withdraw",
            json={"owner_token": token, "action": "delete"},
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "withdrawn_by_author"
        assert post_id not in [p["id"] for p in client.get("/api/v1/posts").json()]
        assert client.get(f"/posts/{post_id}").status_code == 404


def test_consent_can_be_withdrawn_without_deleting():
    from app.models import Post

    app = _app()
    with TestClient(app) as client:
        created = _post(client)
        response = client.post(
            f"/api/v1/ownership/post/{created['id']}/withdraw",
            json={"owner_token": created["owner_token"], "action": "withdraw_consent"},
        )
        assert response.status_code == 200
        # The post stays public; only research consent is revoked.
        assert created["id"] in [p["id"] for p in client.get("/api/v1/posts").json()]
    with app.state.db.session() as session:
        assert session.get(Post, created["id"]).training_consent is False


def test_token_does_not_link_a_person_across_posts():
    """Each contribution gets its own token, so possession of one reveals
    nothing about any other contribution."""
    app = _app()
    with TestClient(app) as client:
        first, second = _post(client), _post(client)
        assert first["owner_token"] != second["owner_token"]
        crossed = client.post(
            f"/api/v1/ownership/post/{second['id']}/withdraw",
            json={"owner_token": first["owner_token"], "action": "delete"},
        )
        assert crossed.status_code == 403
