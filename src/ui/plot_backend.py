"""
Interactive Chart Backend — 3Blue1Brown glow + Notion dark mode.

Uses PySide6.QtCharts for live, hoverable charts. Each data point shows
a tooltip on hover. Lines have a multi-layer glow effect. Smooth spline
curves where possible.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt, QPointF, QMargins
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QLinearGradient, QCursor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QToolTip
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QSplineSeries, QScatterSeries,
    QAreaSeries, QBarSeries, QBarSet, QHorizontalBarSeries,
    QBarCategoryAxis, QValueAxis, QDateTimeAxis, QCategoryAxis,
)

logger = logging.getLogger(__name__)

# ── Notion Dark Mode palette ─────────────────────────────────────────────────
BG        = QColor("#191919")      # Notion dark background
SURFACE   = QColor("#252525")      # Notion dark surface / card
HOVER_BG  = QColor("#2f2f2f")      # Notion dark hover
BORDER    = QColor("#333333")      # Notion dark border
TEXT      = QColor("#e3e3e3")      # Notion primary text
MUTED     = QColor("#9b9a97")      # Notion secondary text
DIM       = QColor("#5a5a5a")      # Notion dimmed text
GRID_CLR  = QColor("#2a2a2a")      # subtle grid

# 3B1B neon accents (from Manim color constants)
BLUE   = "#58C4DD"
GREEN  = "#83C167"
RED    = "#FC6255"
GOLD   = "#F4D345"
TEAL   = "#5CD0B3"
PINK   = "#E48D9E"
PURPLE = "#9A72AC"
ORANGE = "#FF862F"

PALETTE = [BLUE, GREEN, RED, GOLD, TEAL, PINK, PURPLE, ORANGE]


def _base_chart(title: str = "") -> QChart:
    """Create a styled chart with Notion dark background."""
    chart = QChart()
    chart.setBackgroundBrush(QBrush(BG))
    chart.setBackgroundRoundness(0)
    chart.setMargins(QMargins(8, 8, 8, 8))

    if title:
        chart.setTitle(title)
        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Normal)
        chart.setTitleFont(font)
        chart.setTitleBrush(QBrush(MUTED))

    chart.legend().setVisible(False)
    chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
    chart.setAnimationDuration(400)
    return chart


def _value_axis(label: str = "", visible_grid: bool = True) -> QValueAxis:
    """Minimal value axis — Notion-clean."""
    axis = QValueAxis()
    axis.setLabelsColor(DIM)
    axis.setLabelsFont(QFont("Segoe UI", 8))
    axis.setGridLineColor(GRID_CLR)
    axis.setGridLineVisible(visible_grid)
    axis.setLineVisible(False)
    axis.setMinorGridLineVisible(False)
    axis.setTitleText(label)
    axis.setTitleBrush(QBrush(DIM))
    axis.setTitleFont(QFont("Segoe UI", 8))
    return axis


def _datetime_axis(fmt: str = "MMM dd") -> QDateTimeAxis:
    axis = QDateTimeAxis()
    axis.setFormat(fmt)
    axis.setLabelsColor(DIM)
    axis.setLabelsFont(QFont("Segoe UI", 8))
    axis.setGridLineColor(GRID_CLR)
    axis.setGridLineVisible(True)
    axis.setLineVisible(False)
    axis.setMinorGridLineVisible(False)
    return axis


def _cat_axis(categories: list) -> QBarCategoryAxis:
    axis = QBarCategoryAxis()
    axis.append(categories)
    axis.setLabelsColor(MUTED)
    axis.setLabelsFont(QFont("Segoe UI", 8))
    axis.setGridLineVisible(False)
    axis.setLineVisible(False)
    return axis


def _glow_line(chart: QChart, points: list, color_hex: str,
               x_axis, y_axis, width: float = 2.5) -> None:
    """Add a glowing line: 3 faded layers + 1 bright core."""
    color = QColor(color_hex)

    for glow_w, alpha in [(width * 5, 15), (width * 3, 35), (width * 1.8, 70)]:
        glow = QLineSeries()
        for p in points:
            glow.append(p)
        glow_color = QColor(color)
        glow_color.setAlpha(alpha)
        pen = QPen(glow_color, glow_w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        glow.setPen(pen)
        chart.addSeries(glow)
        glow.attachAxis(x_axis)
        glow.attachAxis(y_axis)

    # Core line
    core = QLineSeries()
    for p in points:
        core.append(p)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    core.setPen(pen)
    chart.addSeries(core)
    core.attachAxis(x_axis)
    core.attachAxis(y_axis)


def _glow_area(chart: QChart, points: list,
               color_hex: str, x_axis, y_axis) -> None:
    """Gradient fill under a glowing line using a dedicated QAreaSeries.

    Upper/lower series are parented to the chart so Python doesn't GC them
    while QAreaSeries still holds C++ pointers to them.
    """
    upper = QLineSeries(chart)
    lower = QLineSeries(chart)
    for p in points:
        upper.append(p)
        lower.append(p.x(), 0)

    area = QAreaSeries(upper, lower)
    fill = QColor(color_hex)
    fill.setAlpha(20)
    area.setBrush(QBrush(fill))
    area.setPen(QPen(Qt.PenStyle.NoPen))
    chart.addSeries(area)
    area.attachAxis(x_axis)
    area.attachAxis(y_axis)


def _hover_dots(chart: QChart, points: list, color_hex: str,
                x_axis, y_axis, labels: list = None,
                fmt_func=None) -> QScatterSeries:
    """Interactive scatter dots with hover tooltips + 3B1B glow."""
    color = QColor(color_hex)

    # Outer glow halo
    halo = QScatterSeries()
    halo.setMarkerSize(16)
    halo_color = QColor(color)
    halo_color.setAlpha(40)
    halo.setColor(halo_color)
    halo.setBorderColor(QColor(0, 0, 0, 0))
    for p in points:
        halo.append(p)
    chart.addSeries(halo)
    halo.attachAxis(x_axis)
    halo.attachAxis(y_axis)

    # Core dot
    dots = QScatterSeries()
    dots.setMarkerSize(8)
    dots.setColor(color)
    dots.setBorderColor(QColor(0, 0, 0, 0))
    for p in points:
        dots.append(p)

    _labels = labels or []
    _fmt = fmt_func or (lambda p: f"{p.y():.1f}")

    def _on_hover(point: QPointF, state: bool):
        if state:
            if _labels:
                # Find closest point
                min_dist = float("inf")
                label = ""
                for i, p in enumerate(points):
                    d = abs(p.x() - point.x()) + abs(p.y() - point.y())
                    if d < min_dist:
                        min_dist = d
                        label = _labels[i] if i < len(_labels) else _fmt(p)
                QToolTip.showText(
                    QCursor.pos(),
                    label
                )
            else:
                QToolTip.showText(
                    QCursor.pos(),
                    _fmt(point)
                )

    dots.hovered.connect(_on_hover)
    chart.addSeries(dots)
    dots.attachAxis(x_axis)
    dots.attachAxis(y_axis)
    return dots


def make_chart_view(chart: QChart) -> QChartView:
    """Wrap chart in a styled view with antialiasing."""
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setStyleSheet("background: transparent; border: none;")
    view.setMinimumHeight(200)
    return view


# ── Public chart functions ───────────────────────────────────────────────────
# Each returns a QChartView (interactive widget, not a static image)

def plot_sessions_over_time(sessions: list) -> QChartView:
    chart = _base_chart("sessions over time")

    if not sessions:
        chart.setTitle("sessions over time — no data yet")
        return make_chart_view(chart)

    from collections import Counter
    dates = [s.start_time.date() for s in sessions if s.start_time]
    counts = Counter(dates)
    sorted_dates = sorted(counts.keys())
    values = [counts[d] for d in sorted_dates]

    x_axis = _datetime_axis()
    y_axis = _value_axis()
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

    points = []
    labels = []
    for d, v in zip(sorted_dates, values):
        dt = datetime(d.year, d.month, d.day)
        ms = dt.timestamp() * 1000
        points.append(QPointF(ms, v))
        labels.append(f"{d.strftime('%b %d')}: {v} sessions")

    _glow_line(chart, points, BLUE, x_axis, y_axis)
    _glow_area(chart, points, BLUE, x_axis, y_axis)
    _hover_dots(chart, points, BLUE, x_axis, y_axis, labels)

    y_axis.setRange(0, max(values) * 1.2 + 1)
    return make_chart_view(chart)


def plot_focus_metrics(stats: dict) -> QChartView:
    chart = _base_chart("average session breakdown")

    labels_list = ["net focused", "break time", "procrastination"]
    values = [
        stats.get("avg_net_focused") or 0,
        stats.get("avg_break_duration") or 0,
        stats.get("avg_procrastination_duration") or 0,
    ]
    colors = [GREEN, BLUE, RED]

    y_axis = _cat_axis(labels_list[::-1])
    x_axis = _value_axis()
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

    series = QHorizontalBarSeries()
    for label, val, color_hex in zip(labels_list, values, colors):
        bar_set = QBarSet(label)
        bar_set.append(val)
        bar_set.setColor(QColor(color_hex))
        bar_set.setBorderColor(QColor(0, 0, 0, 0))
        series.append(bar_set)

    series.setBarWidth(0.5)

    def _hover(status, idx, barset):
        if status:
            QToolTip.showText(QCursor.pos(), f"{barset.label()}: {barset.at(idx):.1f} min")

    series.hovered.connect(_hover)
    chart.addSeries(series)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)

    x_axis.setRange(0, max(values) * 1.15 + 1)
    return make_chart_view(chart)


def plot_focus_block_histogram(focus_blocks: list) -> QChartView:
    chart = _base_chart("focus block distribution")

    if not focus_blocks:
        chart.setTitle("focus block distribution — no data yet")
        return make_chart_view(chart)

    import numpy as np
    n_bins = min(15, max(4, len(focus_blocks) // 3))
    counts, bin_edges = np.histogram(focus_blocks, bins=n_bins)

    categories = []
    for i in range(len(bin_edges) - 1):
        categories.append(f"{bin_edges[i]:.0f}")

    y_axis = _value_axis()
    x_axis = _cat_axis(categories)
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

    bar_set = QBarSet("focus blocks")
    bar_set.setColor(QColor(PURPLE))
    bar_set.setBorderColor(QColor(0, 0, 0, 0))
    for c in counts:
        bar_set.append(float(c))

    series = QBarSeries()
    series.append(bar_set)
    series.setBarWidth(0.85)

    def _hist_hover(status, idx, barset):
        if status and 0 <= idx < len(counts):
            lo = bin_edges[idx]
            hi = bin_edges[idx + 1]
            QToolTip.showText(
                QCursor.pos(),
                f"{lo:.0f}–{hi:.0f} min: {counts[idx]} blocks"
            )

    series.hovered.connect(_hist_hover)
    chart.addSeries(series)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)

    y_axis.setRange(0, max(counts) * 1.2 + 1)
    return make_chart_view(chart)


def plot_burnout_procrastination_timing(stats: dict) -> QChartView:
    chart = _base_chart("avg time until events")

    labels_list = ["burnout", "procrastination", "break"]
    values = [
        stats.get("avg_time_to_burnout") or 0,
        stats.get("avg_time_to_procrastination") or 0,
        stats.get("avg_time_to_break") or 0,
    ]
    colors = [RED, ORANGE, BLUE]

    x_axis = _value_axis()
    y_axis = _cat_axis(labels_list[::-1])
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

    series = QHorizontalBarSeries()
    for label, val, color_hex in zip(labels_list, values, colors):
        bar_set = QBarSet(label)
        bar_set.append(val)
        bar_set.setColor(QColor(color_hex))
        bar_set.setBorderColor(QColor(0, 0, 0, 0))
        series.append(bar_set)

    series.setBarWidth(0.5)

    def _hover(status, idx, barset):
        if status:
            QToolTip.showText(QCursor.pos(), f"{barset.label()}: {barset.at(idx):.1f} min")

    series.hovered.connect(_hover)
    chart.addSeries(series)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)

    x_axis.setRange(0, max(values) * 1.15 + 1)
    return make_chart_view(chart)


def plot_focus_ratio_trend(sessions: list) -> QChartView:
    chart = _base_chart("focus ratio trend")

    valid = [(s.start_time, s.focus_ratio) for s in sessions
             if s.start_time and s.focus_ratio is not None]

    if not valid:
        chart.setTitle("focus ratio trend — no data yet")
        return make_chart_view(chart)

    x_axis = _datetime_axis()
    y_axis = _value_axis()
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

    points = []
    labels = []
    for dt, ratio in valid:
        ms = dt.timestamp() * 1000
        pct = ratio * 100
        points.append(QPointF(ms, pct))
        labels.append(f"{dt.strftime('%b %d')}: {pct:.1f}%")

    _glow_line(chart, points, GREEN, x_axis, y_axis)
    _glow_area(chart, points, GREEN, x_axis, y_axis)
    _hover_dots(chart, points, GREEN, x_axis, y_axis, labels)

    y_axis.setRange(0, 105)
    return make_chart_view(chart)


def plot_category_comparison(sessions: list, repo) -> QChartView:
    chart = _base_chart("category comparison")
    chart.legend().setVisible(True)
    chart.legend().setLabelColor(MUTED)
    chart.legend().setFont(QFont("Segoe UI", 8))
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

    from collections import defaultdict
    cat_data = defaultdict(lambda: {"focus": [], "break": [], "proc": []})

    for s in sessions:
        task = repo.get_task(s.task_id)
        if not task:
            continue
        cat = repo.get_category(task.category_id)
        name = cat.name if cat else "Unknown"
        if s.net_focused_min:
            cat_data[name]["focus"].append(s.net_focused_min)
        cat_data[name]["break"].append(s.break_duration_min)
        cat_data[name]["proc"].append(s.procrastination_duration_min)

    if not cat_data:
        chart.setTitle("category comparison — no data yet")
        return make_chart_view(chart)

    categories = list(cat_data.keys())
    def avg(lst): return sum(lst) / len(lst) if lst else 0

    focus_set = QBarSet("focus")
    focus_set.setColor(QColor(GREEN))
    focus_set.setBorderColor(QColor(0, 0, 0, 0))

    break_set = QBarSet("break")
    break_set.setColor(QColor(BLUE))
    break_set.setBorderColor(QColor(0, 0, 0, 0))

    proc_set = QBarSet("procrastination")
    proc_set.setColor(QColor(RED))
    proc_set.setBorderColor(QColor(0, 0, 0, 0))

    for c in categories:
        focus_set.append(avg(cat_data[c]["focus"]))
        break_set.append(avg(cat_data[c]["break"]))
        proc_set.append(avg(cat_data[c]["proc"]))

    series = QBarSeries()
    series.append(focus_set)
    series.append(break_set)
    series.append(proc_set)
    series.setBarWidth(0.6)

    def _cat_hover(status, idx, barset):
        if status and 0 <= idx < len(categories):
            QToolTip.showText(
                QCursor.pos(),
                f"{categories[idx]} — {barset.label()}: {barset.at(idx):.1f} min"
            )

    series.hovered.connect(_cat_hover)
    chart.addSeries(series)

    x_axis = _cat_axis(categories)
    y_axis = _value_axis()
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(x_axis)
    series.attachAxis(y_axis)

    return make_chart_view(chart)
