"""
Sprite Generator — Custom mushroom buddy pixel art.

A cute hand-crafted mushroom character with:
  - Rounded red cap with white polka dots and a shine highlight
  - Cream stem with expressive dot eyes and a little smile
  - Stubby feet / base
  - Full animation set: idle bob, blink, bounce, walk-wobble,
    jump arc (with squash on landing), angry shake, attacks
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor, QBrush

logger = logging.getLogger(__name__)

W, H = 48, 64

# ── Palette ───────────────────────────────────────────────────────────────────
OUTLINE    = QColor(30,  20,  15)
CAP        = QColor(198, 44,  24)       # main cap red
CAP_SHADE  = QColor(145, 26,  10)       # right / underside shadow
CAP_SHINE  = QColor(226, 84,  58)       # upper-left highlight
SPOT       = QColor(244, 239, 222)      # white spot fill
SPOT_SHADE = QColor(206, 196, 174)      # spot shadow edge
STEM       = QColor(237, 220, 190)      # bright stem centre
STEM_SIDE  = QColor(205, 185, 150)      # stem mid-tone
STEM_EDGE  = QColor(172, 150, 114)      # stem outer edge
EYE        = QColor(30,  20,  15)
EYE_SHINE  = QColor(255, 255, 255)
CHEEK      = QColor(228, 94,  72, 130)  # semi-transparent blush
MOUTH      = QColor(150, 48,  32)
ANGRY      = QColor(218, 48,  48)


# ── Cap profile ───────────────────────────────────────────────────────────────
# Each entry: (x_left, width) for that row of the cap dome.
# 18 rows total; rendered starting at cap_y.
_CAP_ROWS: List[tuple[int, int]] = [
    (21, 6),    # row  0 — narrow tip
    (19, 10),   # row  1
    (16, 16),   # row  2
    (14, 20),   # row  3
    (12, 24),   # row  4
    (11, 26),   # row  5
    (10, 28),   # row  6
    (10, 28),   # row  7
    (10, 28),   # row  8
    (10, 28),   # row  9
    (10, 28),   # row 10
    (10, 28),   # row 11
    ( 8, 32),   # row 12 — rim flares out
    ( 8, 32),   # row 13
    ( 8, 32),   # row 14 — widest
    ( 9, 30),   # row 15
    (11, 26),   # row 16
    (12, 24),   # row 17 — curls back under
]
_CAP_H = len(_CAP_ROWS)  # 18


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _img() -> QImage:
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    return img


def _px(p: QPainter, x: int, y: int, c: QColor) -> None:
    if 0 <= x < W and 0 <= y < H:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawRect(x, y, 1, 1)


def _rect(p: QPainter, x: int, y: int, w: int, h: int, c: QColor) -> None:
    if w > 0 and h > 0:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawRect(x, y, w, h)


# ── Mushroom parts ────────────────────────────────────────────────────────────

def _draw_cap(p: QPainter, cap_y: int) -> None:
    """Dome cap with outline, highlight, shadow, and white spots."""

    # Fill body row-by-row
    for i, (xl, w) in enumerate(_CAP_ROWS):
        _rect(p, xl, cap_y + i, w, 1, CAP)

    # ── Outline ──
    # Top tip (row above row-0)
    for x in range(21, 27):
        _px(p, x, cap_y - 1, OUTLINE)
    # Left / right per-row edge pixels
    for i, (xl, w) in enumerate(_CAP_ROWS):
        _px(p, xl - 1,  cap_y + i, OUTLINE)
        _px(p, xl + w,  cap_y + i, OUTLINE)
    # Bottom underside of last row
    xl_last, w_last = _CAP_ROWS[-1]
    for x in range(xl_last, xl_last + w_last):
        _px(p, x, cap_y + _CAP_H, OUTLINE)

    # ── Highlight (upper-left arc) ──
    _rect(p, 17, cap_y + 2, 4, 1, CAP_SHINE)
    _rect(p, 15, cap_y + 3, 6, 2, CAP_SHINE)
    _rect(p, 14, cap_y + 5, 5, 2, CAP_SHINE)
    _rect(p, 14, cap_y + 7, 3, 2, CAP_SHINE)

    # ── Shadow (right side) ──
    _rect(p, 34, cap_y + 4,  3, 8,  CAP_SHADE)
    _rect(p, 33, cap_y + 12, 4, 3,  CAP_SHADE)

    # ── White spots ──
    # Large left spot
    _rect(p, 15, cap_y + 7,  5, 4, SPOT)
    _rect(p, 14, cap_y + 8,  7, 2, SPOT)
    _px(p,  14, cap_y + 11, SPOT_SHADE)
    _rect(p, 15, cap_y + 11, 5, 1, SPOT_SHADE)
    # Small top spot
    _rect(p, 22, cap_y + 2,  4, 3, SPOT)
    _rect(p, 21, cap_y + 3,  6, 1, SPOT)
    _rect(p, 22, cap_y + 5,  4, 1, SPOT_SHADE)
    # Right spot
    _rect(p, 29, cap_y + 9,  4, 3, SPOT)
    _rect(p, 28, cap_y + 10, 6, 1, SPOT)
    _rect(p, 29, cap_y + 12, 4, 1, SPOT_SHADE)


def _draw_stem(p: QPainter, stem_y: int, stem_h: int,
               eyes: str = "open", mouth: str = "smile") -> None:
    """Cream stem with face. stem_y = top of stem."""
    sx, sw = 14, 20   # left edge, width

    # Body
    _rect(p, sx,           stem_y,  sw,          stem_h, STEM)
    _rect(p, sx,           stem_y,  2,            stem_h, STEM_EDGE)   # left dark edge
    _rect(p, sx + sw - 2,  stem_y,  2,            stem_h, STEM_EDGE)   # right dark edge
    _rect(p, sx + 2,       stem_y,  2,            stem_h, STEM_SIDE)   # inner side tone
    _rect(p, sx + sw - 4,  stem_y,  2,            stem_h, STEM_SIDE)

    # Outline sides
    _rect(p, sx - 1,       stem_y,  1, stem_h, OUTLINE)
    _rect(p, sx + sw,      stem_y,  1, stem_h, OUTLINE)

    # Face — vertically centred in stem
    face_y = stem_y + max(2, stem_h // 2 - 5)

    # Cheeks
    _rect(p, sx + 1,      face_y + 4, 3, 2, CHEEK)
    _rect(p, sx + sw - 4, face_y + 4, 3, 2, CHEEK)

    # Eyes
    if eyes == "open":
        _rect(p, 19, face_y,     3, 3, EYE);  _px(p, 19, face_y, EYE_SHINE)
        _rect(p, 26, face_y,     3, 3, EYE);  _px(p, 26, face_y, EYE_SHINE)

    elif eyes == "closed":
        _rect(p, 19, face_y + 1, 3, 1, EYE)
        _rect(p, 26, face_y + 1, 3, 1, EYE)

    elif eyes == "happy":
        # ^ ^ arcs
        for dx in range(3):
            yy = face_y + (0 if dx == 1 else 1)
            _px(p, 19 + dx, yy, EYE)
            _px(p, 26 + dx, yy, EYE)

    elif eyes == "angry":
        _rect(p, 19, face_y + 1, 3, 2, EYE)
        _rect(p, 26, face_y + 1, 3, 2, EYE)
        # Angled brows
        _px(p, 18, face_y - 2, OUTLINE);  _px(p, 19, face_y - 3, OUTLINE)
        _px(p, 20, face_y - 3, OUTLINE);  _px(p, 21, face_y - 2, OUTLINE)
        _px(p, 27, face_y - 2, OUTLINE);  _px(p, 28, face_y - 3, OUTLINE)
        _px(p, 29, face_y - 3, OUTLINE);  _px(p, 30, face_y - 2, OUTLINE)

    elif eyes == "wide":
        _rect(p, 18, face_y - 1, 4, 4, EYE);  _px(p, 18, face_y - 1, EYE_SHINE)
        _rect(p, 26, face_y - 1, 4, 4, EYE);  _px(p, 26, face_y - 1, EYE_SHINE)

    # Mouth
    if mouth == "smile":
        _rect(p, 21, face_y + 6, 6, 1, MOUTH)
        _px(p,  20, face_y + 5, MOUTH);  _px(p, 27, face_y + 5, MOUTH)

    elif mouth == "open":
        _rect(p, 21, face_y + 5, 6, 3, OUTLINE)
        _rect(p, 22, face_y + 5, 4, 2, MOUTH)

    elif mouth == "angry":
        _rect(p, 20, face_y + 6, 8, 1, MOUTH)
        _px(p, 21, face_y + 5, MOUTH);  _px(p, 24, face_y + 7, MOUTH)
        _px(p, 27, face_y + 5, MOUTH)

    elif mouth == "surprise":
        _rect(p, 22, face_y + 5, 4, 3, OUTLINE)
        _rect(p, 23, face_y + 5, 2, 2, MOUTH)


def _draw_base(p: QPainter, base_y: int) -> None:
    """Two little rounded feet at the base."""
    # Main connector bar
    _rect(p, 13, base_y,      22, 3, STEM_SIDE)
    # Left foot
    _rect(p, 11, base_y + 2,   9, 3, STEM)
    _rect(p, 11, base_y + 4,   9, 1, STEM_SIDE)
    # Right foot
    _rect(p, 28, base_y + 2,   9, 3, STEM)
    _rect(p, 28, base_y + 4,   9, 1, STEM_SIDE)
    # Outline
    _rect(p, 12, base_y - 1,  24, 1, OUTLINE)   # top edge
    _px(p,  11, base_y, OUTLINE);  _px(p, 35, base_y, OUTLINE)
    for x in range(11, 20):  _px(p, x, base_y + 5, OUTLINE)   # left foot bottom
    for x in range(28, 37):  _px(p, x, base_y + 5, OUTLINE)   # right foot bottom
    _px(p, 10, base_y + 2, OUTLINE);  _px(p, 10, base_y + 3, OUTLINE)
    _px(p, 10, base_y + 4, OUTLINE)
    _px(p, 36, base_y + 2, OUTLINE);  _px(p, 36, base_y + 3, OUTLINE)
    _px(p, 36, base_y + 4, OUTLINE)


def _draw_mushroom(p: QPainter, yo: int = 0,
                   eyes: str = "open", mouth: str = "smile",
                   vsqueeze: int = 0) -> None:
    """
    Full mushroom character.
      yo        – vertical offset; negative moves the sprite upward (jump).
      vsqueeze  – positive values squash the stem height (landing impact).
    """
    cap_y  = 6 + yo
    stem_y = cap_y + _CAP_H
    stem_h = max(6, 14 - vsqueeze)
    base_y = stem_y + stem_h

    _draw_cap(p, cap_y)
    _draw_stem(p, stem_y, stem_h, eyes, mouth)
    _draw_base(p, base_y)


# ── Frame Generators ──────────────────────────────────────────────────────────

def _gen_idle_frames() -> List[QImage]:
    """4-frame subtle breathing bob (0 → -1 → -1 → 0)."""
    frames = []
    for yo in [0, 0, -1, -1]:
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, yo=yo)
        p.end()
        frames.append(img)
    return frames


def _gen_blink_frames() -> List[QImage]:
    """5-frame blink: open → open → closed → closed → open."""
    states = [
        ("open",   "smile"),
        ("open",   "smile"),
        ("closed", "smile"),
        ("closed", "smile"),
        ("open",   "smile"),
    ]
    frames = []
    for eyes, mouth in states:
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, eyes=eyes, mouth=mouth)
        p.end()
        frames.append(img)
    return frames


def _gen_idle_variant_frames() -> List[QImage]:
    """6-frame happy little bounce."""
    offsets = [0, -2, -4, -4, -2, 0]
    frames = []
    for yo in offsets:
        eyes  = "happy" if yo <= -3 else "open"
        mouth = "open"  if yo <= -3 else "smile"
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, yo=yo, eyes=eyes, mouth=mouth)
        p.end()
        frames.append(img)
    return frames


def _gen_walk_frames() -> List[QImage]:
    """4-frame wobble — mushrooms don't run, they bounce in place."""
    frames = []
    for yo in [0, -1, 0, -1]:
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, yo=yo)
        p.end()
        frames.append(img)
    return frames


