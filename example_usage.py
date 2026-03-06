"""
example_usage.py — Minimal demo application using the updater module.

Run:
    pip install -r requirements.txt
    python example_usage.py

Replace CURRENT_VERSION and GITHUB_REPO with your own values.
"""

import sys

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

# ── Import the update module ──────────────────────────────────────────────────
from updater import UpdateManager

# ── Configuration ─────────────────────────────────────────────────────────────
CURRENT_VERSION = "v0.0.1"
GITHUB_REPO     = "bibekchandsah/brightness"   # ← change to your GitHub repo


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"My App  {CURRENT_VERSION}")
        self.setMinimumSize(400, 200)

        central = QWidget()
        layout  = QVBoxLayout(central)

        layout.addWidget(QLabel(f"Running version:  {CURRENT_VERSION}"))

        check_btn = QPushButton("Check for Updates Now")
        check_btn.clicked.connect(self._on_check)
        layout.addWidget(check_btn)

        self.setCentralWidget(central)

    def _on_check(self):
        # Access the singleton and trigger a manual check
        mgr = UpdateManager._instance
        if mgr:
            mgr.manual_check()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # keep running in tray after close

    # ── Initialise the updater (one line!) ────────────────────────────────────
    update_mgr = UpdateManager.initialize(
        current_version      = CURRENT_VERSION,
        repo                 = GITHUB_REPO,
        github_token         = "",      # optional — set to avoid 403 rate-limit errors
        auto_update          = True,    # check on startup
        auto_download        = False,   # ask user before downloading
        auto_restart         = False,   # restart automatically after download
        check_interval_hours = 6,       # re-check every 6 hours
        allow_prerelease     = False,
        enable_tray          = True,
    )

    # Optional: react to update events from your own code
    update_mgr.update_available.connect(
        lambda v: print(f"[app] Update available: {v}")
    )
    update_mgr.update_downloaded.connect(
        lambda p: print(f"[app] Update downloaded: {p}")
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
