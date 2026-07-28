"""The published hermeneutic — how a passage does or does not support a claim.

This module is the theological commitment of the platform, made explicit.
Everywhere else, Gateway refuses to hide an interpretive choice; this is the
biggest one, so it is written as data, versioned, published on the Method
page, and open to dispute.

WHY THIS EXISTS

Loom stage 1 verified *provenance*: that a cited passage is real and attested
in the canon. It could not check the load-bearing relationship — whether the
passage actually supports the claim. Acts 2:17 genuinely mentions dreams; that
says nothing about whether a relative's dream obliges you to buy a house.

Stage 2 closes that gap by splitting the work:

- **The model classifies.** For each (claim, passage) pairing it fills in a
  narrow, checkable profile: what the passage *does* (command, promise,
  narrative, wisdom saying...), whom it addresses, which covenant it sits in,
  what the claim asserts (obligation, prediction, permission...), whether the
  claim keeps the conditions the passage attaches, and whether the passage is
  even on the claim's subject.
- **The rules below decide.** The support level is then *derived* from that
  profile by a named rule, deterministically. No model output can grant
  textual support that the rules do not yield.

This does not make the system free of model judgment; it relocates it. The
honest claim is: the interpretive step is now narrow, typed, visible, and
governed by rules you can read and argue with — not an opaque verdict.

WHAT THE RULES ENCODE

They encode mainstream grammatical-historical reading: that narrative
describing an event is not automatically a command; that a promise made to a
specific addressee is not automatically a universal guarantee; that a proverb
is a general wisdom saying rather than a contract; that conditions attached to
a promise travel with it; that a Mosaic-covenant obligation needs New
Testament reaffirmation before binding Christians. Sincere Christians dispute
some of these. That is why disputes are surfaced as `disputed_interpretation`
rather than settled, and why this file carries a version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HERMENEUTIC_RULESET_VERSION = "hermeneutic-rules-v2-2026-07"

# --- the classification axes the model must fill in --------------------------

SpeechAct = Literal[
    "command",              # imperative addressed to hearers
    "prohibition",
    "promise",              # commitment by God to someone
    "narrative",            # report of what happened
    "wisdom_saying",        # proverb: generally true, not a guarantee
    "doctrinal_assertion",  # statement about what is the case
    "prophecy",
    "question",
    "lament",               # a human cry, not divine assertion
    # Speech Scripture RECORDS without endorsing: Satan in the wilderness,
    # Job's friends (whom God rebukes), the fool saying there is no God,
    # false prophets. Being in the Bible is not being taught by it.
    "quoted_unendorsed",
    "hyperbole",            # deliberate overstatement for effect
    "poetic_figure",        # metaphor and imagery, not technical description
]

Audience = Literal[
    "all_believers",
    "humanity",
    "specific_individual",
    "specific_group",
    "national_israel",
]

CovenantScope = Literal["creation", "patriarchal", "mosaic", "new_covenant", "eschatological"]

ClaimModality = Literal[
    "obligation",          # "you must / everyone should"
    "prohibition",
    "guarantee",           # "God will certainly do X for anyone who Y"
    "prediction",
    "permission",
    "description",         # "this is how things are"
    "promise_to_claimant", # "this promise applies to me"
]

SUPPORT_ORDER = ("insufficient", "disputed_interpretation", "wisdom_application", "strong_inference", "direct_text")


@dataclass(frozen=True)
class PairingProfile:
    """The model's classification of one (claim, passage) pairing."""

    speech_act: str
    audience: str
    covenant_scope: str
    claim_modality: str
    addresses_claim_subject: bool
    claim_keeps_conditions: bool
    reaffirmed_in_new_covenant: bool = False
    counterpassage_addressed: bool = True


@dataclass(frozen=True)
class Verdict:
    rule: str
    support_level: str
    explanation: str


# --- the rules ----------------------------------------------------------------
# Evaluated in order; the first matching rule decides. Blocking rules come
# first, so a category error can never be outvoted by a supporting rule.

