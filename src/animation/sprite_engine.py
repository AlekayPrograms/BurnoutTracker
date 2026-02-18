"""
Sprite State Machine — controls which animation plays and when.

The sprite engine manages transitions between animation states (idle, blink,
walk, jump, angry, attacks) and serves the correct frame to the renderer.
All timing is configurable via JSON.

Sprites are procedurally generated on first run (see sprite_generator.py)
and cached to src/assets/sprites/.
"""

from __future__ import annotations

import json
import logging
import random
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap, QColor

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "animation.json"
SPRITES_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "assets" / "sprites"
SPRITESHEET_PATH = Path(__file__).resolve().parent.parent.parent / "orangeMushroomAnims.png"

# Default animation config (used if JSON doesn't exist yet)
DEFAULT_CONFIG = {
    "frame_rate_ms": 150,
    "idle_blink_interval_ms": 3000,
    "idle_variant_interval_ms": 8000,
    "walk_speed_px": 2,
    "sprite_scale": 2.0,
    "toggles": {
        "idle_blink": True,
        "idle_variants": True,
        "idle_walking": False,
        "jump_notify": True,
        "aggressive_animation": True,
        "sound_enabled": True,
        "master_animation": True,
    },
    "volume": 0.5,
}


class SpriteState(Enum):
    IDLE = auto()
    BLINK = auto()
    IDLE_VARIANT = auto()
    WALK = auto()
    JUMP_NOTIFY = auto()
    ANGRY_EMOTE = auto()
    ATTACK_1 = auto()
    ATTACK_2 = auto()


