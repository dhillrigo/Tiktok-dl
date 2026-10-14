"""URL parsing and normalisation for TikTok links."""

from __future__ import annotations

import re
from typing import Optional

# Long-form links that carry the numeric video id.
#   https://www.tiktok.com/@user/video/7301234567890123456
#   https://www.tiktokv.com/share/video/7301234567890123456/
#   https://www.tiktok.com/embed/7301234567890123456
_VIDEO_ID_RE = re.compile(
    r"https?://(?:www\.|m\.)?tiktok(?:v)?\.com/"
    r"(?:(?:@[\w.\-]*|share|embed|v)/)?(?:video/)?(?P<id>\d{15,25})",
)

# Short links that must be resolved by yt-dlp (they redirect to the long form).
#   https://vm.tiktok.com/ZMabcdef/   https://vt.tiktok.com/ZSabcdef/
#   https://www.tiktok.com/t/ZTabcdef/
_SHORT_LINK_RE = re.compile(
    r"https?://(?:(?:vm|vt)\.tiktok\.com|(?:www\.)?tiktok\.com/t)/(?P<code>\w+)",
)

_ANY_URL_RE = re.compile(r"https?://\S+")


def extract_video_id(url: str) -> Optional[str]:
    """Return the numeric TikTok video id embedded in ``url`` if present."""
    match = _VIDEO_ID_RE.search(url.strip())
    return match.group("id") if match else None


def is_tiktok_url(url: str) -> bool:
    url = url.strip()
    return bool(_VIDEO_ID_RE.search(url) or _SHORT_LINK_RE.search(url))


def canonical_url(url: str) -> str:
    """Normalise ``url`` to a form yt-dlp handles reliably.

    Long-form links are rewritten to ``https://www.tiktok.com/@_/video/<id>``
    (TikTok ignores the username segment when the id is known). Short links
    are returned trimmed of whitespace and tracking query strings.
    """
    url = url.strip()
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.tiktok.com/@_/video/{video_id}"
    short = _SHORT_LINK_RE.search(url)
    if short:
        return short.group(0).rstrip("/") + "/"
    return url


def find_urls(text: str) -> list[str]:
    """Return every http(s) URL found in a blob of text, in order."""
    return [m.group(0).rstrip(".,;)") for m in _ANY_URL_RE.finditer(text)]
