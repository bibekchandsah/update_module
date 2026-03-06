"""
updater/update_window.py — PyQt6 UI dialogs.

UpdateNotificationDialog  — tells the user a new version is available.
DownloadProgressWindow    — shows live download progress and install button.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .downloader import DownloadWorker
from .utils import get_app_dir, setup_logger


def _window_icon() -> QIcon:
    """Return the app's icon.ico if found, otherwise an empty QIcon."""
    import sys
    app_dir = get_app_dir()
    candidates = [
        app_dir / "icon.ico",
        app_dir.parent / "icon.ico",
        Path(__file__).parent.parent / "icon.ico",
    ]
    # When frozen by PyInstaller (--onefile), bundled data lives in _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / "icon.ico")
    for candidate in candidates:
        if candidate.exists():
            return QIcon(str(candidate))
    return QIcon()

logger = setup_logger()

# ── Shared stylesheet palette ─────────────────────────────────────────────────
_DARK_STYLE = """
QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QLabel {
    color: #cdd6f4;
    background: transparent;
}
QProgressBar {
    border: none;
    background-color: #313244;
    border-radius: 5px;
    height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 5px;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 22px;
    font-weight: bold;
    font-size: 12px;
    min-width: 90px;
}
QPushButton:hover  { background-color: #b4befe; }
QPushButton:pressed { background-color: #7287fd; }
QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}
QPushButton#secondary {
    background-color: #313244;
    color: #cdd6f4;
}
QPushButton#secondary:hover  { background-color: #45475a; }
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#danger:hover { background-color: #eba0ac; }
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
}
QPushButton#success:hover { background-color: #94e2d5; }
"""


