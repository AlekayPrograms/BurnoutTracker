"""Unit tests for the ML prediction engine."""

import sqlite3
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.database import SCHEMA_SQL
from src.data.repository import Repository
from src.ml.predictor import BurnoutPredictor


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return Repository(conn)


@pytest.fixture
def predictor(repo):
    return BurnoutPredictor(repo)


def _seed_sessions(repo: Repository, count: int = 10):
    """Helper: create N completed sessions with events."""
    cat = repo.create_category("Test")
    task = repo.create_task("Task", cat.id)
    now = datetime.now()

    for i in range(count):
        start = now - timedelta(days=count - i, hours=9)
        s = repo.create_session(task.id, start)

        # Add events
        repo.add_event(s.id, "work_start", start)
        burnout_time = start + timedelta(minutes=30 + i * 2)
        repo.add_event(s.id, "burnout", burnout_time)

        break_start = start + timedelta(minutes=20 + i)
        repo.add_event(s.id, "break_start", break_start)
        repo.add_event(s.id, "break_end", break_start + timedelta(minutes=5))

        end = start + timedelta(minutes=60 + i * 3)
        repo.add_event(s.id, "work_end", end)

        s.end_time = end
        s.gross_duration_min = (end - start).total_seconds() / 60
        s.break_duration_min = 5.0
        s.procrastination_duration_min = 0.0
        s.net_focused_min = s.gross_duration_min - 5.0
        s.focus_ratio = s.net_focused_min / s.gross_duration_min
        s.longest_focus_block_min = 20.0 + i
        s.interruption_count = 1
        repo.end_session(s)

    return cat.id


class TestPredictor:
    def test_no_data_returns_none(self, predictor):
        result = predictor.predict("time_to_burnout")
        assert result is None

    def test_has_enough_data(self, predictor, repo):
        assert not predictor.has_enough_data()
        _seed_sessions(repo, 5)
        assert predictor.has_enough_data()

    def test_predict_with_data(self, predictor, repo):
        cat_id = _seed_sessions(repo, 10)
        predictor.clear_cache()

        result = predictor.predict("time_to_burnout", cat_id)
        assert result is not None
        assert result > 0

    def test_predict_net_focused(self, predictor, repo):
        cat_id = _seed_sessions(repo, 10)
        predictor.clear_cache()

        result = predictor.predict("net_focused_time", cat_id)
        assert result is not None
        assert result > 0

    def test_predict_focus_block(self, predictor, repo):
        cat_id = _seed_sessions(repo, 10)
        predictor.clear_cache()

        result = predictor.predict("focus_block_length", cat_id)
        assert result is not None

    def test_train_all(self, predictor, repo):
        _seed_sessions(repo, 10)
        results = predictor.train_all()
        assert "time_to_burnout" in results
        assert results["time_to_burnout"]["status"] == "trained"

    def test_global_fallback(self, predictor, repo):
        """When no category data, should fall back to global."""
        _seed_sessions(repo, 10)
        predictor.clear_cache()

        result = predictor.predict("time_to_burnout", category_id=9999)
        # Should fall back to global
        assert result is not None

    def test_optimal_session_length(self, predictor, repo):
        cat_id = _seed_sessions(repo, 10)
        predictor.clear_cache()

        result = predictor.predict_optimal_session_length(cat_id)
        assert result is not None
        assert result > 0

    def test_ema_basic(self):
        values = [10, 20, 30, 40, 50]
        result = BurnoutPredictor._exponential_moving_average(values)
        assert 30 < result < 50  # should be biased toward recent values