class SpriteEngine:
    """
    State machine that manages sprite animation frames.

    Each state has a list of frames (QPixmap). The engine cycles through
    frames at a configurable rate and handles transitions.
    """

    def __init__(self) -> None:
        self.config = self._load_config()
        self.state = SpriteState.IDLE
        self.frames: Dict[SpriteState, List[QPixmap]] = {}
        self.current_frame_index = 0
        self.scale = self.config.get("sprite_scale", 2.0)

        # Callbacks
        self.on_frame_changed: Optional[Callable[[QPixmap], None]] = None

        # Animation timer
        self._frame_timer = QTimer()
        self._frame_timer.timeout.connect(self._advance_frame)

        # Idle behavior timers
        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._trigger_blink)

        self._variant_timer = QTimer()
        self._variant_timer.timeout.connect(self._trigger_idle_variant)

        # Queue for returning to idle after one-shot animations
        self._return_to_idle = False
        self._queued_callback: Optional[Callable] = None

    # ── Public API ──────────────────────────────────────────────────────────

    def load_sprites(self) -> None:
        """Load sprites — tries sprite sheet first, then individual frame folders."""
        if SPRITESHEET_PATH.exists():
            self._load_from_spritesheet()
            if SpriteState.IDLE in self.frames:
                logger.info("Loaded sprites from sprite sheet: %s", SPRITESHEET_PATH.name)
                return

        # Fallback: load from individual frame folders
        from .sprite_generator import generate_placeholder_sprites
        if not (SPRITES_DIR / "idle").exists():
            generate_placeholder_sprites(SPRITES_DIR)

        for state in SpriteState:
            folder = SPRITES_DIR / state.name.lower()
            if folder.exists():
                frame_files = sorted(folder.glob("*.png"))
                pixmaps = []
                for f in frame_files:
                    px = QPixmap(str(f))
                    if not px.isNull():
                        pixmaps.append(px)
                if pixmaps:
                    self.frames[state] = pixmaps
                    logger.info("Loaded %d frames for %s", len(pixmaps), state.name)

        if SpriteState.IDLE not in self.frames:
            logger.warning("No idle frames found; generating fallback.")
            generate_placeholder_sprites(SPRITES_DIR)
            self.load_sprites()

    def _load_from_spritesheet(self) -> None:
        """Parse orangeMushroomAnims.png and extract frames by auto-detecting sprites."""
        sheet = QImage(str(SPRITESHEET_PATH))
        if sheet.isNull():
            logger.warning("Failed to load sprite sheet")
            return

        # Convert magenta (255,0,255) background to transparent
        sheet = sheet.convertToFormat(QImage.Format.Format_ARGB32)
        magenta = QColor(255, 0, 255).rgba()
        for y in range(sheet.height()):
            for x in range(sheet.width()):
                if sheet.pixel(x, y) == magenta:
                    sheet.setPixel(x, y, QColor(0, 0, 0, 0).rgba())

        # Sprite regions detected from the sheet layout (243x279):
        # Row 0: 3 standing poses (idle frames)
        # Row 1: 3 more poses (variations/blink)
        # Row 2: 1 angry face pose
        # Row 3: 3 mushroom cap poses (flipped/dead — used for jump/attack)
        sprite_regions = [
            # (x, y, w, h) — bounding boxes of each sprite
            # Row 0: idle poses
            (6, 4, 63, 58),      # 0: idle standing 1
            (72, 4, 63, 58),     # 1: idle standing 2
            # Row 1: more poses
            (6, 72, 64, 64),     # 2: variation (angry face)
            (73, 72, 62, 64),    # 3: variation
            (138, 72, 63, 64),   # 4: variation
            # Row 2: single angry pose
            (6, 141, 62, 65),    # 5: angry/hurt
            # Row 3: mushroom caps (rolling/attack)
            (8, 215, 61, 59),    # 6: cap 1
            (75, 215, 59, 59),   # 7: cap 2
            (141, 215, 59, 59),  # 8: cap 3
        ]

        extracted = []
        for i, (rx, ry, rw, rh) in enumerate(sprite_regions):
            cropped = sheet.copy(rx, ry, rw, rh)
            px = QPixmap.fromImage(cropped)
            if not px.isNull():
                extracted.append(px)
                logger.info("Extracted sprite %d: %dx%d from (%d,%d)", i, rw, rh, rx, ry)

        if len(extracted) < 6:
            logger.warning("Not enough sprites extracted from sheet (%d)", len(extracted))
            return

        # Map extracted sprites to animation states
        # IDLE: cycle through standing poses (0, 1)
        self.frames[SpriteState.IDLE] = [extracted[0], extracted[1], extracted[0]]

        # BLINK: use the variations as blink frames (quick pose swap)
        self.frames[SpriteState.BLINK] = [extracted[0], extracted[3], extracted[4], extracted[3], extracted[0]]

        # IDLE_VARIANT: bounce between poses
        self.frames[SpriteState.IDLE_VARIANT] = [extracted[0], extracted[3], extracted[4], extracted[3], extracted[0]]

        # WALK: alternate between standing poses
        self.frames[SpriteState.WALK] = [extracted[0], extracted[1]] * 4

        # JUMP_NOTIFY: standing → angry face → back
        self.frames[SpriteState.JUMP_NOTIFY] = [
            extracted[0], extracted[0], extracted[2], extracted[2],
            extracted[5], extracted[5], extracted[2], extracted[0]
        ]

        # ANGRY_EMOTE: angry face shake
        self.frames[SpriteState.ANGRY_EMOTE] = [extracted[2], extracted[5], extracted[2], extracted[5], extracted[2], extracted[5]]

        # ATTACK_1: roll into mushroom cap
        self.frames[SpriteState.ATTACK_1] = [extracted[2], extracted[5], extracted[6], extracted[7], extracted[6], extracted[5]]

        # ATTACK_2: another cap roll
        self.frames[SpriteState.ATTACK_2] = [extracted[5], extracted[7], extracted[8], extracted[7], extracted[5], extracted[0]]

        logger.info("Sprite sheet loaded: %d states mapped", len(self.frames))

    def start(self) -> None:
        """Begin animation playback."""
        if not self.config["toggles"]["master_animation"]:
            return
        fps = self.config.get("frame_rate_ms", 150)
        self._frame_timer.start(fps)

        if self.config["toggles"]["idle_blink"]:
            self._blink_timer.start(self.config.get("idle_blink_interval_ms", 3000))
        if self.config["toggles"]["idle_variants"]:
            self._variant_timer.start(self.config.get("idle_variant_interval_ms", 8000))

    def stop(self) -> None:
        self._frame_timer.stop()
        self._blink_timer.stop()
        self._variant_timer.stop()

    def set_state(self, new_state: SpriteState, one_shot: bool = False,
                  callback: Optional[Callable] = None) -> None:
        """
        Transition to a new animation state.
        one_shot=True: play once then return to IDLE.
        callback: called when one-shot finishes.
        """
        if new_state not in self.frames:
            logger.warning("No frames for state %s, staying in %s", new_state, self.state)
            return
        self.state = new_state
        self.current_frame_index = 0
        self._return_to_idle = one_shot
        self._queued_callback = callback

    def play_notification(self) -> None:
        """Play jump_notify animation (gentle reminder)."""
        if self.config["toggles"]["jump_notify"]:
            self.set_state(SpriteState.JUMP_NOTIFY, one_shot=True)

    def play_aggressive(self) -> None:
        """Play angry emote + attack combo (aggressive reminder)."""
        if not self.config["toggles"]["aggressive_animation"]:
            self.play_notification()  # fallback to gentle
            return

        def _after_angry():
            self.set_state(SpriteState.ATTACK_1, one_shot=True, callback=lambda: (
                self.set_state(SpriteState.ATTACK_2, one_shot=True)
            ))

        self.set_state(SpriteState.ANGRY_EMOTE, one_shot=True, callback=_after_angry)

    def get_current_frame(self) -> Optional[QPixmap]:
        """Return the current animation frame, scaled."""
        frames = self.frames.get(self.state)
        if not frames:
            frames = self.frames.get(SpriteState.IDLE)
        if not frames:
            return None
        idx = self.current_frame_index % len(frames)
        px = frames[idx]

        # Nearest-neighbor scaling for pixel art clarity
        if self.scale != 1.0:
            new_w = int(px.width() * self.scale)
            new_h = int(px.height() * self.scale)
            px = px.scaled(new_w, new_h)  # Qt::FastTransformation is nearest-neighbor for upscale
        return px

    def set_scale(self, scale: float) -> None:
        self.scale = max(0.5, min(scale, 5.0))
        self.config["sprite_scale"] = self.scale

    def update_toggles(self, toggles: dict) -> None:
        self.config["toggles"].update(toggles)
        self.save_config()

    def save_config(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=2)

    def reset_config(self) -> None:
        self.config = DEFAULT_CONFIG.copy()
        self.config["toggles"] = DEFAULT_CONFIG["toggles"].copy()
        self.save_config()

    # ── Internal ────────────────────────────────────────────────────────────

    def _advance_frame(self) -> None:
        """Called every frame tick. Advances frame index, handles one-shots."""
        frames = self.frames.get(self.state)
        if not frames:
            return

        self.current_frame_index += 1

        if self.current_frame_index >= len(frames):
            if self._return_to_idle:
                cb = self._queued_callback
                self._return_to_idle = False
                self._queued_callback = None
                if cb:
                    cb()
                else:
                    self.state = SpriteState.IDLE
                    self.current_frame_index = 0
            else:
                self.current_frame_index = 0  # loop

        if self.on_frame_changed:
            frame = self.get_current_frame()
            if frame:
                self.on_frame_changed(frame)

    def _trigger_blink(self) -> None:
        if self.state == SpriteState.IDLE:
            self.set_state(SpriteState.BLINK, one_shot=True)

    def _trigger_idle_variant(self) -> None:
        if self.state == SpriteState.IDLE and random.random() < 0.4:
            self.set_state(SpriteState.IDLE_VARIANT, one_shot=True)

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH) as f:
                    cfg = json.load(f)
                # Merge with defaults for any missing keys
                merged = DEFAULT_CONFIG.copy()
                merged.update(cfg)
                merged["toggles"] = {**DEFAULT_CONFIG["toggles"], **cfg.get("toggles", {})}
                return merged
            except (json.JSONDecodeError, KeyError):
                logger.warning("Bad animation config, using defaults.")
        return DEFAULT_CONFIG.copy()


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Implements a finite state machine for sprite animations. Each "state"
#   (idle, blink, walk, jump, angry, attacks) has a list of frames that
#   cycle on a timer. One-shot states play once then return to idle.
#
# Key design decisions:
#   - State machine pattern: clean separation of animation logic from
#     rendering. The widget just asks for get_current_frame().
#   - One-shot with callback chaining: the aggressive sequence plays
#     angry_emote → attack_1 → attack_2 by chaining callbacks.
#   - Config-driven: all timing and toggles are in JSON. The user can
#     tweak behavior without touching code.
#
# Data flow:
#   Timer tick → _advance_frame() → increment index → call on_frame_changed
#   → BuddyWidget updates its pixmap on screen.
#
# Interviewer-friendly talking points:
#   1. Finite state machines are everywhere in game dev. This is the same
#      pattern used for character controllers in Unity/Unreal.
#   2. Nearest-neighbor scaling: critical for pixel art. Bilinear/bicubic
#      would blur the pixels and ruin the crispness of small sprites.
#   3. Config hot-reload: we could add file-watching to reload animation.json
#      at runtime without restarting the app.