def _sep() -> QFrame:
    """Return a thin horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("QFrame { color: #313244; }")
    return line


# ── Update notification dialog ────────────────────────────────────────────────

class UpdateNotificationDialog(QDialog):
    """
    Shown when a new release is detected.

    Signals
    -------
    download_requested()  — user clicked 'Download Update'
    skipped()             — user dismissed the dialog
    """

    download_requested = pyqtSignal()
    skipped            = pyqtSignal()

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        release_notes: str = "",
        update_type: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._latest = latest_version
        self._setup_ui(current_version, latest_version, release_notes, update_type)

    def _setup_ui(self, current: str, latest: str, notes: str, utype: str) -> None:
        self.setWindowTitle("Update Available")
        self.setWindowIcon(_window_icon())
        self.setFixedWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(_DARK_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(26, 22, 26, 22)

        # ── Title ────────────────────────────────────────────────────────────
        title = QLabel("🚀  Update Available")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa; background: transparent;")
        layout.addWidget(title)

        # ── Version row ───────────────────────────────────────────────────────
        badge_color = {"major": "#f38ba8", "minor": "#fab387", "patch": "#a6e3a1"}.get(
            utype, "#89b4fa"
        )
        badge = f'<span style="color:{badge_color}; font-weight:bold;">[{utype.upper()}]</span> ' if utype else ""
        ver_lbl = QLabel(
            f"{badge}Version <b>{latest}</b> is available<br>"
            f'<span style="color:#6c7086; font-size:10px;">You are running {current}</span>'
        )
        ver_lbl.setFont(QFont("Segoe UI", 10))
        ver_lbl.setTextFormat(Qt.TextFormat.RichText)
        ver_lbl.setWordWrap(True)
        layout.addWidget(ver_lbl)

        # ── Release notes ─────────────────────────────────────────────────────
        if notes and notes.strip():
            layout.addWidget(_sep())
            max_chars = 400
            short = notes.strip()[:max_chars] + ("…" if len(notes.strip()) > max_chars else "")
            notes_lbl = QLabel(short)
            notes_lbl.setFont(QFont("Segoe UI", 9))
            notes_lbl.setStyleSheet("color: #a6adc8; background: transparent;")
            notes_lbl.setWordWrap(True)
            layout.addWidget(notes_lbl)

        layout.addSpacing(6)
        layout.addWidget(_sep())

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("secondary")
        skip_btn.clicked.connect(self._on_skip)

        dl_btn = QPushButton("Download Update")
        dl_btn.clicked.connect(self._on_download)
        dl_btn.setDefault(True)

        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(dl_btn)
        layout.addLayout(btn_row)

    def _on_skip(self) -> None:
        self.skipped.emit()
        self.close()

    def _on_download(self) -> None:
        self.download_requested.emit()
        self.close()


# ── Download progress window ──────────────────────────────────────────────────

class DownloadProgressWindow(QDialog):
    """
    Shows live download progress.

    Signals
    -------
    download_finished(file_path) — emitted as soon as the file is on disk.
    install_ready(file_path)     — emitted when install should be triggered
                                   (auto after 2 s, or on button click).
    """

    download_finished = pyqtSignal(str)   # fired immediately when download is done
    install_ready     = pyqtSignal(str)   # fired when it's time to actually install

    def __init__(
        self,
        download_url: str,
        filename: str,
        latest_version: str,
        auto_restart: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._url          = download_url
        self._filename     = filename
        self._latest       = latest_version
        self._auto_restart = auto_restart
        self._file_path    = ""

        self._worker = DownloadWorker(parent=self)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.download_complete.connect(self._on_complete)
        self._worker.download_failed.connect(self._on_failed)
        self._worker.download_cancelled.connect(self._on_cancelled)

        self._setup_ui()

    # ── UI build ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setWindowTitle("Downloading Update")
        self.setWindowIcon(_window_icon())
        self.setFixedSize(440, 290)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(_DARK_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(26, 22, 26, 22)

        # Title
        title = QLabel("⬇  Downloading Update")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa; background: transparent;")
        layout.addWidget(title)

        self._status_lbl = QLabel(f"Downloading version {self._latest}…")
        self._status_lbl.setFont(QFont("Segoe UI", 10))
        self._status_lbl.setStyleSheet("color: #a6adc8; background: transparent;")
        layout.addWidget(self._status_lbl)

        layout.addSpacing(4)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        # Percentage centred
        self._pct_lbl = QLabel("0 %")
        self._pct_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pct_lbl)

        # Stats row
        stats = QHBoxLayout()
        self._speed_lbl = QLabel("Speed: —")
        self._eta_lbl   = QLabel("ETA: —")
        self._size_lbl  = QLabel("— / —")
        for lbl in (self._speed_lbl, self._eta_lbl, self._size_lbl):
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #585b70; background: transparent;")
        stats.addWidget(self._speed_lbl)
        stats.addStretch()
        stats.addWidget(self._eta_lbl)
        stats.addStretch()
        stats.addWidget(self._size_lbl)
        layout.addLayout(stats)

        layout.addStretch()
        layout.addWidget(_sep())

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("danger")
        self._cancel_btn.clicked.connect(self._on_cancel)

        self._install_btn = QPushButton("Install && Restart")
        self._install_btn.setObjectName("success")
        self._install_btn.setVisible(False)
        self._install_btn.clicked.connect(self._trigger_install)

        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._install_btn)
        layout.addLayout(btn_row)

    # ── Public API ────────────────────────────────────────────────────────────

    def start_download(self) -> None:
        """Begin the download (call after show())."""
        from . import config
        dest = str(get_app_dir() / config.DOWNLOAD_FOLDER)
        self._worker.start_download(self._url, dest, self._filename)
        logger.info(f"Started download: {self._filename}")

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_progress(
        self, percent: int, speed: str, eta: str, downloaded: str, total: str
    ) -> None:
        self._bar.setValue(percent)
        self._pct_lbl.setText(f"{percent} %")
        self._speed_lbl.setText(f"Speed: {speed}")
        self._eta_lbl.setText(f"ETA: {eta}")
        self._size_lbl.setText(f"{downloaded} / {total}")

    def _on_complete(self, file_path: str) -> None:
        self._file_path = file_path
        self._status_lbl.setText(
            f"✔  Download complete — version {self._latest} ready"
        )
        self._status_lbl.setStyleSheet("color: #a6e3a1; background: transparent;")
        self._bar.setValue(100)
        self._pct_lbl.setText("100 %")
        self._cancel_btn.setEnabled(False)
        logger.info(f"Download finished: {file_path}")

        # Always emit download_finished immediately so the tray can update
        self.download_finished.emit(file_path)

        if self._auto_restart:
            self._status_lbl.setText(
                "✔  Download complete — installing in 2 s…"
            )
            QTimer.singleShot(2000, self._trigger_install)
        else:
            self._install_btn.setVisible(True)
            self._install_btn.setEnabled(True)

    def _on_failed(self, error: str) -> None:
        self._status_lbl.setText(f"✘  Download failed: {error}")
        self._status_lbl.setStyleSheet("color: #f38ba8; background: transparent;")
        self._cancel_btn.setText("Close")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.setStyleSheet("")   # reset object-name style
        logger.error(f"Download failed: {error}")

    def _on_cancelled(self) -> None:
        self._status_lbl.setText("Download cancelled.")
        self._status_lbl.setStyleSheet("color: #fab387; background: transparent;")
        self._cancel_btn.setText("Close")

    def _on_cancel(self) -> None:
        self._worker.cancel()
        self.close()

    def _trigger_install(self) -> None:
        if self._file_path:
            self.install_ready.emit(self._file_path)
            self.close()

    # ── closeEvent ────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._worker.cancel()
        super().closeEvent(event)
