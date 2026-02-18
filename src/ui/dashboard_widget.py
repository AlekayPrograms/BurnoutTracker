"""
Dashboard Widget — Notion dark mode + 3B1B interactive charts.

Charts are live QtCharts widgets with hover tooltips and glow effects.
Layout uses Notion's dark mode color scheme for a clean, refined look.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDateEdit, QPushButton, QScrollArea, QFrame,
    QSizePolicy,
)
from PySide6.QtCharts import QChartView

from src.data.repository import Repository
from src.ui import plot_backend

logger = logging.getLogger(__name__)

# Notion dark mode palette
_BG       = "#191919"
_SURFACE  = "#252525"
_HOVER    = "#2f2f2f"
_BORDER   = "#333333"
_TEXT     = "#e3e3e3"
_MUTED    = "#9b9a97"
_DIM      = "#5a5a5a"


class MetricCard(QFrame):
    """Notion-style metric card — neon value on dark surface."""

    def __init__(self, label: str, accent: str = "#58C4DD",
                 tooltip: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(70)
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: {_SURFACE};
                border-radius: 6px;
                border: 1px solid {_BORDER};
            }}
            MetricCard:hover {{
                background-color: {_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(2)

        self.value_label = QLabel("—")
        self.value_label.setStyleSheet(f"""
            font-size: 20px; font-weight: 500; color: {accent};
            background: transparent;
        """)

        # Bottom row: label + help icon
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)

        self.name_label = QLabel(label.lower())
        self.name_label.setStyleSheet(f"""
            font-size: 9px; color: {_DIM}; font-weight: 400;
            background: transparent; letter-spacing: 0.5px;
        """)
        self.name_label.setWordWrap(True)
        bottom.addWidget(self.name_label)
        bottom.addStretch()

        if tooltip:
            help_label = QLabel("?")
            help_label.setFixedSize(14, 14)
            help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            help_label.setStyleSheet(f"""
                font-size: 8px; font-weight: 600; color: {_DIM};
                background: {_BORDER}; border-radius: 7px;
            """)
            help_label.setToolTip(f'<span style="color: white;">{tooltip.replace(chr(10), "<br>")}</span>')
            bottom.addWidget(help_label)

        layout.addWidget(self.value_label)
        layout.addLayout(bottom)

    def set_value(self, value: Optional[float], fmt: str = "{:.1f}",
                  suffix: str = "") -> None:
        if value is not None:
            self.value_label.setText(fmt.format(value) + suffix)
        else:
            self.value_label.setText("—")


class SectionHeader(QWidget):
    """Notion-style section label — understated, clean."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 16, 0, 6)
        layout.setSpacing(0)

        label = QLabel(text.lower())
        label.setStyleSheet(f"""
            font-size: 11px; font-weight: 600; color: {_MUTED};
            background: transparent; letter-spacing: 1px;
        """)
        layout.addWidget(label)
        layout.addStretch()


