"""
Main Window — the central hub of BurnoutTracker.

Contains:
  - Session control panel (Begin Working, breaks, burnout, etc.)
  - Live timer display
  - Buddy interaction area
  - Tab navigation to Dashboard, Research, Settings
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot, Signal
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QLineEdit, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QTextBrowser, QFrame,
    QSizePolicy, QSystemTrayIcon, QMenu, QApplication,
)

from src.data.database import Database
from src.data.repository import Repository
from src.services.session_service import SessionService, SessionState
from src.services.tracking_service import TrackingService
from src.services.break_research import BreakResearch
from src.ml.predictor import BurnoutPredictor
from src.animation.sprite_engine import SpriteEngine
from src.animation.buddy_widget import BuddyWidget
from src.animation.sound_manager import SoundManager
from src.ui.dashboard_widget import DashboardWidget
from src.ui.settings_widget import SettingsWidget
from src.ui.styles import DARK_STYLESHEET

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """The main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BurnoutTracker")
        self.setMinimumSize(900, 650)
        self.resize(1050, 750)

        # ── Initialize core systems ─────────────────────────────────────
        self.db = Database()
        self.db.connect()
        self.repo = Repository(self.db.conn)
        self.session_svc = SessionService(self.repo)
        self.break_research = BreakResearch()
        self.predictor = BurnoutPredictor(self.repo)
        self.sprite_engine = SpriteEngine()
        self.sound = SoundManager()

        # Tracking service with callbacks
        self.tracking_svc = TrackingService(
            self.repo, self.session_svc,
            on_burnout_check=self._on_burnout_check,
            on_procrastination_reminder=self._on_procrastination_reminder,
            on_break_elapsed=self._on_break_elapsed,
        )

        # ── Live timer ──────────────────────────────────────────────────
        self._live_timer = QTimer()
        self._live_timer.timeout.connect(self._update_timer_display)
        self._live_timer.setInterval(1000)

        # ── Build UI ────────────────────────────────────────────────────
        self._build_ui()

        # ── Initialize sprite engine ────────────────────────────────────
        self.sprite_engine.load_sprites()
        self.sprite_engine.start()

        # ── Desktop buddy ──────────────────────────────────────────────
        self.buddy = BuddyWidget(self.sprite_engine)
        self._connect_buddy_signals()
        self.buddy.show()

        # ── System tray ────────────────────────────────────────────────
        self._setup_tray()

        # ── Train ML on launch ──────────────────────────────────────────
        if self.repo.count_sessions() >= 3:
            self.predictor.train_all()

        self._update_button_states()

        # ── Start hidden — interaction is buddy-driven ─────────────────
        self.hide()

    # ── UI Construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Session Control
        self.session_tab = self._build_session_tab()
        self.tabs.addTab(self.session_tab, "Session")

        # Tab 2: Dashboard
        self.dashboard = DashboardWidget(self.repo)
        self.tabs.addTab(self.dashboard, "Dashboard")

        # Tab 3: Research
        self.research_tab = self._build_research_tab()
        self.tabs.addTab(self.research_tab, "Learn More")

        # Tab 4: Settings
        self.settings_widget = SettingsWidget(
            self.repo, self.sprite_engine, self.sound
        )
        self.settings_widget.settings_changed.connect(self._on_settings_changed)
        self.tabs.addTab(self.settings_widget, "Settings")

        # Refresh dashboard when switching to it
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_session_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── State display ───────────────────────────────────────────
        self.state_label = QLabel("Ready to work")
        self.state_label.setObjectName("state_label")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.state_label)

        # ── Timer display ───────────────────────────────────────────
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.timer_label)

        # ── Task info ───────────────────────────────────────────────
        self.task_info_label = QLabel("")
        self.task_info_label.setObjectName("subtitle")
        self.task_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.task_info_label)

        # ── ML insight ──────────────────────────────────────────────
        self.insight_label = QLabel("")
        self.insight_label.setObjectName("subtitle")
        self.insight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insight_label.setWordWrap(True)
        layout.addWidget(self.insight_label)

        # ── Primary buttons ─────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_begin = QPushButton("Begin Working")
        self.btn_begin.setObjectName("primary")
        self.btn_begin.setMinimumHeight(48)
        self.btn_begin.clicked.connect(self._on_begin_working)
        btn_layout.addWidget(self.btn_begin)

        self.btn_stop = QPushButton("Stop Working")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setMinimumHeight(48)
        self.btn_stop.clicked.connect(self._on_stop_working)
        btn_layout.addWidget(self.btn_stop)

        layout.addLayout(btn_layout)

        # ── Secondary buttons ───────────────────────────────────────
        sec_layout = QHBoxLayout()
        sec_layout.setSpacing(12)

        self.btn_break = QPushButton("Start Break")
        self.btn_break.clicked.connect(self._on_break)
        sec_layout.addWidget(self.btn_break)

        self.btn_procrastinate = QPushButton("I'm Procrastinating")
        self.btn_procrastinate.setObjectName("warning")
        self.btn_procrastinate.clicked.connect(self._on_procrastinate)
        sec_layout.addWidget(self.btn_procrastinate)

        self.btn_burnout = QPushButton("I'm Burnt Out")
        self.btn_burnout.setObjectName("danger")
        self.btn_burnout.clicked.connect(self._on_burnout)
        sec_layout.addWidget(self.btn_burnout)

        self.btn_resume = QPushButton("Resume Working")
        self.btn_resume.setObjectName("success")
        self.btn_resume.clicked.connect(self._on_resume)
        sec_layout.addWidget(self.btn_resume)

        layout.addLayout(sec_layout)

        # ── Break advice area ───────────────────────────────────────
        self.advice_label = QLabel("")
        self.advice_label.setObjectName("subtitle")
        self.advice_label.setWordWrap(True)
        self.advice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.advice_label)

        layout.addStretch()
        return widget

    def _build_research_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Break Research & Productivity Science")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("Non-medical productivity guidance based on published research.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            "QTextBrowser { background-color: #313244; border-radius: 8px; padding: 12px; }"
        )

        html_parts = []
        for entry in self.break_research.format_research_for_display():
            html_parts.append(f"""
            <div style="margin-bottom: 20px; padding: 12px; background: #45475a; border-radius: 8px;">
                <h3 style="color: #89b4fa; margin: 0;">{entry['title']}</h3>
                <p style="color: #cdd6f4;">{entry['summary']}</p>
                <p style="color: #a6adc8;">
                    <b>Optimal work:</b> {entry['optimal_work']} &nbsp;|&nbsp;
                    <b>Optimal break:</b> {entry['optimal_break']}
                </p>
                <p style="color: #a6adc8; font-size: 11px;">
                    {entry['citation']}<br>
                    <a href="{entry['url']}" style="color: #89b4fa;">{entry['url']}</a>
                </p>
            </div>
            """)

        browser.setHtml("".join(html_parts))
        layout.addWidget(browser)
        return widget

    def _setup_tray(self) -> None:
        """System tray icon for minimizing to tray."""
        self.tray = QSystemTrayIcon(self)
        # Use a default icon — we'll generate a proper one later
        self.tray.setToolTip("BurnoutTracker")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ── Buddy signal wiring ──────────────────────────────────────────────

    def _connect_buddy_signals(self) -> None:
        """Wire up the buddy's speech bubble menu signals."""
        self.buddy.begin_working.connect(self._on_begin_working)
        self.buddy.stop_working.connect(self._on_stop_working)
        self.buddy.take_break.connect(self._on_break)
        self.buddy.procrastinating.connect(self._on_procrastinate)
        self.buddy.burnout.connect(self._on_burnout)
        self.buddy.resume_working.connect(self._on_resume)
        self.buddy.open_dashboard.connect(self._on_open_dashboard)
        self.buddy.open_settings.connect(self._on_open_settings)
        self.buddy.quit_app.connect(self._quit_app)

    @Slot()
    def _on_open_dashboard(self) -> None:
        """Show main window with dashboard tab selected."""
        self.tabs.setCurrentIndex(1)
        self.dashboard.load_filters()
        self.dashboard.refresh_data()
        self.show()
        self.raise_()
        self.activateWindow()

    @Slot()
    def _on_open_settings(self) -> None:
        """Show main window with settings tab selected."""
        self.tabs.setCurrentIndex(3)
        self.show()
        self.raise_()
        self.activateWindow()

    def _sync_buddy_state(self) -> None:
        """Keep the buddy's menu context in sync with session state."""
        state_map = {
            SessionState.IDLE: "idle",
            SessionState.WORKING: "working",
            SessionState.ON_BREAK: "break",
            SessionState.PROCRASTINATING: "procrastinating",
        }
        self.buddy.set_user_state(state_map.get(self.session_svc.state, "idle"))

    # ── Session actions ─────────────────────────────────────────────────

    @Slot()
    def _on_begin_working(self) -> None:
        """Start a new work session — prompt for task."""
        # Show window temporarily for the task dialog
        self.show()
        self.raise_()
        self.tabs.setCurrentIndex(0)

        dialog = TaskInputDialog(self.session_svc, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.hide()
            return

        task_id = dialog.selected_task_id
        if task_id is None:
            self.hide()
            return

        task = self.repo.get_task(task_id)
        cat = self.repo.get_category(task.category_id) if task else None

        session = self.session_svc.begin_session(task_id)

        self.task_info_label.setText(
            f"Task: {task.name}  |  Category: {cat.name if cat else '?'}"
        )

        # ML-powered insight
        self._show_ml_insight(cat.id if cat else None)

        # Start tracking timers
        predicted = self.predictor.predict("time_to_burnout", cat.id if cat else None)
        self.tracking_svc.start_work_tracking(predicted)
        self._live_timer.start()
        self._update_button_states()
        self._sync_buddy_state()
        self.sound.play("popup_prompt")

        # Hide main window — the buddy stays on screen
        self.hide()

    @Slot()
    def _on_stop_working(self) -> None:
        if self.session_svc.state == SessionState.IDLE:
            return
        session = self.session_svc.end_session()
        self.tracking_svc.stop_all()
        self._live_timer.stop()
        self.timer_label.setText("00:00:00")
        self.task_info_label.setText("")
        self.insight_label.setText("")
        self.advice_label.setText("")
        self.state_label.setText("Session complete!")
        self._update_button_states()
        self._sync_buddy_state()
        self.sound.play("timer_complete")

        # Show break advice if applicable
        if session.break_duration_min and session.break_duration_min > 0:
            advice = self.break_research.get_break_advice(session.break_duration_min)
            self.advice_label.setText(advice)

        # Retrain ML if enough sessions
        count = self.repo.count_sessions()
        if count >= 3 and count % 5 == 0:
            self.predictor.train_all()

    @Slot()
    def _on_break(self) -> None:
        if self.session_svc.state == SessionState.WORKING:
            self.session_svc.start_break()
            self.tracking_svc.stop_work_tracking()
            self.tracking_svc.start_break_tracking()

            # Suggest break length
            elapsed = self.session_svc.get_elapsed_minutes()
            ml_suggest = self.predictor.suggest_break_length()
            research_suggest = self.break_research.suggest_break_length(elapsed)
            suggest = ml_suggest or research_suggest
            self.advice_label.setText(f"Suggested break: ~{suggest:.0f} min")

            self._update_button_states()
            self._sync_buddy_state()
        elif self.session_svc.state == SessionState.ON_BREAK:
            self.session_svc.end_break()
            self.tracking_svc.stop_break_tracking()
            self.tracking_svc.start_work_tracking()
            self.advice_label.setText("")
            self._update_button_states()
            self._sync_buddy_state()

    @Slot()
    def _on_procrastinate(self) -> None:
        if self.session_svc.state != SessionState.WORKING:
            return
        self.session_svc.start_procrastination()
        self.tracking_svc.stop_work_tracking()
        self.tracking_svc.start_procrastination_reminders()
        self._update_button_states()
        self._sync_buddy_state()

    @Slot()
    def _on_burnout(self) -> None:
        if self.session_svc.state == SessionState.IDLE:
            return
        self.session_svc.log_burnout()
        reply = QMessageBox.question(
            self, "Burnout Logged",
            "Burnout logged. Do you want to take a break or end the session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_break()
        else:
            self._on_stop_working()

    @Slot()
    def _on_resume(self) -> None:
        """Resume working from break or procrastination."""
        state = self.session_svc.state
        if state == SessionState.ON_BREAK:
            elapsed = self.session_svc.get_current_interval_minutes()
            self.session_svc.end_break()
            self.tracking_svc.stop_break_tracking()
            advice = self.break_research.get_break_advice(elapsed)
            self.advice_label.setText(advice)
        elif state == SessionState.PROCRASTINATING:
            self.session_svc.end_procrastination()
            self.tracking_svc.stop_procrastination_reminders()
            self.advice_label.setText("Nice! Back to focus mode.")
        else:
            return

        self.tracking_svc.start_work_tracking()
        self._update_button_states()
        self._sync_buddy_state()

    # ── Tracking callbacks ──────────────────────────────────────────────

    def _on_burnout_check(self) -> None:
        self.sprite_engine.play_notification()
        self.sound.play("jump_notify")
        if not self.predictor.has_enough_data():
            msg = (
                "Hey! How are you doing?\n\n"
                "I don't have enough data yet to predict burnout timing. "
                "Keep using the 'I'm Burnt Out' button when you feel it, "
                "and I'll learn your patterns!"
            )
        else:
            msg = "Hey! Are you feeling burnt out?"

        reply = QMessageBox.question(
            self, "Burnout Check", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_burnout()

    def _on_procrastination_reminder(self, elapsed_min: float) -> None:
        self.sprite_engine.play_aggressive()
        self.sound.play("procrastination_nag")
        QMessageBox.warning(
            self, "Procrastination Alert",
            f"You've been procrastinating for {elapsed_min:.0f} minutes.\n"
            "Want to get back to work?",
        )

    def _on_break_elapsed(self, elapsed_min: float) -> None:
        self.sprite_engine.play_notification()
        self.sound.play("jump_notify")
        advice = self.break_research.get_break_advice(elapsed_min)
        QMessageBox.information(
            self, "Break Update",
            f"Your break has been {elapsed_min:.0f} minutes.\n\n{advice}",
        )

    # ── Timer display ───────────────────────────────────────────────────

    @Slot()
    def _update_timer_display(self) -> None:
        elapsed = self.session_svc.get_elapsed_minutes()
        hours = int(elapsed // 60)
        mins = int(elapsed % 60)
        secs = int((elapsed * 60) % 60)
        self.timer_label.setText(f"{hours:02d}:{mins:02d}:{secs:02d}")

        state = self.session_svc.state
        if state == SessionState.WORKING:
            self.state_label.setText("Working...")
        elif state == SessionState.ON_BREAK:
            brk_min = self.session_svc.get_current_interval_minutes()
            self.state_label.setText(f"On Break ({brk_min:.0f} min)")
        elif state == SessionState.PROCRASTINATING:
            proc_min = self.session_svc.get_current_interval_minutes()
            self.state_label.setText(f"Procrastinating ({proc_min:.0f} min)")

    # ── ML insights ─────────────────────────────────────────────────────

    def _show_ml_insight(self, category_id: Optional[int]) -> None:
        parts = []
        burnout = self.predictor.predict("time_to_burnout", category_id)
        if burnout:
            parts.append(f"Predicted burnout in ~{burnout:.0f} min")

        focus = self.predictor.predict("net_focused_time", category_id)
        if focus:
            parts.append(f"Expected focus: ~{focus:.0f} min")

        optimal = self.predictor.predict_optimal_session_length(category_id)
        if optimal:
            parts.append(f"Optimal session: ~{optimal:.0f} min")

        break_point = self.predictor.predict_break_insertion_point(category_id)
        if break_point:
            parts.append(f"Break suggested at ~{break_point:.0f} min")

        if parts:
            self.insight_label.setText(" | ".join(parts))
        else:
            self.insight_label.setText(
                "Not enough data for predictions yet. Keep tracking!"
            )

    # ── Button state management ─────────────────────────────────────────

    def _update_button_states(self) -> None:
        state = self.session_svc.state
        idle = state == SessionState.IDLE
        working = state == SessionState.WORKING
        on_break = state == SessionState.ON_BREAK
        procrastinating = state == SessionState.PROCRASTINATING

        self.btn_begin.setEnabled(idle)
        self.btn_stop.setEnabled(not idle)
        self.btn_break.setEnabled(working or on_break)
        self.btn_break.setText("End Break" if on_break else "Start Break")
        self.btn_procrastinate.setEnabled(working)
        self.btn_burnout.setEnabled(not idle)
        self.btn_resume.setEnabled(on_break or procrastinating)
        self.btn_resume.setVisible(on_break or procrastinating)

    # ── Misc ────────────────────────────────────────────────────────────

    @Slot()
    def _on_settings_changed(self) -> None:
        intervals = self.settings_widget.get_intervals()
        self.tracking_svc.update_intervals(**intervals)
        if hasattr(self, 'buddy'):
            self.buddy.update_scale(self.sprite_engine.scale)

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        if index == 1:  # Dashboard tab
            self.dashboard.load_filters()
            self.dashboard.refresh_data()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_app(self) -> None:
        if self.session_svc.state != SessionState.IDLE:
            reply = QMessageBox.question(
                self, "Session Active",
                "You have an active work session!\n\n"
                "End the session and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.session_svc.end_session()
            self.tracking_svc.stop_all()
            self._live_timer.stop()

        self.buddy.close()
        self.sprite_engine.stop()
        self.db.close()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()


class TaskInputDialog(QDialog):
    """Dialog to select/create a task when starting work."""

    def __init__(self, session_svc: SessionService, parent=None) -> None:
        super().__init__(parent)
        self.session_svc = session_svc
        self.selected_task_id: Optional[int] = None
        self.setWindowTitle("What are you working on?")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        # Task name
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Enter task description...")
        layout.addRow("Task:", self.task_input)

        # Category selector
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        categories = self.session_svc.list_categories()
        for c in categories:
            self.cat_combo.addItem(c.name, c.id)
        self.cat_combo.setCurrentText("")
        self.cat_combo.lineEdit().setPlaceholderText("Select or type new category...")
        layout.addRow("Category:", self.cat_combo)

        # Recent tasks
        self.recent_combo = QComboBox()
        self.recent_combo.addItem("— or pick a recent task —", None)
        tasks = self.session_svc.list_tasks()
        for t in tasks[:20]:
            cat = self.session_svc.repo.get_category(t.category_id)
            label = f"{t.name} ({cat.name})" if cat else t.name
            self.recent_combo.addItem(label, t.id)
        self.recent_combo.currentIndexChanged.connect(self._on_recent_selected)
        layout.addRow("Recent:", self.recent_combo)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @Slot()
    def _on_accept(self) -> None:
        # Check if recent task was selected
        recent_id = self.recent_combo.currentData()
        if recent_id is not None:
            self.selected_task_id = recent_id
            self.accept()
            return

        # Create/find task + category
        task_name = self.task_input.text().strip()
        cat_name = self.cat_combo.currentText().strip()

        if not task_name:
            QMessageBox.warning(self, "Missing Info", "Please enter a task name.")
            return
        if not cat_name:
            QMessageBox.warning(self, "Missing Info", "Please select or enter a category.")
            return

        category = self.session_svc.get_or_create_category(cat_name)
        task = self.session_svc.get_or_create_task(task_name, category.id)
        self.selected_task_id = task.id
        self.accept()

    @Slot(int)
    def _on_recent_selected(self, index: int) -> None:
        task_id = self.recent_combo.currentData()
        if task_id is not None:
            task = self.session_svc.repo.get_task(task_id)
            if task:
                self.task_input.setText(task.name)
                cat = self.session_svc.repo.get_category(task.category_id)
                if cat:
                    idx = self.cat_combo.findText(cat.name)
                    if idx >= 0:
                        self.cat_combo.setCurrentIndex(idx)


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The "control center" of the app. It creates all services, wires them
#   together, and contains the session control UI (buttons, timer, buddy).
#
# Key classes:
#   - MainWindow: QMainWindow subclass. Creates Database, Repository,
#     SessionService, TrackingService, BurnoutPredictor, SpriteEngine,
#     SoundManager, BuddyWidget, and all UI tabs.
#   - TaskInputDialog: popup for entering task + category when starting work.
#
# Data flow (buddy-driven):
#   User clicks buddy → speech bubble menu appears → selects action →
#   buddy emits signal → MainWindow handles it (e.g. begin_working →
#   TaskInputDialog → session_svc.begin_session() → tracking starts).
#   The main window stays hidden unless Dashboard or Settings is requested.
#
# Interviewer-friendly talking points:
#   1. Composition over inheritance: MainWindow OWNS all the services
#      rather than inheriting from them. Clean dependency graph.
#   2. Minimize-to-tray: closeEvent() hides instead of quitting. The buddy
#      stays on screen and the session keeps running.
#   3. ML is non-blocking: predictions happen in the constructor and
#      at the end of sessions. For heavy models you'd use a QThread, but
#      our lightweight models run in <100ms.
