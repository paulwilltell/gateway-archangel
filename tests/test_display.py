"""How findings are worded and ordered for a reader.

These pin the tone contract: the engine's cold vocabulary never reaches the
page, agreement is met before correction, and nothing is suppressed to
achieve either.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.display import (
    QUESTIONS_SHOWN,
    alignment_label,
    order_claims,
    split_claims,
    support_label,
)
from app.main import create_app


def _claim(level: str, text: str = "A claim") -> dict:
    return {"support_level": level, "alignment": "aligned", "claim": text, "rationale": "r"}


def test_engine_vocabulary_never_reaches_the_reader():
    """'unsupported' beneath someone's testimony reads as a verdict on them."""
    for level, label in (
        ("insufficient", "not stated in this passage"),
        ("direct_text", "the passage says this"),
        ("disputed_interpretation", "Christians read this differently"),
    ):
        assert support_label(level) == label
        assert "_" not in support_label(level)

    assert alignment_label("unsupported") == "goes beyond the passages cited"
    assert alignment_label("mixed") == "partly holds"


def test_wording_still_states_the_finding_plainly():
    """Gentler wording must not become vaguer wording."""
    assert "not stated" in support_label("insufficient")
    assert "beyond" in alignment_label("unsupported")
    assert "conflicts" in alignment_label("contradicted")


def test_confirmed_points_come_before_questions():
    ordered = order_claims([
        _claim("insufficient"), _claim("direct_text"),
        _claim("disputed_interpretation"), _claim("strong_inference"),
    ])
    assert [c["support_level"] for c in ordered] == [
        "direct_text", "strong_inference", "disputed_interpretation", "insufficient",
    ]


def test_questions_are_folded_but_never_dropped():
    claims = [_claim("direct_text")] + [_claim("insufficient", f"q{i}") for i in range(6)]
    grouped = split_claims(claims)

    assert len(grouped["held"]) == 1
    assert len(grouped["questioned"]) == QUESTIONS_SHOWN
    assert len(grouped["questioned_extra"]) == 6 - QUESTIONS_SHOWN
    total = len(grouped["held"]) + len(grouped["questioned"]) + len(grouped["questioned_extra"])
    assert total == len(claims), "every finding must survive display grouping"


def test_a_rendered_analysis_leads_with_what_holds():
    app = create_app(
        Settings(app_env="test", database_url="sqlite://", seed_demo_data=True, archangel_analyzer="heuristic")
    )
    with TestClient(app) as client:
        post_id = client.post(
            "/api/v1/posts",
            json={
                "author_name": "Reader",
                "title": "Forgiveness and letting go of revenge",
                "body": "Ephesians 4:32 teaches forgiveness and Romans 12:19 rejects personal revenge.",
            },
        ).json()["id"]
        page = client.get(f"/posts/{post_id}").text

    assert "What your passages carry" in page or "Worth a second look" in page
    # The raw engine vocabulary must not appear as a reader-facing label.
    assert ">insufficient<" not in page
    assert ">unsupported<" not in page
