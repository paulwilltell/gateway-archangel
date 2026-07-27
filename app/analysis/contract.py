from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Alignment = Literal["aligned", "mixed", "unsupported", "contradicted", "uncertain"]
SupportLevel = Literal[
    "direct_text",
    "strong_inference",
    "wisdom_application",
    "disputed_interpretation",
    "insufficient",
]


class ScriptureEvidence(BaseModel):
    reference: str
    text: str
    source_id: str = "kjv_local"
    relevance: str


class PairingClassification(BaseModel):
    """The model's classification of one (claim, passage) pairing.

    This replaces the model asserting support. It states narrow, checkable
    facts about the passage and the claim; the published hermeneutic rules
    (app/hermeneutic.py) derive the support level from them.
    """

    reference: str
    speech_act: Literal[
        "command", "prohibition", "promise", "narrative", "wisdom_saying",
        "doctrinal_assertion", "prophecy", "question", "lament",
    ]
    audience: Literal[
        "all_believers", "humanity", "specific_individual", "specific_group", "national_israel",
    ]
    covenant_scope: Literal["creation", "patriarchal", "mosaic", "new_covenant", "eschatological"]
    claim_modality: Literal[
        "obligation", "prohibition", "guarantee", "prediction",
        "permission", "description", "promise_to_claimant",
    ]
    addresses_claim_subject: bool
    claim_keeps_conditions: bool
    reaffirmed_in_new_covenant: bool = False
    counterpassage_addressed: bool = True


class ClaimAssessment(BaseModel):
    claim: str
    alignment: Alignment
    support_level: SupportLevel
    rationale: str
    evidence_references: list[str] = Field(default_factory=list)
    pairings: list[PairingClassification] = Field(default_factory=list, max_length=8)


class SafetyResult(BaseModel):
    level: Literal["none", "concern", "urgent", "immediate"] = "none"
    category: str = "none"
    display_message: str | None = None
    resources: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """The only shape Archangel may persist or expose.

    This is intentionally an analysis record, not a conversational AI reply.
    """

    alignment: Alignment
    support_level: SupportLevel
    confidence: float = Field(ge=0.0, le=1.0)
    claims: list[ClaimAssessment] = Field(default_factory=list, max_length=8)
    evidence: list[ScriptureEvidence] = Field(default_factory=list, max_length=12)
    context_notes: list[str] = Field(default_factory=list, max_length=8)
    reasoning_flags: list[str] = Field(default_factory=list, max_length=8)
    fruit_signals: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    safety: SafetyResult = Field(default_factory=SafetyResult)
    analyzer_mode: str = "heuristic"


ANALYSIS_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "alignment",
        "support_level",
        "confidence",
        "claims",
        "evidence",
        "context_notes",
        "reasoning_flags",
        "fruit_signals",
        "limitations",
        "safety",
        "analyzer_mode",
    ],
    "properties": {
        "alignment": {"type": "string", "enum": ["aligned", "mixed", "unsupported", "contradicted", "uncertain"]},
        "support_level": {
            "type": "string",
            "enum": ["direct_text", "strong_inference", "wisdom_application", "disputed_interpretation", "insufficient"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "claims": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "alignment", "support_level", "rationale", "evidence_references", "pairings"],
                "properties": {
                    "claim": {"type": "string"},
                    "alignment": {"type": "string", "enum": ["aligned", "mixed", "unsupported", "contradicted", "uncertain"]},
                    "support_level": {
                        "type": "string",
                        "enum": ["direct_text", "strong_inference", "wisdom_application", "disputed_interpretation", "insufficient"],
                    },
                    "rationale": {"type": "string"},
                    "evidence_references": {"type": "array", "items": {"type": "string"}},
                    "pairings": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "reference", "speech_act", "audience", "covenant_scope",
                                "claim_modality", "addresses_claim_subject",
                                "claim_keeps_conditions", "reaffirmed_in_new_covenant",
                                "counterpassage_addressed",
                            ],
                            "properties": {
                                "reference": {"type": "string"},
                                "speech_act": {"type": "string", "enum": [
                                    "command", "prohibition", "promise", "narrative", "wisdom_saying",
                                    "doctrinal_assertion", "prophecy", "question", "lament"]},
                                "audience": {"type": "string", "enum": [
                                    "all_believers", "humanity", "specific_individual",
                                    "specific_group", "national_israel"]},
                                "covenant_scope": {"type": "string", "enum": [
                                    "creation", "patriarchal", "mosaic", "new_covenant", "eschatological"]},
                                "claim_modality": {"type": "string", "enum": [
                                    "obligation", "prohibition", "guarantee", "prediction",
                                    "permission", "description", "promise_to_claimant"]},
                                "addresses_claim_subject": {"type": "boolean"},
                                "claim_keeps_conditions": {"type": "boolean"},
                                "reaffirmed_in_new_covenant": {"type": "boolean"},
                                "counterpassage_addressed": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
        },
        "evidence": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["reference", "text", "source_id", "relevance"],
                "properties": {
                    "reference": {"type": "string"},
                    "text": {"type": "string"},
                    "source_id": {"type": "string"},
                    "relevance": {"type": "string"},
                },
            },
        },
        "context_notes": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "reasoning_flags": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "fruit_signals": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "limitations": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "safety": {
            "type": "object",
            "additionalProperties": False,
            "required": ["level", "category", "display_message", "resources"],
            "properties": {
                "level": {"type": "string", "enum": ["none", "concern", "urgent", "immediate"]},
                "category": {"type": "string"},
                "display_message": {"type": ["string", "null"]},
                "resources": {"type": "array", "items": {"type": "string"}},
            },
        },
        "analyzer_mode": {"type": "string"},
    },
}
