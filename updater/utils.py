"""
updater/utils.py — Shared helpers: logging, version comparison, formatting.
"""

import hashlib
import logging
import re
import sys
from pathlib import Path


# ── App directory ────────────────────────────────────────────────────────────

def get_app_dir() -> Path:
    """Return the directory that contains the running application."""
    if getattr(sys, "frozen", False):          # PyInstaller / Nuitka bundle
        return Path(sys.executable).parent
    return Path(sys.argv[0]).resolve().parent


# ── Logger ───────────────────────────────────────────────────────────────────

def setup_logger(log_file: str = "update.log") -> logging.Logger:
    """Configure and return the 'updater' logger (idempotent)."""
    logger = logging.getLogger("updater")
    if logger.handlers:
        return logger                          # already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    try:
        log_path = get_app_dir() / log_file
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass  # read-only filesystem — skip file logging

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


# ── Version helpers ──────────────────────────────────────────────────────────

def parse_version(version_str: str) -> tuple:
    """Parse a version string such as 'v1.2.3' into a (1, 2, 3) tuple."""
    cleaned = version_str.lstrip("vV").strip()
    parts = re.findall(r"\d+", cleaned)
    return tuple(int(p) for p in parts[:3]) if parts else (0, 0, 0)


def compare_versions(current: str, latest: str) -> int:
    """
    Compare two version strings.

    Returns:
        -1  current < latest  →  update available
         0  current == latest →  up to date
        +1  current > latest  →  running a newer version
    """
    cur = parse_version(current)
    lat = parse_version(latest)
    if cur < lat:
        return -1
    if cur > lat:
        return 1
    return 0


def get_update_type(current: str, latest: str) -> str:
    """Return 'major', 'minor', 'patch', or 'none'."""
    cur = parse_version(current)
    lat = parse_version(latest)
    if len(lat) < 3 or len(cur) < 3:
        return "none"
    if lat[0] > cur[0]:
        return "major"
    if lat[1] > cur[1]:
        return "minor"
    if lat[2] > cur[2]:
        return "patch"
    return "none"


# ── File integrity ───────────────────────────────────────────────────────────

def verify_sha256(file_path: str, expected_hash: str) -> bool:
    """Return True if the file's SHA-256 matches *expected_hash* (hex string)."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest().lower() == expected_hash.strip().lower()
    except OSError:
        return False


# ── Human-readable formatting ────────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    """Convert a byte count to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_time(seconds: float) -> str:
    """Convert a number of seconds to a human-readable duration."""
    if seconds < 0 or seconds == float("inf") or seconds != seconds:
        return "Calculating…"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    h, rem = divmod(seconds, 3600)
    return f"{h}h {rem // 60}m"
