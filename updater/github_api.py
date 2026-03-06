"""
updater/github_api.py — GitHub Releases API helpers.

All network I/O is intentionally synchronous; the caller is responsible
for running these in a background thread.
"""

import datetime
from typing import Dict, List, Optional, Tuple

import requests

from .utils import compare_versions, setup_logger

logger = setup_logger()

_GITHUB_ACCEPT  = "application/vnd.github+json"
_GITHUB_VERSION = "2022-11-28"
_TIMEOUT        = 15  # seconds


def _build_headers() -> Dict[str, str]:
    """Build request headers, adding Authorization if a token is configured."""
    from . import config
    headers = {
        "Accept":               _GITHUB_ACCEPT,
        "X-GitHub-Api-Version": _GITHUB_VERSION,
    }
    token = (getattr(config, "GITHUB_TOKEN", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _log_rate_limit(resp: requests.Response) -> None:
    """Log remaining API quota from response headers (informational)."""
    remaining = resp.headers.get("X-RateLimit-Remaining")
    limit     = resp.headers.get("X-RateLimit-Limit")
    reset_ts  = resp.headers.get("X-RateLimit-Reset")
    if remaining is not None and limit is not None:
        logger.debug(f"GitHub rate limit: {remaining}/{limit} remaining")
    if remaining == "0" and reset_ts:
        try:
            reset_dt = datetime.datetime.fromtimestamp(int(reset_ts))
            logger.warning(
                f"GitHub rate limit exhausted. Resets at {reset_dt.strftime('%H:%M:%S')} "
                f"({reset_dt.strftime('%Y-%m-%d')})"
            )
        except (ValueError, OSError):
            pass


def _handle_http_error(exc: requests.exceptions.HTTPError) -> None:
    """Emit a helpful log message for common HTTP error codes."""
    resp = exc.response
    code = resp.status_code if resp is not None else 0

    if code == 403:
        # Distinguish rate-limit from access-denied
        reset_ts = (resp.headers.get("X-RateLimit-Reset") or "") if resp is not None else ""
        remaining = (resp.headers.get("X-RateLimit-Remaining") or "1") if resp is not None else "1"
        if remaining == "0" and reset_ts:
            try:
                reset_dt = datetime.datetime.fromtimestamp(int(reset_ts))
                logger.error(
                    f"GitHub rate limit exceeded. "
                    f"Resets at {reset_dt.strftime('%H:%M:%S')} on {reset_dt.strftime('%Y-%m-%d')}. "
                    f"Set GITHUB_TOKEN in updater/config.py for 5000 requests/hour."
                )
            except (ValueError, OSError):
                logger.error(
                    "GitHub rate limit exceeded. "
                    "Set GITHUB_TOKEN in updater/config.py to increase your quota."
                )
        else:
            logger.error(
                "GitHub returned 403 Forbidden. If this is a private repo, "
                "ensure GITHUB_TOKEN in updater/config.py has 'repo' scope."
            )
    elif code == 404:
        logger.error(
            f"GitHub repo not found (404). "
            f"Check that GITHUB_REPO is correct in updater/config.py."
        )
    elif code == 401:
        logger.error(
            "GitHub returned 401 Unauthorized. "
            "Check that GITHUB_TOKEN in updater/config.py is valid."
        )
    else:
        logger.error(f"GitHub API HTTP error: {exc}")


# ── Release fetching ─────────────────────────────────────────────────────────

def get_latest_release(
    repo: str,
    allow_prerelease: bool = False,
) -> Optional[Dict]:
    """
    Fetch the most recent non-draft release from GitHub.

    Returns the full release JSON dict, or None on error / no suitable release.
    """
    url = f"https://api.github.com/repos/{repo}/releases"

    try:
        resp = requests.get(url, headers=_build_headers(), timeout=_TIMEOUT)
        _log_rate_limit(resp)
        resp.raise_for_status()
        releases: List[Dict] = resp.json()
    except requests.exceptions.ConnectionError:
        logger.error("GitHub unreachable — check your internet connection")
        return None
    except requests.exceptions.Timeout:
        logger.error("GitHub API request timed out")
        return None
    except requests.exceptions.HTTPError as exc:
        _handle_http_error(exc)
        return None
    except Exception as exc:
        logger.error(f"Unexpected error fetching releases: {exc}")
        return None

    for release in releases:
        if release.get("draft", False):
            continue
        if not allow_prerelease and release.get("prerelease", False):
            continue
        logger.info(f"Latest suitable release: {release.get('tag_name', '?')}")
        return release

    logger.warning(f"No suitable release found for {repo}")
    return None


# ── Asset helpers ────────────────────────────────────────────────────────────

def get_release_assets(release: Dict) -> List[Dict]:
    """Return the list of asset objects for a release."""
    return release.get("assets", [])


def find_asset(release: Dict, filename: Optional[str] = None) -> Optional[Dict]:
    """
    Locate the best downloadable asset.

    If *filename* is provided, match by exact name (case-insensitive).
    Otherwise auto-detect: prefer .exe → .zip → .tar.gz → first asset.
    """
    assets = get_release_assets(release)
    if not assets:
        logger.warning("Release has no downloadable assets")
        return None

    if filename:
        for asset in assets:
            if asset["name"].lower() == filename.lower():
                return asset
        logger.warning(f"Asset '{filename}' not found in release")
        return None

    # Auto-detection priority
    for preferred_ext in (".exe", ".zip", ".tar.gz", ".tar.bz2"):
        for asset in assets:
            if asset["name"].lower().endswith(preferred_ext):
                return asset

    return assets[0]


# ── High-level check ─────────────────────────────────────────────────────────

def is_update_available(
    current_version: str,
    repo: str,
    allow_prerelease: bool = False,
) -> Tuple[bool, Optional[Dict]]:
    """
    Check whether a newer version is available on GitHub.

    Returns:
        (True,  release_dict)  — update found
        (False, None)          — up to date or network error
    """
    release = get_latest_release(repo, allow_prerelease)
    if not release:
        return False, None

    latest_version = release.get("tag_name", "")
    result = compare_versions(current_version, latest_version)

    if result == -1:
        logger.info(f"Update available: {current_version} → {latest_version}")
        return True, release

    logger.info(
        f"Up to date. Current={current_version}, Latest={latest_version}"
    )
    return False, None
