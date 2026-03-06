"""
updater/downloader.py — Threaded file downloader with Qt progress signals.

DownloadWorker lives on the main thread but performs I/O in a daemon thread.
Signals are delivered to the main thread automatically by PyQt6's connection
mechanism (AutoConnection across threads).
"""

import threading
import time
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from .utils import format_size, format_time, setup_logger

logger = setup_logger()


class DownloadWorker(QObject):
    """
    Manages a single file download with progress reporting.

    Signals
    -------
    progress_updated(percent, speed_str, eta_str, downloaded_str, total_str)
    download_complete(file_path)
    download_failed(error_message)
    download_cancelled()
    """

    progress_updated  = pyqtSignal(int, str, str, str, str)
    download_complete = pyqtSignal(str)
    download_failed   = pyqtSignal(str)
    download_cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel_flag = False
        self._thread: Optional[threading.Thread] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def start_download(self, url: str, dest_folder: str, filename: str) -> None:
        """Begin downloading *url* into *dest_folder/filename* in the background."""
        self._cancel_flag = False
        self._thread = threading.Thread(
            target=self._run,
            args=(url, dest_folder, filename),
            daemon=True,
            name=f"DownloadWorker-{filename}",
        )
        self._thread.start()

    def cancel(self) -> None:
        """Signal the download loop to stop at the next chunk boundary."""
        self._cancel_flag = True

    # ── Worker ───────────────────────────────────────────────────────────────

    def _run(self, url: str, dest_folder: str, filename: str) -> None:
        dest_dir  = Path(dest_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        temp_path = dest_dir / (filename + ".part")

        try:
            logger.info(f"Download started: {url}")
            response = requests.get(
                url, stream=True, timeout=30, allow_redirects=True
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0) or 0)
            downloaded  = 0
            start_time  = time.monotonic()
            last_ui_update = start_time

            with open(temp_path, "wb") as fh:
                for chunk in response.iter_content(chunk_size=65536):
                    if self._cancel_flag:
                        logger.info("Download cancelled by user")
                        temp_path.unlink(missing_ok=True)
                        self.download_cancelled.emit()
                        return

                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)

                    now     = time.monotonic()
                    elapsed = now - start_time

                    # Emit progress every 500 ms
                    if now - last_ui_update >= 0.5:
                        last_ui_update = now
                        self._emit_progress(downloaded, total_size, elapsed)

            # Rename .part → final file
            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)

            # Final 100 % emit
            self.progress_updated.emit(
                100,
                "0 B/s",
                "Done",
                format_size(downloaded),
                format_size(total_size) if total_size else format_size(downloaded),
            )
            logger.info(f"Download complete: {dest_path}")
            self.download_complete.emit(str(dest_path))

        except requests.exceptions.ConnectionError:
            self._fail("Connection error — check your internet connection")
        except requests.exceptions.Timeout:
            self._fail("Download timed out")
        except requests.exceptions.HTTPError as exc:
            self._fail(f"HTTP error {exc.response.status_code}")
        except OSError as exc:
            self._fail(f"File system error: {exc}")
        except Exception as exc:
            self._fail(f"Unexpected error: {exc}")
        finally:
            temp_path.unlink(missing_ok=True)   # clean up if still present

    def _emit_progress(self, downloaded: int, total: int, elapsed: float) -> None:
        percent = int(downloaded / total * 100) if total > 0 else 0
        speed   = downloaded / elapsed if elapsed > 0 else 0
        eta     = (total - downloaded) / speed if (speed > 0 and total > 0) else float("inf")

        self.progress_updated.emit(
            percent,
            f"{format_size(int(speed))}/s",
            format_time(eta),
            format_size(downloaded),
            format_size(total) if total > 0 else "?",
        )

    def _fail(self, message: str) -> None:
        logger.error(f"Download failed: {message}")
        self.download_failed.emit(message)
