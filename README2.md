# BurnoutTracker — Interview Notes

## System Overview (Plain English)

BurnoutTracker is a desktop productivity app that helps you work smarter. You start a work session, and it tracks when you take breaks, when you procrastinate, and when you burn out. Over time, it learns your patterns and starts predicting when you'll need a break BEFORE you burn out.

There's also a cute animated desktop buddy (think MapleStory chibi character) that lives on your screen and nudges you with reminders.

---

## Key Components

### 1. Data Layer (`src/data/`)
- **database.py**: Opens the SQLite database and creates all tables
- **models.py**: Python dataclasses that define the shape of data (Session, Task, Category, Event)
- **repository.py**: The ONLY place SQL queries live. Every other module calls repository methods instead of writing SQL

**Why this matters:** The Repository Pattern means if you ever switch databases (SQLite → Postgres), you only change ONE file.

### 2. Service Layer (`src/services/`)
- **session_service.py**: The state machine that controls work sessions. Enforces rules like "you can't start a break while already on break"
- **tracking_service.py**: Runs background timers that prompt you for check-ins (using Qt timers for thread safety)
- **break_research.py**: Contains baked-in productivity research (Pomodoro, DeskTime 52/17, etc.) and gives contextual advice

**Why this matters:** Business logic is separated from UI. You could build a CLI version using the same services.

### 3. ML Engine (`src/ml/`)
- **predictor.py**: Predicts time-to-burnout, time-to-procrastination, optimal session length, etc.

**How it works (simple terms):**
- Looks at your past sessions and extracts values (e.g., "it took 35 min to burn out last time")
- If you have 8+ sessions: fits a trend line (linear regression) to predict the next value
- If you have 3-7 sessions: uses a weighted average that favors recent sessions (exponential moving average)
- If you have <3 sessions: says "not enough data" and waits
- Always checks category-specific data first, falls back to global averages

### 4. Animation Engine (`src/animation/`)
- **sprite_engine.py**: Finite state machine for animations (idle, blink, walk, jump, angry, attack)
- **sprite_generator.py**: Programmatically draws pixel art sprites (no copyrighted assets)
- **buddy_widget.py**: Transparent overlay window that shows the character on your desktop
- **sound_manager.py**: Generates and plays retro SFX from sine waves

### 5. UI Layer (`src/ui/`)
- **main_window.py**: Central hub that wires everything together
- **dashboard_widget.py**: Stats dashboard with charts and filters
- **settings_widget.py**: Toggle animations, adjust volume, export data
- **plot_backend.py**: Generates dark-mode charts (swappable with MATLAB)
- **styles.py**: Dark theme CSS for the entire app

---

## How Reminders Work

1. When you start working, a **burnout check timer** starts (default: every 45 min, or ML-predicted interval)
2. When the timer fires, the buddy does a jump animation + chime, and a dialog asks "Are you burnt out?"
3. If you click "I'm Procrastinating," a **5-minute nag loop** starts with progressively aggressive animations
4. If you take a break, a **30-minute elapsed timer** starts and tells you how long you've been away
5. All reminders and responses are logged to the database for ML training

---

## How ML Predictions Work (Simple Terms)

Think of it like this: the app keeps a diary of your work patterns.

**Training:** After every 5 sessions, it reads all your past data and learns:
- "You usually burn out after 40 minutes of coding"
- "You take your first break at 25 minutes"
- "Your typical focused work block is 22 minutes"

**Prediction:** When you start a new session, it looks up predictions for your current category and shows them. It uses these to set smarter timer intervals.

**Technical details:**
- Linear regression: draws a trend line through your data points (like a best-fit line in stats class)
- EMA (exponential moving average): weighted average where recent sessions count more (alpha=0.3 means the latest session contributes 30%)
- Clamping: predictions are bounded to 0.5x-2x of the mean, preventing wild extrapolation

---

## How the DB Schema Supports Everything

```
categories ──< tasks ──< sessions ──< events
                                   ──< reminder_logs
```

- **categories** and **tasks**: two-level grouping for work
- **sessions**: one per "Begin Working" → "Stop Working" cycle
  - Stores pre-computed aggregates (net_focused_min, focus_ratio) for fast dashboard rendering
