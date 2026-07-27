from __future__ import annotations

import re

from app.analysis.contract import AnalysisResult, ClaimAssessment, ScriptureEvidence
from app.models import BibleVerse
from app.safety import SafetyAssessment

HARM_AS_DIVINE_COMMAND = re.compile(
    r"\b(?:god|jesus|the lord) (?:told|commanded|wants) me to (?:kill|hurt|attack|punish|destroy)\b",
    re.IGNORECASE,
)
PRIVATE_REVELATION = re.compile(r"\b(?:god|jesus|the lord) told me\b", re.IGNORECASE)
ABSOLUTE_CERTAINTY = re.compile(r"\b(?:definitely|without a doubt|guaranteed|100%|always means)\b", re.IGNORECASE)
REVENGE_APPROVAL = re.compile(r"\b(?:revenge is right|i should get revenge|pay them back|make them suffer)\b", re.IGNORECASE)
ALIGNED_PATTERNS = (
    re.compile(r"\bforgiv(?:e|eness|ing)\b", re.IGNORECASE),
    re.compile(r"\blove (?:your|my|our) enem(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bspeak(?:ing)? the truth in love\b", re.IGNORECASE),
    re.compile(r"\bbe (?:slow|quick) to (?:speak|hear)\b", re.IGNORECASE),
)


def analyze_heuristically(
    text: str,
    evidence_rows: list[BibleVerse],
    safety: SafetyAssessment,
) -> AnalysisResult:
    evidence = [
        ScriptureEvidence(
            reference=row.reference,
            text=row.text,
            source_id=row.source_id,
            relevance="Retrieved because the post cited this passage or used a related biblical theme.",
        )
        for row in evidence_rows
    ]
    refs = [item.reference for item in evidence]

    reasoning_flags: list[str] = []
    context_notes: list[str] = []
    limitations = [
        "Deterministic foundation analysis; it does not replace full literary, historical, Hebrew, or Greek exegesis.",
        "The system evaluates the written claim, not the author's faith, intent, salvation, or hidden motives.",
    ]

    if PRIVATE_REVELATION.search(text):
        reasoning_flags.append("private_revelation_claim_requires_caution")
        context_notes.append("A personal claim of revelation cannot be verified from the written biblical corpus alone.")
    if ABSOLUTE_CERTAINTY.search(text):
        reasoning_flags.append("unsupported_certainty_risk")
    if len(refs) == 1:
        reasoning_flags.append("single_passage_proof_texting_risk")
    if not refs:
        reasoning_flags.append("no_retrieved_textual_evidence")

    if HARM_AS_DIVINE_COMMAND.search(text) or REVENGE_APPROVAL.search(text):
        alignment = "contradicted"
        support = "direct_text"
        confidence = 0.92
        rationale = "The claim appears to present personal harm or revenge as divinely authorized; the retrieved biblical pattern rejects personal vengeance and commands love of enemies."
        fruit_signals = ["risk_of_harm", "retaliation", "spiritualized_coercion"]
    elif any(pattern.search(text) for pattern in ALIGNED_PATTERNS) and refs:
        alignment = "aligned"
        support = "strong_inference"
        confidence = 0.74
        rationale = "The central idea is consistent with the retrieved passages, though the exact application still depends on context."
        fruit_signals = ["forgiveness", "truthfulness", "peace_seeking"]
    elif refs:
        alignment = "uncertain"
        support = "wisdom_application"
        confidence = 0.52
        rationale = "Relevant passages were found, but a deterministic analyzer cannot establish that every conclusion in the post follows from them."
        fruit_signals = ["reflection_requested"]
    else:
        alignment = "unsupported"
        support = "insufficient"
        confidence = 0.40
        rationale = "No adequate biblical evidence was retrieved from the approved local corpus for the main claim."
        fruit_signals = ["insufficient_evidence"]

    claim_text = text.strip().replace("\n", " ")[:480]
    claims = [
        ClaimAssessment(
            claim=claim_text,
            alignment=alignment,
            support_level=support,
            rationale=rationale,
            evidence_references=refs,
        )
    ]

    return AnalysisResult(
        alignment=alignment,
        support_level=support,
        confidence=confidence,
        claims=claims,
        evidence=evidence,
        context_notes=context_notes,
        reasoning_flags=reasoning_flags,
        fruit_signals=fruit_signals,
        limitations=limitations,
        safety={
            "level": safety.level,
            "category": safety.category,
            "display_message": safety.display_message,
            "resources": list(safety.resources),
        },
        analyzer_mode="heuristic",
    )
