import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().with_name("inventory.db")
SCHEMA_PATH = Path(__file__).resolve().with_name("schema.sql")


def connect(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a database with foreign key checks and rows accessible by name."""
    if database_path is None:
        database_path = os.environ.get("INVENTORY_DB") or DEFAULT_DB_PATH

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def setup_database(connection: sqlite3.Connection) -> None:
    """Create missing tables and indexes before starting application transactions."""
    # executescript commits a pending transaction, so refuse to interrupt one.
    if connection.in_transaction:
        raise sqlite3.ProgrammingError(
            "Cannot set up the schema during an active transaction."
        )
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