- **events**: the source of truth — every start/stop/burnout is timestamped
  - We can always recompute session aggregates from events
- **reminder_logs**: what the buddy asked and what you answered
- **model_versions**: ML model artifacts with versioning for rollback

---

## Common Pitfalls and How We Avoided Them

### 1. State Machine Corruption
**Problem:** What if the user clicks "Start Break" twice?
**Solution:** SessionService enforces valid transitions. You can only start a break from the WORKING state. Invalid transitions raise RuntimeError.

### 2. Forgotten Intervals
**Problem:** User starts a break, then clicks "Stop Working" without ending the break.
**Solution:** `end_session()` auto-closes any open break or procrastination interval before computing aggregates.

### 3. Overlapping Intervals
**Problem:** Break and procrastination happening simultaneously would corrupt metrics.
**Solution:** The state machine prevents this — you must be in WORKING state to start either one. They're mutually exclusive.

### 4. ML with Tiny Data
**Problem:** New users have 0 sessions. The model can't predict anything.
**Solution:** Tiered fallback: regression → EMA → global → None. The UI gracefully shows "Not enough data yet" and encourages manual logging.

### 5. Wild ML Predictions
**Problem:** Linear regression can predict negative minutes or absurdly large values.
**Solution:** Clamping to [0.5 × mean, 2 × mean] keeps predictions reasonable.

### 6. Thread Safety
**Problem:** Background timers modifying UI from wrong thread causes crashes.
**Solution:** Using QTimer (runs on the Qt event loop) instead of threading.Timer. All callbacks are thread-safe by design.

### 7. Pixel Art Scaling
**Problem:** Scaling pixel art with bilinear interpolation blurs it.
**Solution:** Nearest-neighbor scaling (Qt::FastTransformation) preserves sharp pixel edges.

### 8. Database Performance
**Problem:** Scanning thousands of events for every dashboard refresh.
**Solution:** Pre-computed aggregates on Session rows. Dashboard reads those directly. We CAN recompute from events for auditing, but don't need to for rendering.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│                 main.py                      │
│            (Entry Point)                     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              MainWindow                      │
│   (Creates & wires all components)          │
├─────────┬──────────┬──────────┬─────────────┤
│ Session │Dashboard │Research  │ Settings    │
│   Tab   │  Widget  │  Tab     │  Widget     │
└────┬────┴────┬─────┴──────────┴──────┬──────┘
     │         │                       │
┌────▼────┐ ┌──▼──────────┐  ┌────────▼──────┐
│Session  │ │ Plot        │  │ Sprite Engine │
│Service  │ │ Backend     │  │ + Buddy Widget│
│         │ │(matplotlib) │  │ + Sound Mgr   │
├─────────┤ └─────────────┘  └───────────────┘
│Tracking │
│Service  │
├─────────┤
│Break    │
│Research │
└────┬────┘
     │
┌────▼────┐    ┌──────────┐
│Repository│───▶│  SQLite  │
└────┬────┘    └──────────┘
     │
┌────▼────┐
│ Burnout │
│Predictor│
│  (ML)   │
└─────────┘
```

---

## Quick Interview Q&A

**Q: Why SQLite instead of a cloud database?**
A: This is a local-first desktop app. SQLite is serverless, zero-config, and stores everything in one file. No network dependency, no account needed, your data stays on your machine.

**Q: Why PySide6 instead of Electron?**
A: PySide6 gives native OS integration (transparent overlays, system tray) with much lower memory footprint than Electron. The desktop buddy needs a transparent window, which is straightforward in Qt.

**Q: How would you scale this to multiple users?**
A: Swap SQLite for PostgreSQL in the repository layer, add user authentication, put the backend behind a REST API. The modular architecture means only the data layer changes.

**Q: What would you improve next?**
A: (1) Add a QThread for ML training so it doesn't block the UI with large datasets. (2) Add interactive charts (zoom/pan). (3) Add habit streaks and gamification. (4) Mobile companion app with sync.

**Q: How do you ensure data integrity?**
A: Foreign keys are ON, the state machine prevents invalid transitions, aggregates can be recomputed from raw events, and WAL mode prevents database corruption from crashes.
