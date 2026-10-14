"""Download videos with yt-dlp.

A :class:`TikTokDownloader` wraps ``yt_dlp.YoutubeDL`` with:

* a persistent :class:`~tiktok_dl.state.DownloadState` so re-runs skip what is
  already on disk and failures can be retried,
* a small thread pool with a global throttle so TikTok does not rate-limit us,
* structured :class:`~tiktok_dl.models.DownloadResult` objects instead of
  exceptions and log noise.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, Optional

from tiktok_dl.config import DownloadConfig
from tiktok_dl.models import DownloadResult, DownloadStatus, SavedVideo
from tiktok_dl.state import DownloadState

log = logging.getLogger(__name__)

ResultCallback = Callable[[DownloadResult, int, int], None]


class _YdlLogger:
    """Route yt-dlp's chatter through :mod:`logging`."""

    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose

    def debug(self, msg: str) -> None:
        # yt-dlp sends both debug and info-level messages here, prefixed with
        # "[debug] " for the former.
        if msg.startswith("[debug] "):
            if self.verbose:
                log.debug(msg[len("[debug] "):])
        else:
            log.debug(msg)

    def info(self, msg: str) -> None:
        log.debug(msg)

    def warning(self, msg: str) -> None:
        log.warning(msg)

    def error(self, msg: str) -> None:
        log.error(msg)


class _Throttle:
    """Ensure at least ``interval`` seconds pass between successive calls."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait_for = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self.interval
        if wait_for > 0:
            time.sleep(wait_for)


class TikTokDownloader:
    def __init__(self, config: DownloadConfig, state: DownloadState) -> None:
        self.config = config
        self.state = state
        self._throttle = _Throttle(config.delay)
        self._local = threading.local()

    # ------------------------------------------------------------ yt-dlp glue
    def build_ydl_opts(self, video: SavedVideo) -> dict:
        cfg = self.config
        out_dir = cfg.output_dir
        if cfg.group_by_category:
            out_dir = out_dir / video.category.value
        opts: dict = {
            "outtmpl": str(out_dir / cfg.filename_template),
            "retries": cfg.retries,
            "fragment_retries": cfg.retries,
            "continuedl": True,
            "overwrites": False,
            "noplaylist": True,
            "ignoreerrors": False,
            "quiet": True,
            "no_warnings": not cfg.verbose,
            "noprogress": True,
            "logger": _YdlLogger(cfg.verbose),
            "restrictfilenames": cfg.restrict_filenames,
            "windowsfilenames": True,
            "writeinfojson": cfg.write_metadata,
            "writethumbnail": cfg.write_thumbnail,
            "postprocessors": [],
        }
        if cfg.embed_metadata:
            opts["postprocessors"].append({"key": "FFmpegMetadata", "add_metadata": True})
        if cfg.cookies_file:
            opts["cookiefile"] = str(cfg.cookies_file)
        if cfg.cookies_from_browser:
            opts["cookiesfrombrowser"] = (cfg.cookies_from_browser,)
        if cfg.proxy:
            opts["proxy"] = cfg.proxy
        opts.update(cfg.extra_ydl_opts)
        return opts

    def _ydl(self, video: SavedVideo):
        """Return a per-thread ``YoutubeDL`` for this video's output folder."""
        import yt_dlp

        opts = self.build_ydl_opts(video)
        cache_key = opts["outtmpl"]
        cached = getattr(self._local, "ydl", None)
        if cached is None or cached[0] != cache_key:
            self._local.ydl = (cache_key, yt_dlp.YoutubeDL(opts))
        return self._local.ydl[1]

    # --------------------------------------------------------------- download
    def download(self, video: SavedVideo) -> DownloadResult:
        """Download one video, returning a result instead of raising."""
        if self.state.is_done(video):
            return DownloadResult(video, DownloadStatus.SKIPPED, error="already downloaded")

        import yt_dlp

        self._throttle.wait()
        try:
            ydl = self._ydl(video)
            info = ydl.extract_info(video.url, download=True)
            if info is None:
                raise yt_dlp.utils.DownloadError("yt-dlp returned no video info")
            filepath = _final_filepath(ydl, info)
            result = DownloadResult(
                video,
                DownloadStatus.OK,
                filepath=filepath,
                title=info.get("title"),
                uploader=info.get("uploader") or info.get("creator"),
            )
        except Exception as exc:  # noqa: BLE001 - we want every failure recorded
            result = DownloadResult(video, DownloadStatus.FAILED, error=_clean_error(exc))
        self.state.record(result)
        return result

    def download_all(
        self,
        videos: Iterable[SavedVideo],
        on_result: Optional[ResultCallback] = None,
    ) -> list[DownloadResult]:
        """Download ``videos`` concurrently; results are in completion order."""
        todo = list(videos)
        total = len(todo)
        results: list[DownloadResult] = []
        if total == 0:
            return results

        workers = min(self.config.workers, total)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dl") as pool:
            futures = {pool.submit(self.download, v): v for v in todo}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if on_result:
                    on_result(result, len(results), total)
        return results


def _final_filepath(ydl, info: dict) -> Optional[str]:
    """Figure out where yt-dlp actually wrote the file."""
    downloads = info.get("requested_downloads") or []
    for item in downloads:
        path = item.get("filepath")
        if path and Path(path).exists():
            return str(Path(path).resolve())
    try:
        guess = ydl.prepare_filename(info)
    except Exception:  # noqa: BLE001
        return None
    return str(Path(guess).resolve()) if Path(guess).exists() else guess


def _clean_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    # yt-dlp prefixes errors with "ERROR: [TikTok] <id>: " which is noise here.
    for prefix in ("ERROR: ", "\x1b[0;31mERROR:\x1b[0m "):
        if message.startswith(prefix):
            message = message[len(prefix):]
    # ... and suffixes it with boilerplate about filing a bug report.
    message = re.split(r";\s*please report this issue", message, maxsplit=1)[0]
    return message.strip()
