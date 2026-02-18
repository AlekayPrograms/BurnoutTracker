"""Unit tests for the data layer (database, repository, models)."""

import sqlite3
import pytest
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.database import Database
from src.data.repository import Repository
from src.data.models import Session, Category, Task, Event


@pytest.fixture
def repo():
    """Create an in-memory database for testing."""
    db = Database(db_path=Path(":memory:"))
    # Override connect to use :memory:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    from src.data.database import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return Repository(conn)


class TestCategory:
    def test_create_category(self, repo: Repository):
        cat = repo.create_category("Coding")
        assert cat.id is not None
        assert cat.name == "Coding"

    def test_duplicate_category(self, repo: Repository):
        repo.create_category("Coding")
        cat2 = repo.create_category("Coding")
        # Should not create a duplicate
        assert cat2.name == "Coding"
        cats = repo.list_categories()
        assert len(cats) == 1

    def test_list_categories(self, repo: Repository):
        repo.create_category("Coding")
        repo.create_category("Writing")
        cats = repo.list_categories()
        assert len(cats) == 2
        assert cats[0].name == "Coding"


class TestTask:
    def test_create_task(self, repo: Repository):
        cat = repo.create_category("Coding")
        task = repo.create_task("Fix bug #42", cat.id)
        assert task.id is not None
        assert task.name == "Fix bug #42"
        assert task.category_id == cat.id

    def test_search_tasks(self, repo: Repository):
        cat = repo.create_category("Coding")
        repo.create_task("Frontend work", cat.id)
        repo.create_task("Backend API", cat.id)
        # SQLite LIKE is case-insensitive for ASCII
        results = repo.search_tasks("frontend")
        assert len(results) == 1
        results = repo.search_tasks("Frontend")
        assert len(results) == 1
        results = repo.search_tasks("Nonexistent")
        assert len(results) == 0


class TestSession:
    def test_create_and_end_session(self, repo: Repository):
        cat = repo.create_category("Coding")
        task = repo.create_task("Test task", cat.id)
        now = datetime.now()

        session = repo.create_session(task.id, now)
        assert session.id is not None
        assert session.task_id == task.id

        session.end_time = now + timedelta(hours=1)
        session.gross_duration_min = 60.0
        session.net_focused_min = 50.0
        session.break_duration_min = 5.0
        session.procrastination_duration_min = 5.0
        session.focus_ratio = 50.0 / 60.0
        session.interruption_count = 2
        session.longest_focus_block_min = 30.0
        repo.end_session(session)

        loaded = repo.get_session(session.id)
        assert loaded is not None
        assert loaded.gross_duration_min == 60.0
        assert loaded.net_focused_min == 50.0

    def test_list_sessions_with_filters(self, repo: Repository):
        cat = repo.create_category("Coding")
        task = repo.create_task("Test", cat.id)
        now = datetime.now()

        s = repo.create_session(task.id, now - timedelta(days=1))
        s.end_time = now
        s.gross_duration_min = 60.0
        repo.end_session(s)

        sessions = repo.list_sessions(category_id=cat.id)
        assert len(sessions) == 1

        sessions = repo.list_sessions(start_after=now - timedelta(days=2))
        assert len(sessions) == 1

        sessions = repo.list_sessions(start_after=now + timedelta(days=1))
        assert len(sessions) == 0


class TestEvents:
    def test_add_and_get_events(self, repo: Repository):
        cat = repo.create_category("Test")
        task = repo.create_task("T", cat.id)
        session = repo.create_session(task.id, datetime.now())

        repo.add_event(session.id, "work_start")
        repo.add_event(session.id, "break_start")
        repo.add_event(session.id, "break_end")

        events = repo.get_events(session.id)
        assert len(events) == 3
        assert events[0].event_type == "work_start"

    def test_latest_event(self, repo: Repository):
        cat = repo.create_category("Test")
        task = repo.create_task("T", cat.id)
        session = repo.create_session(task.id, datetime.now())

        repo.add_event(session.id, "work_start")
        repo.add_event(session.id, "burnout")

        latest = repo.get_latest_event(session.id)
        assert latest.event_type == "burnout"


class TestDashboardStats:
    def test_empty_stats(self, repo: Repository):
        stats = repo.get_dashboard_stats()
        assert stats["session_count"] == 0
        assert stats["avg_net_focused"] is None

    def test_stats_with_data(self, repo: Repository):
        cat = repo.create_category("Coding")
        task = repo.create_task("Work", cat.id)
        now = datetime.now()

        for i in range(3):
            s = repo.create_session(task.id, now - timedelta(days=i))
            s.end_time = now - timedelta(days=i) + timedelta(hours=1)
            s.gross_duration_min = 60.0
            s.net_focused_min = 50.0
            s.break_duration_min = 5.0
            s.procrastination_duration_min = 5.0
            s.focus_ratio = 50.0 / 60.0
            s.interruption_count = 2
            s.longest_focus_block_min = 25.0
            repo.end_session(s)

        stats = repo.get_dashboard_stats()
        assert stats["session_count"] == 3
        assert stats["avg_net_focused"] == 50.0
        assert abs(stats["avg_focus_ratio"] - (50.0 / 60.0)) < 0.01
