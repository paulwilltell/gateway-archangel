"""Loom ⨯ Archangel: deterministic claim-grounding verification.

These tests pin the merge contract: groundings derive only from attested
citations, ungrounded textual support is downgraded, truth maintenance
retracts groundings when attestation is withdrawn, and the whole record is
bit-deterministic.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.analysis.contract import AnalysisResult, ClaimAssessment
from app.config import Settings
from app.db import Database
from app.loom_bridge import CORPUS_NODE, build_grounding_graph, verify_with_loom
from app.main import create_app


def _result_with_claims(claims: list[ClaimAssessment]) -> AnalysisResult:
    return AnalysisResult(
        alignment="aligned",
        support_level="direct_text",
        confidence=0.9,
        claims=claims,
        evidence=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="heuristic",
    )


def _claim(text: str, support: str, refs: list[str]) -> ClaimAssessment:
    return ClaimAssessment(
        claim=text,
        alignment="aligned",
        support_level=support,
        rationale="Rationale.",
        evidence_references=refs,
    )


def _db_session():
    settings = Settings(app_env="test", database_url="sqlite://", seed_demo_data=False)
    database = Database(settings.database_url)
    database.create_all()
    return settings, database


def _seed_corpus(db, settings):
    from app.analysis.retrieval import seed_corpus

    seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)


def test_grounding_derives_only_from_attested_citations():
    loom = build_grounding_graph(
        [
            {"index": 0, "cited": ["Ephesians 4:32"]},
            {"index": 1, "cited": ["Hezekiah 3:16"]},  # not a real book
            {"index": 2, "cited": []},
        ],
        attested_refs={"Ephesians 4:32"},
    )
    assert loom._thread_exists("claim_0", "grounded_in", CORPUS_NODE)
    assert not loom._thread_exists("claim_1", "grounded_in", CORPUS_NODE)
    assert not loom._thread_exists("claim_2", "grounded_in", CORPUS_NODE)


def test_truth_maintenance_retracts_grounding_with_last_support():
    # Synthetic single-token refs: Loom's filter grammar cannot tokenize
    # values containing spaces, and this test is about TMS semantics, not
    # reference formats (the bridge itself never calls filter).
    loom = build_grounding_graph(
        [{"index": 0, "cited": ["RefA", "RefB"]}],
        attested_refs={"RefA", "RefB"},
    )
    assert loom._thread_exists("claim_0", "grounded_in", CORPUS_NODE)
    # Withdraw one attestation: grounding survives on the other support.
    loom.filter("head=RefA and rel=attested_in")
    assert loom._thread_exists("claim_0", "grounded_in", CORPUS_NODE)
    # Withdraw the last: grounding must fall.
    loom.filter("head=RefB and rel=attested_in")
    assert not loom._thread_exists("claim_0", "grounded_in", CORPUS_NODE)


def test_ungrounded_textual_support_is_downgraded():
    settings, database = _db_session()
    with database.session() as db:
        _seed_corpus(db, settings)
        result = _result_with_claims(
            [
                _claim("Real citation", "direct_text", ["John 3:16"]),
                _claim("Fabricated citation", "direct_text", ["Hezekiah 3:16"]),
                _claim("Wisdom, no citation", "wisdom_application", []),
            ]
        )
        record = verify_with_loom(db, result)

    assert record["summary"] == {"total_claims": 3, "grounded": 1, "downgraded": 1}
    assert result.claims[0].support_level == "direct_text"
    assert result.claims[1].support_level == "insufficient"
    assert result.claims[1].alignment == "unsupported"
    assert "Loom" in result.claims[1].rationale
    # Wisdom claims make no textual-support claim, so nothing to withdraw.
    assert result.claims[2].support_level == "wisdom_application"
    assert "loom_ungrounded_claim_downgraded" in result.reasoning_flags
    assert record["claims"][0]["trace"] and "grounded_in" in record["claims"][0]["trace"]
    assert record["claims"][1]["trace"] is None


def test_verification_is_deterministic():
    settings, database = _db_session()
    with database.session() as db:
        _seed_corpus(db, settings)

        def run():
            result = _result_with_claims(
                [_claim("A", "direct_text", ["John 3:16", "Psalms 23:1"])]
            )
            return json.dumps(verify_with_loom(db, result), sort_keys=True)

        assert run() == run()


def test_analysis_payload_carries_loom_verification():
    # seed_demo_data=True loads the canonical corpus — without it nothing can
    # be attested and Loom (correctly) grounds zero claims.
    app = create_app(
        Settings(app_env="test", database_url="sqlite://", seed_demo_data=True, archangel_analyzer="heuristic")
    )
    with TestClient(app) as client:
        post_id = client.post(
            "/api/v1/posts",
            json={
                "author_name": "Tester",
                "title": "Forgiveness and revenge",
                "body": "Ephesians 4:32 teaches forgiveness and Romans 12:19 rejects revenge.",
            },
        ).json()["id"]
        analysis = client.get(f"/api/v1/analysis/post/{post_id}").json()

    loom = analysis["loom_verification"]
    assert loom["engine"] == "loom-2.2"
    assert loom["summary"]["total_claims"] >= 1
    assert loom["summary"]["grounded"] == loom["summary"]["total_claims"]
    assert loom["summary"]["downgraded"] == 0
