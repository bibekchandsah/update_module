"""
updater — PyQt6 Auto-Update Module
===================================

Quick start
-----------
    from updater import UpdateManager

    UpdateManager.initialize(
        current_version = "v1.0.0",
        repo            = "username/repo",
        auto_update     = True,
        auto_restart    = True,
    )

That single call wires up:
  * Startup update check (after 3 s)
  * Periodic re-check (every CHECK_INTERVAL_HOURS)
  * System-tray icon with context menu
  * Notification dialogs
  * Threaded downloader with live progress
  * Safe in-place installer with automatic backup
"""

from .updater import UpdateManager
from . import config

__all__ = ["UpdateManager", "config"]
__version__ = "1.0.0"