def _gen_jump_frames() -> List[QImage]:
    """8-frame jump arc with squash on landing and ! at peak."""
    # (yo, vsqueeze, eyes, mouth)
    keyframes = [
        ( 0,  0, "open",    "smile"),    # standing
        (-3,  0, "open",    "smile"),    # lifting off
        (-7,  0, "open",    "open"),     # rising
        (-12, 0, "happy",   "open"),     # peak — excited!
        (-12, 0, "happy",   "open"),     # hold peak
        (-7,  0, "open",    "open"),     # falling
        (-3,  0, "wide",    "surprise"), # about to land
        ( 0,  5, "open",    "smile"),    # squash on landing
    ]
    frames = []
    for yo, vsq, eyes, mouth in keyframes:
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, yo=yo, eyes=eyes, mouth=mouth, vsqueeze=vsq)
        # Yellow ! exclamation at peak
        if yo <= -12:
            ex, ey = 38, 4 + yo
            _rect(p, ex, ey,     2, 6, QColor(255, 220, 50))
            _rect(p, ex, ey + 8, 2, 2, QColor(255, 220, 50))
        p.end()
        frames.append(img)
    return frames


def _gen_angry_frames() -> List[QImage]:
    """6-frame angry shake with vein and steam puffs."""
    frames = []
    for i in range(6):
        yo = -1 if i % 2 == 0 else 1
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        _draw_mushroom(p, yo=yo, eyes="angry", mouth="angry")
        # Anger vein symbol (top-right)
        vx, vy = 37, 2
        _rect(p, vx,     vy, 2, 5, ANGRY)
        _rect(p, vx + 4, vy, 2, 5, ANGRY)
        _rect(p, vx - 1, vy + 2, 8, 2, ANGRY)
        # Alternating steam puffs
        steam = QColor(210, 210, 210, 140)
        if i % 2 == 0:
            _rect(p, 2,  8 + yo, 3, 2, steam)
            _rect(p, 1,  6 + yo, 2, 2, QColor(210, 210, 210, 80))
        else:
            _rect(p, 43, 8 + yo, 3, 2, steam)
            _rect(p, 44, 6 + yo, 2, 2, QColor(210, 210, 210, 80))
        p.end()
        frames.append(img)
    return frames


