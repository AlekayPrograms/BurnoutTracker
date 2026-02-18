"""
Sound Manager — handles SFX playback for the desktop buddy.

Uses pygame.mixer for lightweight audio. All sounds are generated
programmatically (no copyrighted audio files).
"""

from __future__ import annotations

import logging
import struct
import math
import wave
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

# Whether pygame mixer is available
_mixer_available = False
try:
    import pygame.mixer
    _mixer_available = True
except ImportError:
    logger.warning("pygame not installed; sounds will be disabled.")


class SoundManager:
    """Manages SFX playback with volume control and toggles."""

    def __init__(self, enabled: bool = True, volume: float = 0.5) -> None:
        self.enabled = enabled
        self.volume = max(0.0, min(volume, 1.0))
        self._initialized = False
        self._sounds: dict = {}

        if _mixer_available and enabled:
            self._init_mixer()

    def _init_mixer(self) -> None:
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self._initialized = True
            self._generate_sounds()
            logger.info("Sound manager initialized.")
        except Exception as e:
            logger.warning("Could not init audio: %s", e)

    def _generate_sounds(self) -> None:
        """Generate original SFX programmatically."""
        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

        sound_specs = {
            "jump_notify": self._gen_chime,
            "popup_prompt": self._gen_popup,
            "angry_punch": self._gen_punch,
            "timer_complete": self._gen_timer_done,
            "procrastination_nag": self._gen_nag,
        }

        for name, gen_func in sound_specs.items():
            path = SOUNDS_DIR / f"{name}.wav"
            if not path.exists():
                wav_data = gen_func()
                with open(path, "wb") as f:
                    f.write(wav_data)
            try:
                self._sounds[name] = pygame.mixer.Sound(str(path))
                self._sounds[name].set_volume(self.volume)
            except Exception as e:
                logger.warning("Could not load sound %s: %s", name, e)

    def play(self, sound_name: str) -> None:
        """Play a named sound effect."""
        if not self.enabled or not self._initialized:
            return
        sound = self._sounds.get(sound_name)
        if sound:
            sound.set_volume(self.volume)
            sound.play()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(volume, 1.0))
        for s in self._sounds.values():
            s.set_volume(self.volume)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled and not self._initialized and _mixer_available:
            self._init_mixer()

    # ── Sound generators (simple waveforms) ─────────────────────────────────

    @staticmethod
    def _make_wav(samples: list, sample_rate: int = 22050) -> bytes:
        """Pack raw samples into a WAV byte string."""
        buf = BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            data = b"".join(struct.pack("<h", int(s)) for s in samples)
            w.writeframes(data)
        return buf.getvalue()

    @classmethod
    def _gen_chime(cls) -> bytes:
        """Soft ascending chime (jump notify)."""
        sr = 22050
        samples = []
        freqs = [523, 659, 784]  # C5, E5, G5
        for i, freq in enumerate(freqs):
            dur = int(sr * 0.08)
            for t in range(dur):
                amp = 8000 * (1 - t / dur)  # fade out
                samples.append(amp * math.sin(2 * math.pi * freq * t / sr))
            samples.extend([0] * int(sr * 0.02))  # gap
        return cls._make_wav(samples, sr)

    @classmethod
    def _gen_popup(cls) -> bytes:
        """Short pop sound (popup prompt)."""
        sr = 22050
        samples = []
        for t in range(int(sr * 0.1)):
            amp = 10000 * math.exp(-t / (sr * 0.03))
            freq = 800 - (400 * t / (sr * 0.1))
            samples.append(amp * math.sin(2 * math.pi * freq * t / sr))
        return cls._make_wav(samples, sr)

    @classmethod
    def _gen_punch(cls) -> bytes:
        """Impact sound (angry punch)."""
        sr = 22050
        samples = []
        # Two hits
        for _ in range(2):
            for t in range(int(sr * 0.06)):
                amp = 12000 * math.exp(-t / (sr * 0.015))
                freq = 200 + 100 * math.exp(-t / (sr * 0.02))
                samples.append(amp * math.sin(2 * math.pi * freq * t / sr))
            samples.extend([0] * int(sr * 0.08))
        return cls._make_wav(samples, sr)

    @classmethod
    def _gen_timer_done(cls) -> bytes:
        """Completion jingle."""
        sr = 22050
        samples = []
        freqs = [523, 659, 784, 1047]  # C5, E5, G5, C6
        for freq in freqs:
            dur = int(sr * 0.12)
            for t in range(dur):
                amp = 7000 * (1 - t / dur)
                samples.append(amp * math.sin(2 * math.pi * freq * t / sr))
        return cls._make_wav(samples, sr)

    @classmethod
    def _gen_nag(cls) -> bytes:
        """Attention-getting beep (procrastination reminder)."""
        sr = 22050
        samples = []
        for _ in range(2):
            freq = 880
            dur = int(sr * 0.1)
            for t in range(dur):
                amp = 6000 * (1 if t < dur * 0.8 else (1 - (t - dur * 0.8) / (dur * 0.2)))
                samples.append(amp * math.sin(2 * math.pi * freq * t / sr))
            samples.extend([0] * int(sr * 0.1))
        return cls._make_wav(samples, sr)


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   Generates and plays original sound effects. No copyrighted audio.
#   Sounds are synthesized from basic waveforms (sine waves with envelopes).
#
# Key design decisions:
#   - Programmatic audio: sine waves with amplitude envelopes create
#     convincing retro game sounds. Same technique as NES/SNES audio.
#   - pygame.mixer: lightweight, cross-platform audio library. We only use
#     the mixer module, not full pygame.
#   - Graceful degradation: if pygame isn't installed, sounds silently disable.
#
# Data flow:
#   App start → SoundManager.__init__() → generates WAV files if missing →
#   loads into pygame.mixer.Sound objects → play("jump_notify") plays them.
#
# Interviewer-friendly talking points:
#   1. Envelope shaping: multiplying the sine wave by an exponential decay
#      creates a natural "pluck" or "hit" sound. This is basic DSP.
#   2. WAV format: uncompressed audio — we generate it in-memory with the
#      wave module, no external tools needed.
#   3. Volume normalization: all sounds have similar peak amplitudes so
#      the volume slider works uniformly across all SFX.
