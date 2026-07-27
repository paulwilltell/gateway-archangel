from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=True,
        archangel_analyzer="heuristic",
    )


def test_home_and_health_load():
    app = create_app(make_settings())
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "GATEWAY" in home.text
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"


def test_human_post_gets_analysis_but_no_ai_reply():
    app = create_app(make_settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/posts",
            json={
                "author_name": "Test Member",
                "title": "Forgiveness without revenge",
                "body": "Ephesians 4:32 teaches forgiveness, and Romans 12:19 rejects personal revenge.",
                "training_consent": True,
            },
        )
        assert response.status_code == 201
        post_id = response.json()["id"]
        analysis = client.get(f"/api/v1/analysis/post/{post_id}")
        assert analysis.status_code == 200
        assert analysis.json()["alignment"] == "aligned"

        posts = client.get("/api/v1/posts").json()
        created = next(item for item in posts if item["id"] == post_id)
        assert created["replies"] == []
