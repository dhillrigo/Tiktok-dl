"""Runtime configuration for a download run."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# yt-dlp output template. Produces e.g.
#   2024-03-17_some.creator_7301234567890123456.mp4
DEFAULT_FILENAME_TEMPLATE = (
    "%(upload_date>%Y-%m-%d|unknown-date)s_%(uploader|unknown)s_%(id)s.%(ext)s"
)


@dataclass
class DownloadConfig:
    output_dir: Path = Path("downloads")
    filename_template: str = DEFAULT_FILENAME_TEMPLATE
    #: Put each category (favorites, likes, ...) in its own sub-folder.
    group_by_category: bool = True
    cookies_file: Optional[Path] = None
    #: Browser name understood by yt-dlp, e.g. "chrome", "firefox", "edge".
    cookies_from_browser: Optional[str] = None
    proxy: Optional[str] = None
    #: Also write ``<video>.info.json`` next to each download.
    write_metadata: bool = False
    write_thumbnail: bool = False
    #: Embed title/uploader/date into the mp4 container (requires ffmpeg).
    embed_metadata: bool = False
    #: Number of concurrent downloads. Keep this low to avoid rate limiting.
    workers: int = 2
    #: Minimum seconds between the *start* of two downloads (global).
    delay: float = 1.0
    retries: int = 3
    #: Replace characters outside ASCII letters/digits in filenames.
    restrict_filenames: bool = False
    verbose: bool = False
    #: Escape hatch: raw options merged into the yt-dlp option dict last.
    extra_ydl_opts: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        if self.cookies_file is not None:
            self.cookies_file = Path(self.cookies_file)
        if self.workers < 1:
            raise ValueError("workers must be >= 1")
        if self.delay < 0:
            raise ValueError("delay must be >= 0")