def _blocking_rules(p: PairingProfile) -> Verdict | None:
    if not p.addresses_claim_subject:
        return Verdict(
            "topic_mismatch",
            "insufficient",
            "The passage does not address the subject of the claim. A verse that mentions a "
            "related word is not thereby about the claim.",
        )

    if p.speech_act == "quoted_unendorsed":
        return Verdict(
            "speaker_not_endorsed",
            "insufficient",
            "Scripture records these words without affirming them — they belong to a speaker "
            "the text does not endorse. A statement being in the Bible is not the Bible "
            "teaching it.",
        )

    if p.speech_act == "hyperbole" and p.claim_modality in {"obligation", "prohibition", "guarantee"}:
        return Verdict(
            "hyperbole_read_literally",
            "wisdom_application",
            "The passage uses deliberate overstatement for effect. Its force is real and the "
            "seriousness it presses is genuine, but the literal action is not the thing "
            "commanded.",
        )

    if p.speech_act == "poetic_figure" and p.claim_modality in {"guarantee", "prediction"}:
        return Verdict(
            "poetic_figure_pressed_literally",
            "insufficient",
            "The passage speaks in metaphor and imagery. Pressing a figure into a guarantee or "
            "a prediction of mechanism asks of poetry what it does not offer.",
        )

    if p.speech_act in {"narrative", "lament"} and p.claim_modality in {"obligation", "prohibition", "guarantee"}:
        return Verdict(
            "descriptive_not_prescriptive",
            "insufficient",
            "The passage reports what happened or what someone cried out; the claim turns that "
            "into a rule or guarantee. Scripture describing an event is not thereby commanding it.",
        )

    if p.speech_act == "wisdom_saying" and p.claim_modality == "guarantee":
        return Verdict(
            "proverb_read_as_guarantee",
            "insufficient",
            "A wisdom saying states what is generally so, not what is always so. Reading it as a "
            "guarantee promises what the genre does not.",
        )

    if not p.claim_keeps_conditions:
        return Verdict(
            "condition_dropped",
            "insufficient",
            "The passage attaches conditions the claim drops. A conditional promise cannot be "
            "cited as an unconditional one.",
        )

    if p.audience in {"specific_individual", "national_israel"} and p.claim_modality in {"guarantee", "promise_to_claimant"}:
        return Verdict(
            "addressee_generalized",
            "insufficient",
            "The passage speaks to a particular person or to Israel as a nation; the claim converts "
            "that into a guarantee for the individual reader. The addressee is part of the meaning.",
        )

    if p.covenant_scope == "mosaic" and p.claim_modality in {"obligation", "prohibition"} and not p.reaffirmed_in_new_covenant:
        return Verdict(
            "covenant_scope_unreaffirmed",
            "disputed_interpretation",
            "The obligation belongs to the Mosaic covenant and the claim binds it on Christians "
            "without New Testament reaffirmation. Christians have long disagreed about which such "
            "obligations carry over.",
        )

    return None


def _supporting_rules(p: PairingProfile) -> Verdict:
    if p.speech_act in {"command", "prohibition"} and p.audience in {"all_believers", "humanity"} \
            and p.claim_modality in {"obligation", "prohibition"}:
        return Verdict(
            "direct_command",
            "direct_text",
            "The passage commands what the claim asserts, addressed to those the claim addresses.",
        )

    if p.speech_act == "doctrinal_assertion" and p.claim_modality == "description":
        return Verdict(
            "direct_assertion",
            "direct_text",
            "The passage asserts what the claim describes.",
        )

    # Narrative cannot command (blocked above), but it fully supports a claim
    # about what the passage records. "Gideon laid out a fleece" is directly
    # attested by the account; only "therefore you should" is not.
    if p.speech_act == "poetic_figure" and p.claim_modality == "description":
        return Verdict(
            "poetic_figure_teaches",
            "strong_inference",
            "Poetry teaches truly, in its own register. The claim describes what the imagery "
            "conveys rather than pressing it for technical detail.",
        )

    if p.speech_act in {"narrative", "lament", "prophecy", "question"} and p.claim_modality == "description":
        return Verdict(
            "narrative_reports_event",
            "direct_text",
            "The passage records what the claim describes. Note that this supports the description "
            "only — it does not make the reported action normative.",
        )

    if p.speech_act == "promise" and p.audience in {"all_believers", "humanity"} \
            and p.claim_modality in {"promise_to_claimant", "guarantee"}:
        return Verdict(
            "promise_rightly_claimed",
            "strong_inference",
            "The promise is made to those the claimant belongs to, and the claim keeps its conditions.",
        )

    if p.speech_act == "wisdom_saying":
        return Verdict(
            "wisdom_applied",
            "wisdom_application",
            "A wisdom saying supports a prudent application without commanding it.",
        )

    if p.speech_act in {"command", "prohibition", "doctrinal_assertion", "promise"}:
        return Verdict(
            "principle_extension",
            "strong_inference",
            "The passage bears on the claim, but reaching the claim requires an interpretive step "
            "beyond what the passage states in its own terms.",
        )

    return Verdict(
        "no_rule_matched",
        "insufficient",
        "No rule in the published set yields textual support for this pairing.",
    )


