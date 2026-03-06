"""
updater/tray_ui.py — System tray icon and notification support.

The icon is drawn programmatically (an upward-arrow inside a circle) so
no external image file is required.  Place 'assets/update_icon.png'
alongside this package to override with a custom icon.
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygon,
)
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from .utils import setup_logger

logger = setup_logger()


# ── Icon factory ─────────────────────────────────────────────────────────────

def _make_icon() -> QIcon:
    """Return the tray icon — from file if available, otherwise generated."""
    icon_file = Path(__file__).parent / "assets" / "update_icon.png"
    if icon_file.exists():
        return QIcon(str(icon_file))
    return _draw_icon()


def _draw_icon(size: int = 64) -> QIcon:
    """Draw a simple ↑ arrow inside a filled circle using Qt primitives."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background circle
    painter.setBrush(QColor("#89b4fa"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Arrow shaft
    shaft_pen = QPen(QColor("#1e1e2e"), max(2, size // 16))
    shaft_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(shaft_pen)
    cx = size // 2
    painter.drawLine(cx, size * 3 // 4, cx, size // 4)

    # Arrow head (filled triangle)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1e1e2e"))
    tip = size // 5
    mid = size // 3
    spread = size // 5
    head = QPolygon([
        QPoint(cx,          tip),
        QPoint(cx - spread, mid),
        QPoint(cx + spread, mid),
    ])
    painter.drawPolygon(head)

    painter.end()
    return QIcon(px)


# ── Tray integration ─────────────────────────────────────────────────────────

class UpdateTrayIcon(QObject):
    """
    Wraps QSystemTrayIcon with updater-aware context menu and notifications.

    Signals
    -------
    check_updates_requested()
    download_update_requested()
    restart_requested()
    exit_requested()
    """

    check_updates_requested   = pyqtSignal()
    download_update_requested = pyqtSignal()
    restart_requested         = pyqtSignal()
    exit_requested            = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._release_url: Optional[str] = None
        self._tray: Optional[QSystemTrayIcon] = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this system — "
                           "tray notifications will be skipped")
            return

        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_make_icon())
        self._tray.setToolTip("App Updater")

        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.show()
        logger.info("System tray icon initialised")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        self._menu = QMenu()

        # ── Update submenu ────────────────────────────────────────────────────
        self._update_menu = QMenu("Update")
        self._menu.addMenu(self._update_menu)

        self._check_action = QAction("Check for Updates")
        self._check_action.triggered.connect(self.check_updates_requested)
        self._update_menu.addAction(self._check_action)

        self._dl_action = QAction("Download Update")
        self._dl_action.setEnabled(False)
        self._dl_action.triggered.connect(self.download_update_requested)
        self._update_menu.addAction(self._dl_action)

        self._restart_action = QAction("Restart to Update")
        self._restart_action.setEnabled(False)
        self._restart_action.triggered.connect(self.restart_requested)
        self._update_menu.addAction(self._restart_action)

        self._open_action = QAction("Open Release Page")
        self._open_action.setEnabled(False)
        self._open_action.triggered.connect(self._open_release_page)
        self._update_menu.addAction(self._open_action)

        self._menu.addSeparator()

        exit_action = QAction("Exit")
        exit_action.triggered.connect(self.exit_requested)
        self._menu.addAction(exit_action)

    def _open_release_page(self) -> None:
        if self._release_url:
            QDesktopServices.openUrl(QUrl(self._release_url))

    # ── Public API ────────────────────────────────────────────────────────────

    def set_update_available(self, version: str, release_url: str = "") -> None:
        """Enable download action and update tooltip when an update is found."""
        self._release_url = release_url
        self._dl_action.setEnabled(True)
        self._open_action.setEnabled(bool(release_url))
        if self._tray:
            self._tray.setToolTip(f"Update Available: {version}")

    def set_download_ready(self) -> None:
        """Enable restart action once the download is complete."""
        self._restart_action.setEnabled(True)
        if self._tray:
            self._tray.setToolTip("Update ready — restart to install")

    def notify(self, title: str, message: str) -> None:
        """Show a balloon / toast notification from the tray."""
        if self._tray and self._tray.isVisible():
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
            logger.info(f"Tray notification: [{title}] {message}")
