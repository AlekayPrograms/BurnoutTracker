"""
Desktop Buddy Widget — the on-screen character with speech bubble menu.

A transparent, always-on-top Qt widget that renders the sprite and shows
a speech bubble with action options when clicked. This is the PRIMARY
interaction point — the main window only opens through buddy menu choices.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPoint, QSize, Signal, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPixmap, QPainter, QMouseEvent, QColor, QPen, QBrush,
    QFont, QPainterPath, QLinearGradient, QFontMetrics,
)
from PySide6.QtWidgets import QWidget, QApplication, QGraphicsDropShadowEffect

from .sprite_engine import SpriteEngine, SpriteState

logger = logging.getLogger(__name__)

# Speech bubble styling
BUBBLE_BG = QColor(30, 30, 46, 240)           # dark bg
BUBBLE_BORDER = QColor(137, 180, 250, 200)    # blue accent
BUBBLE_TEXT = QColor(205, 214, 244)            # light text
BUBBLE_HOVER = QColor(69, 71, 90)             # hover bg
BUBBLE_ACCENT = QColor(137, 180, 250)         # blue
BUBBLE_GREEN = QColor(166, 227, 161)          # green
BUBBLE_ORANGE = QColor(250, 179, 135)         # orange
BUBBLE_PINK = QColor(243, 139, 168)           # pink
BUBBLE_YELLOW = QColor(249, 226, 175)         # yellow

# Menu item definitions: (label, color_accent, signal_name)
BUBBLE_RED = QColor(243, 139, 168)           # red for quit

IDLE_MENU = [
    ("Begin Working", BUBBLE_GREEN, "begin_working"),
    ("Dashboard", BUBBLE_ACCENT, "open_dashboard"),
    ("Settings", BUBBLE_YELLOW, "open_settings"),
    ("Quit", BUBBLE_RED, "quit_app"),
]

WORKING_MENU = [
    ("Take a Break", BUBBLE_ACCENT, "take_break"),
    ("I'm Procrastinating", BUBBLE_ORANGE, "procrastinating"),
    ("I'm Burnt Out", BUBBLE_PINK, "burnout"),
    ("Stop Working", BUBBLE_PINK, "stop_working"),
    ("Dashboard", BUBBLE_ACCENT, "open_dashboard"),
    ("Quit", BUBBLE_RED, "quit_app"),
]

BREAK_MENU = [
    ("Resume Working", BUBBLE_GREEN, "resume_working"),
    ("Dashboard", BUBBLE_ACCENT, "open_dashboard"),
    ("Quit", BUBBLE_RED, "quit_app"),
]

PROCRASTINATING_MENU = [
    ("Get Back to Work!", BUBBLE_GREEN, "resume_working"),
    ("Dashboard", BUBBLE_ACCENT, "open_dashboard"),
    ("Quit", BUBBLE_RED, "quit_app"),
]

ITEM_HEIGHT = 36
ITEM_PADDING = 8
BUBBLE_WIDTH = 200
BUBBLE_RADIUS = 12
TAIL_SIZE = 10


class BuddyWidget(QWidget):
    """Transparent overlay with animated buddy + speech bubble menu."""

    # Signals for each action
    begin_working = Signal()
    stop_working = Signal()
    take_break = Signal()
    procrastinating = Signal()
    burnout = Signal()
    resume_working = Signal()
    open_dashboard = Signal()
    open_settings = Signal()
    quit_app = Signal()

    def __init__(self, sprite_engine: SpriteEngine, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.engine = sprite_engine
        self._current_pixmap: Optional[QPixmap] = None
        self._drag_offset: Optional[QPoint] = None
        self._drag_started = False
        self._walking = False
        self._walk_direction = 1

        # Speech bubble state
        self._bubble_visible = False
        self._current_menu: list = IDLE_MENU
        self._hovered_item: int = -1
        self._user_state: str = "idle"  # idle, working, on_break, procrastinating

        # Widget flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        # Size: sprite area + bubble area above
        self._sprite_w = 96
        self._sprite_h = 128
        self._update_size()

        # Connect sprite engine
        self.engine.on_frame_changed = self._on_frame

        # Walk timer
        self._walk_timer = QTimer()
        self._walk_timer.timeout.connect(self._walk_step)

        # Position at bottom-right
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.width() - 200, geo.height() - self.height() - 20)

    def set_user_state(self, state: str) -> None:
        """Update menu based on current session state."""
        self._user_state = state
        if state == "idle":
            self._current_menu = IDLE_MENU
        elif state == "working":
            self._current_menu = WORKING_MENU
        elif state == "on_break":
            self._current_menu = BREAK_MENU
        elif state == "procrastinating":
            self._current_menu = PROCRASTINATING_MENU
        self.update()

    def _update_size(self) -> None:
        """Recalculate widget size based on bubble visibility."""
        if self._bubble_visible:
            bubble_h = len(self._current_menu) * ITEM_HEIGHT + ITEM_PADDING * 2 + TAIL_SIZE + 8
            total_h = bubble_h + self._sprite_h
            total_w = max(BUBBLE_WIDTH + 20, self._sprite_w + 40)
            self.setFixedSize(total_w, total_h)
        else:
            self.setFixedSize(self._sprite_w + 20, self._sprite_h + 10)

    def _bubble_rect(self) -> QRectF:
        """Get the speech bubble rectangle."""
        bubble_h = len(self._current_menu) * ITEM_HEIGHT + ITEM_PADDING * 2
        x = (self.width() - BUBBLE_WIDTH) / 2
        return QRectF(x, 4, BUBBLE_WIDTH, bubble_h)

    def _sprite_rect(self) -> QRectF:
        """Get the sprite drawing area."""
        if self._bubble_visible:
            bubble_h = len(self._current_menu) * ITEM_HEIGHT + ITEM_PADDING * 2 + TAIL_SIZE + 8
            x = (self.width() - self._sprite_w) / 2
            return QRectF(x, bubble_h, self._sprite_w, self._sprite_h)
        else:
            x = (self.width() - self._sprite_w) / 2
            return QRectF(x, 0, self._sprite_w, self._sprite_h)

    # ── Public ──────────────────────────────────────────────────────────────

    def start_walking(self) -> None:
        if self.engine.config["toggles"].get("idle_walking"):
            self._walking = True
            self._walk_timer.start(50)

    def stop_walking(self) -> None:
        self._walking = False
        self._walk_timer.stop()

    def update_scale(self, scale: float) -> None:
        self.engine.set_scale(scale)
        self._sprite_w = int(48 * scale)
        self._sprite_h = int(64 * scale)
        self._update_size()
        self.update()

    def show_bubble(self) -> None:
        self._bubble_visible = True
        # Reposition so sprite stays in same place
        old_sprite_y = self.y()
        self._update_size()
        bubble_h = len(self._current_menu) * ITEM_HEIGHT + ITEM_PADDING * 2 + TAIL_SIZE + 8
        self.move(self.x() - (self.width() - self._sprite_w - 20) // 2,
                  self.y() - bubble_h)
        self.update()

    def hide_bubble(self) -> None:
        if not self._bubble_visible:
            return
        bubble_h = len(self._current_menu) * ITEM_HEIGHT + ITEM_PADDING * 2 + TAIL_SIZE + 8
        old_x = self.x()
        old_y = self.y()
        self._bubble_visible = False
        self._hovered_item = -1
        self._update_size()
        self.move(old_x + (BUBBLE_WIDTH + 20 - self._sprite_w - 20) // 2,
                  old_y + bubble_h)
        self.update()

    # ── Paint ───────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw speech bubble
        if self._bubble_visible:
            self._draw_bubble(p)

        # Draw sprite
        if self._current_pixmap and not self._current_pixmap.isNull():
            sr = self._sprite_rect()
            scaled = self._current_pixmap.scaled(
                int(sr.width()), int(sr.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            x = int(sr.x() + (sr.width() - scaled.width()) / 2)
            y = int(sr.y() + (sr.height() - scaled.height()) / 2)
            p.drawPixmap(x, y, scaled)

        p.end()

    def _draw_bubble(self, p: QPainter) -> None:
        """Draw the speech bubble with menu items."""
        br = self._bubble_rect()

        # ── Bubble shadow ──
        shadow_rect = br.adjusted(2, 2, 2, 2)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, BUBBLE_RADIUS, BUBBLE_RADIUS)
        p.fillPath(shadow_path, QColor(0, 0, 0, 60))

        # ── Bubble body ──
        path = QPainterPath()
        path.addRoundedRect(br, BUBBLE_RADIUS, BUBBLE_RADIUS)
        p.fillPath(path, BUBBLE_BG)

        # Border
        p.setPen(QPen(BUBBLE_BORDER, 1.5))
        p.drawRoundedRect(br, BUBBLE_RADIUS, BUBBLE_RADIUS)

        # ── Tail (triangle pointing down to buddy) ──
        tail_x = br.center().x()
        tail_y = br.bottom()
        tail_path = QPainterPath()
        tail_path.moveTo(tail_x - TAIL_SIZE, tail_y - 1)
        tail_path.lineTo(tail_x, tail_y + TAIL_SIZE)
        tail_path.lineTo(tail_x + TAIL_SIZE, tail_y - 1)
        tail_path.closeSubpath()
        p.fillPath(tail_path, BUBBLE_BG)
        p.setPen(QPen(BUBBLE_BORDER, 1.5))
        p.drawLine(int(tail_x - TAIL_SIZE), int(tail_y),
                   int(tail_x), int(tail_y + TAIL_SIZE))
        p.drawLine(int(tail_x), int(tail_y + TAIL_SIZE),
                   int(tail_x + TAIL_SIZE), int(tail_y))

        # ── Menu items ──
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        p.setFont(font)

        for i, (label, accent, _) in enumerate(self._current_menu):
            item_y = br.y() + ITEM_PADDING + i * ITEM_HEIGHT
            item_rect = QRectF(br.x() + 6, item_y, br.width() - 12, ITEM_HEIGHT - 4)

            # Hover highlight
            if i == self._hovered_item:
                hover_path = QPainterPath()
                hover_path.addRoundedRect(item_rect, 6, 6)
                p.fillPath(hover_path, BUBBLE_HOVER)

            # Accent dot
            dot_y = item_y + ITEM_HEIGHT / 2 - 3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(accent))
            p.drawEllipse(int(item_rect.x() + 8), int(dot_y), 6, 6)

            # Label text
            p.setPen(QPen(BUBBLE_TEXT if i != self._hovered_item else accent))
            text_rect = QRectF(item_rect.x() + 22, item_y, item_rect.width() - 28, ITEM_HEIGHT)
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, label)

        # ── State indicator at top ──
        state_text = {
            "idle": "Hey there!",
            "working": "Working hard!",
            "on_break": "Taking a break~",
            "procrastinating": "Hmm...",
        }.get(self._user_state, "")

        if state_text:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QPen(QColor(166, 173, 200, 160)))
            # Draw above the first item
            p.drawText(QRectF(br.x() + 6, br.y() + 2, br.width() - 12, 14),
                      Qt.AlignmentFlag.AlignCenter, state_text)

    # ── Mouse events ────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.position().toPoint()
            self._drag_started = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()

        # Drag detection
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._drag_started:
                delta = (pos - self._drag_offset).manhattanLength()
                if delta > 5:
                    self._drag_started = True
            if self._drag_started:
                new_pos = self.mapToGlobal(pos) - self._drag_offset
                self.move(new_pos)
                return

        # Hover detection on bubble items
        if self._bubble_visible:
            br = self._bubble_rect()
            old_hover = self._hovered_item
            self._hovered_item = -1
            for i in range(len(self._current_menu)):
                item_y = br.y() + ITEM_PADDING + i * ITEM_HEIGHT
                item_rect = QRectF(br.x() + 6, item_y, br.width() - 12, ITEM_HEIGHT - 4)
                if item_rect.contains(pos.toPointF()):
                    self._hovered_item = i
                    break
            if old_hover != self._hovered_item:
                self.setCursor(Qt.CursorShape.PointingHandCursor
                             if self._hovered_item >= 0
                             else Qt.CursorShape.ArrowCursor)
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_started:
            self._drag_offset = None
            self._drag_started = False
            return

        pos = event.position().toPoint()

        # Check if clicked on a menu item
        if self._bubble_visible:
            br = self._bubble_rect()
            for i, (label, accent, signal_name) in enumerate(self._current_menu):
                item_y = br.y() + ITEM_PADDING + i * ITEM_HEIGHT
                item_rect = QRectF(br.x() + 6, item_y, br.width() - 12, ITEM_HEIGHT - 4)
                if item_rect.contains(pos.toPointF()):
                    self.hide_bubble()
                    signal = getattr(self, signal_name, None)
                    if signal:
                        signal.emit()
                    self._drag_offset = None
                    return

            # Clicked outside bubble items — check if on sprite or elsewhere
            sr = self._sprite_rect()
            if not sr.contains(pos.toPointF()):
                self.hide_bubble()
                self._drag_offset = None
                return

        # Toggle bubble on sprite click
        sr = self._sprite_rect()
        if sr.contains(pos.toPointF()):
            if self._bubble_visible:
                self.hide_bubble()
            else:
                self.show_bubble()

        self._drag_offset = None

    def leaveEvent(self, event) -> None:
        self._hovered_item = -1
        self.update()

    # ── Internal ────────────────────────────────────────────────────────────

    def _on_frame(self, pixmap: QPixmap) -> None:
        self._current_pixmap = pixmap
        self.update()

    def _walk_step(self) -> None:
        if not self._walking or self._bubble_visible:
            return
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        speed = self.engine.config.get("walk_speed_px", 2)
        new_x = self.x() + self._walk_direction * speed

        if new_x <= geo.left():
            self._walk_direction = 1
            new_x = geo.left()
        elif new_x + self.width() >= geo.right():
            self._walk_direction = -1
            new_x = geo.right() - self.width()

        self.move(new_x, self.y())

        if random.random() < 0.005:
            self._walk_timer.stop()
            QTimer.singleShot(2000, lambda: self._walk_timer.start(50) if self._walking else None)


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The desktop buddy is now the PRIMARY interaction point. Clicking it
#   opens a speech bubble with context-sensitive menu options. The bubble
#   changes based on session state (idle, working, break, procrastinating).
#
# Key design:
#   - Speech bubble drawn with QPainterPath (rounded rect + triangle tail)
#   - Menu items have colored accent dots and hover highlights
#   - Drag vs click detection: 5px threshold prevents accidental drags
#   - Context-sensitive: the menu changes based on what the user is doing
#   - Signals emitted for each action — the main window connects to these
#
# Interviewer-friendly talking points:
#   1. This is a "radial menu" / "pie menu" pattern adapted for a buddy
#      character — common in games (The Sims, MMOs).
#   2. The QPainterPath approach draws vector shapes that look sharp at
#      any DPI, unlike bitmap-based bubbles.
#   3. State-driven menu: same widget, different options based on context.
#      This is the Strategy pattern in action.