def _gen_attack1_frames() -> List[QImage]:
    """6-frame excited spin-dash."""
    y_offsets = [0, -2, -5, -2, 0, 0]
    frames = []
    for i, yo in enumerate(y_offsets):
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        eyes  = "angry" if i < 4 else "open"
        mouth = "angry" if i < 4 else "smile"
        _draw_mushroom(p, yo=yo, eyes=eyes, mouth=mouth)
        if i == 2:   # impact flash
            _rect(p, 38, 20 + yo, 4, 1, QColor(255, 255, 100))
            _rect(p, 39, 19 + yo, 2, 3, QColor(255, 255, 100))
        p.end()
        frames.append(img)
    return frames


def _gen_attack2_frames() -> List[QImage]:
    """6-frame ground-stomp with landing shockwave."""
    y_offsets = [0, -3, -6, -3,  0, 0]
    vsqueezes = [0,  0,  0,  0,  4, 0]
    frames = []
    for i, (yo, vsq) in enumerate(zip(y_offsets, vsqueezes)):
        img = _img()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        eyes  = "angry" if i < 4 else "open"
        mouth = "angry" if i < 3 else "smile"
        _draw_mushroom(p, yo=yo, eyes=eyes, mouth=mouth, vsqueeze=vsq)
        if i == 4:   # stomp shockwave
            _rect(p, 10, 47, 28, 2, QColor(255, 255, 100, 160))
        p.end()
        frames.append(img)
    return frames


def generate_placeholder_sprites(sprites_dir: Path) -> None:
    """Generate all sprite animation frames to disk."""
    logger.info("Generating mushroom sprites in %s", sprites_dir)
    sprites_dir.mkdir(parents=True, exist_ok=True)

    generators = {
        "idle":         _gen_idle_frames,
        "blink":        _gen_blink_frames,
        "idle_variant": _gen_idle_variant_frames,
        "walk":         _gen_walk_frames,
        "jump_notify":  _gen_jump_frames,
        "angry_emote":  _gen_angry_frames,
        "attack_1":     _gen_attack1_frames,
        "attack_2":     _gen_attack2_frames,
    }

    for state_name, gen_func in generators.items():
        folder = sprites_dir / state_name
        folder.mkdir(parents=True, exist_ok=True)
        frames = gen_func()
        for i, img in enumerate(frames):
            path = folder / f"frame_{i:02d}.png"
            img.save(str(path))
        logger.info("Generated %d frames for %s", len(frames), state_name)
