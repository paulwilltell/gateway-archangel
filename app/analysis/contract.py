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


class ClaimAssessment(BaseModel):
    claim: str
    alignment: Alignment
    support_level: SupportLevel
    rationale: str
    evidence_references: list[str] = Field(default_factory=list)


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
                "required": ["claim", "alignment", "support_level", "rationale", "evidence_references"],
                "properties": {
                    "claim": {"type": "string"},
                    "alignment": {"type": "string", "enum": ["aligned", "mixed", "unsupported", "contradicted", "uncertain"]},
                    "support_level": {
                        "type": "string",
                        "enum": ["direct_text", "strong_inference", "wisdom_application", "disputed_interpretation", "insufficient"],
                    },
                    "rationale": {"type": "string"},
                    "evidence_references": {"type": "array", "items": {"type": "string"}},
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
