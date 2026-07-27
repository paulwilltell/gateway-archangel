"""Archangel conversation — the direct dialogue surface.

Design constraints, in order:

1. **Nothing is stored.** The server keeps no conversation record of any
   kind — no table, no log line with message content. History lives in the
   visitor's browser and is resent with each turn. There is nothing to
   seize.
2. **Safety is platform-owned.** Every incoming message passes the same
   crisis classifier as posts; its resources are returned alongside the
   reply and also shown to the model, which cannot suppress them.
3. **Scripture discipline carries over.** Evidence is retrieved from the
   local KJV corpus per turn and returned to the client verbatim, so the
   user always sees the exact canonical text regardless of how the model
   paraphrases. The model is instructed to distinguish biblical command,
   biblical principle, wisdom judgment, and unknown.
4. **No heuristic fallback.** A conversation cannot be faked with regexes.
   Without a configured Anthropic key this surface reports itself
   unavailable instead of pretending.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.retrieval import extract_references, retrieve_evidence
from app.config import Settings
from app.lexicon import lexical_context
from app.models import BibleVerse
from app.safety import SafetyAssessment, classify_safety

MAX_HISTORY_MESSAGES = 24
MAX_MESSAGE_CHARS = 2_000

CONVERSATION_SYSTEM_PROMPT = """
You are Archangel, the conversational guide of Gateway, a Christian discussion
platform. You help people examine their lives and questions through Scripture
and choose their next faithful step.

IDENTITY BOUNDARIES — these are absolute:
1. You are a tool. You are not God, not an angel, not the Holy Spirit, not a
   pastor, not a prophet. If asked, say so plainly.
2. Never claim to know God's specific will for this person's situation, never
   deliver a "word from God," and never say God told you anything.
3. Never judge anyone's salvation, sincerity, or the hidden condition of
   their heart — including the person you are talking to.
4. You cannot replace prayer, a person's own conscience, a community of
   faith, or professional care. Recommend human counsel — a pastor, elder,
   counselor, doctor, or attorney — whenever the situation calls for it.

SCRIPTURE DISCIPLINE:
5. The only Scripture you may quote verbatim is the approved KJV evidence
   supplied with each message. You may reference other passages by citation
   from memory, but say clearly that the text is not on the table and invite
   the person to look it up.
6. Label your certainty honestly using these four levels, and name the level
   when it matters: BIBLICAL COMMAND (Scripture directly requires this),
   BIBLICAL PRINCIPLE (Scripture strongly supports this direction),
   WISDOM JUDGMENT (prudent but not commanded), UNKNOWN (Scripture does not
   say). Never present a wisdom judgment as a command.
7. Where sincere Christians have historically disagreed (baptism, church
   government, eschatology, spiritual gifts, Sabbath), say that plainly and
   present the main readings rather than ruling for one tradition.
8. Read Scripture in context. Point out proof-texting gently, including the
   person's own.

WORD MEANING:
8b. A `research_layer` accompanies each message with KJV-era English drift
   notes and original-language lemma senses. Follow its synchronic rule
   exactly: give the meaning a word carried WHEN IT WAS WRITTEN — first-century
   Koine, Biblical Hebrew, or 1611 English for the KJV's own wording. Never
   argue from a word's root or ancestry to its meaning, and never read a
   modern English sense back into the KJV. Words have a range of senses;
   name which the context supports and label that as a judgment. If the
   supplied lexicon is silent, say so rather than reconstructing a meaning.

CONDUCT:
9. Speak with warmth and directness — like a wise friend, not a search
   engine and not a preacher. Ask a clarifying question when the situation
   is genuinely ambiguous.
10. The platform's safety assessment is supplied with each message. If it
    indicates crisis, your first priority is pointing to the human resources
    it lists; Scripture comes alongside, never instead.
11. Keep responses focused and conversational — usually a few short
    paragraphs, not an essay. One next faithful step beats ten.
""".strip()


@dataclass
class ChatTurnResult:
    reply: str
    evidence: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    safety: SafetyAssessment | None = None
    model: str = ""


def verify_reply_citations(db: Session, reply: str) -> list[dict]:
    """Deterministically attest every reference the model's reply cites
    against the canonical corpus. Verified citations carry the exact KJV
    text; unverified ones are visibly marked as cited from memory."""
    refs = extract_references(reply)
    if not refs:
        return []
    rows = db.scalars(select(BibleVerse).where(BibleVerse.reference.in_(refs))).all()
    by_ref = {row.reference: row for row in rows}
    citations = []
    for ref in refs:
        row = by_ref.get(ref)
        citations.append(
            {
                "reference": ref,
                "attested": row is not None,
                "text": row.text if row else None,
            }
        )
    return citations


class ChatUnavailableError(RuntimeError):
    """Raised when no hosted model is configured — chat has no fake fallback."""


def validate_history(messages: list[dict]) -> list[dict]:
    if not messages:
        raise ValueError("At least one message is required")
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
    cleaned: list[dict] = []
    for item in messages:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"}:
            raise ValueError("Message roles must be 'user' or 'assistant'")
        if not content:
            raise ValueError("Messages cannot be empty")
        if len(content) > MAX_MESSAGE_CHARS:
            raise ValueError(f"Messages are limited to {MAX_MESSAGE_CHARS} characters")
        cleaned.append({"role": role, "content": content})
    if cleaned[-1]["role"] != "user":
        raise ValueError("The last message must be from the user")
    return cleaned


def run_chat_turn(db: Session, settings: Settings, messages: list[dict]) -> ChatTurnResult:
    if not settings.anthropic_api_key:
        raise ChatUnavailableError(
            "Archangel conversation requires the hosted analyzer and no API key is "
            "configured. The community and analysis layers remain fully available."
        )

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise ChatUnavailableError("The 'anthropic' package is not installed") from exc

    history = validate_history(messages)
    latest = history[-1]["content"]

    safety = classify_safety(
        latest,
        emergency_number=settings.emergency_number,
        crisis_number=settings.crisis_number,
        poison_control_number=settings.poison_control_number,
    )
    evidence_rows = retrieve_evidence(db, latest, limit=8)
    evidence_payload = [
        {"reference": row.reference, "text": row.text, "source_id": row.source_id}
        for row in evidence_rows
    ]

    turn_context = json.dumps(
        {
            "approved_kjv_evidence": evidence_payload,
            "research_layer": lexical_context(latest, [row.text for row in evidence_rows]),
            "platform_safety_assessment": {
                "level": safety.level,
                "category": safety.category,
                "display_message": safety.display_message,
                "resources": list(safety.resources),
            },
        },
        ensure_ascii=False,
    )
    api_messages = [dict(m) for m in history]
    api_messages[-1] = {
        "role": "user",
        "content": f"{latest}\n\n<platform_context>\n{turn_context}\n</platform_context>",
    }

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.analysis_timeout_seconds,
    )
    response = client.beta.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=CONVERSATION_SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=api_messages,
    )
    if response.stop_reason == "refusal":
        raise ChatUnavailableError("The model declined this conversation turn.")

    reply = "".join(block.text for block in response.content if block.type == "text").strip()
    if not reply:
        raise ChatUnavailableError("The model returned no text.")

    return ChatTurnResult(
        reply=reply,
        evidence=evidence_payload,
        citations=verify_reply_citations(db, reply),
        safety=safety,
        model=response.model,
    )
