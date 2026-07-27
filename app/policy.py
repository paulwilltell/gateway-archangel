"""Platform content policy — the only grounds for removal.

Gateway is a free place to post: no viewpoint, theological, or quality
moderation, ever. Content is refused or removed only for the categories
below, which mirror docs/CONTENT_POLICY.md:

- sexual_content: explicit sexual material or solicitation
- abusive_content: harassment or abuse directed at a person
- spam: commercial flooding that drowns out human conversation
- threat: credible threats of violence against a person
- doxxing: publishing someone's private identifying information, or trying to
  unmask an anonymous member — an attack on the platform's core promise
- self_harm_encouragement: urging someone toward suicide or self-injury
- exploitation: grooming or sexual approach to a minor
- fraud: financial solicitation, scams, impersonation of another person
- illegal: content the operator is legally required to remove

Every one of these is a category of *conduct*, not of belief. No theological
position, however heterodox, unpopular, or badly argued, is ever grounds for
removal. The line is: moderate harmful conduct, never doctrinal conclusions.

The deterministic screen here is intentionally narrow: it blocks only
unambiguous cases at submission time. Testimony about abuse, confession of
sin, and pastoral discussion of sexuality are common and legitimate in a
Christian community and MUST pass this screen — nuanced cases go to the
human review queue (flagged by Archangel or reported by readers), never to
an automated block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

POLICY_CATEGORIES = (
    "sexual_content",
    "abusive_content",
    "spam",
    "threat",
    "doxxing",
    "self_harm_encouragement",
    "exploitation",
    "fraud",
    "illegal",
)

_HARASSMENT = re.compile(
    r"\bkill\s+your\s*self\b|\bkys\b|\byou\s+(?:should|deserve\s+to)\s+die\b|\bgo\s+die\b",
    re.IGNORECASE,
)
# Unambiguous slurs only. Quoting one in testimony is possible but rare; the
# rejection message invites rephrasing rather than silently discarding.
_SLURS = re.compile(
    r"\b(?:nigger|nigga|faggot|kike|spic|wetback|chink|tranny)\b",
    re.IGNORECASE,
)
_SEXUAL_SOLICITATION = re.compile(
    r"(?:pornhub|xvideos|xnxx|xhamster|onlyfans)\.com"
    r"|\b(?:buy|sell(?:ing)?)\s+(?:my\s+)?nudes\b"
    r"|\bescort\s+services?\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://", re.IGNORECASE)
# Urging another person toward self-injury. Distinct from someone disclosing
# their own suicidal thoughts, which is a crisis to support (see app/safety.py),
# never a violation — hence the second-person framing required here.
_SELF_HARM_ENCOURAGEMENT = re.compile(
    r"\byou\s+(?:should|ought\s+to|need\s+to|deserve\s+to)\s+(?:kill\s+yourself|end\s+your\s+life|die)\b"
    r"|\bgo\s+(?:ahead\s+and\s+)?(?:kill\s+yourself|end\s+it)\b"
    r"|\bthe\s+world\s+(?:would\s+be|is)\s+better\s+(?:off\s+)?without\s+you\b",
    re.IGNORECASE,
)
# Deanonymization: trying to unmask a pen name is an attack on the platform's
# central promise, so it is a removal category in its own right.
_DEANONYMIZE = re.compile(
    r"\b(?:his|her|their|your)\s+real\s+name\s+is\b"
    r"|\bI\s+(?:know|found\s+out)\s+who\s+(?:you|he|she|they)\s+(?:really\s+)?(?:are|is)\b"
    r"|\b(?:posting|here\s+is|this\s+is)\s+(?:his|her|their)\s+(?:home\s+)?address\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PolicyVerdict:
    allowed: bool
    category: str | None = None
    message: str | None = None


def _is_spam(text: str) -> bool:
    if len(_URL.findall(text)) > 4:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 6:
        counts: dict[str, int] = {}
        for line in lines:
            counts[line] = counts.get(line, 0) + 1
        if max(counts.values()) >= 5:
            return True
    return False


def screen_content(text: str) -> PolicyVerdict:
    if _SELF_HARM_ENCOURAGEMENT.search(text):
        return PolicyVerdict(
            allowed=False,
            category="self_harm_encouragement",
            message=(
                "This content was refused under Gateway's content policy: urging another "
                "person toward self-harm. If you are the one struggling, that is welcome "
                "here and is not a violation — say so plainly and you will be met with "
                "Scripture and crisis resources, not a block."
            ),
        )
    if _DEANONYMIZE.search(text):
        return PolicyVerdict(
            allowed=False,
            category="doxxing",
            message=(
                "This content was refused under Gateway's content policy: publishing "
                "private identifying information or attempting to unmask an anonymous "
                "member. People post here under pen names precisely so this is not "
                "possible; protecting that is not viewpoint moderation."
            ),
        )
    if _HARASSMENT.search(text) or _SLURS.search(text):
        return PolicyVerdict(
            allowed=False,
            category="abusive_content",
            message=(
                "This content was refused under Gateway's content policy: abusive content "
                "directed at a person. Gateway never moderates viewpoints or theology — "
                "see the Method page. If you are quoting abuse you experienced, please "
                "rephrase the quoted words."
            ),
        )
    if _SEXUAL_SOLICITATION.search(text):
        return PolicyVerdict(
            allowed=False,
            category="sexual_content",
            message=(
                "This content was refused under Gateway's content policy: explicit sexual "
                "material or solicitation. Honest discussion of sexuality, temptation, and "
                "recovery is welcome."
            ),
        )
    if _is_spam(text):
        return PolicyVerdict(
            allowed=False,
            category="spam",
            message=(
                "This content was refused under Gateway's content policy: it looks like "
                "automated or commercial spam (many links or heavily repeated lines)."
            ),
        )
    return PolicyVerdict(allowed=True)
