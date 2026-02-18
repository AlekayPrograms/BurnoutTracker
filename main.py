"""
BurnoutTracker — AI Animated Desktop Buddy
Entry point for the application.
"""

import faulthandler
import logging
import sys
from pathlib import Path

faulthandler.enable()

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.ui.styles import DARK_STYLESHEET


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("burnout_tracker.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting BurnoutTracker...")

    app = QApplication(sys.argv)
    app.setApplicationName("BurnoutTracker")
    app.setOrganizationName("BurnoutTracker")

    # Apply dark theme globally
    app.setStyleSheet(DARK_STYLESHEET)

    # High DPI support
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    window = MainWindow()
    window.show()

    logger.info("Application started.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Explanation (for interviews)
# ---------------------------------------------------------------------------
# What this file does:
#   The entry point — the "main()" that starts everything. Sets up logging,
#   creates the Qt application, applies the dark theme, and opens MainWindow.
#
# Key points:
#   - sys.path manipulation: ensures imports work whether you run from the
#     repo root or another directory.
#   - QApplication: required singleton for any Qt app. Must be created
#     before any widget.
#   - app.exec(): starts the Qt event loop. The program "lives" inside
#     this loop until the user quits.
#
# Interviewer-friendly talking points:
#   1. The event loop is the heartbeat of GUI apps. All timers, button
#      clicks, and repaints are processed by app.exec().
#   2. Logging to both console and file: console for development, file
#      for debugging user-reported issues.
#   3. High DPI support: without this, pixel art would look tiny on
#      4K monitors.
