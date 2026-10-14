from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Iterator

from tiktok_dl.models import SavedVideo


class VideoSource(ABC):
    """Produces the videos that should be downloaded."""

    name: str = "source"

    @abstractmethod
    def videos(self) -> Iterator[SavedVideo]:
        """Yield videos in the order they should be processed."""


def dedupe(videos: Iterable[SavedVideo]) -> list[SavedVideo]:
    """Drop duplicate videos (by id / URL), keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[SavedVideo] = []
    for video in videos:
        if video.key in seen:
            continue
        seen.add(video.key)
        unique.append(video)
    return unique
