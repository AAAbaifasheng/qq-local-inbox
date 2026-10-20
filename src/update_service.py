from __future__ import annotations

import threading
from pathlib import Path

from .updater import (
    StagedUpdate,
    check_for_update,
    find_pending,
    stage_update,
)


class UpdateService:
    """Background update checks. Results are posted to the app's event queue."""

    def __init__(self, current_version: str, staging_root: Path, events):
        self.current_version = current_version
        self.staging_root = Path(staging_root)
        self.events = events
        self.latest_info = None
        self.last_error = ""
        self.pending_update: StagedUpdate | None = find_pending(
            self.staging_root, self.current_version)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start_check(self, auto_download: bool = True) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._thread = threading.Thread(
                target=self._run, args=(auto_download,), daemon=True)
            self._thread.start()
            return True

    def refresh_pending(self) -> StagedUpdate | None:
        self.pending_update = find_pending(self.staging_root, self.current_version)
        return self.pending_update

    def _run(self, auto_download: bool) -> None:
        self.events.put(("update_checking", None))
        try:
            info = check_for_update(self.current_version)
        except Exception as exc:
            self.last_error = str(exc)[:160]
            self.events.put(("update_error", self.last_error))
            return
        if info is None:
            self.latest_info = None
            self.events.put(("update_checked", None))
            return
        self.latest_info = info
        self.events.put(("update_available", info))
        if not auto_download:
            return
        try:
            stage_update(info, self.staging_root)
        except Exception as exc:
            self.last_error = str(exc)[:160]
            self.events.put(("update_error", self.last_error))
            return
        self.refresh_pending()
        self.events.put(("update_staged", info))
