"""Shared challenge completion, persisted independently of live sessions."""

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

# Never change an applied migration; append a new numbered migration instead.
MIGRATIONS = (
    (
        1,
        "CREATE TABLE challenge_completion ("
        "challenge_id TEXT PRIMARY KEY, completed_at TEXT NOT NULL)",
    ),
)


def connect() -> sqlite3.Connection:
    path = Path(os.environ.get("SQLITE_PATH", "data/progress.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=5)


def migrate() -> None:
    with closing(connect()) as connection:
        for version, statement in MIGRATIONS:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations "
                    "(version INTEGER PRIMARY KEY)"
                )
                if connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone():
                    continue
                connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
                )


def read_completed() -> set[str]:
    with closing(connect()) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT challenge_id FROM challenge_completion"
            )
        }


def save_completion(challenge_id: str) -> None:
    with closing(connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO challenge_completion (challenge_id, completed_at) "
            "VALUES (?, ?) ON CONFLICT (challenge_id) DO NOTHING",
            (challenge_id, datetime.now(UTC).isoformat()),
        )


def reset_completion() -> None:
    """Clear shared completion atomically, preserving migrations and other data."""
    with closing(connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM challenge_completion")
