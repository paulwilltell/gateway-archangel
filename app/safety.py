from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SafetyAssessment:
    level: str = "none"  # none | concern | urgent | immediate
    category: str = "none"
    display_message: str | None = None
    resources: tuple[str, ...] = field(default_factory=tuple)


IMMEDIATE_SELF_HARM = (
    re.compile(r"\b(?:i am|i'm|im) going to (?:kill|hurt) myself\b", re.IGNORECASE),
    re.compile(r"\b(?:i am|i'm|im) going to end my life\b", re.IGNORECASE),
    re.compile(r"\b(?:i have|i've got) (?:a )?plan to (?:die|kill myself|end my life)\b", re.IGNORECASE),
    # Time-proximity in either order: "tonight ... end my life" and
    # "end my life tonight" are the same emergency.
    re.compile(r"\b(?:tonight|right now|today)\b.{0,35}\b(?:kill myself|end my life|suicide)\b", re.IGNORECASE),
    re.compile(r"\b(?:kill myself|end my life|suicide)\b.{0,35}\b(?:tonight|right now|today)\b", re.IGNORECASE),
)

SELF_HARM_CONCERN = (
    re.compile(r"\b(?:want to die|wish i were dead|don't want to live|do not want to live)\b", re.IGNORECASE),
    re.compile(r"\b(?:suicidal|suicide)\b", re.IGNORECASE),
)

IMMEDIATE_VIOLENCE = (
    re.compile(r"\b(?:i am|i'm|im) going to (?:kill|shoot|stab|hurt) (?:him|her|them|someone)\b", re.IGNORECASE),
    re.compile(r"\bi have a (?:gun|weapon|knife).{0,40}\b(?:kill|hurt|attack)\b", re.IGNORECASE),
)

MEDICAL_EMERGENCY = (
    re.compile(r"\b(?:can't|cannot) breathe\b", re.IGNORECASE),
    re.compile(r"\bchest pain\b.{0,50}\b(?:severe|crushing|sudden)\b", re.IGNORECASE),
    re.compile(r"\b(?:unconscious|not waking up|seizure|major bleeding)\b", re.IGNORECASE),
    re.compile(r"\boverdose\b.{0,50}\b(?:not breathing|unresponsive|collapsed)\b", re.IGNORECASE),
)

POISONING = (
    re.compile(r"\b(?:poisoned|swallowed|ingested)\b.{0,40}\b(?:bleach|cleaner|pesticide|chemical)\b", re.IGNORECASE),
)


def classify_safety(
    text: str,
    *,
    emergency_number: str = "911",
    crisis_number: str = "988",
    poison_control_number: str = "1-800-222-1222",
) -> SafetyAssessment:
    """Conservative pre-model safety classifier.

    The result is structured so the platform can display a referral without the AI
    pretending to provide medical diagnosis, crisis counseling, or emergency care.
    """

    if any(pattern.search(text) for pattern in IMMEDIATE_SELF_HARM):
        return SafetyAssessment(
            level="immediate",
            category="self_harm",
            display_message=(
                f"Immediate safety concern detected. In the United States, call {emergency_number} now "
                f"or call/text {crisis_number}. Stay with another person and move away from weapons or other means."
            ),
            resources=(f"Emergency: {emergency_number}", f"Suicide & Crisis Lifeline: {crisis_number}"),
        )

    if any(pattern.search(text) for pattern in IMMEDIATE_VIOLENCE):
        return SafetyAssessment(
            level="immediate",
            category="violence",
            display_message=(
                f"Immediate danger to another person may be present. Call {emergency_number} or local emergency services now."
            ),
            resources=(f"Emergency: {emergency_number}",),
        )

    if any(pattern.search(text) for pattern in MEDICAL_EMERGENCY):
        return SafetyAssessment(
            level="immediate",
            category="medical_emergency",
            display_message=(
                f"Possible medical emergency detected. This platform does not provide medical care; call {emergency_number} now."
            ),
            resources=(f"Emergency: {emergency_number}",),
        )

    if any(pattern.search(text) for pattern in POISONING):
        return SafetyAssessment(
            level="urgent",
            category="poisoning",
            display_message=(
                f"Possible poisoning or dangerous exposure detected. Contact Poison Control at {poison_control_number}; "
                f"call {emergency_number} if the person collapses, has a seizure, cannot breathe, or cannot be awakened."
            ),
            resources=(f"Poison Control: {poison_control_number}", f"Emergency: {emergency_number}"),
        )

    if any(pattern.search(text) for pattern in SELF_HARM_CONCERN):
        return SafetyAssessment(
            level="urgent",
            category="self_harm",
            display_message=(
                f"Serious emotional-safety concern detected. In the United States, call or text {crisis_number}; "
                f"call {emergency_number} if danger is immediate."
            ),
            resources=(f"Suicide & Crisis Lifeline: {crisis_number}", f"Emergency: {emergency_number}"),
        )

    return SafetyAssessment()
