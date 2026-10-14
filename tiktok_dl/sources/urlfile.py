"""A plain text file with one TikTok URL per line (comments with ``#``)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from tiktok_dl.models import SavedVideo, VideoCategory
from tiktok_dl.sources.base import VideoSource
from tiktok_dl.urls import canonical_url, extract_video_id, find_urls, is_tiktok_url


class UrlFileSource(VideoSource):
    name = "url-file"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"URL list not found: {self.path}")

    def videos(self) -> Iterator[SavedVideo]:
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                for raw in find_urls(line):
                    if is_tiktok_url(raw):
                        yield SavedVideo(
                            url=canonical_url(raw),
                            video_id=extract_video_id(raw),
                            category=VideoCategory.URL_LIST,
                            source=str(self.path),
                        )
