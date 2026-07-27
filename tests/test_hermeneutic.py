"""Loom stage 2: support levels are derived from published rules, not asserted.

These tests pin the hermeneutic itself. Changing one means changing the
platform's stated interpretive commitments, which is a decision to make
deliberately and version — not a test to quietly adjust.
"""

from __future__ import annotations

from app.analysis.contract import AnalysisResult, ClaimAssessment, PairingClassification
from app.hermeneutic import PairingProfile, evaluate_pairing, published_rules, weakest
from app.loom_bridge import (
    build_entailment_graph,
    derive_entailment,
    derived_support_levels,
)


def _profile(**overrides) -> PairingProfile:
    base = dict(
        speech_act="command",
        audience="all_believers",
        covenant_scope="new_covenant",
        claim_modality="obligation",
        addresses_claim_subject=True,
        claim_keeps_conditions=True,
        reaffirmed_in_new_covenant=False,
        counterpassage_addressed=True,
    )
    base.update(overrides)
    return PairingProfile(**base)


# --- the rules themselves -----------------------------------------------------

def test_a_command_to_all_believers_yields_direct_text():
    verdict = evaluate_pairing(_profile())
    assert verdict.rule == "direct_command"
    assert verdict.support_level == "direct_text"


def test_narrative_cannot_become_a_command():
    """The classic error: Scripture describing an event is not commanding it."""
    verdict = evaluate_pairing(_profile(speech_act="narrative"))
    assert verdict.rule == "descriptive_not_prescriptive"
    assert verdict.support_level == "insufficient"


def test_narrative_does_support_a_claim_about_what_it_records():
    """The other half of the descriptive/prescriptive distinction, and a gap
    found by live testing: "Judges 6:37 records Gideon laying out a fleece" is
    directly attested. Only "therefore you should" is not."""
    describing = evaluate_pairing(_profile(speech_act="narrative", claim_modality="description"))
    assert describing.rule == "narrative_reports_event"
    assert describing.support_level == "direct_text"

    prescribing = evaluate_pairing(_profile(speech_act="narrative", claim_modality="obligation"))
    assert prescribing.support_level == "insufficient"


def test_a_lament_is_not_a_divine_guarantee():
    verdict = evaluate_pairing(_profile(speech_act="lament", claim_modality="guarantee"))
    assert verdict.support_level == "insufficient"


def test_a_proverb_is_not_a_guarantee_but_does_support_wisdom():
    as_guarantee = evaluate_pairing(_profile(speech_act="wisdom_saying", claim_modality="guarantee"))
    assert as_guarantee.rule == "proverb_read_as_guarantee"
    assert as_guarantee.support_level == "insufficient"

    as_wisdom = evaluate_pairing(_profile(speech_act="wisdom_saying", claim_modality="obligation"))
    assert as_wisdom.support_level == "wisdom_application"


def test_dropping_a_condition_removes_support():
    verdict = evaluate_pairing(_profile(speech_act="promise", claim_keeps_conditions=False))
    assert verdict.rule == "condition_dropped"
    assert verdict.support_level == "insufficient"


def test_a_promise_to_israel_is_not_an_individual_guarantee():
    """The Malachi 3:10 prosperity error, encoded."""
    verdict = evaluate_pairing(
        _profile(speech_act="promise", audience="national_israel", claim_modality="guarantee")
    )
    assert verdict.rule == "addressee_generalized"
    assert verdict.support_level == "insufficient"


def test_a_promise_to_all_believers_is_claimable():
    verdict = evaluate_pairing(
        _profile(speech_act="promise", audience="all_believers", claim_modality="promise_to_claimant")
    )
    assert verdict.support_level == "strong_inference"


def test_unreaffirmed_mosaic_obligation_is_disputed_not_settled():
    verdict = evaluate_pairing(_profile(covenant_scope="mosaic", reaffirmed_in_new_covenant=False))
    assert verdict.support_level == "disputed_interpretation"
    reaffirmed = evaluate_pairing(_profile(covenant_scope="mosaic", reaffirmed_in_new_covenant=True))
    assert reaffirmed.support_level == "direct_text"


def test_a_verse_off_the_claims_subject_supports_nothing():
    """Acts 2:17 mentions dreams; that does not make it about buying a house."""
    verdict = evaluate_pairing(_profile(addresses_claim_subject=False))
    assert verdict.rule == "topic_mismatch"
    assert verdict.support_level == "insufficient"


def test_an_unaddressed_counterpassage_caps_support_at_disputed():
    verdict = evaluate_pairing(_profile(counterpassage_addressed=False))
    assert verdict.support_level == "disputed_interpretation"
    assert "counterpassage_unaddressed" in verdict.rule


def test_blocking_rules_cannot_be_outvoted_by_supporting_ones():
    """A category error must survive an otherwise perfect profile."""
    verdict = evaluate_pairing(_profile(speech_act="narrative", audience="all_believers"))
    assert verdict.support_level == "insufficient"


def test_strongest_supporting_passage_governs_a_claim():
    assert weakest(["insufficient", "direct_text"]) == "direct_text"
    assert weakest(["insufficient", "wisdom_application"]) == "wisdom_application"
    assert weakest([]) == "insufficient"


