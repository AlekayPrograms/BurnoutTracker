"""
Session Service — orchestrates the lifecycle of a work session.

Handles: begin working, end working, state transitions, and computing
session aggregates from raw events when a session ends.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from src.data.models import Category, Event, Session, Task
from src.data.repository import Repository

logger = logging.getLogger(__name__)


class SessionState:
    """Tracks the in-memory state of the current session."""
    IDLE = "idle"
    WORKING = "working"
    ON_BREAK = "on_break"
    PROCRASTINATING = "procrastinating"


class SessionService:
    """
    Manages the lifecycle of work sessions.

    Only ONE session can be active at a time. State transitions:
        idle → working → (on_break | procrastinating) ↔ working → idle
    """

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.current_session: Optional[Session] = None
        self.state: str = SessionState.IDLE

    # ── Category / Task management ──────────────────────────────────────────

    def get_or_create_category(self, name: str) -> Category:
        cat = self.repo.get_category_by_name(name)
        if cat:
            return cat
        return self.repo.create_category(name)

    def get_or_create_task(self, task_name: str, category_id: int) -> Task:
        tasks = self.repo.search_tasks(task_name)
        for t in tasks:
            if t.category_id == category_id and t.name.lower() == task_name.lower():
                return t
        return self.repo.create_task(task_name, category_id)

    def list_categories(self) -> List[Category]:
        return self.repo.list_categories()

    def list_tasks(self, category_id: Optional[int] = None) -> List[Task]:
        return self.repo.list_tasks(category_id)

    # ── Session lifecycle ───────────────────────────────────────────────────

    def begin_session(self, task_id: int) -> Session:
        """Start a new work session."""
        if self.state != SessionState.IDLE:
            raise RuntimeError("A session is already active.")
        now = datetime.now()
        self.current_session = self.repo.create_session(task_id, now)
        self.repo.add_event(self.current_session.id, "work_start", now)
        self.state = SessionState.WORKING
        logger.info("Session %d started for task %d", self.current_session.id, task_id)
        return self.current_session

    def end_session(self) -> Session:
        """End the current session, auto-closing any open break/procrastination."""
        if self.state == SessionState.IDLE or self.current_session is None:
            raise RuntimeError("No active session to end.")

        now = datetime.now()
        # Auto-close open intervals
        if self.state == SessionState.ON_BREAK:
            self.repo.add_event(self.current_session.id, "break_end", now)
        elif self.state == SessionState.PROCRASTINATING:
            self.repo.add_event(self.current_session.id, "procrastination_end", now)

        self.repo.add_event(self.current_session.id, "work_end", now)

        # Compute aggregates from events
        self._compute_session_aggregates(now)

        self.repo.end_session(self.current_session)
        session = self.current_session
        self.current_session = None
        self.state = SessionState.IDLE
        logger.info("Session %d ended.", session.id)
        return session

    # ── Break management ────────────────────────────────────────────────────

    def start_break(self) -> Event:
        self._require_state(SessionState.WORKING, "start a break")
        now = datetime.now()
        self.state = SessionState.ON_BREAK
        return self.repo.add_event(self.current_session.id, "break_start", now)

    def end_break(self) -> Event:
        self._require_state(SessionState.ON_BREAK, "end a break")
        now = datetime.now()
        self.state = SessionState.WORKING
        return self.repo.add_event(self.current_session.id, "break_end", now)

    # ── Procrastination management ──────────────────────────────────────────

    def start_procrastination(self) -> Event:
        self._require_state(SessionState.WORKING, "log procrastination")
        now = datetime.now()
        self.state = SessionState.PROCRASTINATING
        return self.repo.add_event(self.current_session.id, "procrastination_start", now)

    def end_procrastination(self) -> Event:
        self._require_state(SessionState.PROCRASTINATING, "end procrastination")
        now = datetime.now()
        self.state = SessionState.WORKING
        return self.repo.add_event(self.current_session.id, "procrastination_end", now)

    # ── Burnout ─────────────────────────────────────────────────────────────

    def log_burnout(self) -> Event:
        """Log a burnout event. Doesn't change state — user decides next step."""
        if self.state == SessionState.IDLE or self.current_session is None:
            raise RuntimeError("No active session.")
        now = datetime.now()
        return self.repo.add_event(self.current_session.id, "burnout", now)

    # ── Resume working (from break or procrastination) ──────────────────────

    def resume_working(self) -> Event:
        """Universal 'get back to work' — closes whichever interval is open."""
        if self.state == SessionState.ON_BREAK:
            return self.end_break()
        elif self.state == SessionState.PROCRASTINATING:
            return self.end_procrastination()
        else:
            raise RuntimeError("Not on break or procrastinating.")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def get_elapsed_minutes(self) -> float:
        """Minutes since session started."""
        if not self.current_session or not self.current_session.start_time:
            return 0.0
        return (datetime.now() - self.current_session.start_time).total_seconds() / 60.0

    def get_current_interval_minutes(self) -> float:
        """Minutes in the current break/procrastination interval."""
        if self.current_session is None:
            return 0.0
        events = self.repo.get_events(self.current_session.id)
        if not events:
            return 0.0
        last = events[-1]
        if last.event_type in ("break_start", "procrastination_start"):
            return (datetime.now() - last.timestamp).total_seconds() / 60.0
        return 0.0

    def _require_state(self, expected: str, action: str) -> None:
        if self.state != expected:
            raise RuntimeError(
                f"Cannot {action}: current state is '{self.state}', "
                f"expected '{expected}'."
            )
        if self.current_session is None:
            raise RuntimeError("No active session.")

    def _compute_session_aggregates(self, end_time: datetime) -> None:
        """Walk events to compute all session-level aggregates."""
        s = self.current_session
        s.end_time = end_time
        s.gross_duration_min = (end_time - s.start_time).total_seconds() / 60.0

        events = self.repo.get_events(s.id)

        break_total = 0.0
        proc_total = 0.0
        interruptions = 0
        focus_blocks: List[float] = []

        last_work_start: Optional[datetime] = None

        for evt in events:
            if evt.event_type == "work_start":
                last_work_start = evt.timestamp

            elif evt.event_type in ("break_start", "procrastination_start"):
                interruptions += 1
                # Close current focus block
                if last_work_start:
                    block_min = (evt.timestamp - last_work_start).total_seconds() / 60.0
                    if block_min > 0:
                        focus_blocks.append(block_min)
                    last_work_start = None

            elif evt.event_type == "break_end":
                # find matching break_start
                start_evt = self._find_preceding(events, evt, "break_start")
                if start_evt:
                    break_total += (evt.timestamp - start_evt.timestamp).total_seconds() / 60.0
                last_work_start = evt.timestamp  # resume focus

            elif evt.event_type == "procrastination_end":
                start_evt = self._find_preceding(events, evt, "procrastination_start")
                if start_evt:
                    proc_total += (evt.timestamp - start_evt.timestamp).total_seconds() / 60.0
                last_work_start = evt.timestamp  # resume focus

            elif evt.event_type == "work_end":
                if last_work_start:
                    block_min = (evt.timestamp - last_work_start).total_seconds() / 60.0
                    if block_min > 0:
                        focus_blocks.append(block_min)

        s.break_duration_min = break_total
        s.procrastination_duration_min = proc_total
        s.net_focused_min = s.gross_duration_min - break_total - proc_total
        s.longest_focus_block_min = max(focus_blocks) if focus_blocks else s.net_focused_min
        s.interruption_count = interruptions
        s.focus_ratio = (
            s.net_focused_min / s.gross_duration_min
            if s.gross_duration_min and s.gross_duration_min > 0
            else None
        )

    @staticmethod
    def _find_preceding(events: List[Event], current: Event, target_type: str) -> Optional[Event]:
        """Find the most recent event of target_type before current."""
        best: Optional[Event] = None
        for e in events:
            if e.timestamp >= current.timestamp:
                break
            if e.event_type == target_type:
                best = e
        return best


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Manages the full lifecycle of a work session — start, stop, break,
#   procrastination, burnout. It's the "state machine" for user work flow.
#
# Key classes:
#   - SessionState: enum-like constants for the 4 states (idle, working,
#     on_break, procrastinating).
#   - SessionService: enforces valid state transitions and computes
#     aggregates when a session ends.
#
# Data flow:
#   UI button click → SessionService.begin_session() → creates Session +
#   Event in DB → state = WORKING → user clicks "Break" →
#   SessionService.start_break() → logs Event → state = ON_BREAK → ...
#   → end_session() → walks all events → computes aggregates → stores.
#
# Interviewer-friendly talking points:
#   1. State machine pattern: only valid transitions are allowed (can't
#      start a break while already on break). This prevents corrupt data.
#   2. Auto-close on end: if the user forgets to end a break, end_session()
#      closes it automatically. Defensive programming for real users.
#   3. Aggregate computation walks events: O(n) in number of events per
#      session, which is always small (usually <50). No performance concern.
