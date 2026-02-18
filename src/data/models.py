"""
Data models for BurnoutTracker.

These are plain dataclasses that represent database rows. They decouple the rest
of the app from raw SQL dictionaries so every layer speaks the same "language."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Category:
    """A work category (e.g. 'Coding', 'Writing')."""
    id: Optional[int] = None
    name: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Task:
    """A specific task belonging to a category."""
    id: Optional[int] = None
    name: str = ""
    category_id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Session:
    """One work session from 'Begin Working' to 'Stop Working'."""
    id: Optional[int] = None
    task_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    gross_duration_min: Optional[float] = None
    break_duration_min: float = 0.0
    procrastination_duration_min: float = 0.0
    net_focused_min: Optional[float] = None
    longest_focus_block_min: Optional[float] = None
    interruption_count: int = 0
    focus_ratio: Optional[float] = None


@dataclass
class Event:
    """
    A timestamped event inside a session.

    event_type is one of:
        'work_start', 'work_end',
        'break_start', 'break_end',
        'procrastination_start', 'procrastination_end',
        'burnout',
        'reminder_prompt', 'reminder_response'
    """
    id: Optional[int] = None
    session_id: Optional[int] = None
    event_type: str = ""
    timestamp: Optional[datetime] = None
    payload: Optional[str] = None  # JSON string for extra data


@dataclass
class ReminderLog:
    """Tracks reminders sent and user responses."""
    id: Optional[int] = None
    session_id: Optional[int] = None
    reminder_type: str = ""       # 'burnout_check', 'procrastination_check', 'break_suggest'
    prompted_at: Optional[datetime] = None
    response: Optional[str] = None  # 'yes', 'no', 'dismissed'
    responded_at: Optional[datetime] = None


@dataclass
class ModelVersion:
    """Metadata about a trained ML model artifact."""
    id: Optional[int] = None
    model_name: str = ""
    version: int = 1
    trained_at: Optional[datetime] = None
    artifact_path: str = ""
    metrics_json: Optional[str] = None  # JSON string with training metrics


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Defines the "shape" of every important object in the system as Python
#   dataclasses. Think of them as typed structs — they carry data but have no
#   database logic themselves.
#
# Key classes and why they exist:
#   - Category / Task: two-level hierarchy so users can group work
#     (e.g. Category="School", Task="CS 440 HW3").
#   - Session: one continuous work period. Pre-computed aggregates
#     (net_focused_min, focus_ratio, etc.) live here for fast dashboard
#     rendering, but can always be recomputed from raw Events.
#   - Event: the granular log — every start/stop of work/break/procrastination
#     is an Event. This is the "source of truth."
#   - ReminderLog: tracks what the buddy asked and what the user answered,
#     so the ML can learn from responses over time.
#   - ModelVersion: lets us keep old model artifacts around for rollback.
#
# Data flow:
#   User action → Service creates Event(s) → Repository persists to SQLite
#   Dashboard reads Sessions / Events → computes or uses pre-computed stats
#
# Interviewer-friendly talking points:
#   1. Dataclasses vs ORM: we skip heavyweight ORMs (SQLAlchemy) because the
#      schema is small and we want transparent SQL. Trade-off: more manual
#      mapping, but total control and zero magic.
#   2. Pre-computed aggregates: Session stores net_focused_min so the
#      dashboard doesn't re-scan thousands of events on every render. We still
#      *can* recompute from events for correctness auditing.
#   3. Event sourcing lite: every state change is an Event, so we can always
#      reconstruct session timelines. This is a simplified version of the
#      event-sourcing pattern used in production systems.
