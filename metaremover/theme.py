"""Dark by default. Light is a dim off-white so it does not glare."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

ORG = "MetaRemover"
APP = "MetaRemover"


def is_dark() -> bool:
    return QSettings(ORG, APP).value("dark", True, type=bool)


def set_dark(dark: bool) -> None:
    QSettings(ORG, APP).setValue("dark", dark)


def _dark_palette() -> QPalette:
    pal = QPalette()
    bg = QColor(28, 28, 30)
    base = QColor(44, 44, 46)
    txt = QColor(226, 226, 230)
    dis = QColor(142, 142, 147)
    btn = QColor(58, 58, 60)
    hl = QColor(10, 132, 255)
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.WindowText, txt)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, QColor(36, 36, 38))
    pal.setColor(QPalette.Text, txt)
    pal.setColor(QPalette.Button, btn)
    pal.setColor(QPalette.ButtonText, txt)
    pal.setColor(QPalette.BrightText, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipBase, QColor(40, 40, 44))
    pal.setColor(QPalette.ToolTipText, txt)
    pal.setColor(QPalette.Highlight, hl)
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.PlaceholderText, QColor(142, 142, 147))
    pal.setColor(QPalette.Light, QColor(72, 72, 74))
    pal.setColor(QPalette.Mid, QColor(58, 58, 60))
    pal.setColor(QPalette.Dark, QColor(22, 22, 24))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText):
        pal.setColor(QPalette.Disabled, role, dis)
    return pal


def _light_palette() -> QPalette:
    """Soft paper, not #FFFFFF. Darker text than a billboard white theme."""
    pal = QPalette()
    window = QColor(214, 214, 218)
    base = QColor(232, 232, 235)
    text = QColor(40, 40, 44)
    muted = QColor(110, 110, 116)
    btn = QColor(224, 224, 228)
    hl = QColor(48, 110, 180)
    pal.setColor(QPalette.Window, window)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, QColor(222, 222, 226))
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.Button, btn)
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.BrightText, QColor(20, 20, 22))
    pal.setColor(QPalette.ToolTipBase, QColor(236, 236, 232))
    pal.setColor(QPalette.ToolTipText, text)
    pal.setColor(QPalette.Highlight, hl)
    pal.setColor(QPalette.HighlightedText, QColor(250, 250, 250))
    pal.setColor(QPalette.PlaceholderText, muted)
    pal.setColor(QPalette.Light, QColor(240, 240, 242))
    pal.setColor(QPalette.Mid, QColor(196, 196, 200))
    pal.setColor(QPalette.Dark, QColor(168, 168, 172))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText):
        pal.setColor(QPalette.Disabled, role, muted)
    return pal


def stylesheet(dark: bool) -> str:
    if dark:
        return """
            QToolTip {
                background: #2c2c30; color: #e2e2e6;
                border: 1px solid #4a4a50;
                padding: 4px 8px;
            }
        """
    return """
            QMainWindow, QDialog { background: #d6d6da; }
            QToolTip {
                background: #ecece8; color: #2a2a2e;
                border: 1px solid #b8b8bc;
                padding: 4px 8px;
            }
        """


def apply(app: QApplication, dark: bool | None = None) -> None:
    if dark is None:
        dark = is_dark()
    set_dark(dark)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_dark_palette() if dark else _light_palette())
    app.setStyleSheet(stylesheet(dark))


def map_colors(dark: bool) -> dict[str, QColor]:
    if dark:
        return {
            "ocean": QColor(14, 22, 32),
            "land": QColor(48, 64, 82),
            "coast": QColor(70, 92, 116),
            "grid": QColor(32, 44, 58),
            "pin": QColor(80, 168, 230),
            "pin_fill": QColor(80, 168, 230, 180),
            "text": QColor(226, 226, 230),
        }
    return {
        "ocean": QColor(176, 196, 210),
        "land": QColor(220, 224, 214),
        "coast": QColor(150, 164, 148),
        "grid": QColor(198, 206, 210),
        "pin": QColor(48, 110, 180),
        "pin_fill": QColor(48, 110, 180, 180),
        "text": QColor(40, 40, 44),
    }
