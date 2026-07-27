from types import SimpleNamespace

from app.analysis.contract import AnalysisResult, ClaimAssessment, ScriptureEvidence
from app.analysis.engine import _enforce_evidence_boundary


def _result(evidence: list[ScriptureEvidence], refs: list[str]) -> AnalysisResult:
    return AnalysisResult(
        alignment="aligned",
        support_level="direct_text",
        confidence=0.93,
        claims=[
            ClaimAssessment(
                claim="A claim",
                alignment="aligned",
                support_level="direct_text",
                rationale="Claimed support",
                evidence_references=refs,
            )
        ],
        evidence=evidence,
        context_notes=[],
        reasoning_flags=[],
        fruit_signals=[],
        limitations=[],
        safety={"level": "none", "category": "none", "display_message": None, "resources": []},
        analyzer_mode="openai",
    )


def test_replaces_altered_quote_with_exact_retrieved_text():
    row = SimpleNamespace(reference="Micah 6:8", text="Exact approved text", source_id="kjv_local")
    result = _result(
        [ScriptureEvidence(reference="Micah 6:8", text="Invented wording", source_id="kjv_local", relevance="Relevant")],
        ["Micah 6:8"],
    )

    locked = _enforce_evidence_boundary(result, [row])

    assert locked.evidence[0].text == "Exact approved text"
    assert "provider_quotation_replaced_with_exact_corpus_text" in locked.reasoning_flags
    assert locked.support_level == "direct_text"


def test_removes_unretrieved_reference_and_downgrades_support():
    row = SimpleNamespace(reference="Micah 6:8", text="Exact approved text", source_id="kjv_local")
    result = _result(
        [ScriptureEvidence(reference="Revelation 99:1", text="Fabricated", source_id="kjv_local", relevance="Claimed")],
        ["Revelation 99:1"],
    )

    locked = _enforce_evidence_boundary(result, [row])

    assert locked.evidence == []
    assert locked.claims[0].evidence_references == []
    assert locked.alignment == "unsupported"
    assert locked.support_level == "insufficient"
    assert locked.confidence <= 0.45
    assert "provider_citations_outside_retrieved_corpus_removed" in locked.reasoning_flags
