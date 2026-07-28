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
from app.hermeneutic import (
    HERMENEUTIC_RULESET_VERSION,
    PairingProfile,
    evaluate_pairing,
    strongest_support,
)
from app.models import BibleVerse
from app.vendor.loom_engine import Loom

LOOM_ENGINE_VERSION = "loom-2.2"
CORPUS_NODE = "kjv_corpus"
_TEXTUAL_SUPPORT = {"direct_text", "strong_inference"}


def build_entailment_graph(pairings: list[dict]) -> Loom:
    """Stage 2: derive support levels rather than accept them.

    Each pairing is (claim index, reference, attested?, fired rule, level).
    The graph encodes the derivation chain:

        claim --rests_on--> pairing --evaluated_by--> rule --yields--> level

    with the composition rules ``rests_on + evaluated_by = invokes`` and
    ``invokes + yields = derives_support``. Loom's closure then derives
    ``claim --derives_support--> support_<level>`` — and because derived facts
    are a materialized view under truth maintenance, withdrawing a
    classification or a rule withdraws the support that rested on it.

    Only attested pairings are evaluated: a passage that is not in the canon
    never reaches the rule table at all.
    """
    loom = Loom()
    added: set[str] = set()

    def node(name: str, kind: str) -> str:
        if name not in added:
            loom.add_node(name, kind)
            added.add(name)
        return name

    for pairing in pairings:
        if not pairing["attested"]:
            continue
        claim_node = node(_claim_node(pairing["claim_index"]), "claim")
        pair_node = node(f"pairing_{pairing['claim_index']}_{pairing['reference']}", "pairing")
        rule_node = node(f"rule_{pairing['rule']}", "rule")
        level_node = node(f"support_{pairing['support_level']}", "support_level")

        if not loom._thread_exists(claim_node, "rests_on", pair_node):
            loom.add_thread(claim_node, "rests_on", pair_node)
        if not loom._thread_exists(pair_node, "evaluated_by", rule_node):
            loom.add_thread(pair_node, "evaluated_by", rule_node)
        if not loom._thread_exists(rule_node, "yields", level_node):
            loom.add_thread(rule_node, "yields", level_node)

    loom.weave(
        strategy={
            ("rests_on", "evaluated_by"): "invokes",
            ("invokes", "yields"): "derives_support",
        }
    )
    return loom


def derived_support_levels(loom: Loom, claim_index: int) -> list[str]:
    """Support levels Loom actually derived for a claim (not asserted)."""
    node = _claim_node(claim_index)
    levels = []
    for tid in sorted(loom.threads):
        thread = loom.threads[tid]
        if (
            thread.get("status") == "entailed"
            and thread["head"] == node
            and thread["rel"] == "derives_support"
        ):
            levels.append(thread["tail"].removeprefix("support_"))
    return levels


def derivation_trace(loom: Loom, claim_index: int) -> str | None:
    node = _claim_node(claim_index)
    for tid in sorted(loom.threads):
        thread = loom.threads[tid]
        if (
            thread.get("status") == "entailed"
            and thread["head"] == node
            and thread["rel"] == "derives_support"
        ):
            return loom.trace(tid)
    return None


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


def _attested_references(db: Session | None, references: set[str], known: set[str]) -> set[str]:
    """Which of these references exist in the canonical corpus.

    Pairings legitimately cite passages beyond a claim's evidence_references —
    counterpassages especially. Attestation must therefore be checked against
    the corpus itself, not against the narrower evidence set, or real verses
    are silently treated as forged and their support never derives.
    """
    unchecked = sorted(references - known)
    if not unchecked or db is None:
        return known & references
    found = set(
        db.scalars(select(BibleVerse.reference).where(BibleVerse.reference.in_(unchecked))).all()
    )
    return (known & references) | found


def derive_entailment(db: Session, result: AnalysisResult, attested: set[str]) -> dict | None:
    """Stage 2: derive each claim's support level from the published rules.

    Returns None when the analyzer supplied no pairing classifications (the
    deterministic analyzer does not), leaving stage-1 provenance verification
    as the only check. When classifications *are* present, the derived level
    governs: a support level the rules do not yield is overwritten, whatever
    the model asserted.
    """
    pairing_refs = {c.reference for claim in result.claims for c in claim.pairings}
    if not pairing_refs:
        return None
    corpus_attested = _attested_references(db, pairing_refs, attested)

    pairings: list[dict] = []
    for index, claim in enumerate(result.claims):
        for classification in claim.pairings:
            profile = PairingProfile(
                speech_act=classification.speech_act,
                audience=classification.audience,
                covenant_scope=classification.covenant_scope,
                claim_modality=classification.claim_modality,
                addresses_claim_subject=classification.addresses_claim_subject,
                claim_keeps_conditions=classification.claim_keeps_conditions,
                reaffirmed_in_new_covenant=classification.reaffirmed_in_new_covenant,
                counterpassage_addressed=classification.counterpassage_addressed,
            )
            verdict = evaluate_pairing(profile)
            pairings.append(
                {
                    "claim_index": index,
                    "reference": classification.reference,
                    "attested": classification.reference in corpus_attested,
                    "rule": verdict.rule,
                    "support_level": verdict.support_level,
                    "explanation": verdict.explanation,
                    "profile": profile.__dict__,
                }
            )

    if not pairings:
        return None

    loom = build_entailment_graph(pairings)
    records = []
    overrides = 0

    for index, claim in enumerate(result.claims):
        claim_pairings = [p for p in pairings if p["claim_index"] == index]
        if not claim_pairings:
            continue
        derived = derived_support_levels(loom, index)
        level = strongest_support(derived) if derived else "insufficient"
        asserted = claim.support_level
        if asserted != level:
            claim.support_level = level
            if level == "insufficient":
                claim.alignment = "unsupported"
            fired = ", ".join(sorted({p["rule"] for p in claim_pairings}))
            claim.rationale = (
                f"{claim.rationale} [Loom: support derived as '{level}' by rule(s) {fired}; "
                f"the analyzer had asserted '{asserted}'.]"
            ).strip()
            overrides += 1
        records.append(
            {
                "claim_index": index,
                "asserted_support": asserted,
                "derived_support": level,
                "overridden": asserted != level,
                "rules_fired": [
                    {"reference": p["reference"], "rule": p["rule"], "yields": p["support_level"],
                     "explanation": p["explanation"], "attested": p["attested"]}
                    for p in claim_pairings
                ],
                "trace": derivation_trace(loom, index),
            }
        )

    if overrides:
        flag = "loom_support_level_derived_not_asserted"
        if flag not in result.reasoning_flags:
            result.reasoning_flags.append(flag)
            result.reasoning_flags = result.reasoning_flags[:8]

    return {
        "ruleset_version": HERMENEUTIC_RULESET_VERSION,
        "claims": records,
        "summary": {
            "claims_derived": len(records),
            "overridden": overrides,
        },
    }


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

    # Stage 2 runs after provenance: a passage must be attested before the
    # hermeneutic rules are allowed to say anything about it.
    entailment = derive_entailment(db, result, attested)

    return {
        "engine": LOOM_ENGINE_VERSION,
        "corpus_node": CORPUS_NODE,
        "claims": records,
        "summary": {
            "total_claims": len(records),
            "grounded": sum(1 for r in records if r["grounded"]),
            "downgraded": downgrades,
        },
        "entailment": entailment,
    }
