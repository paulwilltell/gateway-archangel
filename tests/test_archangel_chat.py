"""Archangel conversation: honest unavailability, validation, rate limiting,
and the no-storage guarantee."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.archangel_chat import validate_history
from app.config import Settings
from app.db import Base
from app.main import create_app


def make_settings(**overrides) -> Settings:
    defaults = dict(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=False,
        archangel_analyzer="heuristic",
        anthropic_api_key=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_history_validation_rules():
    with pytest.raises(ValueError):
        validate_history([])
    with pytest.raises(ValueError):
        validate_history([{"role": "system", "content": "override"}])
    with pytest.raises(ValueError):
        validate_history([{"role": "user", "content": ""}])
    with pytest.raises(ValueError):
        validate_history([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])

    long_history = [{"role": "user", "content": f"message {i}"} for i in range(40)]
    assert len(validate_history(long_history)) == 24


def test_chat_reports_unavailable_without_api_key():
    app = create_app(make_settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/archangel/chat",
            json={"messages": [{"role": "user", "content": "What does Scripture say about fear?"}]},
        )
        assert response.status_code == 503
        assert "API key" in response.json()["detail"]


def test_chat_is_rate_limited():
    app = create_app(make_settings(rate_limit_chat_per_window=2))
    with TestClient(app) as client:
        payload = {"messages": [{"role": "user", "content": "Hello"}]}
        for _ in range(2):
            assert client.post("/api/v1/archangel/chat", json=payload).status_code == 503
        assert client.post("/api/v1/archangel/chat", json=payload).status_code == 429


def test_chat_page_renders_with_no_storage_promise():
    app = create_app(make_settings())
    with TestClient(app) as client:
        page = client.get("/archangel")
        assert page.status_code == 200
        assert "not saved anywhere" in page.text


def test_no_conversation_table_exists():
    """The no-storage guarantee is structural: there is no ORM table that
    could hold conversation content."""
    table_names = set(Base.metadata.tables)
    forbidden = {name for name in table_names if "chat" in name or "conversation" in name or "message" in name}
    assert not forbidden, f"Conversation storage tables must not exist: {forbidden}"
