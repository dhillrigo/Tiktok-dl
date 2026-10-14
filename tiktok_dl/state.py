"""Persistent record of what has already been downloaded.

Stored as a JSON file in the output directory so a run can be interrupted and
resumed, and failures can be retried later with ``--retry-failed``.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tiktok_dl.models import DownloadResult, DownloadStatus, SavedVideo

STATE_FILENAME = ".tiktok-dl-state.json"


class DownloadState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
        if self.path.is_file():
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._entries = dict(data.get("videos", {}))

    # ------------------------------------------------------------------ query
    def status_of(self, video: SavedVideo) -> Optional[DownloadStatus]:
        entry = self._entries.get(video.key)
        return DownloadStatus(entry["status"]) if entry else None

    def is_done(self, video: SavedVideo) -> bool:
        entry = self._entries.get(video.key)
        if not entry or entry.get("status") != DownloadStatus.OK.value:
            return False
        filepath = entry.get("filepath")
        # If the file was deleted since, treat it as not done so it re-downloads.
        return not filepath or Path(filepath).exists()

    def has_failed(self, video: SavedVideo) -> bool:
        return self.status_of(video) == DownloadStatus.FAILED

    def entries(self) -> dict[str, dict]:
        return dict(self._entries)

    # ----------------------------------------------------------------- update
    def record(self, result: DownloadResult) -> None:
        entry = {
            "url": result.video.url,
            "video_id": result.video.video_id,
            "category": result.video.category.value,
            "saved_at": result.video.saved_at,
            "status": result.status.value,
            "filepath": result.filepath,
            "title": result.title,
            "uploader": result.uploader,
            "error": result.error,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with self._lock:
            self._entries[result.video.key] = entry
            self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"version": 1, "videos": self._entries}, fh, indent=2, ensure_ascii=False)
        tmp.replace(self.path)
