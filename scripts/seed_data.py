"""
Seed Data Generator — creates realistic fake data for development and testing.

Run: python scripts/seed_data.py
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.database import Database
from src.data.repository import Repository


def seed(num_sessions: int = 30) -> None:
    db = Database()
    db.connect()
    repo = Repository(db.conn)

    # ── Categories & Tasks ──────────────────────────────────────────────
    categories_tasks = {
        "Coding": ["Frontend React", "Backend API", "Bug Fixing", "Code Review"],
        "Writing": ["Blog Post", "Documentation", "Research Paper"],
        "Studying": ["CS 440 HW", "Linear Algebra", "Reading Textbook"],
        "Design": ["UI Mockups", "Logo Design", "Wireframes"],
    }

    task_ids = []
    for cat_name, task_names in categories_tasks.items():
        cat = repo.create_category(cat_name)
        for t_name in task_names:
            task = repo.create_task(t_name, cat.id)
            task_ids.append(task.id)

    # ── Generate sessions ───────────────────────────────────────────────
    base_date = datetime.now() - timedelta(days=30)

    for i in range(num_sessions):
        task_id = random.choice(task_ids)
        start = base_date + timedelta(days=i, hours=random.randint(8, 14),
                                       minutes=random.randint(0, 59))

        session = repo.create_session(task_id, start)
        repo.add_event(session.id, "work_start", start)

        cursor = start
        events_in_session = []
        interruption_count = 0
        break_total = 0.0
        proc_total = 0.0
        focus_blocks = []
        last_work_start = start

        # Simulate 1-4 interruptions
        num_interruptions = random.randint(0, 4)
        for _ in range(num_interruptions):
            # Work for 10-60 min
            work_dur = random.uniform(10, 60)
            event_time = cursor + timedelta(minutes=work_dur)

            focus_blocks.append(work_dur)
            interruption_count += 1

            if random.random() < 0.6:
                # Break
                repo.add_event(session.id, "break_start", event_time)
                break_dur = random.uniform(3, 25)
                end_time = event_time + timedelta(minutes=break_dur)
                repo.add_event(session.id, "break_end", end_time)
                break_total += break_dur
                cursor = end_time
            else:
                # Procrastination
                repo.add_event(session.id, "procrastination_start", event_time)
                proc_dur = random.uniform(5, 30)
                end_time = event_time + timedelta(minutes=proc_dur)
                repo.add_event(session.id, "procrastination_end", end_time)
                proc_total += proc_dur
                cursor = end_time

            last_work_start = cursor

        # Maybe a burnout event
        if random.random() < 0.3:
            burnout_time = cursor + timedelta(minutes=random.uniform(5, 20))
            repo.add_event(session.id, "burnout", burnout_time)

        # Final work stretch
        final_work = random.uniform(10, 45)
        focus_blocks.append(final_work)
        end_time = cursor + timedelta(minutes=final_work)
        repo.add_event(session.id, "work_end", end_time)

        # Compute aggregates
        gross = (end_time - start).total_seconds() / 60.0
        net = gross - break_total - proc_total

        session.end_time = end_time
        session.gross_duration_min = gross
        session.break_duration_min = break_total
        session.procrastination_duration_min = proc_total
        session.net_focused_min = max(0, net)
        session.longest_focus_block_min = max(focus_blocks) if focus_blocks else net
        session.interruption_count = interruption_count
        session.focus_ratio = net / gross if gross > 0 else 0

        repo.end_session(session)

    db.close()
    print(f"Seeded {num_sessions} sessions across {len(task_ids)} tasks.")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seed(count)


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this script does:
#   Generates realistic fake data so you can demo the app without working
#   for 30 days first. Creates categories, tasks, and sessions with
#   randomized breaks, procrastination, and burnout events.
#
# Key points:
#   - Realistic distributions: work durations 10-60 min, breaks 3-25 min,
#     procrastination 5-30 min. These match real-world patterns.
#   - Computed aggregates: mimics what SessionService._compute_session_aggregates()
#     does, so the dashboard works immediately with seeded data.
#
# Interviewer-friendly talking points:
#   1. Seed data is essential for development and demos. You can't test a
#      stats dashboard with an empty database.
#   2. The random distributions are tuned to create interesting charts
#      (some sessions have many interruptions, some have none).
#   3. This script uses the same Repository interface as the real app —
#      no raw SQL duplication.
