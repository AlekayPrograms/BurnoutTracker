"""
Settings Panel — animation toggles, sound, intervals, data management.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QFileDialog, QGridLayout, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QFrame,
)

from src.animation.sprite_engine import SpriteEngine
from src.animation.sound_manager import SoundManager
from src.data.repository import Repository

logger = logging.getLogger(__name__)


class SettingsWidget(QWidget):
    """Settings panel for the app."""

    settings_changed = Signal()

    def __init__(
        self,
        repo: Repository,
        sprite_engine: SpriteEngine,
        sound_manager: SoundManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.engine = sprite_engine
        self.sound = sound_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll area so everything fits
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 20)

        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)

        # ── Animation & Sprite (side by side) ────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        anim_group = QGroupBox("Animation")
        anim_layout = QGridLayout(anim_group)
        anim_layout.setSpacing(6)

        toggles = self.engine.config["toggles"]

        self.cb_master = QCheckBox("Master Animation")
        self.cb_master.setChecked(toggles["master_animation"])
        self.cb_master.toggled.connect(lambda v: self._toggle("master_animation", v))
        anim_layout.addWidget(self.cb_master, 0, 0)

        self.cb_blink = QCheckBox("Idle Blink")
        self.cb_blink.setChecked(toggles["idle_blink"])
        self.cb_blink.toggled.connect(lambda v: self._toggle("idle_blink", v))
        anim_layout.addWidget(self.cb_blink, 0, 1)

        self.cb_variants = QCheckBox("Idle Variants")
        self.cb_variants.setChecked(toggles["idle_variants"])
        self.cb_variants.toggled.connect(lambda v: self._toggle("idle_variants", v))
        anim_layout.addWidget(self.cb_variants, 1, 0)

        self.cb_walking = QCheckBox("Idle Walking")
        self.cb_walking.setChecked(toggles["idle_walking"])
        self.cb_walking.toggled.connect(lambda v: self._toggle("idle_walking", v))
        anim_layout.addWidget(self.cb_walking, 1, 1)

        self.cb_jump = QCheckBox("Jump Notify")
        self.cb_jump.setChecked(toggles["jump_notify"])
        self.cb_jump.toggled.connect(lambda v: self._toggle("jump_notify", v))
        anim_layout.addWidget(self.cb_jump, 2, 0)

        self.cb_aggressive = QCheckBox("Aggressive Animation")
        self.cb_aggressive.setChecked(toggles["aggressive_animation"])
        self.cb_aggressive.toggled.connect(lambda v: self._toggle("aggressive_animation", v))
        anim_layout.addWidget(self.cb_aggressive, 2, 1)

        top_row.addWidget(anim_group, 1)

        # Right column: scale + sound stacked
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        scale_group = QGroupBox("Sprite Scale")
        scale_layout = QHBoxLayout(scale_group)
        scale_layout.setContentsMargins(10, 8, 10, 8)

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(50)
        self.scale_slider.setMaximum(500)
        self.scale_slider.setValue(int(self.engine.scale * 100))
        self.scale_label = QLabel(f"{self.engine.scale:.1f}x")
        self.scale_slider.valueChanged.connect(self._on_scale_changed)

        scale_layout.addWidget(QLabel("0.5x"))
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(QLabel("5.0x"))
        scale_layout.addWidget(self.scale_label)
        right_col.addWidget(scale_group)

        sound_group = QGroupBox("Sound")
        sound_layout = QHBoxLayout(sound_group)
        sound_layout.setContentsMargins(10, 8, 10, 8)

        self.cb_sound = QCheckBox("Enabled")
        self.cb_sound.setChecked(self.sound.enabled)
        self.cb_sound.toggled.connect(self._on_sound_toggled)
        sound_layout.addWidget(self.cb_sound)

        sound_layout.addWidget(QLabel("Vol:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(int(self.sound.volume * 100))
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        sound_layout.addWidget(self.volume_slider)

        self.vol_label = QLabel(f"{int(self.sound.volume * 100)}%")
        sound_layout.addWidget(self.vol_label)
        right_col.addWidget(sound_group)

        right_col.addStretch()
        top_row.addLayout(right_col, 1)
        layout.addLayout(top_row)

        # ── Reminder Intervals ──────────────────────────────────────────
        interval_group = QGroupBox("Reminder Intervals (minutes)")
        interval_layout = QGridLayout(interval_group)
        interval_layout.setColumnStretch(1, 0)
        interval_layout.setColumnStretch(3, 0)
        interval_layout.setColumnStretch(5, 1)

        interval_layout.addWidget(QLabel("Burnout check:"), 0, 0)
        self.burnout_spin = QSpinBox()
        self.burnout_spin.setRange(5, 180)
        self.burnout_spin.setValue(45)
        self.burnout_spin.setFixedWidth(70)
        interval_layout.addWidget(self.burnout_spin, 0, 1)

        interval_layout.addWidget(QLabel("  Procrastination nag:"), 0, 2)
        self.proc_spin = QSpinBox()
        self.proc_spin.setRange(1, 30)
        self.proc_spin.setValue(5)
        self.proc_spin.setFixedWidth(70)
        interval_layout.addWidget(self.proc_spin, 0, 3)

        interval_layout.addWidget(QLabel("  Break elapsed:"), 0, 4)
        self.break_spin = QSpinBox()
        self.break_spin.setRange(5, 120)
        self.break_spin.setValue(30)
        self.break_spin.setFixedWidth(70)
        interval_layout.addWidget(self.break_spin, 0, 5)

        layout.addWidget(interval_group)

        # ── Data Management ─────────────────────────────────────────────
        data_group = QGroupBox("Data Management")
        data_layout = QVBoxLayout(data_group)
        data_layout.setSpacing(10)

        # Top buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(30)
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_btn)

        reset_anim_btn = QPushButton("Reset Animation Config")
        reset_anim_btn.setFixedHeight(30)
        reset_anim_btn.clicked.connect(self._reset_animation)
        btn_row.addWidget(reset_anim_btn)

        btn_row.addStretch()

        reset_btn = QPushButton("Reset All Data")
        reset_btn.setObjectName("danger")
        reset_btn.setFixedHeight(30)
        reset_btn.clicked.connect(self._reset_data)
        btn_row.addWidget(reset_btn)
        data_layout.addLayout(btn_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        sep.setFixedHeight(1)
        data_layout.addWidget(sep)

        # Date range delete row
        range_row = QHBoxLayout()
        range_row.setSpacing(6)

        range_label = QLabel("Delete by date range:")
        range_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        range_row.addWidget(range_label)

        range_row.addWidget(QLabel("From"))
        self.del_date_from = QDateEdit()
        self.del_date_from.setCalendarPopup(True)
        self.del_date_from.setDate((datetime.now() - timedelta(days=30)).date())
        self.del_date_from.setFixedWidth(120)
        range_row.addWidget(self.del_date_from)

        range_row.addWidget(QLabel("to"))
        self.del_date_to = QDateEdit()
        self.del_date_to.setCalendarPopup(True)
        self.del_date_to.setDate(datetime.now().date())
        self.del_date_to.setFixedWidth(120)
        range_row.addWidget(self.del_date_to)

        del_range_btn = QPushButton("Delete Range")
        del_range_btn.setObjectName("danger")
        del_range_btn.setFixedHeight(28)
        del_range_btn.clicked.connect(self._delete_date_range)
        range_row.addWidget(del_range_btn)

        range_row.addStretch()
        data_layout.addLayout(range_row)

        # Session history header + refresh
        hist_row = QHBoxLayout()
        hist_label = QLabel("Session History")
        hist_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        hist_row.addWidget(hist_label)
        hist_row.addStretch()
        refresh_table_btn = QPushButton("Refresh")
        refresh_table_btn.setFixedHeight(24)
        refresh_table_btn.setFixedWidth(80)
        refresh_table_btn.clicked.connect(self._refresh_session_table)
        hist_row.addWidget(refresh_table_btn)
        data_layout.addLayout(hist_row)

        # Session table
        self.session_table = QTableWidget()
        self.session_table.setColumnCount(5)
        self.session_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Task", "Duration", ""]
        )
        header = self.session_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.session_table.setColumnWidth(0, 40)
        self.session_table.setColumnWidth(3, 70)
        self.session_table.setColumnWidth(4, 50)
        self.session_table.verticalHeader().setVisible(False)
        self.session_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.session_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.session_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.session_table.setAlternatingRowColors(True)
        self.session_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e2e;
                gridline-color: #313244;
                border: 1px solid #313244;
                border-radius: 6px;
                selection-background-color: #2a4d3a;
                selection-color: #a6e3a1;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #2a4d3a;
                color: #a6e3a1;
            }
            QTableWidget::item:alternate {
                background-color: #232336;
            }
            QTableWidget::item:alternate:selected {
                background-color: #2a4d3a;
                color: #a6e3a1;
            }
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            QHeaderView::section {
                background-color: #181825;
                color: #a6adc8;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 6px 8px;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        data_layout.addWidget(self.session_table, 1)

        layout.addWidget(data_group, 1)
        scroll.setWidget(content)

    # ── Slots ───────────────────────────────────────────────────────────

    def _toggle(self, key: str, value: bool) -> None:
        self.engine.update_toggles({key: value})
        self.settings_changed.emit()

    @Slot(int)
    def _on_scale_changed(self, value: int) -> None:
        scale = value / 100.0
        self.scale_label.setText(f"{scale:.1f}x")
        self.engine.set_scale(scale)
        self.settings_changed.emit()

    @Slot(bool)
    def _on_sound_toggled(self, enabled: bool) -> None:
        self.sound.set_enabled(enabled)

    @Slot(int)
    def _on_volume_changed(self, value: int) -> None:
        vol = value / 100.0
        self.vol_label.setText(f"{value}%")
        self.sound.set_volume(vol)

    def get_intervals(self) -> dict:
        return {
            "burnout_min": self.burnout_spin.value(),
            "proc_min": self.proc_spin.value(),
            "break_min": self.break_spin.value(),
        }

    @Slot()
    def _export_csv(self) -> None:
        csv_text = self.repo.export_sessions_csv()
        if not csv_text:
            QMessageBox.information(self, "Export", "No data to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "burnout_tracker_export.csv", "CSV files (*.csv)"
        )
        if path:
            Path(path).write_text(csv_text, encoding="utf-8")
            QMessageBox.information(self, "Export", f"Data exported to {path}")

    @Slot()
    def _reset_data(self) -> None:
        reply = QMessageBox.warning(
            self, "Reset All Data",
            "This will permanently delete ALL sessions, tasks, and categories.\n"
            "This action cannot be undone.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.reset_all_data()
            QMessageBox.information(self, "Reset", "All data has been reset.")
            self.settings_changed.emit()

    @Slot()
    def _reset_animation(self) -> None:
        self.engine.reset_config()
        QMessageBox.information(self, "Reset", "Animation config reset to defaults.")
        self.settings_changed.emit()

    @Slot()
    def _delete_date_range(self) -> None:
        start = datetime.combine(
            self.del_date_from.date().toPython(), datetime.min.time()
        )
        end = datetime.combine(
            self.del_date_to.date().toPython(), datetime.max.time()
        )
        reply = QMessageBox.warning(
            self, "Delete Sessions",
            f"Delete all sessions from {start.date()} to {end.date()}?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self.repo.delete_sessions_in_range(start, end)
            QMessageBox.information(
                self, "Deleted", f"{count} session(s) deleted."
            )
            self._refresh_session_table()
            self.settings_changed.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_session_table()

    @Slot()
    def _refresh_session_table(self) -> None:
        sessions = self.repo.list_sessions(limit=100)
        self.session_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self.session_table.setRowHeight(row, 32)

            id_item = QTableWidgetItem(str(s.id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.session_table.setItem(row, 0, id_item)

            date_str = s.start_time.strftime("%b %d, %Y  %H:%M") if s.start_time else "—"
            self.session_table.setItem(row, 1, QTableWidgetItem(date_str))

            task = self.repo.get_task(s.task_id)
            task_name = task.name if task else "—"
            self.session_table.setItem(row, 2, QTableWidgetItem(task_name))

            dur = f"{s.gross_duration_min:.0f} min" if s.gross_duration_min else "—"
            dur_item = QTableWidgetItem(dur)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.session_table.setItem(row, 3, dur_item)

            del_btn = QPushButton("Del")
            del_btn.setFixedSize(40, 22)
            del_btn.setToolTip(f"Delete session #{s.id}")
            del_btn.setStyleSheet("""
                QPushButton {
                    background: #313244; color: #cdd6f4;
                    border: 1px solid #585b70; border-radius: 4px;
                    font-size: 10px; font-weight: 600;
                    padding: 0px;
                }
                QPushButton:hover { background: #f38ba8; color: #1e1e2e; border-color: #f38ba8; }
            """)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda checked, sid=s.id: self._delete_single(sid))
            self.session_table.setCellWidget(row, 4, del_btn)

    def _delete_single(self, session_id: int) -> None:
        reply = QMessageBox.warning(
            self, "Delete Session",
            f"Delete session #{session_id}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.delete_session(session_id)
            self._refresh_session_table()
            self.settings_changed.emit()


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The settings panel — checkboxes for animation toggles, sliders for
#   scale and volume, spinboxes for reminder intervals, and buttons for
#   data export/reset.
#
# Key design decisions:
#   - Immediate feedback: toggling a checkbox immediately updates the
#     sprite engine. No "Save" button needed.
#   - Signal emission: settings_changed signal lets the main window
#     react to changes (e.g., restart timers with new intervals).
#   - Confirmation dialogs: destructive actions (reset data) require
#     explicit confirmation. Defense against accidental clicks.
#
# Data flow:
#   User toggles checkbox → _toggle() → engine.update_toggles() → config
#   saved to JSON → settings_changed signal → main window updates.
#
# Interviewer-friendly talking points:
#   1. Qt signals/slots: type-safe observer pattern. The settings widget
#      doesn't know about the main window — it just emits a signal.
#   2. Data export uses repo.export_sessions_csv() — the settings panel
#      doesn't know SQL, it delegates to the repository.
#   3. The reset confirmation uses StandardButton.No as default —
#      defensive UX so pressing Enter doesn't accidentally delete data.
