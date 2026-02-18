"""
Dark mode stylesheet for the entire application.
Catppuccin Mocha-inspired palette.
"""

DARK_STYLESHEET = """
/* ── Base ────────────────────────────────────────────────────────── */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e2e;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border-color: #313244;
}

QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
}

QPushButton#primary:hover {
    background-color: #74c7ec;
}

QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
}

QPushButton#danger:hover {
    background-color: #eba0ac;
}

QPushButton#warning {
    background-color: #fab387;
    color: #1e1e2e;
    border: none;
}

QPushButton#warning:hover {
    background-color: #f9e2af;
}

QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: none;
}

/* ── Input fields ────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #89b4fa;
}

/* ── ComboBox ────────────────────────────────────────────────────── */
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 10px;
    min-width: 120px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    selection-background-color: #45475a;
}

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: #cdd6f4;
}

QLabel#title {
    font-size: 22px;
    font-weight: 700;
    color: #89b4fa;
}

QLabel#subtitle {
    font-size: 15px;
    color: #a6adc8;
}

QLabel#metric_value {
    font-size: 28px;
    font-weight: 700;
    color: #a6e3a1;
}

QLabel#metric_label {
    font-size: 11px;
    color: #a6adc8;
}

QLabel#timer {
    font-size: 36px;
    font-weight: 700;
    font-family: "Consolas", "Courier New", monospace;
    color: #f9e2af;
}

QLabel#state_label {
    font-size: 15px;
    font-weight: 600;
    color: #cba6f7;
}

/* ── Tab Widget ──────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #cdd6f4;
}

/* ── Scroll Area ─────────────────────────────────────────────────── */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #585b70;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #89b4fa;
}

/* ── Slider ──────────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 6px;
    background-color: #313244;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background-color: #89b4fa;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background-color: #74c7ec;
}

/* ── Group Box ───────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}

/* ── SpinBox ─────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ── Message Box ─────────────────────────────────────────────────── */
QMessageBox {
    background-color: #1e1e2e;
}

/* ── DateEdit ────────────────────────────────────────────────────── */
QDateEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ── CheckBox ────────────────────────────────────────────────────── */
QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #585b70;
    border-radius: 4px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Progress Bar ────────────────────────────────────────────────── */
QProgressBar {
    background-color: #313244;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    height: 12px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
"""
