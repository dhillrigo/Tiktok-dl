"""Video sources: things that produce a list of :class:`SavedVideo`."""

from tiktok_dl.sources.base import VideoSource, dedupe
from tiktok_dl.sources.export import TikTokExportSource
from tiktok_dl.sources.urlfile import UrlFileSource

__all__ = ["VideoSource", "TikTokExportSource", "UrlFileSource", "dedupe"]
