"""
ML Prediction Engine — lightweight models for predicting burnout,
procrastination, and break timing.

Design philosophy:
  - Works with TINY datasets (even 3-5 sessions).
  - Falls back gracefully: moving averages → category-level → global.
  - No heavy frameworks; just scikit-learn and numpy.
  - Model artifacts saved locally with versioning.
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.data.models import Session
from src.data.repository import Repository

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MIN_SAMPLES_FOR_REGRESSION = 8
MIN_SAMPLES_FOR_AVERAGE = 3


class BurnoutPredictor:
    """
    Predicts optimal timing for burnout, procrastination, and breaks.

    Strategy (per target):
      1. If >= 8 sessions for this category → linear regression
      2. If >= 3 sessions for this category → exponential moving average
      3. If >= 3 sessions globally → global moving average
      4. Else → return None (insufficient data)
    """

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        # In-memory caches for predictions
        self._cache: Dict[str, float] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def train_all(self) -> Dict[str, dict]:
        """
        (Re)train all models. Called on app launch or after N sessions.
        Returns a summary of what was trained.
        """
        results = {}
        for target in ("time_to_burnout", "time_to_procrastination",
                        "time_to_break", "net_focused_time",
                        "time_to_first_interruption", "focus_block_length"):
            result = self._train_target(target)
            results[target] = result
        return results

    def predict(
        self,
        target: str,
        category_id: Optional[int] = None,
        task_id: Optional[int] = None,
    ) -> Optional[float]:
        """
        Predict a value for the given target.

        Returns minutes (float) or None if insufficient data.
        """
        cache_key = f"{target}_{category_id}_{task_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try category-level first, then global
        sessions = self.repo.list_sessions(
            category_id=category_id, task_id=task_id, limit=200
        )
        value = self._predict_from_sessions(target, sessions)

        if value is None and category_id is not None:
            # Fallback to global
            sessions = self.repo.list_sessions(limit=200)
            value = self._predict_from_sessions(target, sessions)

        if value is not None:
            self._cache[cache_key] = value
        return value

    def predict_optimal_session_length(
        self, category_id: Optional[int] = None
    ) -> Optional[float]:
        """Recommend gross session length to maximize focused time."""
        net = self.predict("net_focused_time", category_id)
        if net is None:
            return None
        # Add typical break overhead (from history or default 15%)
        sessions = self.repo.list_sessions(category_id=category_id, limit=50)
        if sessions:
            avg_ratio = np.mean([
                s.focus_ratio for s in sessions
                if s.focus_ratio is not None and s.focus_ratio > 0
            ] or [0.85])
            return net / avg_ratio if avg_ratio > 0 else None
        return net / 0.85

    def predict_break_insertion_point(
        self, category_id: Optional[int] = None
    ) -> Optional[float]:
        """Recommend when to insert a break (minutes into session)."""
        focus_block = self.predict("focus_block_length", category_id)
        if focus_block is not None:
            return focus_block * 0.9  # suggest break slightly before typical limit
        return self.predict("time_to_first_interruption", category_id)

    def suggest_break_length(
        self, category_id: Optional[int] = None
    ) -> Optional[float]:
        """Suggest break length based on historical recovery patterns."""
        sessions = self.repo.list_sessions(category_id=category_id, limit=100)
        if not sessions:
            sessions = self.repo.list_sessions(limit=100)

        # Find sessions where a break was followed by good focus
        break_lengths: List[float] = []
        for s in sessions:
            if s.break_duration_min and s.break_duration_min > 0 and s.interruption_count:
                avg_break = s.break_duration_min / max(s.interruption_count, 1)
                break_lengths.append(avg_break)

        if len(break_lengths) >= MIN_SAMPLES_FOR_AVERAGE:
            return float(np.mean(break_lengths))
        return None

    def has_enough_data(self, category_id: Optional[int] = None) -> bool:
        """Check if we have enough data for meaningful predictions."""
        sessions = self.repo.list_sessions(category_id=category_id, limit=10)
        return len(sessions) >= MIN_SAMPLES_FOR_AVERAGE

    def clear_cache(self) -> None:
        self._cache.clear()

    # ── Internal ────────────────────────────────────────────────────────────

    def _predict_from_sessions(
        self, target: str, sessions: List[Session]
    ) -> Optional[float]:
        """Extract target values and run prediction strategy."""
        values = self._extract_target_values(target, sessions)
        if not values:
            return None

        if len(values) >= MIN_SAMPLES_FOR_REGRESSION:
            return self._linear_regression_predict(values)
        elif len(values) >= MIN_SAMPLES_FOR_AVERAGE:
            return self._exponential_moving_average(values)
        return None

    def _extract_target_values(
        self, target: str, sessions: List[Session]
    ) -> List[float]:
        """Pull the relevant metric from each session."""
        values: List[float] = []
        for s in sessions:
            val = self._get_target_value(target, s)
            if val is not None and val > 0:
                values.append(val)
        return values

    def _get_target_value(self, target: str, session: Session) -> Optional[float]:
        """Map target name to session attribute or computed value."""
        if target == "time_to_burnout":
            return self._time_to_event(session, "burnout")
        elif target == "time_to_procrastination":
            return self._time_to_event(session, "procrastination_start")
        elif target == "time_to_break":
            return self._time_to_event(session, "break_start")
        elif target == "net_focused_time":
            return session.net_focused_min
        elif target == "time_to_first_interruption":
            return self._time_to_first_interruption(session)
        elif target == "focus_block_length":
            return session.longest_focus_block_min
        return None

    def _time_to_event(self, session: Session, event_type: str) -> Optional[float]:
        """Minutes from session start to first occurrence of event_type."""
        if not session.start_time or not session.id:
            return None
        events = self.repo.get_events(session.id)
        for e in events:
            if e.event_type == event_type:
                return (e.timestamp - session.start_time).total_seconds() / 60.0
        return None

    def _time_to_first_interruption(self, session: Session) -> Optional[float]:
        """Minutes from session start to first break or procrastination."""
        if not session.start_time or not session.id:
            return None
        events = self.repo.get_events(session.id)
        for e in events:
            if e.event_type in ("break_start", "procrastination_start"):
                return (e.timestamp - session.start_time).total_seconds() / 60.0
        # No interruption → the whole session was focused
        return session.gross_duration_min

    def _linear_regression_predict(self, values: List[float]) -> float:
        """
        Simple linear regression on sequential values.
        X = session index (0, 1, 2, ...), Y = target value.
        Predicts the NEXT value. Bounded to [0.5 * mean, 2 * mean].
        """
        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)

        # Fit y = mx + b
        A = np.vstack([x, np.ones(len(x))]).T
        result = np.linalg.lstsq(A, y, rcond=None)
        m, b = result[0]

        prediction = m * len(values) + b
        mean_val = float(np.mean(y))

        # Clamp to reasonable range
        prediction = max(mean_val * 0.5, min(prediction, mean_val * 2.0))
        return float(prediction)

    @staticmethod
    def _exponential_moving_average(values: List[float], alpha: float = 0.3) -> float:
        """
        Exponential moving average — weights recent sessions more heavily.
        alpha=0.3 means the most recent value contributes 30%.
        """
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return float(ema)

    def _train_target(self, target: str) -> dict:
        """Train and save a model for one target. Returns summary."""
        sessions = self.repo.list_sessions(limit=500)
        values = self._extract_target_values(target, sessions)

        if len(values) < MIN_SAMPLES_FOR_AVERAGE:
            return {"status": "insufficient_data", "samples": len(values)}

        # Save model artifact (just the values and metadata for now)
        artifact = {
            "target": target,
            "values": values,
            "trained_at": datetime.now().isoformat(),
            "sample_count": len(values),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
        }

        artifact_path = MODELS_DIR / f"{target}_model.pkl"
        with open(artifact_path, "wb") as f:
            pickle.dump(artifact, f)

        metrics = {
            "sample_count": len(values),
            "mean": artifact["mean"],
            "std": artifact["std"],
        }
        self.repo.save_model_version(target, str(artifact_path), metrics)
        self.clear_cache()

        logger.info("Trained %s: %d samples, mean=%.1f", target, len(values), artifact["mean"])
        return {"status": "trained", **metrics}


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The "brain" of the app. It looks at your past sessions and predicts when
#   you'll burn out, procrastinate, or need a break. It also recommends
#   optimal session lengths and break insertion points.
#
# Key design decisions:
#   - Tiered fallback strategy: regression → EMA → global averages → None.
#     This is critical because new users have no data!
#   - Linear regression on session sequence (not datetime): we're predicting
#     "next session" behavior, treating sessions as a time series.
#   - EMA (exponential moving average) with alpha=0.3: recent sessions matter
#     more than old ones. If you've been improving focus, the model adapts.
#
# Data flow:
#   App launch → train_all() → reads Sessions → extracts values per target →
#   saves artifacts to /models/ → predict() reads from cache or computes
#
# Interviewer-friendly talking points:
#   1. Why not deep learning? Overkill for <100 data points per user. Simple
#      regression + EMA are more robust with tiny datasets. A neural net
#      would overfit immediately.
#   2. Clamping predictions: the regression line can extrapolate wildly
#      (negative minutes!). We clamp to [0.5*mean, 2*mean] for safety.
#   3. Model versioning: every retrain saves a new version so we could
#      roll back if a bad batch of data corrupts predictions.
