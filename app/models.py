from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(80), index=True)
    normalized_name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(24), default="member")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")
    replies: Mapped[list["Reply"]] = relationship(back_populates="author")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    status: Mapped[str] = mapped_column(String(24), default="published")
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    # SHA-256 of the author's ownership token. The token itself is shown once
    # and never stored, so possession proves authorship without the server
    # holding anything that links a person to their posts.
    owner_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    author: Mapped[User] = relationship(back_populates="posts")
    replies: Mapped[list["Reply"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Reply.created_at",
    )

    @property
    def published_replies(self) -> list["Reply"]:
        return [reply for reply in self.replies if reply.status == "published"]


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_reply_id: Mapped[str | None] = mapped_column(ForeignKey("replies.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="published")
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    post: Mapped[Post] = relationship(back_populates="replies")
    author: Mapped[User] = relationship(back_populates="replies")


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_type: Mapped[str] = mapped_column(String(16))  # post | reply
    target_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    alignment: Mapped[str] = mapped_column(String(24), default="uncertain")
    support_level: Mapped[str] = mapped_column(String(32), default="insufficient")
    confidence: Mapped[int] = mapped_column(Integer, default=0)  # integer percent
    analyzer_mode: Mapped[str] = mapped_column(String(32), default="heuristic")
    engine_version: Mapped[str] = mapped_column(String(64))
    corpus_version: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BibleVerse(Base):
    __tablename__ = "bible_verses"
    __table_args__ = (
        UniqueConstraint("source_id", "reference", name="uq_source_reference"),
        Index("ix_bible_book_chapter", "book", "chapter"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(String(64), default="kjv_local")
    reference: Mapped[str] = mapped_column(String(80), index=True)
    book: Mapped[str] = mapped_column(String(64), index=True)
    chapter: Mapped[int] = mapped_column(Integer)
    verse: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(24), default="English")
    original_language: Mapped[str | None] = mapped_column(String(24), nullable=True)
    license: Mapped[str] = mapped_column(String(120), default="Public Domain in the United States")
    corpus_version: Mapped[str] = mapped_column(String(64), index=True)
    is_canonical_source: Mapped[bool] = mapped_column(Boolean, default=True)


class ConsentEvent(Base):
    __tablename__ = "consent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    policy_version: Mapped[str] = mapped_column(String(64))
    consented: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrainingCandidate(Base):
    __tablename__ = "training_candidates"
    __table_args__ = (
        UniqueConstraint("analysis_id", name="uq_training_analysis"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    redacted_text: Mapped[str] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(String(24), default="pending_theological_review")
    reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentReport(Base):
    """A content-first report queue entry.

    Deliberately carries no reporter or author identity — reports point at
    content, and moderation decisions are made about content. See
    docs/ANTI_SURVEILLANCE_POLICY.md.
    """

    __tablename__ = "content_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="human")  # human | archangel
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)  # removed | dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(24), default="system")
    target_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