def test_the_ruleset_is_published_for_inspection():
    rules = published_rules()
    assert len(rules) >= 10
    assert {r["kind"] for r in rules} == {"blocking", "supporting", "capping"}
    for rule in rules:
        assert rule["when"] and rule["yields"]


# --- Loom derivation ------------------------------------------------------------

def test_loom_derives_support_and_truth_maintenance_holds():
    pairings = [
        {"claim_index": 0, "reference": "RefA", "attested": True,
         "rule": "direct_command", "support_level": "direct_text"},
    ]
    loom = build_entailment_graph(pairings)
    assert derived_support_levels(loom, 0) == ["direct_text"]

    # Withdraw the rule application: the derived support must fall with it.
    loom.filter("rel=evaluated_by")
    assert derived_support_levels(loom, 0) == []


def test_unattested_pairings_never_reach_the_rule_table():
    loom = build_entailment_graph(
        [{"claim_index": 0, "reference": "Hezekiah 3:16", "attested": False,
          "rule": "direct_command", "support_level": "direct_text"}]
    )
    assert derived_support_levels(loom, 0) == []


def test_derived_support_overrides_what_the_model_asserted():
    """The model claims direct_text from a narrative passage; the rules say no."""
    result = AnalysisResult(
        alignment="aligned",
        support_level="direct_text",
        confidence=0.95,
        claims=[
            ClaimAssessment(
                claim="Because Gideon laid out a fleece, believers should seek signs this way.",
                alignment="aligned",
                support_level="direct_text",
                rationale="Asserted by the analyzer.",
                evidence_references=["Judges 6:37"],
                pairings=[
                    PairingClassification(
                        reference="Judges 6:37",
                        speech_act="narrative",
                        audience="specific_individual",
                        covenant_scope="mosaic",
                        claim_modality="obligation",
                        addresses_claim_subject=True,
                        claim_keeps_conditions=True,
                    )
                ],
            )
        ],
        evidence=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="anthropic",
    )

    record = derive_entailment(None, result, attested={"Judges 6:37"})

    assert record["summary"]["overridden"] == 1
    assert result.claims[0].support_level == "insufficient"
    assert result.claims[0].alignment == "unsupported"
    assert "descriptive_not_prescriptive" in result.claims[0].rationale
    assert "loom_support_level_derived_not_asserted" in result.reasoning_flags
    assert record["claims"][0]["trace"] and "derives_support" in record["claims"][0]["trace"]


def test_counterpassage_references_are_attested_against_the_corpus():
    """Regression: pairings may cite passages beyond a claim's own evidence
    list (counterpassages especially). Checking attestation against that
    narrower list treated real verses as forged and silently derived nothing,
    marking a well-supported claim insufficient."""
    from app.analysis.retrieval import seed_corpus
    from app.config import Settings
    from app.db import Database

    settings = Settings(app_env="test", database_url="sqlite://", seed_demo_data=False)
    database = Database(settings.database_url)
    database.create_all()

    result = AnalysisResult(
        alignment="aligned",
        support_level="strong_inference",
        confidence=0.8,
        claims=[
            ClaimAssessment(
                claim="Believers are commanded to forgive one another.",
                alignment="aligned",
                support_level="strong_inference",
                rationale="r",
                # Note: Luke 17:3 is a counterpassage, deliberately absent here.
                evidence_references=["Colossians 3:13"],
                pairings=[
                    PairingClassification(
                        reference="Colossians 3:13", speech_act="command",
                        audience="all_believers", covenant_scope="new_covenant",
                        claim_modality="obligation", addresses_claim_subject=True,
                        claim_keeps_conditions=True,
                    ),
                    PairingClassification(
                        reference="Luke 17:3", speech_act="command",
                        audience="all_believers", covenant_scope="new_covenant",
                        claim_modality="obligation", addresses_claim_subject=True,
                        claim_keeps_conditions=True,
                    ),
                ],
            )
        ],
        evidence=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="anthropic",
    )

    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        record = derive_entailment(db, result, attested={"Colossians 3:13"})

    fired = {r["reference"]: r for r in record["claims"][0]["rules_fired"]}
    assert fired["Luke 17:3"]["attested"] is True, "a real verse was treated as unattested"
    assert record["claims"][0]["derived_support"] == "direct_text"


def test_the_rules_are_published_on_the_method_page():
    """A hermeneutic applied in secret is the thing this platform exists to
    avoid. If the rules govern, they must be readable."""
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    app = create_app(
        Settings(app_env="test", database_url="sqlite://", seed_demo_data=False, archangel_analyzer="heuristic")
    )
    with TestClient(app) as client:
        page = client.get("/method").text
    assert 'id="hermeneutic"' in page
    assert "descriptive_not_prescriptive" in page
    assert "addressee_generalized" in page
    assert "hermeneutic-rules-v1" in page


def test_no_classifications_means_no_stage_two_claims():
    """The deterministic analyzer supplies no pairings; stage 2 stays silent
    rather than inventing a verdict."""
    result = AnalysisResult(
        alignment="aligned",
        support_level="strong_inference",
        confidence=0.7,
        claims=[
            ClaimAssessment(
                claim="A claim", alignment="aligned", support_level="strong_inference",
                rationale="r", evidence_references=["John 3:16"],
            )
        ],
        evidence=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="heuristic",
    )
    assert derive_entailment(None, result, attested={"John 3:16"}) is None
    assert result.claims[0].support_level == "strong_inference"
