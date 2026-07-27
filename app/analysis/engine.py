from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.contract import AnalysisResult, ScriptureEvidence
from app.analysis.heuristic import analyze_heuristically
from app.analysis.providers import (
    ProviderError,
    analyze_with_anthropic,
    analyze_with_local_openai_compatible,
    analyze_with_openai,
)
from app.analysis.prompt import SYSTEM_INSTRUCTIONS
from app.consensus import ConsensusRecord, apply_consensus
from app.analysis.retrieval import (
    COUNTERPASSAGE_VERSION,
    THEME_INDEX_VERSION,
    retrieval_context,
    retrieve_evidence,
)
from app.config import Settings
from app.lexicon import LEXICAL_RULES, lexical_context, lexicon_source
from app.loom_bridge import LOOM_ENGINE_VERSION, verify_with_loom
from app.models import Analysis, AuditEvent, ContentReport, Post, Reply, TrainingCandidate
from app.pii import scan_and_redact
from app.safety import classify_safety


@dataclass(frozen=True)
class TargetContent:
    target_type: str
    target_id: str
    text: str
    training_consent: bool
    visibility: str
    status: str


ANALYSIS_SCHEMA_VERSION = "archangel-analysis-schema-1"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_provenance(settings: Settings, result: AnalysisResult) -> dict:
    """Everything needed to reproduce or impeach this analysis.

    A conclusion is only as trustworthy as the machinery that produced it, so
    each record names its corpus, its retrieval and index versions, the exact
    prompt (by hash), the model, and the deterministic engines involved. When
    a past analysis looks wrong, this says which component to suspect.
    """
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "engine_version": settings.archangel_engine_version,
        "analyzer_mode": result.analyzer_mode,
        "model": settings.anthropic_model if result.analyzer_mode == "anthropic" else None,
        "corpus_version": settings.corpus_version,
        "theme_index_version": THEME_INDEX_VERSION,
        "counterpassage_index_version": COUNTERPASSAGE_VERSION,
        "lexicon_source": lexicon_source(),
        "loom_engine": LOOM_ENGINE_VERSION,
        "system_prompt_sha256": hashlib.sha256(SYSTEM_INSTRUCTIONS.encode("utf-8")).hexdigest(),
        "lexical_rules_sha256": hashlib.sha256(LEXICAL_RULES.encode("utf-8")).hexdigest(),
        "training_policy_version": settings.training_policy_version,
    }


def load_target(db: Session, target_type: str, target_id: str) -> TargetContent:
    if target_type == "post":
        row = db.get(Post, target_id)
        if not row:
            raise LookupError("Post not found")
        return TargetContent(
            target_type="post",
            target_id=row.id,
            text=f"{row.title}\n\n{row.body}",
            training_consent=row.training_consent,
            visibility=row.visibility,
            status=row.status,
        )
    if target_type == "reply":
        row = db.get(Reply, target_id)
        if not row:
            raise LookupError("Reply not found")
        return TargetContent(
            target_type="reply",
            target_id=row.id,
            text=row.body,
            training_consent=row.training_consent,
            visibility="public",
            status=row.status,
        )
    raise ValueError("target_type must be 'post' or 'reply'")


def _provider_analysis(
    settings: Settings,
    content: str,
    evidence_payload: list[dict[str, str]],
    safety_payload: dict,
    lexical_payload: dict | None = None,
    context_payload: dict | None = None,
) -> AnalysisResult:
    if settings.archangel_analyzer == "anthropic":
        return analyze_with_anthropic(
            settings=settings,
            content=content,
            evidence=evidence_payload,
            safety=safety_payload,
            lexical=lexical_payload,
            context=context_payload,
        )
    if settings.archangel_analyzer == "openai":
        return analyze_with_openai(
            settings=settings,
            content=content,
            evidence=evidence_payload,
            safety=safety_payload,
        )
    if settings.archangel_analyzer == "local_openai_compatible":
        return analyze_with_local_openai_compatible(
            settings=settings,
            content=content,
            evidence=evidence_payload,
            safety=safety_payload,
        )
    raise ProviderError("No external provider selected")



