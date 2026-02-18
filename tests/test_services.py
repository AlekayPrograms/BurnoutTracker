"""Unit tests for the service layer."""

import sqlite3
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.database import SCHEMA_SQL
from src.data.repository import Repository
from src.services.session_service import SessionService, SessionState
from src.services.break_research import BreakResearch


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return Repository(conn)


@pytest.fixture
def svc(repo):
    return SessionService(repo)


@pytest.fixture
def seeded_svc(svc):
    """Service with a category and task ready to use."""
    cat = svc.get_or_create_category("Coding")
    task = svc.get_or_create_task("Test Task", cat.id)
    return svc, task.id


class TestSessionService:
    def test_begin_session(self, seeded_svc):
        svc, task_id = seeded_svc
        session = svc.begin_session(task_id)
        assert session.id is not None
        assert svc.state == SessionState.WORKING

    def test_cannot_begin_twice(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        with pytest.raises(RuntimeError, match="already active"):
            svc.begin_session(task_id)

    def test_end_session_computes_aggregates(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        session = svc.end_session()
        assert session.end_time is not None
        assert session.gross_duration_min is not None
        assert session.gross_duration_min >= 0
        assert svc.state == SessionState.IDLE

    def test_break_flow(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        assert svc.state == SessionState.WORKING

        svc.start_break()
        assert svc.state == SessionState.ON_BREAK

        svc.end_break()
        assert svc.state == SessionState.WORKING

    def test_procrastination_flow(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)

        svc.start_procrastination()
        assert svc.state == SessionState.PROCRASTINATING

        svc.end_procrastination()
        assert svc.state == SessionState.WORKING

    def test_cannot_break_while_procrastinating(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        svc.start_procrastination()
        with pytest.raises(RuntimeError, match="expected 'working'"):
            svc.start_break()

    def test_auto_close_on_end(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        svc.start_break()
        # End session without ending break — should auto-close
        session = svc.end_session()
        assert svc.state == SessionState.IDLE
        assert session.break_duration_min >= 0

    def test_resume_working(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        svc.start_break()
        svc.resume_working()
        assert svc.state == SessionState.WORKING

    def test_log_burnout(self, seeded_svc):
        svc, task_id = seeded_svc
        svc.begin_session(task_id)
        event = svc.log_burnout()
        assert event.event_type == "burnout"

    def test_get_or_create_category(self, svc):
        cat1 = svc.get_or_create_category("New Cat")
        cat2 = svc.get_or_create_category("New Cat")
        assert cat1.id == cat2.id


class TestBreakResearch:
    def test_advice_short_break(self):
        br = BreakResearch()
        advice = br.get_break_advice(2.0)
        assert "short" in advice.lower()

    def test_advice_good_break(self):
        br = BreakResearch()
        advice = br.get_break_advice(10.0)
        assert "nice" in advice.lower() or "good" in advice.lower() or "desktime" in advice.lower()

    def test_advice_long_break(self):
        br = BreakResearch()
        advice = br.get_break_advice(45.0)
        assert "long" in advice.lower()

    def test_suggest_break_length(self):
        br = BreakResearch()
        assert br.suggest_break_length(20) == 5.0
        assert br.suggest_break_length(50) == 10.0
        assert br.suggest_break_length(100) == 20.0

    def test_research_entries(self):
        br = BreakResearch()
        entries = br.get_all_research()
        assert len(entries) >= 5
        assert all(e.url for e in entries)
