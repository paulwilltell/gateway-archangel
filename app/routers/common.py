from __future__ import annotations

import re
import secrets

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConsentEvent, User
from app.policy import screen_content


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, action: str) -> None:
    settings = request.app.state.settings
    limiter = request.app.state.rate_limiter
    limits = {
        "post": settings.rate_limit_posts_per_window,
        "reply": settings.rate_limit_replies_per_window,
        "report": settings.rate_limit_reports_per_window,
        "chat": settings.rate_limit_chat_per_window,
    }
    if not limiter.allow(client_key(request), action, limits[action], settings.rate_limit_window_seconds):
        raise HTTPException(
            429,
            f"Rate limit reached: at most {limits[action]} {action}s per "
            f"{settings.rate_limit_window_seconds // 60} minutes. Please wait and try again.",
        )


def enforce_content_policy(*parts: str) -> None:
    verdict = screen_content("\n".join(parts))
    if not verdict.allowed:
        raise HTTPException(422, verdict.message)


def require_moderator(request: Request) -> None:
    configured = request.app.state.settings.moderation_token
    if not configured:
        raise HTTPException(503, "Moderation is not configured on this deployment (set MODERATION_TOKEN).")
    supplied = request.headers.get("x-moderation-token", "")
    if not secrets.compare_digest(supplied, configured):
        raise HTTPException(403, "Invalid moderation token")


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


_PSEUDONYM_STEMS = ("Sojourner", "Pilgrim", "Witness", "Watchman", "Servant", "Traveler")


def anonymous_pseudonym(db: Session) -> str:
    """A fresh pseudonym with no link to any prior identity. Collisions are
    regenerated so two people are never merged into one pen name."""
    import secrets as _secrets

    for _ in range(50):
        candidate = f"{_secrets.choice(_PSEUDONYM_STEMS)}-{_secrets.randbelow(9000) + 1000}"
        if not db.scalar(select(User).where(User.normalized_name == normalize_name(candidate))):
            return candidate
    return f"Sojourner-{_secrets.token_hex(4)}"


def get_or_create_user(db: Session, display_name: str) -> User:
    normalized = normalize_name(display_name)
    user = db.scalar(select(User).where(User.normalized_name == normalized))
    if user:
        return user
    user = User(display_name=display_name.strip(), normalized_name=normalized)
    db.add(user)
    db.flush()
    return user


def record_consent(
    db: Session,
    *,
    user_id: str,
    target_type: str,
    target_id: str,
    consented: bool,
    policy_version: str,
) -> None:
    db.add(
        ConsentEvent(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            policy_version=policy_version,
            consented=consented,
        )
    )
