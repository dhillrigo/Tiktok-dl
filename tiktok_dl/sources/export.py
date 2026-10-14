"""Parse the "Download your data" export that TikTok provides.

TikTok lets you request your data from *Settings → Account → Download your
data* in either JSON or TXT format. Both formats contain the lists we care
about:

* **Favorite Videos** – the videos you saved/bookmarked ("Saved" tab).
* **Like List** – the videos you liked.
* **Video Browsing History** – everything you watched.
* **Share History** – videos you shared.

The exact key names have changed between export versions (``Activity`` vs
``Your Activity``, ``Link`` vs ``link`` vs ``VideoLink``) so the parser walks
the JSON tolerant of casing and nesting rather than hard-coding one schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from tiktok_dl.models import SavedVideo, VideoCategory
from tiktok_dl.sources.base import VideoSource
from tiktok_dl.urls import canonical_url, extract_video_id, find_urls, is_tiktok_url

# Section names as they appear in exports, mapped to our categories.
# Matching is case-insensitive and ignores spaces/underscores.
_SECTION_CATEGORIES: dict[str, VideoCategory] = {
    "favoritevideos": VideoCategory.FAVORITES,
    "favoritevideolist": VideoCategory.FAVORITES,
    "likelist": VideoCategory.LIKES,
    "itemfavoritelist": VideoCategory.LIKES,
    "videobrowsinghistory": VideoCategory.HISTORY,
    "videolist": VideoCategory.HISTORY,
    "sharehistory": VideoCategory.SHARED,
    "sharehistorylist": VideoCategory.SHARED,
}

DEFAULT_CATEGORIES = frozenset({VideoCategory.FAVORITES})


def _norm_key(key: str) -> str:
    return re.sub(r"[\s_\-]", "", key).lower()


def _section_category(key: str) -> Optional[VideoCategory]:
    return _SECTION_CATEGORIES.get(_norm_key(key))


class TikTokExportSource(VideoSource):
    """Reads videos out of a TikTok data export (``.json`` or ``.txt``)."""

    name = "tiktok-export"

    def __init__(
        self,
        path: str | Path,
        categories: Iterable[VideoCategory] = DEFAULT_CATEGORIES,
    ) -> None:
        self.path = Path(path)
        self.categories = frozenset(categories)
        if not self.path.is_file():
            raise FileNotFoundError(f"TikTok export not found: {self.path}")

    # ------------------------------------------------------------------ public
    def videos(self) -> Iterator[SavedVideo]:
        if self.path.suffix.lower() == ".json":
            yield from self._from_json()
        else:
            yield from self._from_text()

    # -------------------------------------------------------------------- JSON
    def _from_json(self) -> Iterator[SavedVideo]:
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        yield from self._walk(data, current=None)

    def _walk(self, node: Any, current: Optional[VideoCategory]) -> Iterator[SavedVideo]:
        """Recursively walk ``node`` yielding videos in wanted sections."""
        if isinstance(node, dict):
            # A leaf entry looks like {"Date": "...", "Link": "https://..."}.
            entry = self._entry_from_dict(node, current)
            if entry is not None:
                yield entry
                return
            for key, value in node.items():
                category = _section_category(str(key)) or current
                yield from self._walk(value, category)
        elif isinstance(node, list):
            for item in node:
                yield from self._walk(item, current)

    def _entry_from_dict(
        self, node: dict, category: Optional[VideoCategory]
    ) -> Optional[SavedVideo]:
        link_key = next((k for k in node if "link" in _norm_key(str(k))), None)
        if link_key is None or not isinstance(node[link_key], str):
            return None
        if category is None or category not in self.categories:
            return None
        raw = node[link_key].strip()
        if not is_tiktok_url(raw):
            return None
        date_key = next((k for k in node if "date" in _norm_key(str(k))), None)
        saved_at = str(node[date_key]).strip() if date_key else None
        return SavedVideo(
            url=canonical_url(raw),
            video_id=extract_video_id(raw),
            category=category,
            saved_at=saved_at,
            source=str(self.path),
        )

    # -------------------------------------------------------------------- text
    _HEADING_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]+)\s*:?\s*$")
    _FIELD_RE = re.compile(r"^\s*(?P<key>[A-Za-z][A-Za-z ]*?)\s*:\s*(?P<value>.*)$")

    def _from_text(self) -> Iterator[SavedVideo]:
        """Parse the TXT export, which is a flat list of ``Key: value`` lines.

        Sections are introduced by a line such as ``Favorite Videos`` and
        each entry is ``Date: ...`` followed by ``Link: ...``.
        """
        category: Optional[VideoCategory] = None
        pending_date: Optional[str] = None
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                heading = self._HEADING_RE.match(line)
                if heading and _section_category(heading.group(1)) is not None:
                    category = _section_category(heading.group(1))
                    pending_date = None
                    continue
                field = self._FIELD_RE.match(line)
                if not field:
                    continue
                key = _norm_key(field.group("key"))
                value = field.group("value").strip()
                if "date" in key:
                    pending_date = value
                elif "link" in key:
                    urls = find_urls(value)
                    if category in self.categories and urls and is_tiktok_url(urls[0]):
                        yield SavedVideo(
                            url=canonical_url(urls[0]),
                            video_id=extract_video_id(urls[0]),
                            category=category,
                            saved_at=pending_date,
                            source=str(self.path),
                        )
                    pending_date = None
