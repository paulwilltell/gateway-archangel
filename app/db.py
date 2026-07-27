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
        self._sync_added_columns()

    def _sync_added_columns(self) -> None:
        """Add columns that exist in the models but not yet in the database.

        `create_all` creates missing *tables* but never alters existing ones,
        so adding a model field silently breaks an already-populated database
        while a fresh test database passes. This closes that gap for additive
        changes only — it never drops, renames, or retypes anything.

        It is a stopgap, not a migration system. Anything beyond adding a
        nullable column (backfills, renames, constraint changes, Postgres in
        production) needs a real migration tool such as Alembic.
        """
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        with self.engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue
                present = {col["name"] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in present:
                        continue
                    if not (column.nullable or column.default is not None):
                        raise RuntimeError(
                            f"Cannot auto-add non-nullable column {table.name}.{column.name} "
                            "to an existing database; write a migration."
                        )
                    ddl = column.type.compile(dialect=self.engine.dialect)
                    connection.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}')
                    )

        # A column added above may carry an index that create_all did not
        # create, because the table already existed.
        inspector = inspect(self.engine)
        for table in Base.metadata.sorted_tables:
            if table.name not in set(inspector.get_table_names()):
                continue
            present = {idx["name"] for idx in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name not in present:
                    index.create(bind=self.engine)

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
