"""
updater/updater.py — UpdateManager: the single entry-point for all update logic.

Usage
-----
    from updater import UpdateManager

    UpdateManager.initialize(
        current_version = "v1.0.0",
        repo            = "username/repo",
        auto_update     = True,
        auto_restart    = True,
    )

The manager is a singleton QObject that wires together the GitHub API,
downloader, installer, dialogs and tray icon.  All network I/O runs in
daemon threads so the GUI stays responsive.
"""

import threading
from typing import Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from . import config as _cfg
from .github_api import find_asset, is_update_available
from .installer import install_update
from .tray_ui import UpdateTrayIcon
from .update_window import DownloadProgressWindow, UpdateNotificationDialog
from .utils import get_update_type, setup_logger

logger = setup_logger()


class UpdateManager(QObject):
    """
    Singleton update manager.  Call ``UpdateManager.initialize(...)`` once,
    usually right after creating your ``QApplication``.

    Public signals
    --------------
    update_available(latest_version: str)
    update_downloaded(file_path: str)
    """

    # ── Public signals ────────────────────────────────────────────────────────
    update_available  = pyqtSignal(str)   # latest version tag
    update_downloaded = pyqtSignal(str)   # local file path

    # ── Internal signal (background thread → main thread) ─────────────────────
    _check_result = pyqtSignal(bool, object)   # (available, release_dict | None)

    # ── Singleton ─────────────────────────────────────────────────────────────
    _instance: Optional["UpdateManager"] = None

    # ── Construction (use initialize() instead) ───────────────────────────────

    def __init__(self):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError(
                "QApplication must be created before UpdateManager.initialize()"
            )
        super().__init__(app)

        # Runtime config (can be overridden by initialize())
        self._current_version  : str  = _cfg.CURRENT_VERSION
        self._repo             : str  = _cfg.GITHUB_REPO
        self._auto_update      : bool = _cfg.AUTO_UPDATE
        self._auto_download    : bool = _cfg.AUTO_DOWNLOAD
        self._auto_restart     : bool = _cfg.AUTO_RESTART
        self._allow_prerelease : bool = _cfg.ALLOW_PRERELEASE
        self._interval_hours   : int  = _cfg.CHECK_INTERVAL_HOURS
        self._asset_filename   : Optional[str] = _cfg.ASSET_FILENAME

        self._latest_release   : Optional[Dict] = None
        self._downloaded_file  : Optional[str]  = None

        self._tray             : Optional[UpdateTrayIcon]          = None
        self._timer            : Optional[QTimer]                  = None
        self._notif_dlg        : Optional[UpdateNotificationDialog] = None
        self._dl_window        : Optional[DownloadProgressWindow]  = None

        # Wire the background-result signal to the main-thread handler
        self._check_result.connect(self._on_check_result)

    # ── Public factory ────────────────────────────────────────────────────────

    @classmethod
    def initialize(
        cls,
        current_version      : Optional[str]  = None,
        repo                 : Optional[str]  = None,
        github_token         : Optional[str]  = None,
        auto_update          : Optional[bool] = None,
        auto_download        : Optional[bool] = None,
        auto_restart         : Optional[bool] = None,
        allow_prerelease     : Optional[bool] = None,
        check_interval_hours : Optional[int]  = None,
        asset_filename       : Optional[str]  = None,
        enable_tray          : bool           = True,
    ) -> "UpdateManager":
        """
        Initialise (or return) the singleton UpdateManager.

        All parameters are optional; omit any to use the value in config.py.
        Pass ``github_token`` here so you never need to edit the updater folder.
        """
        if cls._instance is None:
            cls._instance = cls()

        mgr = cls._instance

        if current_version  is not None: mgr._current_version  = current_version
        if repo             is not None: mgr._repo             = repo
        if auto_update      is not None: mgr._auto_update      = auto_update
        if auto_download    is not None: mgr._auto_download    = auto_download
        if auto_restart     is not None: mgr._auto_restart     = auto_restart
        if allow_prerelease is not None: mgr._allow_prerelease = allow_prerelease
        if check_interval_hours is not None: mgr._interval_hours = check_interval_hours
        if asset_filename   is not None: mgr._asset_filename   = asset_filename

        # Write token into the live config module so github_api picks it up
        if github_token is not None:
            _cfg.GITHUB_TOKEN = github_token

        if enable_tray:
            mgr._setup_tray()

        mgr._setup_timer()

        if mgr._auto_update:
            # Delay the first check so the app's own UI can finish loading
            QTimer.singleShot(3000, mgr.check_for_updates)

        logger.info(
            f"UpdateManager ready | version={mgr._current_version} | "
            f"repo={mgr._repo} | auto_update={mgr._auto_update}"
        )
        return mgr

    # ── Internal setup ────────────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        try:
            self._tray = UpdateTrayIcon()
            self._tray.check_updates_requested.connect(self.check_for_updates)
            self._tray.download_update_requested.connect(self._open_download_window)
            self._tray.restart_requested.connect(self._do_install)
            self._tray.exit_requested.connect(QApplication.quit)
        except Exception as exc:
            logger.error(f"Tray initialisation failed: {exc}")

    def _setup_timer(self) -> None:
        if self._interval_hours > 0:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.check_for_updates)
            self._timer.start(int(self._interval_hours * 3_600_000))
            logger.info(
                f"Periodic check scheduled every {self._interval_hours} hour(s)"
            )

    # ── Update check (public + scheduled) ─────────────────────────────────────

    def check_for_updates(self) -> None:
        """
        Spawn a background thread to query GitHub.
        Results are delivered back to the main thread via ``_check_result``.
        """
        if self._repo == "username/repo":
            logger.warning("GITHUB_REPO is not configured — skipping update check")
            return

        logger.info(f"Checking for updates… (current={self._current_version})")
        threading.Thread(
            target=self._check_worker,
            daemon=True,
            name="UpdateChecker",
        ).start()

    def _check_worker(self) -> None:
        """Runs in background thread — must only emit signals, not touch widgets."""
        try:
            available, release = is_update_available(
                self._current_version,
                self._repo,
                self._allow_prerelease,
            )
            self._check_result.emit(available, release)
        except Exception as exc:
            logger.error(f"Update check worker error: {exc}")
            self._check_result.emit(False, None)

    def _on_check_result(self, available: bool, release: Optional[Dict]) -> None:
        """Runs on the main thread — safe to update UI."""
        if not available or release is None:
            logger.info("No update available")
            if self._tray:
                self._tray.notify(
                    "Up to Date",
                    f"You are running the latest version ({self._current_version})",
                )
            return

        self._latest_release = release
        latest_version = release.get("tag_name", "?")
        release_url    = release.get("html_url", "")
        utype          = get_update_type(self._current_version, latest_version)

        logger.info(f"Update found: {latest_version} ({utype})")
        self.update_available.emit(latest_version)

        if self._tray:
            self._tray.set_update_available(latest_version, release_url)
            self._tray.notify(
                "Update Available",
                f"Version {latest_version} is ready to download",
            )

        if self._auto_download:
            self._open_download_window(minimized=True)
        else:
            self._show_notification(latest_version, utype)

    # ── Notification dialog ───────────────────────────────────────────────────

    def _show_notification(self, latest_version: str, utype: str) -> None:
        if not self._latest_release:
            return
        notes = self._latest_release.get("body", "")
        self._notif_dlg = UpdateNotificationDialog(
            current_version=self._current_version,
            latest_version=latest_version,
            release_notes=notes,
            update_type=utype,
        )
        self._notif_dlg.download_requested.connect(self._open_download_window)
        self._notif_dlg.show()
        self._notif_dlg.raise_()

    # ── Download window ───────────────────────────────────────────────────────

    def _open_download_window(self, minimized: bool = False) -> None:
        if not self._latest_release:
            logger.warning("No release info — cannot start download")
            if self._tray:
                self._tray.notify(
                    "Update Error",
                    "No release information. Please check for updates first.",
                )
            return

        asset = find_asset(self._latest_release, self._asset_filename)
        if not asset:
            logger.error("No downloadable asset found in the release")
            if self._tray:
                self._tray.notify(
                    "Update Error",
                    "No downloadable file was found in this release.",
                )
            return

        # Avoid opening a second window for the same download
        if self._dl_window and self._dl_window.isVisible():
            self._dl_window.raise_()
            return

        self._dl_window = DownloadProgressWindow(
            download_url   = asset["browser_download_url"],
            filename       = asset["name"],
            latest_version = self._latest_release.get("tag_name", ""),
            auto_restart   = self._auto_restart,
        )
        self._dl_window.download_finished.connect(self._on_download_finished)
        self._dl_window.install_ready.connect(self._on_install_triggered)
        if minimized:
            self._dl_window.showMinimized()
        else:
            self._dl_window.show()
        self._dl_window.start_download()

    # ── Post-download / install ───────────────────────────────────────────────

    def _on_download_finished(self, file_path: str) -> None:
        """Called as soon as the file lands on disk — update tray immediately."""
        self._downloaded_file = file_path
        self.update_downloaded.emit(file_path)
        logger.info(f"Download ready: {file_path}")

        if self._tray:
            self._tray.set_download_ready()
            if not self._auto_restart:
                self._tray.notify(
                    "Update Downloaded",
                    "Click 'Restart to Update' in the tray to install",
                )

    def _on_install_triggered(self, file_path: str) -> None:
        """Called when install should actually happen (auto-timer or button click)."""
        self._downloaded_file = file_path
        self._do_install()

    def _do_install(self) -> None:
        if not self._downloaded_file:
            logger.warning("Install requested but no file is ready")
            return
        logger.info(f"Installing update: {self._downloaded_file}")
        # Always restart=True here: by the time _do_install() is called the
        # user has either clicked "Install & Restart" or "Restart to Update",
        # so the new binary must always be launched after replacement.
        # (auto_restart only controls whether install is triggered automatically
        # vs waiting for the user — not whether to relaunch after install.)
        success = install_update(self._downloaded_file, restart=True)
        if not success:
            logger.error("Installation failed")
            if self._tray:
                self._tray.notify(
                    "Update Failed",
                    "Install failed — please download and update manually.",
                )

    # ── Manual helpers ────────────────────────────────────────────────────────

    def manual_check(self) -> None:
        """Convenience alias — trigger an update check programmatically."""
        self.check_for_updates()
