"""Loom ⨯ Archangel — deterministic verification of analysis claims.

Division of labor:

- **Claude proposes.** The analyzer (hosted model or heuristic) extracts
  claims and asserts which corpus verses each claim rests on.
- **Loom disposes.** For every analysis we build a Loom dependency graph:

      claim --supported_by--> verse          (asserted: the analyzer's citation)
      verse --attested_in--> kjv_corpus      (asserted iff the verse exists in
                                              the canonical corpus table)

  with the composition rule `supported_by + attested_in = grounded_in`.
  Loom's entailment closure then *derives* `claim --grounded_in--> kjv_corpus`
  exactly for claims with at least one attested citation. Because derived
  facts are a materialized view under truth maintenance, a grounding survives
  while any citation holds and falls when the last one is withdrawn — the
  property tested in Loom's own gate.

- **The verdict is enforced.** A claim carrying textual support
  (`direct_text` / `strong_inference`) whose grounding does NOT derive is
  downgraded to `insufficient`/`unsupported` — deterministically, whatever
  the model said. Each grounded claim carries Loom's provenance trace so the
  derivation is inspectable, not asserted.

Everything here is pure deterministic computation: no model call, no
randomness, bit-identical output for identical input.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.contract import AnalysisResult
from app.models import BibleVerse
from app.vendor.loom_engine import Loom

LOOM_ENGINE_VERSION = "loom-2.2"
CORPUS_NODE = "kjv_corpus"
_TEXTUAL_SUPPORT = {"direct_text", "strong_inference"}


def _claim_node(index: int) -> str:
    return f"claim_{index}"


def build_grounding_graph(claims: list[dict], attested_refs: set[str]) -> Loom:
    """Construct the dependency graph for one analysis.

    ``claims`` is a list of {"index": int, "cited": [reference, ...]}.
    ``attested_refs`` is the subset of all cited references that exist in the
    canonical corpus. Returns the woven Loom instance; callers query
    ``_thread_exists(claim_node, "grounded_in", CORPUS_NODE)`` and ``trace``.
    """
    loom = Loom()
    loom.add_node(CORPUS_NODE, "corpus")

    all_refs: set[str] = set()
    for claim in claims:
        loom.add_node(_claim_node(claim["index"]), "claim")
        all_refs.update(claim["cited"])
    for ref in sorted(all_refs):
        loom.add_node(ref, "verse")

    # Attestation premises first, then citations; the closure is order-
    # independent but this keeps thread ids stable for identical input.
    for ref in sorted(all_refs):
        if ref in attested_refs:
            loom.add_thread(ref, "attested_in", CORPUS_NODE)
    for claim in claims:
        for ref in claim["cited"]:
            loom.add_thread(_claim_node(claim["index"]), "supported_by", ref)

    loom.weave(strategy={("supported_by", "attested_in"): "grounded_in"})
    return loom


def _grounding_trace(loom: Loom, claim_index: int) -> str | None:
    node = _claim_node(claim_index)
    for tid in sorted(loom.threads):
        t = loom.threads[tid]
        if (
            t.get("status") == "entailed"
            and t["head"] == node
            and t["rel"] == "grounded_in"
            and t["tail"] == CORPUS_NODE
        ):
            return loom.trace(tid)
    return None


def verify_with_loom(db: Session, result: AnalysisResult) -> dict:
    """Verify claim grounding and enforce downgrades. Mutates ``result``
    (support levels, rationale, reasoning flags) and returns the verification
    record to persist alongside the analysis."""

    claims = [
        {"index": i, "cited": list(dict.fromkeys(claim.evidence_references))}
        for i, claim in enumerate(result.claims)
    ]
    all_refs = sorted({ref for claim in claims for ref in claim["cited"]})
    attested: set[str] = set()
    if all_refs:
        attested = set(
            db.scalars(
                select(BibleVerse.reference).where(BibleVerse.reference.in_(all_refs))
            ).all()
        )

    loom = build_grounding_graph(claims, attested)

    records = []
    downgrades = 0
    for claim_info, claim in zip(claims, result.claims):
        grounded = loom._thread_exists(_claim_node(claim_info["index"]), "grounded_in", CORPUS_NODE)
        downgraded = False
        if not grounded and claim.support_level in _TEXTUAL_SUPPORT:
            claim.support_level = "insufficient"
            claim.alignment = "unsupported"
            claim.rationale = (
                f"{claim.rationale} [Loom: no cited passage for this claim is attested "
                "in the canonical corpus; textual support withdrawn deterministically.]"
            ).strip()
            downgraded = True
            downgrades += 1
        records.append(
            {
                "claim_index": claim_info["index"],
                "cited": claim_info["cited"],
                "attested": sorted(set(claim_info["cited"]) & attested),
                "grounded": grounded,
                "downgraded": downgraded,
                "trace": _grounding_trace(loom, claim_info["index"]) if grounded else None,
            }
        )

    if downgrades and "loom_ungrounded_claim_downgraded" not in result.reasoning_flags:
        result.reasoning_flags.append("loom_ungrounded_claim_downgraded")
        result.reasoning_flags = result.reasoning_flags[:8]

    return {
        "engine": LOOM_ENGINE_VERSION,
        "corpus_node": CORPUS_NODE,
        "claims": records,
        "summary": {
            "total_claims": len(records),
            "grounded": sum(1 for r in records if r["grounded"]),
            "downgraded": downgrades,
        },
    }