class ChartSlot(QFrame):
    """Container that holds a QChartView widget — swappable on refresh."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            ChartSlot {{
                background-color: {_SURFACE};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(0)
        self._current_view: Optional[QChartView] = None
        self.setMinimumHeight(220)

    def set_chart(self, view: QChartView) -> None:
        """Replace the current chart with a new one."""
        if self._current_view is not None:
            self._layout.removeWidget(self._current_view)
            self._current_view.deleteLater()
        self._current_view = view
        view.setStyleSheet(f"background: {_SURFACE}; border: none; border-radius: 6px;")
        self._layout.addWidget(view)


class InsightPanel(QFrame):
    """ML-powered recommendation panel at the top of the dashboard."""

    _ACCENT = "#89b4fa"
    _ICON_BG = "#1a2a3a"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            InsightPanel {{
                background-color: {_SURFACE};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        icon = QLabel("💡")
        icon.setStyleSheet(f"""
            font-size: 14px; background: {self._ICON_BG};
            border-radius: 4px; padding: 2px 5px;
        """)
        header.addWidget(icon)
        title = QLabel("recommendations")
        title.setStyleSheet(f"""
            font-size: 11px; font-weight: 600; color: {self._ACCENT};
            background: transparent; letter-spacing: 1px;
        """)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Insight text area
        self._insight_label = QLabel("Collecting data...")
        self._insight_label.setWordWrap(True)
        self._insight_label.setStyleSheet(f"""
            font-size: 12px; color: {_TEXT}; background: transparent;
            line-height: 1.5;
        """)
        layout.addWidget(self._insight_label)

    def update_insights(self, stats: dict, repo) -> None:
        """Generate recommendations from session stats and ML predictions."""
        from src.ml.predictor import BurnoutPredictor

        predictor = BurnoutPredictor(repo)
        predictor.train_all()
        lines = []

        sessions = stats.get("sessions", [])
        count = stats.get("session_count", 0)

        if count < 3:
            self._insight_label.setText(
                "Need at least 3 sessions to generate recommendations. "
                "Keep tracking!"
            )
            return

        # ── Gather predictions ──
        focus_block_raw = predictor.predict("focus_block_length")
        break_point_from_focus = predictor.predict_break_insertion_point()
        break_len = predictor.suggest_break_length()
        burnout_time = predictor.predict("time_to_burnout")
        proc_time = predictor.predict("time_to_procrastination")
        avg_focus = stats.get("avg_net_focused")
        avg_ratio = stats.get("avg_focus_ratio")

        # Use the EARLIER of focus-block limit and procrastination onset
        # as the recommended break point — no point suggesting 33 min blocks
        # if you start drifting at 29 min.
        candidates = [v for v in [break_point_from_focus, proc_time] if v]
        break_point = min(candidates) if candidates else None

        # ── Optimal focus block ──
        if break_point:
            reason_parts = []
            if focus_block_raw:
                reason_parts.append(
                    f"your focus stretches average <b>{focus_block_raw:.0f} min</b>")
            if proc_time:
                reason_parts.append(
                    f"procrastination tends to start around <b>{proc_time:.0f} min</b>")
            reason = " and ".join(reason_parts)
            lines.append(
                f"<b style='color:#83C167'>Take a break every ~{break_point:.0f} min:</b> "
                f"{reason.capitalize()}. "
                f"Breaking before you drift keeps momentum going."
            )

        # ── Break length ──
        if break_len:
            lines.append(
                f"<b style='color:#58C4DD'>Break length:</b> "
                f"Your average break is about <b>{break_len:.0f} min</b>. "
                f"Keep breaks close to this for best recovery."
            )

        # ── Optimal session structure ──
        if avg_focus and break_point and break_len and break_point > 0:
            n_blocks = max(1, round(avg_focus / break_point))
            n_breaks = max(0, n_blocks - 1)
            focus_total = n_blocks * break_point
            break_total = n_breaks * break_len
            session_total = focus_total + break_total
            lines.append(
                f"<b style='color:#F4D345'>Ideal session:</b> "
                f"~<b>{session_total:.0f} min</b> total "
                f"({focus_total:.0f} min work + {break_total:.0f} min breaks) — "
                f"{n_blocks} focus block{'s' if n_blocks > 1 else ''} "
                f"of ~{break_point:.0f} min"
                + (f" with ~{break_len:.0f} min break{'s' if n_breaks > 1 else ''} in between." if n_breaks > 0 else ".")
            )

        # ── Burnout warning ──
        if burnout_time:
            tip = ""
            if break_point and burnout_time > break_point * 2:
                tip = f" That's roughly {burnout_time / break_point:.0f} focus blocks in."
            lines.append(
                f"<b style='color:#FC6255'>Burnout risk:</b> "
                f"You tend to burn out around <b>{burnout_time:.0f} min</b> "
                f"into a session.{tip} "
                f"Consider wrapping up or taking a longer break before then."
            )

        # ── Focus ratio ──
        if avg_ratio is not None:
            pct = avg_ratio * 100
            if pct >= 80:
                verdict = "Excellent focus efficiency."
                color = "#83C167"
            elif pct >= 60:
                verdict = "Good, but shorter sessions or more breaks could help."
                color = "#F4D345"
            else:
                verdict = "Consider shorter work blocks with structured breaks."
                color = "#FC6255"
            lines.append(
                f"<b style='color:{color}'>Efficiency:</b> "
                f"Your focus ratio is <b>{pct:.0f}%</b>. {verdict}"
            )

        if not lines:
            self._insight_label.setText("Not enough data patterns yet. Keep tracking!")
            return

        self._insight_label.setText("<br>".join(lines))


class DashboardWidget(QWidget):
    """Notion dark + 3B1B interactive analytics dashboard."""

    def __init__(self, repo: Repository, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background-color: {_BG}; border-bottom: 1px solid {_BORDER};")
        header.setFixedHeight(46)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)

        title = QLabel("analytics")
        title.setStyleSheet(f"""
            font-size: 13px; font-weight: 600; color: {_MUTED};
            background: transparent; letter-spacing: 1.5px;
        """)
        hl.addWidget(title)
        hl.addStretch()

        for label_text, factory in [("category", self._mk_cat), ("task", self._mk_task)]:
            hl.addWidget(self._flabel(label_text))
            hl.addWidget(factory())

        hl.addWidget(self._flabel("from"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate((datetime.now() - timedelta(days=30)).date())
        self.date_from.setStyleSheet(self._ds())
        hl.addWidget(self.date_from)

        hl.addWidget(self._flabel("to"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(datetime.now().date())
        self.date_to.setStyleSheet(self._ds())
        hl.addWidget(self.date_to)

        rbtn = QPushButton("refresh")
        rbtn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_SURFACE}; color: {_MUTED};
                border: 1px solid {_BORDER}; border-radius: 4px;
                padding: 4px 14px; font-size: 10px; font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {_HOVER}; color: {_TEXT}; }}
        """)
        rbtn.setFixedHeight(24)
        rbtn.clicked.connect(self.refresh_data)
        hl.addWidget(rbtn)

        self.category_combo.currentIndexChanged.connect(self._update_task_filter)
        outer.addWidget(header)

        # ── Scrollable content ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {_BG}; }}
            QScrollBar:vertical {{
                background: {_BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {_BORDER}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: {_BG};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 24)
        cl.setSpacing(16)

        # ── ML Recommendations ────────────────────────────────────
        self.insight_panel = InsightPanel()
        cl.addWidget(self.insight_panel)

        # ── Overview ──────────────────────────────────────────────
        cl.addWidget(SectionHeader("overview"))

        r1 = QHBoxLayout()
        r1.setSpacing(8)
        self.card_sessions = MetricCard("sessions", "#58C4DD",
            "Total number of work sessions in the selected time range.")
        self.card_avg_focus = MetricCard("avg focus", "#83C167",
            "Average minutes of actual focused work per session,\n"
            "excluding breaks and procrastination.")
        self.card_focus_ratio = MetricCard("focus ratio", "#9A72AC",
            "Percentage of session time spent actively focused.\n"
            "Higher is better — 100% means no breaks or procrastination.")
        self.card_avg_gross = MetricCard("avg duration", "#F4D345",
            "Average total session length including breaks\n"
            "and procrastination time.")
        for c in [self.card_sessions, self.card_avg_focus,
                  self.card_focus_ratio, self.card_avg_gross]:
            r1.addWidget(c)
        cl.addLayout(r1)

        self.chart_sessions = ChartSlot()
        cl.addWidget(self.chart_sessions)

        # ── Time Breakdown ────────────────────────────────────────
        cl.addWidget(SectionHeader("time breakdown"))

        r2 = QHBoxLayout()
        r2.setSpacing(8)
        self.card_avg_break = MetricCard("avg break", "#58C4DD",
            "Average break duration per session in minutes.")
        self.card_avg_proc = MetricCard("avg procrastination", "#FF862F",
            "Average time spent procrastinating per session.\n"
            "Tracked when you click 'I'm Procrastinating' on the buddy.")
        self.card_avg_focus_block = MetricCard("avg focus block", "#83C167",
            "Average length of your longest uninterrupted focus\n"
            "stretch within each session.")
        self.card_avg_interruptions = MetricCard("avg interruptions", "#FC6255",
            "Average number of breaks or procrastination periods\n"
            "per session. Lower means more sustained focus.")
        for c in [self.card_avg_break, self.card_avg_proc,
                  self.card_avg_focus_block, self.card_avg_interruptions]:
            r2.addWidget(c)
        cl.addLayout(r2)

        cr2 = QHBoxLayout()
        cr2.setSpacing(10)
        self.chart_focus = ChartSlot()
        self.chart_histogram = ChartSlot()
        cr2.addWidget(self.chart_focus)
        cr2.addWidget(self.chart_histogram)
        cl.addLayout(cr2)

        # ── Behavioral Timing ─────────────────────────────────────
        cl.addWidget(SectionHeader("behavioral timing"))

        r3 = QHBoxLayout()
        r3.setSpacing(8)
        self.card_time_burnout = MetricCard("time to burnout", "#FC6255",
            "Average minutes into a session before burnout is reported.\n"
            "Helps you understand your stamina limit.")
        self.card_time_proc = MetricCard("time to procrastination", "#FF862F",
            "Average minutes into a session before procrastination starts.\n"
            "Shows when your focus typically begins to drift.")
        self.card_time_break = MetricCard("time to break", "#58C4DD",
            "Average minutes into a session before taking your first break.\n"
            "Useful for planning optimal break intervals.")
        for c in [self.card_time_burnout, self.card_time_proc, self.card_time_break]:
            r3.addWidget(c)
        r3.addStretch()
        cl.addLayout(r3)

        cr3 = QHBoxLayout()
        cr3.setSpacing(10)
        self.chart_timing = ChartSlot()
        self.chart_ratio = ChartSlot()
        cr3.addWidget(self.chart_timing)
        cr3.addWidget(self.chart_ratio)
        cl.addLayout(cr3)

        # ── Category Analysis ─────────────────────────────────────
        cl.addWidget(SectionHeader("category analysis"))
        self.chart_category = ChartSlot()
        cl.addWidget(self.chart_category)

        cl.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _mk_cat(self) -> QComboBox:
        self.category_combo = QComboBox()
        self.category_combo.addItem("All", None)
        self.category_combo.setMinimumWidth(90)
        self.category_combo.setStyleSheet(self._cs())
        return self.category_combo

    def _mk_task(self) -> QComboBox:
        self.task_combo = QComboBox()
        self.task_combo.addItem("All", None)
        self.task_combo.setMinimumWidth(90)
        self.task_combo.setStyleSheet(self._cs())
        return self.task_combo

    @staticmethod
    def _flabel(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 9px; color: {_DIM}; font-weight: 400;
            background: transparent; padding-left: 8px; letter-spacing: 0.5px;
        """)
        return lbl

    @staticmethod
    def _cs() -> str:
        return f"""
            QComboBox {{
                background-color: {_SURFACE}; color: {_TEXT};
                border: 1px solid {_BORDER}; border-radius: 4px;
                padding: 3px 8px; font-size: 10px; min-width: 80px;
            }}
            QComboBox:hover {{ border-color: #444; }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QComboBox QAbstractItemView {{
                background-color: {_SURFACE}; color: {_TEXT};
                border: 1px solid {_BORDER}; selection-background-color: {_HOVER};
            }}
        """

    @staticmethod
    def _ds() -> str:
        return f"""
            QDateEdit {{
                background-color: {_SURFACE}; color: {_TEXT};
                border: 1px solid {_BORDER}; border-radius: 4px;
                padding: 3px 6px; font-size: 10px;
            }}
            QDateEdit:hover {{ border-color: #444; }}
        """

    @Slot()
    def refresh_data(self) -> None:
        cat_id = self.category_combo.currentData()
        task_id = self.task_combo.currentData()
        start_after = datetime.combine(self.date_from.date().toPython(), datetime.min.time())
        start_before = datetime.combine(self.date_to.date().toPython(), datetime.max.time())

        stats = self.repo.get_dashboard_stats(
            category_id=cat_id, task_id=task_id,
            start_after=start_after, start_before=start_before,
        )

        # Metric cards
        self.card_sessions.set_value(stats["session_count"], "{:.0f}")
        self.card_avg_focus.set_value(stats["avg_net_focused"], suffix=" min")
        self.card_avg_gross.set_value(stats["avg_gross_duration"], suffix=" min")
        self.card_focus_ratio.set_value(
            stats["avg_focus_ratio"] * 100 if stats["avg_focus_ratio"] else None,
            suffix="%"
        )
        self.card_avg_break.set_value(stats["avg_break_duration"], suffix=" min")
        self.card_avg_proc.set_value(stats["avg_procrastination_duration"], suffix=" min")
        self.card_avg_focus_block.set_value(stats["avg_longest_focus_block"], suffix=" min")
        self.card_avg_interruptions.set_value(stats["avg_interruptions"], "{:.1f}")
        self.card_time_burnout.set_value(stats["avg_time_to_burnout"], suffix=" min")
        self.card_time_proc.set_value(stats["avg_time_to_procrastination"], suffix=" min")
        self.card_time_break.set_value(stats["avg_time_to_break"], suffix=" min")

        # Interactive charts (QChartView widgets)
        sessions = stats["sessions"]
        self.chart_sessions.set_chart(plot_backend.plot_sessions_over_time(sessions))
        self.chart_focus.set_chart(plot_backend.plot_focus_metrics(stats))
        self.chart_histogram.set_chart(
            plot_backend.plot_focus_block_histogram(stats["focus_block_distribution"]))
        self.chart_timing.set_chart(
            plot_backend.plot_burnout_procrastination_timing(stats))
        self.chart_ratio.set_chart(plot_backend.plot_focus_ratio_trend(sessions))
        self.chart_category.set_chart(
            plot_backend.plot_category_comparison(sessions, self.repo))

        # ML recommendations
        self.insight_panel.update_insights(stats, self.repo)

        logger.info("Dashboard refreshed: %d sessions", stats["session_count"])

    def load_filters(self) -> None:
        self.category_combo.clear()
        self.category_combo.addItem("All", None)
        for cat in self.repo.list_categories():
            self.category_combo.addItem(cat.name, cat.id)
        self._update_task_filter()

    @Slot()
    def _update_task_filter(self) -> None:
        cat_id = self.category_combo.currentData()
        self.task_combo.clear()
        self.task_combo.addItem("All", None)
        for task in self.repo.list_tasks(cat_id):
            self.task_combo.addItem(task.name, task.id)