def evaluate_pairing(profile: PairingProfile) -> Verdict:
    """Derive the support level for one (claim, passage) pairing."""
    verdict = _blocking_rules(profile) or _supporting_rules(profile)

    # An unaddressed counterpassage cannot be outranked by a supporting rule:
    # a conclusion drawn from one side of a known tension is, at best, disputed.
    if not profile.counterpassage_addressed and verdict.support_level in {"direct_text", "strong_inference"}:
        return Verdict(
            f"{verdict.rule}+counterpassage_unaddressed",
            "disputed_interpretation",
            f"{verdict.explanation} However, a passage standing in tension with this reading was "
            "supplied and left unaddressed, so the conclusion cannot stand as settled.",
        )
    return verdict


def strongest_support(levels: list[str]) -> str:
    """A claim's support level is its strongest passage — one passage that
    genuinely supports it is enough, and a counterpassage yielding nothing
    does not subtract from a passage that yields something.

    (Named `weakest` until v2, which returned the strongest and caused exactly
    the confusion the name invites.)
    """
    ranked = [level for level in SUPPORT_ORDER if level in set(levels)]
    return ranked[-1] if ranked else "insufficient"


def published_rules() -> list[dict]:
    """The rule set as displayable data, for the Method page."""
    return [
        {"rule": "topic_mismatch", "kind": "blocking", "yields": "insufficient",
         "when": "The passage does not address the claim's subject."},
        {"rule": "speaker_not_endorsed", "kind": "blocking", "yields": "insufficient",
         "when": "Scripture records the words without affirming them — Job's friends, the fool, "
                 "Satan, a false prophet. Being in the Bible is not being taught by it."},
        {"rule": "hyperbole_read_literally", "kind": "blocking", "yields": "wisdom_application",
         "when": "Deliberate overstatement is read as a literal requirement. The force is real; "
                 "the literal action is not the command."},
        {"rule": "poetic_figure_pressed_literally", "kind": "blocking", "yields": "insufficient",
         "when": "A metaphor is pressed into a guarantee or a prediction of mechanism."},
        {"rule": "descriptive_not_prescriptive", "kind": "blocking", "yields": "insufficient",
         "when": "Narrative or lament is read as command or guarantee."},
        {"rule": "proverb_read_as_guarantee", "kind": "blocking", "yields": "insufficient",
         "when": "A wisdom saying is read as an always-true guarantee."},
        {"rule": "condition_dropped", "kind": "blocking", "yields": "insufficient",
         "when": "The claim omits conditions the passage attaches."},
        {"rule": "addressee_generalized", "kind": "blocking", "yields": "insufficient",
         "when": "A promise to an individual or to national Israel is claimed as a personal guarantee."},
        {"rule": "covenant_scope_unreaffirmed", "kind": "blocking", "yields": "disputed_interpretation",
         "when": "A Mosaic obligation is bound on Christians without New Testament reaffirmation."},
        {"rule": "direct_command", "kind": "supporting", "yields": "direct_text",
         "when": "The passage commands what the claim asserts, to the same audience."},
        {"rule": "direct_assertion", "kind": "supporting", "yields": "direct_text",
         "when": "The passage asserts what the claim describes."},
        {"rule": "narrative_reports_event", "kind": "supporting", "yields": "direct_text",
         "when": "A claim simply describes what a narrative records (not that it is normative)."},
        {"rule": "poetic_figure_teaches", "kind": "supporting", "yields": "strong_inference",
         "when": "A claim describes what poetic imagery conveys, without pressing it for detail."},
        {"rule": "promise_rightly_claimed", "kind": "supporting", "yields": "strong_inference",
         "when": "A promise to all believers is claimed with its conditions intact."},
        {"rule": "wisdom_applied", "kind": "supporting", "yields": "wisdom_application",
         "when": "A wisdom saying supports a prudent application."},
        {"rule": "principle_extension", "kind": "supporting", "yields": "strong_inference",
         "when": "The passage bears on the claim but an interpretive step is required."},
        {"rule": "counterpassage_unaddressed", "kind": "capping", "yields": "disputed_interpretation",
         "when": "A supplied passage in tension with the reading was not addressed."},
    ]