def _enforce_evidence_boundary(
    result: AnalysisResult,
    evidence_rows: list,
) -> AnalysisResult:
    """Lock model-supplied citations to the exact retrieved corpus records.

    A provider may reason over the approved excerpts, but it may not introduce a
    new reference, source, or altered quotation. Any accepted quotation is
    reconstructed from the database row rather than trusted from model output.
    """

    approved = {row.reference: row for row in evidence_rows}
    clean_evidence: list[ScriptureEvidence] = []
    rejected = 0
    altered = 0

    for item in result.evidence:
        row = approved.get(item.reference)
        if row is None or item.source_id != row.source_id:
            rejected += 1
            continue
        if item.text.strip() != row.text.strip():
            altered += 1
        clean_evidence.append(
            ScriptureEvidence(
                reference=row.reference,
                text=row.text,
                source_id=row.source_id,
                relevance=item.relevance,
            )
        )

    approved_refs = set(approved)
    for claim in result.claims:
        original = list(claim.evidence_references)
        claim.evidence_references = [ref for ref in original if ref in approved_refs]
        rejected += len(original) - len(claim.evidence_references)

    result.evidence = clean_evidence
    if rejected:
        result.reasoning_flags.append("provider_citations_outside_retrieved_corpus_removed")
    if altered:
        result.reasoning_flags.append("provider_quotation_replaced_with_exact_corpus_text")

    # A result cannot retain a high textual-support label after all approved
    # evidence has been removed. This prevents unsupported provider confidence
    # from entering the training gate.
    if not clean_evidence and result.support_level in {"direct_text", "strong_inference"}:
        result.support_level = "insufficient"
        result.alignment = "unsupported"
        result.confidence = min(result.confidence, 0.45)
        result.limitations.append("No provider citation survived the approved-corpus evidence boundary.")
        for claim in result.claims:
            if claim.support_level in {"direct_text", "strong_inference"}:
                claim.support_level = "insufficient"
                claim.alignment = "unsupported"
                claim.rationale = (
                    "The provider's claimed support was not present in the exact retrieved corpus evidence."
                )

    # Bound lists again after appending platform flags.
    result.reasoning_flags = list(dict.fromkeys(result.reasoning_flags))[:8]
    result.limitations = list(dict.fromkeys(result.limitations))[:8]
    return result

def _queue_training_candidate(
    db: Session,
    *,
    target: TargetContent,
    analysis: Analysis,
    result: AnalysisResult,
    settings: Settings,
) -> None:
    """Apply the non-negotiable training-data gate.

    Rejected content is not copied into the training table. Only content that is
    consented, public, non-sensitive, biblically aligned, and still awaiting a human
    theological review is queued.
    """

    reasons: list[str] = []
    pii = scan_and_redact(target.text)

    if settings.training_data_mode == "off":
        reasons.append("training_disabled")
    if not target.training_consent:
        reasons.append("no_explicit_consent")
    if target.visibility != "public" and not settings.enable_private_content_training:
        reasons.append("private_content_excluded")
    if target.status != "published":
        reasons.append("content_not_published")
    if result.safety.level != "none":
        reasons.append("safety_sensitive_content")
    if pii.contains_pii:
        reasons.append("personally_identifying_information")
    if result.alignment != "aligned":
        reasons.append("not_biblically_aligned")
    if result.confidence < 0.65:
        reasons.append("analysis_confidence_below_threshold")

    if reasons:
        db.add(
            AuditEvent(
                event_type="training_candidate_rejected",
                target_type=target.target_type,
                target_id=target.target_id,
                details_json=json.dumps({"reasons": reasons}, sort_keys=True),
            )
        )
        return

    existing = db.scalar(select(TrainingCandidate).where(TrainingCandidate.analysis_id == analysis.id))
    if existing:
        return

    db.add(
        TrainingCandidate(
            analysis_id=analysis.id,
            target_type=target.target_type,
            target_id=target.target_id,
            content_hash=analysis.content_hash,
            redacted_text=pii.redacted_text,
            review_state="pending_theological_review",
        )
    )
    db.add(
        AuditEvent(
            event_type="training_candidate_queued",
            target_type=target.target_type,
            target_id=target.target_id,
            details_json=json.dumps(
                {
                    "policy": settings.training_policy_version,
                    "state": "pending_theological_review",
                },
                sort_keys=True,
            ),
        )
    )


def _queue_policy_review(db: Session, target: TargetContent, result: AnalysisResult) -> None:
    """When the analyzer flags a possible content-policy violation, open a
    content-first report for human review. Analysis never removes content."""

    if "content_policy_review_needed" not in result.reasoning_flags:
        return
    existing = db.scalar(
        select(ContentReport).where(
            ContentReport.target_type == target.target_type,
            ContentReport.target_id == target.target_id,
            ContentReport.source == "archangel",
            ContentReport.status == "open",
        )
    )
    if existing:
        return
    db.add(
        ContentReport(
            target_type=target.target_type,
            target_id=target.target_id,
            category="policy_review",
            details="Flagged by Archangel analysis for human content-policy review.",
            source="archangel",
        )
    )
    db.add(
        AuditEvent(
            event_type="content_policy_flagged",
            target_type=target.target_type,
            target_id=target.target_id,
            details_json=json.dumps({"source": "archangel"}),
        )
    )


