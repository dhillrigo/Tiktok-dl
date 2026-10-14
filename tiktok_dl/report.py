"""Human-readable summaries of a run."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable, TextIO

from tiktok_dl.models import DownloadResult, DownloadStatus

FAILED_LIST_FILENAME = "failed.txt"


def summarize(results: Iterable[DownloadResult]) -> Counter:
    return Counter(r.status for r in results)


def print_summary(results: list[DownloadResult], out: TextIO) -> None:
    counts = summarize(results)
    out.write(
        "\nDone. {ok} downloaded, {skipped} already present, {failed} failed.\n".format(
            ok=counts[DownloadStatus.OK],
            skipped=counts[DownloadStatus.SKIPPED],
            failed=counts[DownloadStatus.FAILED],
        )
    )
    failures = [r for r in results if r.status == DownloadStatus.FAILED]
    if failures:
        out.write("\nFailed videos:\n")
        for r in failures:
            out.write(f"  {r.video.url}\n    {r.error}\n")


def write_failed_list(results: Iterable[DownloadResult], output_dir: Path) -> Path | None:
    """Write failed URLs to ``failed.txt`` so they can be re-fed with ``--urls``."""
    failures = [r for r in results if r.status == DownloadStatus.FAILED]
    path = output_dir / FAILED_LIST_FILENAME
    if not failures:
        if path.exists():
            path.unlink()
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Videos that failed to download. Re-run with: tiktok-dl download --urls failed.txt\n")
        for r in failures:
            fh.write(f"{r.video.url}  # {r.error}\n")
    return path
