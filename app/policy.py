"""Platform content policy — the only grounds for removal.

Gateway is a free place to post: no viewpoint, theological, or quality
moderation, ever. Content is refused or removed only for the categories
below, which mirror docs/CONTENT_POLICY.md:

- sexual_content: explicit sexual material or solicitation
- abusive_content: harassment or abuse directed at a person
- spam: commercial flooding that drowns out human conversation

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

POLICY_CATEGORIES = ("sexual_content", "abusive_content", "spam", "illegal")

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
