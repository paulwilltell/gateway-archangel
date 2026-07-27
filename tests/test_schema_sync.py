"""Adding a model field must not break an existing database.

`create_all` only creates missing tables; it never alters existing ones. That
gap is invisible to tests built on fresh in-memory databases and breaks the
live one — it did exactly that when ownership tokens were added.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import Database


def test_additive_column_is_applied_to_an_existing_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'drift.db'}"

    database = Database(url)
    database.create_all()

    # Simulate a database created before a column was added to the model.
    # The index must go first; SQLite refuses to drop a column an index needs.
    with database.engine.begin() as connection:
        connection.execute(text("DROP INDEX IF EXISTS ix_posts_owner_token_hash"))
        connection.execute(text("ALTER TABLE posts DROP COLUMN owner_token_hash"))
    assert "owner_token_hash" not in {
        c["name"] for c in inspect(database.engine).get_columns("posts")
    }

    Database(url).create_all()

    inspector = inspect(database.engine)
    assert "owner_token_hash" in {c["name"] for c in inspector.get_columns("posts")}
    # The column's index must come back with it, or lookups silently table-scan.
    assert "ix_posts_owner_token_hash" in {i["name"] for i in inspector.get_indexes("posts")}


def test_sync_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'idem.db'}"
    for _ in range(3):
        Database(url).create_all()
    columns = [c["name"] for c in inspect(Database(url).engine).get_columns("posts")]
    assert len(columns) == len(set(columns))
