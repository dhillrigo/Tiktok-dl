"""Command line interface.

Examples::

    # Download every video in the "Saved"/Favorites list of your data export
    tiktok-dl download --export user_data_tiktok.json

    # Also grab liked videos, using your browser's login cookies
    tiktok-dl download --export user_data_tiktok.json --category favorites likes \
        --cookies-from-browser chrome

    # Just print the URLs that would be downloaded
    tiktok-dl list --export user_data_tiktok.json

    # Download an ad-hoc list of URLs
    tiktok-dl download --urls my_links.txt
    tiktok-dl download https://www.tiktok.com/@someone/video/7301234567890123456
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from tiktok_dl import __version__
from tiktok_dl.config import DEFAULT_FILENAME_TEMPLATE, DownloadConfig
from tiktok_dl.downloader import TikTokDownloader
from tiktok_dl.models import DownloadResult, DownloadStatus, SavedVideo, VideoCategory
from tiktok_dl.report import print_summary, write_failed_list
from tiktok_dl.sources import TikTokExportSource, UrlFileSource, dedupe
from tiktok_dl.state import STATE_FILENAME, DownloadState
from tiktok_dl.urls import canonical_url, extract_video_id, is_tiktok_url

log = logging.getLogger("tiktok_dl")

_CATEGORY_CHOICES = [c.value for c in VideoCategory if c is not VideoCategory.URL_LIST]


# --------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiktok-dl",
        description="Download your saved TikTok videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples::", 1)[1] if __doc__ else None,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared "where do the videos come from" options.
    source = argparse.ArgumentParser(add_help=False)
    source.add_argument(
        "--export", "-e", type=Path, metavar="FILE",
        help="TikTok data export (user_data_tiktok.json or the .txt variant)",
    )
    source.add_argument(
        "--category", "-c", nargs="+", choices=_CATEGORY_CHOICES, default=["favorites"],
        help="which lists to take from the export (default: favorites)",
    )
    source.add_argument(
        "--urls", "-u", type=Path, metavar="FILE",
        help="text file with one TikTok URL per line",
    )
    source.add_argument("url", nargs="*", help="TikTok video URLs to download")
    source.add_argument("--limit", type=int, metavar="N", help="stop after N videos")

    dl = sub.add_parser("download", parents=[source], help="download videos")
    dl.add_argument("--output", "-o", type=Path, default=Path("downloads"), help="output folder (default: ./downloads)")
    dl.add_argument("--flat", action="store_true", help="don't create a sub-folder per category")
    dl.add_argument("--template", default=DEFAULT_FILENAME_TEMPLATE, help="yt-dlp filename template")
    dl.add_argument("--cookies", type=Path, metavar="FILE", help="Netscape-format cookies.txt (for private/age-gated videos)")
    dl.add_argument("--cookies-from-browser", metavar="BROWSER", help="read login cookies from a browser (chrome, firefox, edge, safari, ...)")
    dl.add_argument("--proxy", help="proxy URL passed to yt-dlp")
    dl.add_argument("--workers", "-j", type=int, default=2, help="parallel downloads (default: 2)")
    dl.add_argument("--delay", type=float, default=1.0, help="minimum seconds between download starts (default: 1)")
    dl.add_argument("--retries", type=int, default=3, help="per-video network retries (default: 3)")
    dl.add_argument("--metadata", action="store_true", help="write a .info.json next to each video")
    dl.add_argument("--thumbnail", action="store_true", help="also save the thumbnail image")
    dl.add_argument("--embed-metadata", action="store_true", help="embed title/author/date into the mp4 (needs ffmpeg)")
    dl.add_argument("--restrict-filenames", action="store_true", help="ASCII-only filenames")
    dl.add_argument("--retry-failed", action="store_true", help="re-attempt videos that failed in a previous run")
    dl.add_argument("--dry-run", "-n", action="store_true", help="list what would be downloaded and exit")
    dl.add_argument("--verbose", "-v", action="store_true", help="show yt-dlp debug output")

    ls = sub.add_parser("list", parents=[source], help="print the video URLs found in the sources")
    ls.add_argument("--with-dates", action="store_true", help="prefix each URL with the date it was saved")

    st = sub.add_parser("status", help="summarise a previous run's state file")
    st.add_argument("--output", "-o", type=Path, default=Path("downloads"), help="output folder used for the run")
    st.add_argument("--failed", action="store_true", help="only list failed videos")
    return parser


# ---------------------------------------------------------------- collection
def collect_videos(args: argparse.Namespace) -> list[SavedVideo]:
    videos: list[SavedVideo] = []
    if args.export:
        categories = [VideoCategory(c) for c in args.category]
        videos.extend(TikTokExportSource(args.export, categories).videos())
    if args.urls:
        videos.extend(UrlFileSource(args.urls).videos())
    for raw in args.url or []:
        if not is_tiktok_url(raw):
            raise SystemExit(f"error: not a TikTok URL: {raw}")
        videos.append(SavedVideo(url=canonical_url(raw), video_id=extract_video_id(raw), source="cli"))
    if not videos and not (args.export or args.urls or args.url):
        raise SystemExit("error: give --export FILE, --urls FILE, or one or more URLs (see --help)")
    videos = dedupe(videos)
    if args.limit is not None:
        videos = videos[: max(args.limit, 0)]
    return videos


# ------------------------------------------------------------------ commands
def cmd_list(args: argparse.Namespace) -> int:
    videos = collect_videos(args)
    for v in videos:
        prefix = f"{v.saved_at or '?':<20} " if args.with_dates else ""
        print(f"{prefix}{v.url}")
    print(f"{len(videos)} video(s)", file=sys.stderr)
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    config = DownloadConfig(
        output_dir=args.output,
        filename_template=args.template,
        group_by_category=not args.flat,
        cookies_file=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        proxy=args.proxy,
        write_metadata=args.metadata,
        write_thumbnail=args.thumbnail,
        embed_metadata=args.embed_metadata,
        workers=args.workers,
        delay=args.delay,
        retries=args.retries,
        restrict_filenames=args.restrict_filenames,
        verbose=args.verbose,
    )
    videos = collect_videos(args)
    state = DownloadState(config.output_dir / STATE_FILENAME)

    pending = [v for v in videos if not state.is_done(v)]
    if not args.retry_failed:
        previously_failed = [v for v in pending if state.has_failed(v)]
        pending = [v for v in pending if not state.has_failed(v)]
    else:
        previously_failed = []

    print(
        f"{len(videos)} video(s) found, {len(videos) - len(pending) - len(previously_failed)} already downloaded, "
        f"{len(previously_failed)} previously failed (use --retry-failed), {len(pending)} to download."
    )
    if args.dry_run:
        for v in pending:
            print(f"  {v.url}")
        return 0
    if not pending:
        return 0

    downloader = TikTokDownloader(config, state)
    width = len(str(len(pending)))

    def on_result(result: DownloadResult, done: int, total: int) -> None:
        tag = {DownloadStatus.OK: "ok  ", DownloadStatus.SKIPPED: "skip", DownloadStatus.FAILED: "FAIL"}[result.status]
        detail = Path(result.filepath).name if result.filepath else (result.error or "")
        print(f"[{done:>{width}}/{total}] {tag} {result.video.url}  {detail}", flush=True)

    try:
        results = downloader.download_all(pending, on_result=on_result)
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved; re-run the same command to resume.", file=sys.stderr)
        return 130

    print_summary(results, sys.stdout)
    failed_path = write_failed_list(results, config.output_dir)
    if failed_path:
        print(f"Failed URLs written to {failed_path}")
    return 1 if any(r.status == DownloadStatus.FAILED for r in results) else 0


def cmd_status(args: argparse.Namespace) -> int:
    state_path = args.output / STATE_FILENAME
    if not state_path.is_file():
        print(f"no state file at {state_path}", file=sys.stderr)
        return 1
    entries = DownloadState(state_path).entries()
    counts = {s.value: 0 for s in DownloadStatus}
    for entry in entries.values():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
        if args.failed and entry["status"] != DownloadStatus.FAILED.value:
            continue
        line = f"{entry['status']:<7} {entry['url']}"
        if entry.get("filepath"):
            line += f"  -> {entry['filepath']}"
        if entry.get("error"):
            line += f"  ({entry['error']})"
        print(line)
    print(f"{len(entries)} tracked: " + ", ".join(f"{k}={v}" for k, v in counts.items()), file=sys.stderr)
    return 0


# ---------------------------------------------------------------------- main
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        if args.command == "download":
            return cmd_download(args)
        if args.command == "list":
            return cmd_list(args)
        if args.command == "status":
            return cmd_status(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
