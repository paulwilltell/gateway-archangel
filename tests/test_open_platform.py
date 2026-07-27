"""Open-platform behavior: free posting with a narrow content policy,
rate limiting, content-first reports, and token-guarded moderation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.policy import screen_content


def make_settings(**overrides) -> Settings:
    defaults = dict(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=False,
        archangel_analyzer="heuristic",
        moderation_token="test-moderation-token",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _post_payload(**overrides) -> dict:
    payload = {
        "author_name": "Tester",
        "title": "A question about forgiveness",
        "body": "Ephesians 4:32 teaches forgiveness. How does that relate to trust?",
        "training_consent": False,
    }
    payload.update(overrides)
    return payload


# --- deterministic policy screen -------------------------------------------

def test_screen_blocks_directed_harassment():
    verdict = screen_content("You are worthless, kill yourself.")
    assert not verdict.allowed
    assert verdict.category == "abusive_content"


def test_screen_blocks_porn_link():
    verdict = screen_content("Check out https://pornhub.com/somevideo")
    assert not verdict.allowed
    assert verdict.category == "sexual_content"


def test_screen_blocks_link_flood_spam():
    text = " ".join(f"https://spam{i}.example.com" for i in range(6))
    verdict = screen_content(text)
    assert not verdict.allowed
    assert verdict.category == "spam"


def test_screen_allows_abuse_testimony_and_confession():
    testimony = (
        "My husband abused me for years and I finally left. I am trying to "
        "understand what forgiveness requires of me now."
    )
    confession = "I struggle with porn addiction and lust, and I need prayer and accountability."
    assert screen_content(testimony).allowed
    assert screen_content(confession).allowed


def test_screen_allows_heterodox_viewpoints():
    assert screen_content("I believe the church is wrong about baptism and always has been.").allowed


# --- enforcement at the API ---------------------------------------------------

def test_policy_violation_rejected_at_submission():
    app = create_app(make_settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/posts",
            json=_post_payload(body="Everyone here should just kill yourself honestly."),
        )
        assert response.status_code == 422
        assert "content policy" in response.json()["detail"]


def test_rate_limit_blocks_flooding():
    app = create_app(make_settings(rate_limit_posts_per_window=3))
    with TestClient(app) as client:
        for i in range(3):
            ok = client.post("/api/v1/posts", json=_post_payload(title=f"Post number {i} title"))
            assert ok.status_code == 201
        blocked = client.post("/api/v1/posts", json=_post_payload(title="One post too many now"))
        assert blocked.status_code == 429


# --- reports and moderation ---------------------------------------------------

def test_report_then_remove_then_restore_flow():
    app = create_app(make_settings())
    headers = {"X-Moderation-Token": "test-moderation-token"}
    with TestClient(app) as client:
        post_id = client.post("/api/v1/posts", json=_post_payload()).json()["id"]

        report = client.post(
            "/api/v1/reports",
            json={"target_type": "post", "target_id": post_id, "category": "spam"},
        )
        assert report.status_code == 201

        # No token: refused. Wrong token: refused.
        assert client.get("/api/v1/moderation/reports").status_code == 403
        assert client.get(
            "/api/v1/moderation/reports", headers={"X-Moderation-Token": "wrong"}
        ).status_code == 403

        queue = client.get("/api/v1/moderation/reports", headers=headers).json()
        assert len(queue) == 1
        assert queue[0]["target_id"] == post_id
        assert "author" not in queue[0]  # content-first: no identity in the queue

        removed = client.post(f"/api/v1/moderation/post/{post_id}/remove", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["reports_resolved"] == 1

        listed = [p["id"] for p in client.get("/api/v1/posts").json()]
        assert post_id not in listed
        assert client.get(f"/posts/{post_id}").status_code == 404

        restored = client.post(f"/api/v1/moderation/post/{post_id}/restore", headers=headers)
        assert restored.status_code == 200
        assert post_id in [p["id"] for p in client.get("/api/v1/posts").json()]


def test_moderation_disabled_without_configured_token():
    app = create_app(make_settings(moderation_token=None))
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/moderation/reports", headers={"X-Moderation-Token": "anything"}
        )
        assert response.status_code == 503


def test_removed_reply_hidden_from_post_output():
    app = create_app(make_settings())
    headers = {"X-Moderation-Token": "test-moderation-token"}
    with TestClient(app) as client:
        post_id = client.post("/api/v1/posts", json=_post_payload()).json()["id"]
        reply_id = client.post(
            f"/api/v1/posts/{post_id}/replies",
            json={"author_name": "Replier", "body": "Romans 12:19 is also relevant here."},
        ).json()["id"]

        post = next(p for p in client.get("/api/v1/posts").json() if p["id"] == post_id)
        assert [r["id"] for r in post["replies"]] == [reply_id]

        client.post(f"/api/v1/moderation/reply/{reply_id}/remove", headers=headers)
        post = next(p for p in client.get("/api/v1/posts").json() if p["id"] == post_id)
        assert post["replies"] == []
