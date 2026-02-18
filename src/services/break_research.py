"""
Break Research Layer — built-in knowledge about optimal break timing.

This module contains summaries of real productivity research and provides
gentle warnings when breaks are too long or too short. All guidance is
non-medical and productivity-focused only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ResearchEntry:
    title: str
    summary: str
    optimal_break_min: Optional[float]
    optimal_work_min: Optional[float]
    citation: str
    url: str


# Built-in knowledge base (compiled from public research summaries)
RESEARCH_ENTRIES: List[ResearchEntry] = [
    ResearchEntry(
        title="Pomodoro Technique",
        summary=(
            "Work in 25-minute focused sprints, then take a 5-minute break. "
            "After 4 sprints, take a longer 15–30 minute break. Developed by "
            "Francesco Cirillo in the late 1980s."
        ),
        optimal_break_min=5.0,
        optimal_work_min=25.0,
        citation="Cirillo, F. (2006). The Pomodoro Technique.",
        url="https://francescocirillo.com/products/the-pomodoro-technique",
    ),
    ResearchEntry(
        title="DeskTime 52/17 Rule",
        summary=(
            "Analysis of the most productive employees found they worked for "
            "52 minutes then took 17-minute breaks. The key was 100% dedication "
            "during work periods and fully stepping away during breaks."
        ),
        optimal_break_min=17.0,
        optimal_work_min=52.0,
        citation="Gifford, J. (2014). DeskTime Productivity Study.",
        url="https://desktime.com/blog/17-52-ratio-most-productive-people",
    ),
    ResearchEntry(
        title="Ultradian Rhythms",
        summary=(
            "The body cycles through 90-minute periods of higher and lower "
            "alertness (Basic Rest-Activity Cycle). Working with these natural "
            "rhythms — 90 min work, 20 min rest — can improve sustained focus."
        ),
        optimal_break_min=20.0,
        optimal_work_min=90.0,
        citation="Kleitman, N. (1963). Sleep and Wakefulness.",
        url="https://en.wikipedia.org/wiki/Basic_rest%E2%80%93activity_cycle",
    ),
    ResearchEntry(
        title="Attention Restoration Theory (ART)",
        summary=(
            "Exposure to natural environments (even looking at nature photos) "
            "restores directed attention. Micro-breaks of 5–10 minutes with "
            "nature exposure can significantly replenish cognitive resources."
        ),
        optimal_break_min=10.0,
        optimal_work_min=None,
        citation="Kaplan, S. (1995). The restorative benefits of nature.",
        url="https://doi.org/10.1016/0272-4944(95)90001-2",
    ),
    ResearchEntry(
        title="Cognitive Fatigue & Recovery",
        summary=(
            "Studies show that after ~20 minutes of intense cognitive work, "
            "performance begins to decline. Brief diversions (even 30 seconds) "
            "can dramatically improve focus on prolonged tasks."
        ),
        optimal_break_min=5.0,
        optimal_work_min=20.0,
        citation="Ariga, A. & Lleras, A. (2011). Brief diversions improve focus.",
        url="https://doi.org/10.1016/j.cognition.2010.12.007",
    ),
]


class BreakResearch:
    """Provides break guidance based on built-in research knowledge."""

    def __init__(self) -> None:
        self.entries = RESEARCH_ENTRIES

    def get_all_research(self) -> List[ResearchEntry]:
        return self.entries

    def get_break_advice(self, break_duration_min: float) -> str:
        """Return a gentle warning/encouragement based on break length."""
        if break_duration_min < 3:
            return (
                "That was a very short break! Research suggests at least "
                "5 minutes to restore attention. Consider stepping away "
                "from the screen briefly."
            )
        elif break_duration_min < 8:
            return (
                "Good micro-break! The Pomodoro method recommends around "
                "5 minutes. You're in a solid range for attention restoration."
            )
        elif break_duration_min <= 20:
            return (
                "Nice break length! The DeskTime 52/17 study and ultradian "
                "rhythm research both support breaks in the 15–20 minute range "
                "for deep recovery."
            )
        elif break_duration_min <= 35:
            return (
                "Extended break — this is the Pomodoro 'long break' zone. "
                "Great after several focused sprints. Consider this the "
                "upper end for maintaining momentum."
            )
        else:
            return (
                "Heads up: your break is getting long (over 35 min). "
                "Research suggests it can be harder to re-engage after very "
                "long breaks. Consider easing back into work when ready."
            )

    def suggest_break_length(self, work_duration_min: float) -> float:
        """Suggest a break length based on how long the user has worked."""
        if work_duration_min < 25:
            return 5.0   # Pomodoro micro-break
        elif work_duration_min < 55:
            return 10.0  # mid-range
        elif work_duration_min < 95:
            return 17.0  # DeskTime-style
        else:
            return 20.0  # ultradian full recovery

    def format_research_for_display(self) -> List[dict]:
        """Format research entries for the 'Learn More' UI section."""
        return [
            {
                "title": e.title,
                "summary": e.summary,
                "optimal_work": f"{e.optimal_work_min:.0f} min" if e.optimal_work_min else "Varies",
                "optimal_break": f"{e.optimal_break_min:.0f} min" if e.optimal_break_min else "Varies",
                "citation": e.citation,
                "url": e.url,
            }
            for e in self.entries
        ]


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Contains a mini "knowledge base" of productivity research and provides
#   contextual advice about break lengths. No internet required — it's all
#   baked into the app.
#
# Key classes:
#   - ResearchEntry: dataclass holding one research finding.
#   - BreakResearch: provides advice methods the UI calls.
#     suggest_break_length() maps work duration → recommended break.
#     get_break_advice() evaluates an actual break and gives feedback.
#
# Data flow:
#   User ends break → UI calls get_break_advice(duration) → string displayed
#   User about to break → UI calls suggest_break_length(work_min) → number
#   "Learn More" panel → format_research_for_display() → list of dicts
#
# Interviewer-friendly talking points:
#   1. Hardcoded knowledge vs API: for a local-first app, baking research in
#      avoids network dependencies. Trade-off: needs manual updates.
#   2. The thresholds in get_break_advice() are based on research ranges,
#      not arbitrary. Each maps to a cited study.
#   3. This is "guidance only, non-medical" — important disclaimer for
#      productivity tools that touch wellbeing.
