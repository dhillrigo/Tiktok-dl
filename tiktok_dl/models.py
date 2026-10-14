"""Core data types shared across the package."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VideoCategory(str, Enum):
    """Which list in the TikTok export a video came from."""

    FAVORITES = "favorites"
    LIKES = "likes"
    HISTORY = "history"
    SHARED = "shared"
    URL_LIST = "url-list"


@dataclass(frozen=True)
class SavedVideo:
    """A single video we want to download.

    ``url`` is the canonical, yt-dlp-friendly URL. ``video_id`` is the numeric
    TikTok ID when it can be derived from the URL, otherwise ``None`` (for
    short links such as vm.tiktok.com that need a redirect to resolve).
    """

    url: str
    video_id: Optional[str] = None
    category: VideoCategory = VideoCategory.URL_LIST
    saved_at: Optional[str] = None
    source: str = ""

    @property
    def key(self) -> str:
        """Stable identity used for de-duplication and state tracking."""
        return self.video_id or self.url


class DownloadStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class DownloadResult:
    video: SavedVideo
    status: DownloadStatus
    filepath: Optional[str] = None
    error: Optional[str] = None
    title: Optional[str] = None
    uploader: Optional[str] = None
    extra: dict = field(default_factory=dict)
