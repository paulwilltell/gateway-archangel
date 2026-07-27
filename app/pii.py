from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PiiScan:
    contains_pii: bool
    categories: tuple[str, ...]
    redacted_text: str


def scan_and_redact(text: str) -> PiiScan:
    categories: list[str] = []
    redacted = text

    patterns = (
        (EMAIL_RE, "email", "[REDACTED_EMAIL]"),
        (PHONE_RE, "phone", "[REDACTED_PHONE]"),
        (SSN_RE, "government_id", "[REDACTED_ID]"),
        (ADDRESS_RE, "street_address", "[REDACTED_ADDRESS]"),
    )
    for regex, category, replacement in patterns:
        if regex.search(redacted):
            categories.append(category)
            redacted = regex.sub(replacement, redacted)

    return PiiScan(bool(categories), tuple(categories), redacted)
