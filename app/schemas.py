from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PostCreate(BaseModel):
    author_name: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=5, max_length=180)
    body: str = Field(min_length=10, max_length=8_000)
    training_consent: bool = False

    @field_validator("author_name", "title", "body")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ReplyCreate(BaseModel):
    author_name: str = Field(min_length=2, max_length=80)
    body: str = Field(min_length=2, max_length=4_000)
    training_consent: bool = False

    @field_validator("author_name", "body")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str


class ReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    body: str
    author: UserOut
    created_at: datetime


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    author: UserOut
    created_at: datetime
    replies: list[ReplyOut] = Field(default=[], validation_alias="published_replies")


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=24)


class OwnershipAction(BaseModel):
    owner_token: str = Field(min_length=8, max_length=200)
    action: str = Field(default="delete", pattern="^(delete|withdraw_consent)$")


class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(post|reply)$")
    target_id: str = Field(min_length=1, max_length=36)
    category: str = Field(
        pattern="^(sexual_content|abusive_content|spam|threat|doxxing"
        "|self_harm_encouragement|exploitation|fraud|illegal)$"
    )
    details: str | None = Field(default=None, max_length=2_000)
