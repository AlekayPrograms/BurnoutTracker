"""
Tracking Service — handles proactive reminders and periodic check-ins.

This service runs timers that periodically ask the user if they're burnt out,
procrastinating, or need a break. It also integrates with ML predictions to
adapt timing to the user's historical patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import QTimer

from src.data.repository import Repository
from src.services.session_service import SessionService, SessionState

logger = logging.getLogger(__name__)

# Default intervals (minutes) — overridden by settings or ML
DEFAULT_BURNOUT_CHECK_INTERVAL = 45
DEFAULT_PROCRASTINATION_REMINDER_INTERVAL = 5
DEFAULT_BREAK_ELAPSED_REMINDER_INTERVAL = 30


class TrackingService:
    """
    Manages proactive reminders during active sessions.

    Uses QTimers so callbacks run on the Qt event loop (safe for UI updates).
    """

    def __init__(
        self,
        repo: Repository,
        session_service: SessionService,
        on_burnout_check: Optional[Callable] = None,
        on_procrastination_reminder: Optional[Callable] = None,
        on_break_elapsed: Optional[Callable] = None,
    ) -> None:
        self.repo = repo
        self.session_svc = session_service

        # Callbacks the UI will set
        self.on_burnout_check = on_burnout_check
        self.on_procrastination_reminder = on_procrastination_reminder
        self.on_break_elapsed = on_break_elapsed

        # Configurable intervals (minutes)
        self.burnout_check_interval = DEFAULT_BURNOUT_CHECK_INTERVAL
        self.procrastination_reminder_interval = DEFAULT_PROCRASTINATION_REMINDER_INTERVAL
        self.break_elapsed_interval = DEFAULT_BREAK_ELAPSED_REMINDER_INTERVAL

        # QTimers
        self._burnout_timer = QTimer()
        self._burnout_timer.timeout.connect(self._check_burnout)

        self._proc_timer = QTimer()
        self._proc_timer.timeout.connect(self._remind_procrastination)

        self._break_timer = QTimer()
        self._break_timer.timeout.connect(self._remind_break_elapsed)

    # ── Public API ──────────────────────────────────────────────────────────

    def start_work_tracking(self, predicted_burnout_min: Optional[float] = None) -> None:
        """Begin proactive burnout check-ins during a work session."""
        interval = predicted_burnout_min or self.burnout_check_interval
        self._burnout_timer.start(int(interval * 60 * 1000))
        logger.info("Burnout check timer started: every %.0f min", interval)

    def stop_work_tracking(self) -> None:
        self._burnout_timer.stop()

    def start_procrastination_reminders(self) -> None:
        """Start the 5-minute nagging loop while procrastinating."""
        self._proc_timer.start(
            int(self.procrastination_reminder_interval * 60 * 1000)
        )
        logger.info("Procrastination reminders started.")

    def stop_procrastination_reminders(self) -> None:
        self._proc_timer.stop()

    def start_break_tracking(self) -> None:
        """Start the 30-minute break elapsed reminders."""
        self._break_timer.start(
            int(self.break_elapsed_interval * 60 * 1000)
        )
        logger.info("Break elapsed reminders started.")

    def stop_break_tracking(self) -> None:
        self._break_timer.stop()

    def stop_all(self) -> None:
        self._burnout_timer.stop()
        self._proc_timer.stop()
        self._break_timer.stop()

    def update_intervals(
        self,
        burnout_min: Optional[float] = None,
        proc_min: Optional[float] = None,
        break_min: Optional[float] = None,
    ) -> None:
        """Update check intervals (e.g. from ML predictions or settings)."""
        if burnout_min is not None:
            self.burnout_check_interval = burnout_min
        if proc_min is not None:
            self.procrastination_reminder_interval = proc_min
        if break_min is not None:
            self.break_elapsed_interval = break_min

    # ── Timer callbacks ─────────────────────────────────────────────────────

    def _check_burnout(self) -> None:
        if self.session_svc.state != SessionState.WORKING:
            return
        logger.info("Proactive burnout check triggered.")
        sid = self.session_svc.current_session.id if self.session_svc.current_session else None
        if sid:
            self.repo.add_reminder(sid, "burnout_check")
        if self.on_burnout_check:
            self.on_burnout_check()

    def _remind_procrastination(self) -> None:
        if self.session_svc.state != SessionState.PROCRASTINATING:
            self._proc_timer.stop()
            return
        elapsed = self.session_svc.get_current_interval_minutes()
        logger.info("Procrastination reminder: %.1f min elapsed.", elapsed)
        sid = self.session_svc.current_session.id if self.session_svc.current_session else None
        if sid:
            self.repo.add_reminder(sid, "procrastination_nudge")
        if self.on_procrastination_reminder:
            self.on_procrastination_reminder(elapsed)

    def _remind_break_elapsed(self) -> None:
        if self.session_svc.state != SessionState.ON_BREAK:
            self._break_timer.stop()
            return
        elapsed = self.session_svc.get_current_interval_minutes()
        logger.info("Break elapsed reminder: %.1f min.", elapsed)
        sid = self.session_svc.current_session.id if self.session_svc.current_session else None
        if sid:
            self.repo.add_reminder(sid, "break_elapsed")
        if self.on_break_elapsed:
            self.on_break_elapsed(elapsed)


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Runs background timers that fire callbacks to the UI at smart intervals.
#   During work: periodic "are you burnt out?" checks.
#   During procrastination: every 5 minutes "want to stop procrastinating?"
#   During breaks: every 30 minutes "your break is X min long."
#
# Key design decisions:
#   - Uses QTimer (PySide6) so callbacks run on the main thread — safe for
#     popping up dialog boxes without cross-thread headaches.
#   - Intervals are configurable at runtime so the ML engine can say
#     "this user typically burns out after 32 min, not 45."
#   - Callbacks are injected via constructor so the service is UI-agnostic
#     (testable without a real window).
#
# Data flow:
#   QTimer fires → _check_burnout() → logs ReminderLog to DB → calls
#   on_burnout_check callback → UI shows dialog → user responds →
#   response saved to ReminderLog.
#
# Interviewer-friendly talking points:
#   1. Dependency injection: callbacks passed in, not hardcoded. Makes the
#      service testable with simple mock functions.
#   2. QTimer vs threading.Timer: QTimer integrates with Qt's event loop,
#      so the callback can safely touch UI widgets. threading.Timer would
#      require signals or locks.
#   3. ML integration point: update_intervals() lets the ML engine push
#      personalized timing without the service knowing anything about ML.
