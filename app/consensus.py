"""Run the analysis more than once and disclose where it disagreed with itself.

Measured on `evals/consistency_probe.txt`, roughly two thirds of passages
received a different support level between identical runs (see
`docs/RELIABILITY.md`). Several classification axes encode real interpretive
judgment calls — whether a claim "keeps the conditions" of *"if it be
possible, live peaceably with all"* is a question a careful reader could
answer either way — so asking for a stable answer does not make the question
stable. Two attempts to fix it by prompting made it worse.

This module takes the honest route instead of the confident one:

- The analysis runs more than once.
- Where the runs agree on a passage, the verdict is **settled**.
- Where they disagree, the **weaker** verdict is presented and the passage is
  marked **contested**. Never the stronger: a support level the system cannot
  reproduce is not a support level it has earned.

An unstable verdict is a fact about the evidence, and hiding it would be the
one dishonest move available here. The reader is told that the analyzer
disagreed with itself, which is strictly more information than a confident
single run gives them.

Cost note: N passes cost N times as much. The intended production shape is the
Batch API (50% off, and this work is already asynchronous) with classification
on a smaller model, which makes multiple passes cheaper than one Opus pass is
today.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.contract import AnalysisResult
from app.hermeneutic import PairingProfile, SUPPORT_ORDER, evaluate_pairing


def verse_verdicts(result: AnalysisResult) -> dict[str, str]:
    """The support level each cited passage yields, per the published rules.

    Pure and read-only: the rules are deterministic given a profile, so this
    needs no database and mutates nothing. It is the comparable fingerprint of
    one analysis pass.
    """
    verdicts: dict[str, str] = {}
    for claim in result.claims:
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
            level = evaluate_pairing(profile).support_level
            # A passage cited by several claims takes the weakest reading it
            # received within this pass, for the same reason contested
            # passages take the weaker across passes.
            existing = verdicts.get(classification.reference)
            verdicts[classification.reference] = (
                _weaker(existing, level) if existing else level
            )
    return verdicts


def _weaker(first: str, second: str) -> str:
    rank = {level: index for index, level in enumerate(SUPPORT_ORDER)}
    return first if rank.get(first, 0) <= rank.get(second, 0) else second


@dataclass(frozen=True)
class ConsensusRecord:
    passes: int
    settled: list[str]
    contested: dict[str, dict]
    claims_downgraded: int

    @property
    def contested_rate(self) -> float:
        total = len(self.settled) + len(self.contested)
        return len(self.contested) / total if total else 0.0

    def to_dict(self) -> dict:
        return {
            "passes": self.passes,
            "settled": sorted(self.settled),
            "contested": self.contested,
            "claims_downgraded": self.claims_downgraded,
            "contested_rate": round(self.contested_rate, 3),
        }


def apply_consensus(primary: AnalysisResult, others: list[AnalysisResult]) -> ConsensusRecord:
    """Compare passes, downgrade contested claims in ``primary``, and report.

    ``primary`` is the pass whose prose the reader will see; the others are
    consulted only to test whether its verdicts reproduce. Claims resting on a
    contested passage are lowered to the weakest level any pass gave that
    passage, and their rationale says so.
    """
    if not others:
        return ConsensusRecord(passes=1, settled=[], contested={}, claims_downgraded=0)

    per_pass = [verse_verdicts(primary)] + [verse_verdicts(other) for other in others]
    all_references = {reference for verdicts in per_pass for reference in verdicts}

    settled: list[str] = []
    contested: dict[str, dict] = {}
    for reference in sorted(all_references):
        seen = [verdicts.get(reference) for verdicts in per_pass]
        present = [level for level in seen if level]
        if len(set(present)) == 1 and len(present) == len(per_pass):
            settled.append(reference)
            continue
        weakest = present[0]
        for level in present[1:]:
            weakest = _weaker(weakest, level)
        # Two different failures both count as contested, and conflating them
        # in the display reads as nonsense ("contested — one reading seen").
        # `levels_disagree`: the passes read the same passage differently.
        # `coverage_differs`: a pass did not consider the passage at all, which
        # is a disagreement about what bears on the claim rather than about
        # what the passage says.
        reason = "levels_disagree" if len(set(present)) > 1 else "coverage_differs"
        contested[reference] = {
            "reason": reason,
            "levels_seen": sorted(set(present)),
            "presented": weakest,
            "seen_in_passes": f"{len(present)}/{len(per_pass)}",
        }

    downgraded = 0
    for claim in primary.claims:
        references = [c.reference for c in claim.pairings]
        touched = [r for r in references if r in contested]
        if not touched:
            continue
        target = claim.support_level
        for reference in touched:
            target = _weaker(target, contested[reference]["presented"])
        if target != claim.support_level:
            claim.support_level = target
            if target == "insufficient":
                claim.alignment = "unsupported"
            claim.rationale = (
                f"{claim.rationale} [The analyzer did not reach the same reading of "
                f"{', '.join(sorted(touched))} on a second pass, so the weaker reading "
                "is shown here and this point should be treated as contested rather "
                "than settled.]"
            ).strip()
            downgraded += 1

    if contested:
        flag = "verdict_contested_across_passes"
        if flag not in primary.reasoning_flags:
            primary.reasoning_flags.append(flag)
            primary.reasoning_flags = primary.reasoning_flags[:8]

    return ConsensusRecord(
        passes=len(per_pass),
        settled=settled,
        contested=contested,
        claims_downgraded=downgraded,
    )
