from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    """Small database wrapper that supports SQLite locally and PostgreSQL in production."""

    def __init__(self, url: str):
        self.url = url
        connect_args: dict[str, object] = {}
        engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if url in {"sqlite://", "sqlite:///:memory:"}:
                engine_kwargs["poolclass"] = StaticPool

        self.engine = create_engine(
            url,
            connect_args=connect_args,
            **engine_kwargs,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )

    def create_all(self) -> None:
        from app import models  # noqa: F401 - imports table metadata

        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        db = self.SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
