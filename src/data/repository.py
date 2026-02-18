"""
Repository — the single place where SQL lives.

Every other module talks to Repository, never to raw SQL. This makes it easy
to swap SQLite for Postgres (or mock in tests) without touching business logic.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

from .models import Category, Event, ModelVersion, ReminderLog, Session, Task

logger = logging.getLogger(__name__)

# helper: parse ISO datetime strings from SQLite
_parse_dt = lambda s: datetime.fromisoformat(s) if s else None


class Repository:
    """Data-access layer wrapping a sqlite3 connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ── Categories ──────────────────────────────────────────────────────────

    def create_category(self, name: str) -> Category:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
        )
        self.conn.commit()
        # fetch back (handles IGNORE case)
        row = self.conn.execute(
            "SELECT * FROM categories WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_category(row)

    def get_category(self, category_id: int) -> Optional[Category]:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return self._row_to_category(row) if row else None

    def get_category_by_name(self, name: str) -> Optional[Category]:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_category(row) if row else None

    def list_categories(self) -> List[Category]:
        rows = self.conn.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
        return [self._row_to_category(r) for r in rows]

    # ── Tasks ───────────────────────────────────────────────────────────────

    def create_task(self, name: str, category_id: int) -> Task:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO tasks (name, category_id) VALUES (?, ?)",
            (name, category_id),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE name = ? AND category_id = ?",
            (name, category_id),
        ).fetchone()
        return self._row_to_task(row)

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, category_id: Optional[int] = None) -> List[Task]:
        if category_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE category_id = ? ORDER BY name",
                (category_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks ORDER BY name"
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def search_tasks(self, query: str) -> List[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE name LIKE ? ORDER BY name",
            (f"%{query}%",),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ── Sessions ────────────────────────────────────────────────────────────

    def create_session(self, task_id: int, start_time: datetime) -> Session:
        cur = self.conn.execute(
            "INSERT INTO sessions (task_id, start_time) VALUES (?, ?)",
            (task_id, start_time.isoformat()),
        )
        self.conn.commit()
        return Session(id=cur.lastrowid, task_id=task_id, start_time=start_time)

    def end_session(self, session: Session) -> None:
        self.conn.execute(
            """UPDATE sessions SET
                end_time = ?, gross_duration_min = ?, break_duration_min = ?,
                procrastination_duration_min = ?, net_focused_min = ?,
                longest_focus_block_min = ?, interruption_count = ?,
                focus_ratio = ?
            WHERE id = ?""",
            (
                session.end_time.isoformat() if session.end_time else None,
                session.gross_duration_min,
                session.break_duration_min,
                session.procrastination_duration_min,
                session.net_focused_min,
                session.longest_focus_block_min,
                session.interruption_count,
                session.focus_ratio,
                session.id,
            ),
        )
        self.conn.commit()

    def get_session(self, session_id: int) -> Optional[Session]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(
        self,
        task_id: Optional[int] = None,
        category_id: Optional[int] = None,
        start_after: Optional[datetime] = None,
        start_before: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Session]:
        query = "SELECT s.* FROM sessions s"
        conditions: List[str] = []
        params: list = []

        if category_id is not None:
            query += " JOIN tasks t ON s.task_id = t.id"
            conditions.append("t.category_id = ?")
            params.append(category_id)
        if task_id is not None:
            conditions.append("s.task_id = ?")
            params.append(task_id)
        if start_after:
            conditions.append("s.start_time >= ?")
            params.append(start_after.isoformat())
        if start_before:
            conditions.append("s.start_time <= ?")
            params.append(start_before.isoformat())

        conditions.append("s.end_time IS NOT NULL")  # only completed sessions

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY s.start_time DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def count_sessions(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE end_time IS NOT NULL"
        ).fetchone()
        return row[0]

    # ── Events ──────────────────────────────────────────────────────────────

    def add_event(self, session_id: int, event_type: str,
                  timestamp: Optional[datetime] = None,
                  payload: Optional[str] = None) -> Event:
        ts = timestamp or datetime.now()
        cur = self.conn.execute(
            "INSERT INTO events (session_id, event_type, timestamp, payload) VALUES (?, ?, ?, ?)",
            (session_id, event_type, ts.isoformat(), payload),
        )
        self.conn.commit()
        return Event(id=cur.lastrowid, session_id=session_id,
                     event_type=event_type, timestamp=ts, payload=payload)

    def get_events(self, session_id: int) -> List[Event]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_latest_event(self, session_id: int) -> Optional[Event]:
        row = self.conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return self._row_to_event(row) if row else None

    # ── Reminder Logs ───────────────────────────────────────────────────────

    def add_reminder(self, session_id: int, reminder_type: str) -> ReminderLog:
        cur = self.conn.execute(
            "INSERT INTO reminder_logs (session_id, reminder_type) VALUES (?, ?)",
            (session_id, reminder_type),
        )
        self.conn.commit()
        return ReminderLog(id=cur.lastrowid, session_id=session_id,
                           reminder_type=reminder_type, prompted_at=datetime.now())

    def respond_to_reminder(self, reminder_id: int, response: str) -> None:
        self.conn.execute(
            "UPDATE reminder_logs SET response = ?, responded_at = ? WHERE id = ?",
            (response, datetime.now().isoformat(), reminder_id),
        )
        self.conn.commit()

    # ── Model Versions ──────────────────────────────────────────────────────

    def save_model_version(self, model_name: str, artifact_path: str,
                           metrics: Optional[dict] = None) -> ModelVersion:
        # determine next version number
        row = self.conn.execute(
            "SELECT MAX(version) FROM model_versions WHERE model_name = ?",
            (model_name,),
        ).fetchone()
        next_ver = (row[0] or 0) + 1
        cur = self.conn.execute(
            "INSERT INTO model_versions (model_name, version, artifact_path, metrics_json) VALUES (?, ?, ?, ?)",
            (model_name, next_ver, artifact_path,
             json.dumps(metrics) if metrics else None),
        )
        self.conn.commit()
        return ModelVersion(id=cur.lastrowid, model_name=model_name,
                            version=next_ver, artifact_path=artifact_path)

    def get_latest_model(self, model_name: str) -> Optional[ModelVersion]:
        row = self.conn.execute(
            "SELECT * FROM model_versions WHERE model_name = ? ORDER BY version DESC LIMIT 1",
            (model_name,),
        ).fetchone()
        if not row:
            return None
        return ModelVersion(
            id=row["id"], model_name=row["model_name"],
            version=row["version"],
            trained_at=_parse_dt(row["trained_at"]),
            artifact_path=row["artifact_path"],
            metrics_json=row["metrics_json"],
        )

    # ── Aggregate helpers (for dashboard) ───────────────────────────────────

    def get_dashboard_stats(
        self,
        category_id: Optional[int] = None,
        task_id: Optional[int] = None,
        start_after: Optional[datetime] = None,
        start_before: Optional[datetime] = None,
    ) -> dict:
        """Return pre-computed aggregate stats for the dashboard."""
        sessions = self.list_sessions(
            task_id=task_id, category_id=category_id,
            start_after=start_after, start_before=start_before, limit=10000,
        )
        if not sessions:
            return self._empty_stats()

        gross = [s.gross_duration_min for s in sessions if s.gross_duration_min]
        brk = [s.break_duration_min for s in sessions]
        proc = [s.procrastination_duration_min for s in sessions]
        net = [s.net_focused_min for s in sessions if s.net_focused_min]
        focus_blocks = [s.longest_focus_block_min for s in sessions if s.longest_focus_block_min]
        interruptions = [s.interruption_count for s in sessions]
        ratios = [s.focus_ratio for s in sessions if s.focus_ratio is not None]

        def avg(lst: list) -> Optional[float]:
            return sum(lst) / len(lst) if lst else None

        # Time-to-burnout / procrastination from events
        time_to_burnout = self._avg_time_to_event("burnout", sessions)
        time_to_proc = self._avg_time_to_event("procrastination_start", sessions)
        time_to_break = self._avg_time_to_event("break_start", sessions)

        return {
            "session_count": len(sessions),
            "avg_gross_duration": avg(gross),
            "avg_break_duration": avg(brk),
            "avg_procrastination_duration": avg(proc),
            "avg_net_focused": avg(net),
            "avg_longest_focus_block": avg(focus_blocks),
            "avg_interruptions": avg(interruptions),
            "avg_focus_ratio": avg(ratios),
            "avg_time_to_burnout": time_to_burnout,
            "avg_time_to_procrastination": time_to_proc,
            "avg_time_to_break": time_to_break,
            "focus_block_distribution": focus_blocks,
            "sessions": sessions,
        }

    def _avg_time_to_event(self, event_type: str, sessions: List[Session]) -> Optional[float]:
        """Average minutes from session start to first occurrence of event_type."""
        deltas: List[float] = []
        for s in sessions:
            if not s.start_time:
                continue
            row = self.conn.execute(
                "SELECT MIN(timestamp) FROM events WHERE session_id = ? AND event_type = ?",
                (s.id, event_type),
            ).fetchone()
            if row and row[0]:
                evt_time = datetime.fromisoformat(row[0])
                delta = (evt_time - s.start_time).total_seconds() / 60.0
                deltas.append(delta)
        return sum(deltas) / len(deltas) if deltas else None

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "session_count": 0,
            "avg_gross_duration": None,
            "avg_break_duration": None,
            "avg_procrastination_duration": None,
            "avg_net_focused": None,
            "avg_longest_focus_block": None,
            "avg_interruptions": None,
            "avg_focus_ratio": None,
            "avg_time_to_burnout": None,
            "avg_time_to_procrastination": None,
            "avg_time_to_break": None,
            "focus_block_distribution": [],
            "sessions": [],
        }

    # ── Data export ─────────────────────────────────────────────────────────

    def export_sessions_csv(self) -> str:
        """Return all completed sessions as CSV text."""
        rows = self.conn.execute(
            "SELECT s.*, t.name as task_name, c.name as category_name "
            "FROM sessions s "
            "JOIN tasks t ON s.task_id = t.id "
            "JOIN categories c ON t.category_id = c.id "
            "WHERE s.end_time IS NOT NULL "
            "ORDER BY s.start_time"
        ).fetchall()
        if not rows:
            return ""
        headers = rows[0].keys()
        lines = [",".join(headers)]
        for r in rows:
            lines.append(",".join(str(r[h]) if r[h] is not None else "" for h in headers))
        return "\n".join(lines)

    def delete_session(self, session_id: int) -> None:
        """Delete a single session and its events."""
        self.conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()
        logger.info("Deleted session %d", session_id)

    def delete_sessions_in_range(
        self, start_after: datetime, start_before: datetime
    ) -> int:
        """Delete all sessions within a date range. Returns count deleted."""
        rows = self.conn.execute(
            "SELECT id FROM sessions WHERE start_time >= ? AND start_time <= ? "
            "AND end_time IS NOT NULL",
            (start_after.isoformat(), start_before.isoformat()),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            self.conn.execute(f"DELETE FROM events WHERE session_id IN ({placeholders})", ids)
            self.conn.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", ids)
            self.conn.commit()
        logger.info("Deleted %d sessions in date range", len(ids))
        return len(ids)

    def reset_all_data(self) -> None:
        """Delete all data. Requires explicit confirmation in the UI."""
        for table in ["events", "reminder_logs", "sessions", "tasks",
                       "categories", "model_versions"]:
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.commit()
        logger.warning("All data has been reset.")

    # ── Row mappers ─────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_category(row: sqlite3.Row) -> Category:
        return Category(id=row["id"], name=row["name"],
                        created_at=_parse_dt(row["created_at"]))

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(id=row["id"], name=row["name"],
                    category_id=row["category_id"],
                    created_at=_parse_dt(row["created_at"]))

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"], task_id=row["task_id"],
            start_time=_parse_dt(row["start_time"]),
            end_time=_parse_dt(row["end_time"]),
            gross_duration_min=row["gross_duration_min"],
            break_duration_min=row["break_duration_min"] or 0.0,
            procrastination_duration_min=row["procrastination_duration_min"] or 0.0,
            net_focused_min=row["net_focused_min"],
            longest_focus_block_min=row["longest_focus_block_min"],
            interruption_count=row["interruption_count"] or 0,
            focus_ratio=row["focus_ratio"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"], session_id=row["session_id"],
            event_type=row["event_type"],
            timestamp=_parse_dt(row["timestamp"]),
            payload=row["payload"],
        )


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The Repository is the ONLY place raw SQL queries live. Every other layer
#   calls methods like repo.create_session() instead of writing SQL strings.
#   This is the "Repository Pattern."
#
# Key methods:
#   - CRUD for categories, tasks, sessions, events
#   - get_dashboard_stats(): runs aggregate queries and returns a dict the
#     dashboard can render directly.
#   - export_sessions_csv(): data portability — users can get their data out.
#
# Data flow:
#   Service layer → Repository.method() → SQL → sqlite3.Row → dataclass model
#
# Interviewer-friendly talking points:
#   1. Repository pattern isolates SQL: if we swapped to Postgres, only this
#      file changes. Services and UI stay untouched.
#   2. Aggregate pre-computation vs on-the-fly: we store aggregates on Session
#      rows for speed, but get_dashboard_stats() can recompute from events
#      for correctness verification.
#   3. INSERT OR IGNORE for categories/tasks: idempotent creation avoids
#      duplicate-key errors without a separate "check then insert" round-trip.
