"""How findings are worded and ordered for the person reading them.

The analysis engine's internal vocabulary is precise and cold: a claim is
`unsupported`, its support `insufficient`. Printed beneath someone's account
of their own childhood, those words read as *you are wrong* rather than
*this verse does not say that* — a verdict on the person instead of a
statement about the text.

Nothing here changes a finding. It changes the words the finding is delivered
in, and the order the findings arrive in. That distinction is the whole point:
the platform's job is to tell the truth about a passage without making a
reader feel judged as a person.

Two rules govern this module:

1. **Never soften the substance.** If a passage does not support a claim, the
   wording must still say so plainly. "Goes beyond what this passage says" is
   gentler than "unsupported"; "this is broadly fine" would be a lie.
2. **Lead with what holds.** People read the top. Confirmed points first,
   questions after, so a reader meets agreement before correction and is still
   willing to hear the correction when it comes.
"""

from __future__ import annotations

# Internal support levels, worded for a reader rather than an engine.
SUPPORT_LABELS = {
    "direct_text": "the passage says this",
    "strong_inference": "follows closely from the passage",
    "wisdom_application": "a wise application, not a command",
    "disputed_interpretation": "Christians read this differently",
    "insufficient": "not stated in this passage",
}

ALIGNMENT_LABELS = {
    "aligned": "consistent with the passages cited",
    "mixed": "partly holds",
    "unsupported": "goes beyond the passages cited",
    "contradicted": "conflicts with the passages cited",
    "uncertain": "unclear from the passages cited",
}

# Claims a reader should meet first: what their citations genuinely carry.
_CONFIRMING = {"direct_text", "strong_inference"}

# Strongest first, so agreement precedes correction.
_DISPLAY_ORDER = (
    "direct_text",
    "strong_inference",
    "wisdom_application",
    "disputed_interpretation",
    "insufficient",
)

# How many questions to surface before the rest are folded away. Eight
# critiques at once reads as a firing squad regardless of how fair each one is.
QUESTIONS_SHOWN = 3


def support_label(level: str) -> str:
    return SUPPORT_LABELS.get(level, level.replace("_", " "))


def alignment_label(alignment: str) -> str:
    return ALIGNMENT_LABELS.get(alignment, alignment.replace("_", " "))


def confirms(claim: dict) -> bool:
    return claim.get("support_level") in _CONFIRMING


def order_claims(claims: list[dict]) -> list[dict]:
    """Strongest support first — lead with what holds."""
    rank = {level: index for index, level in enumerate(_DISPLAY_ORDER)}
    return sorted(claims, key=lambda c: rank.get(c.get("support_level"), len(rank)))


def split_claims(claims: list[dict]) -> dict:
    """Confirmed points, then the questions — with the tail folded away.

    Returns `held`, `questioned` (the first few), and `questioned_extra` (the
    remainder, shown behind a disclosure rather than hidden: nothing is
    suppressed, it is only sequenced).
    """
    ordered = order_claims(claims)
    held = [c for c in ordered if confirms(c)]
    questioned = [c for c in ordered if not confirms(c)]
    return {
        "held": held,
        "questioned": questioned[:QUESTIONS_SHOWN],
        "questioned_extra": questioned[QUESTIONS_SHOWN:],
    }