def analyze_target(
    db: Session,
    settings: Settings,
    target_type: str,
    target_id: str,
    *,
    force: bool = False,
) -> Analysis:
    """Analyze one post or reply.

    Results are cached by (content, engine version, corpus version), so
    unchanged content is not re-analyzed. ``force`` bypasses that cache — it
    is what the rerun endpoint needs, since re-running an unchanged post is
    exactly how you test a prompt or model change.
    """
    target = load_target(db, target_type, target_id)
    digest = _content_hash(target.text)

    latest = None if force else db.scalar(
        select(Analysis)
        .where(
            Analysis.target_type == target_type,
            Analysis.target_id == target_id,
            Analysis.content_hash == digest,
            Analysis.engine_version == settings.archangel_engine_version,
            Analysis.corpus_version == settings.corpus_version,
        )
        .order_by(Analysis.created_at.desc())
    )
    if latest:
        return latest

    safety = classify_safety(
        target.text,
        emergency_number=settings.emergency_number,
        crisis_number=settings.crisis_number,
        poison_control_number=settings.poison_control_number,
    )
    evidence_rows = retrieve_evidence(db, target.text)
    evidence_payload = [
        {
            "reference": row.reference,
            "text": row.text,
            "source_id": row.source_id,
            "license": row.license,
        }
        for row in evidence_rows
    ]
    safety_payload = {
        "level": safety.level,
        "category": safety.category,
        "display_message": safety.display_message,
        "resources": list(safety.resources),
    }

    result: AnalysisResult
    provider_error: str | None = None
    consensus: ConsensusRecord | None = None
    if settings.archangel_analyzer == "heuristic":
        result = analyze_heuristically(target.text, evidence_rows, safety)
    else:
        try:
            lexical_payload = lexical_context(target.text, [row.text for row in evidence_rows])
            context_payload = retrieval_context(db, evidence_rows)

            def one_pass() -> AnalysisResult:
                passed = _provider_analysis(
                    settings,
                    target.text,
                    evidence_payload,
                    safety_payload,
                    lexical_payload,
                    context_payload,
                )
                return _enforce_evidence_boundary(passed, evidence_rows)

            result = one_pass()
            # Additional passes exist only to test whether the first pass's
            # verdicts reproduce. A failed extra pass must never lose the
            # analysis we already have, so it degrades to fewer passes.
            others: list[AnalysisResult] = []
            for _ in range(max(0, settings.consensus_passes - 1)):
                try:
                    others.append(one_pass())
                except Exception as exc:
                    db.add(
                        AuditEvent(
                            event_type="consensus_pass_failed",
                            target_type=target_type,
                            target_id=target_id,
                            details_json=json.dumps({"error": f"{type(exc).__name__}: {str(exc)[:200]}"}),
                        )
                    )
                    break
            consensus = apply_consensus(result, others)
        except Exception as exc:  # provider failure must not block the safety boundary
            provider_error = f"{type(exc).__name__}: {str(exc)[:400]}"
            result = analyze_heuristically(target.text, evidence_rows, safety)
            result.limitations.append("External analyzer failed; deterministic fallback was used.")

    # Safety assessment is platform-owned; a model cannot downgrade it.
    result.safety.level = safety.level
    result.safety.category = safety.category
    result.safety.display_message = safety.display_message
    result.safety.resources = list(safety.resources)

    if provider_error:
        db.add(
            AuditEvent(
                event_type="analysis_provider_fallback",
                target_type=target_type,
                target_id=target_id,
                details_json=json.dumps({"error": provider_error}),
            )
        )

    # Deterministic verification: Loom grounds every claim against the
    # canonical corpus and downgrades textual support that does not derive.
    # Runs identically for every analyzer mode; no model can skip it.
    loom_verification = verify_with_loom(db, result)

    analysis = Analysis(
        target_type=target_type,
        target_id=target_id,
        status="completed",
        alignment=result.alignment,
        support_level=result.support_level,
        confidence=round(result.confidence * 100),
        analyzer_mode=result.analyzer_mode,
        engine_version=settings.archangel_engine_version,
        corpus_version=settings.corpus_version,
        result_json=json.dumps(
            {
                **json.loads(result.model_dump_json()),
                "loom_verification": loom_verification,
                "consensus": consensus.to_dict() if consensus else None,
                "provenance": build_provenance(settings, result),
            }
        ),
        content_hash=digest,
    )
    db.add(analysis)
    db.flush()

    _queue_training_candidate(
        db,
        target=target,
        analysis=analysis,
        result=result,
        settings=settings,
    )
    _queue_policy_review(db, target, result)
    return analysis


def analysis_to_dict(row: Analysis | None) -> dict | None:
    if not row:
        return None
    payload = json.loads(row.result_json)
    payload.update(
        {
            "id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "status": row.status,
            "engine_version": row.engine_version,
            "corpus_version": row.corpus_version,
            "created_at": row.created_at.isoformat(),
        }
    )
    return payload
