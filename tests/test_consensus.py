"""Double-run consensus: disclose disagreement, present the weaker reading."""

from __future__ import annotations

from app.analysis.contract import AnalysisResult, ClaimAssessment, PairingClassification
from app.consensus import apply_consensus, verse_verdicts


def _pairing(reference: str, **overrides) -> PairingClassification:
    base = dict(
        reference=reference,
        speech_act="command",
        audience="all_believers",
        covenant_scope="new_covenant",
        claim_modality="obligation",
        addresses_claim_subject=True,
        claim_keeps_conditions=True,
    )
    base.update(overrides)
    return PairingClassification(**base)


def _result(pairings: list[PairingClassification], support: str = "direct_text") -> AnalysisResult:
    return AnalysisResult(
        alignment="aligned",
        support_level=support,
        confidence=0.9,
        claims=[
            ClaimAssessment(
                claim="A claim", alignment="aligned", support_level=support,
                rationale="Because the passage says so.",
                evidence_references=[p.reference for p in pairings],
                pairings=pairings,
            )
        ],
        evidence=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="anthropic",
    )


def test_verdicts_are_a_comparable_fingerprint_of_a_pass():
    result = _result([_pairing("Romans 12:18"), _pairing("Judges 6:37", speech_act="narrative")])
    verdicts = verse_verdicts(result)
    assert verdicts["Romans 12:18"] == "direct_text"
    assert verdicts["Judges 6:37"] == "insufficient"


def test_agreement_across_passes_leaves_the_verdict_alone():
    primary = _result([_pairing("Romans 12:18")])
    second = _result([_pairing("Romans 12:18")])

    record = apply_consensus(primary, [second])

    assert record.contested == {}
    assert record.settled == ["Romans 12:18"]
    assert record.contested_rate == 0.0
    assert primary.claims[0].support_level == "direct_text"
    assert "verdict_contested_across_passes" not in primary.reasoning_flags


def test_disagreement_presents_the_weaker_reading_and_says_so():
    """A support level the system cannot reproduce is not one it has earned."""
    primary = _result([_pairing("Romans 12:18")])
    # Second pass reads the same verse as narrative, which cannot command.
    second = _result([_pairing("Romans 12:18", speech_act="narrative")])

    record = apply_consensus(primary, [second])

    assert "Romans 12:18" in record.contested
    assert record.contested["Romans 12:18"]["presented"] == "insufficient"
    assert record.contested["Romans 12:18"]["levels_seen"] == ["direct_text", "insufficient"]
    assert record.claims_downgraded == 1

    claim = primary.claims[0]
    assert claim.support_level == "insufficient"
    assert claim.alignment == "unsupported"
    assert "contested rather than settled" in claim.rationale
    assert "verdict_contested_across_passes" in primary.reasoning_flags


def test_the_stronger_reading_never_wins():
    primary = _result([_pairing("Romans 12:18", speech_act="narrative")], support="insufficient")
    second = _result([_pairing("Romans 12:18")])

    apply_consensus(primary, [second])

    assert primary.claims[0].support_level == "insufficient"


def test_a_passage_missing_from_one_pass_counts_as_contested():
    """Uneven coverage is itself a disagreement about what bears on the claim."""
    primary = _result([_pairing("Romans 12:18"), _pairing("Luke 17:3")])
    second = _result([_pairing("Romans 12:18")])

    record = apply_consensus(primary, [second])

    assert "Luke 17:3" in record.contested
    assert record.contested["Luke 17:3"]["seen_in_passes"] == "1/2"
    # Distinguished from a verdict disagreement: nothing was read differently,
    # the passage simply was not considered in one pass.
    assert record.contested["Luke 17:3"]["reason"] == "coverage_differs"
    assert record.contested["Luke 17:3"]["levels_seen"] == ["direct_text"]


def test_a_verdict_disagreement_is_labelled_differently_from_a_coverage_gap():
    primary = _result([_pairing("Romans 12:18")])
    second = _result([_pairing("Romans 12:18", speech_act="narrative")])
    record = apply_consensus(primary, [second])
    assert record.contested["Romans 12:18"]["reason"] == "levels_disagree"


def test_a_single_pass_makes_no_consensus_claim():
    primary = _result([_pairing("Romans 12:18")])
    record = apply_consensus(primary, [])
    assert record.passes == 1
    assert record.contested == {} and record.settled == []
    assert primary.claims[0].support_level == "direct_text"


def test_contested_rate_is_reported_for_measurement():
    primary = _result([_pairing("Romans 12:18"), _pairing("Luke 17:3")])
    second = _result([
        _pairing("Romans 12:18", speech_act="narrative"),
        _pairing("Luke 17:3"),
    ])
    record = apply_consensus(primary, [second])
    assert record.contested_rate == 0.5
    assert record.to_dict()["contested_rate"] == 0.5
