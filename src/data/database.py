"""
SQLite database initialization and connection management.

Single responsibility: own the connection, create tables, run migrations.
All actual queries live in Repository.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default DB lives next to the executable / repo root
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "burnout_tracker.db"

SCHEMA_SQL = """
-- Categories ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Tasks ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, category_id)
);

-- Sessions ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id                     INTEGER NOT NULL REFERENCES tasks(id),
    start_time                  TEXT    NOT NULL,
    end_time                    TEXT,
    gross_duration_min          REAL,
    break_duration_min          REAL    DEFAULT 0,
    procrastination_duration_min REAL   DEFAULT 0,
    net_focused_min             REAL,
    longest_focus_block_min     REAL,
    interruption_count          INTEGER DEFAULT 0,
    focus_ratio                 REAL
);

-- Events (source of truth) --------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    event_type  TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    payload     TEXT
);

-- Reminder logs --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reminder_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    reminder_type   TEXT    NOT NULL,
    prompted_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    response        TEXT,
    responded_at    TEXT
);

-- Model versions -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name      TEXT    NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    trained_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    artifact_path   TEXT    NOT NULL,
    metrics_json    TEXT
);

-- Indexes for common queries -------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_events_session   ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type      ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_sessions_task    ON sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_category   ON tasks(category_id);
"""


class Database:
    """Thin wrapper around a SQLite connection."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn: Optional[sqlite3.Connection] = None

    # -- lifecycle -----------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """Open (or return existing) connection and ensure schema exists."""
        if self.conn is not None:
            return self.conn
        logger.info("Connecting to SQLite at %s", self.db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row          # dict-like rows
        self.conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        return self.conn

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed.")

    # -- internal ------------------------------------------------------------

    def _create_tables(self) -> None:
        assert self.conn is not None
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        logger.info("Database schema ensured.")


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Manages the SQLite connection and makes sure all tables exist on startup.
#
# Key pieces:
#   - SCHEMA_SQL: the full DDL. CREATE IF NOT EXISTS makes it idempotent —
#     safe to run every launch.
#   - Database class: holds one connection, enables WAL mode for performance,
#     and turns on foreign keys (SQLite has them OFF by default!).
#
# Data flow:
#   App start → Database.connect() → tables created → Repository uses conn
#
# Interviewer-friendly talking points:
#   1. WAL (Write-Ahead Logging): lets readers and writers work concurrently.
#      Default journal mode locks the whole DB on writes.
#   2. row_factory = sqlite3.Row: rows behave like dicts (row["name"]) which
#      is more readable than positional indexing (row[3]).
#   3. We keep schema in code (not a migration tool) because we're a local
#      single-user app. For a team project you'd use Alembic or similar.
