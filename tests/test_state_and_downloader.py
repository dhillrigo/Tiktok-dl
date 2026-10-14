import threading
import time
from pathlib import Path

from tiktok_dl.config import DownloadConfig
from tiktok_dl.downloader import TikTokDownloader
from tiktok_dl.models import DownloadResult, DownloadStatus, SavedVideo, VideoCategory
from tiktok_dl.state import DownloadState


def _video(vid: str, category=VideoCategory.FAVORITES) -> SavedVideo:
    return SavedVideo(url=f"https://www.tiktok.com/@_/video/{vid}", video_id=vid, category=category)


def test_state_roundtrip_and_missing_file(tmp_path):
    state_path = tmp_path / "state.json"
    state = DownloadState(state_path)
    video = _video("1")
    assert state.status_of(video) is None

    target = tmp_path / "1.mp4"
    target.write_bytes(b"x")
    state.record(DownloadResult(video, DownloadStatus.OK, filepath=str(target)))
    reloaded = DownloadState(state_path)
    assert reloaded.is_done(video)
    assert reloaded.entries()[video.key]["status"] == "ok"

    target.unlink()
    assert not reloaded.is_done(video)  # file deleted -> download again

    reloaded.record(DownloadResult(video, DownloadStatus.FAILED, error="boom"))
    assert DownloadState(state_path).has_failed(video)


class FakeYdl:
    """Stands in for yt_dlp.YoutubeDL in tests."""

    calls: list = []
    lock = threading.Lock()

    def __init__(self, opts):
        self.opts = opts

    def extract_info(self, url, download=True):
        with self.lock:
            FakeYdl.calls.append((url, time.monotonic()))
        vid = url.rsplit("/", 1)[-1]
        if vid.endswith("9"):
            import yt_dlp

            raise yt_dlp.utils.DownloadError("ERROR: [TikTok] Video not available")
        out = Path(self.opts["outtmpl"]).parent / f"{vid}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"video")
        return {"id": vid, "title": f"t{vid}", "uploader": "u", "requested_downloads": [{"filepath": str(out)}]}


def test_downloader_records_results_and_skips_done(tmp_path, monkeypatch):
    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYdl)
    FakeYdl.calls = []

    config = DownloadConfig(output_dir=tmp_path / "out", workers=2, delay=0)
    state = DownloadState(tmp_path / "out" / "state.json")
    dl = TikTokDownloader(config, state)

    videos = [_video("11"), _video("22", VideoCategory.LIKES), _video("39")]
    results = {r.video.video_id: r for r in dl.download_all(videos)}

    assert results["11"].status is DownloadStatus.OK
    assert results["11"].filepath.endswith("favorites/11.mp4")
    assert results["22"].filepath.endswith("likes/22.mp4")
    assert results["39"].status is DownloadStatus.FAILED
    assert results["39"].error == "[TikTok] Video not available"

    # Second run: finished videos are skipped without touching yt-dlp.
    FakeYdl.calls = []
    again = {r.video.video_id: r for r in dl.download_all(videos)}
    assert again["11"].status is DownloadStatus.SKIPPED
    assert [u.rsplit("/", 1)[-1] for u, _ in FakeYdl.calls] == ["39"]


def test_throttle_spaces_out_downloads(tmp_path, monkeypatch):
    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYdl)
    FakeYdl.calls = []
    config = DownloadConfig(output_dir=tmp_path, workers=4, delay=0.15)
    dl = TikTokDownloader(config, DownloadState(tmp_path / "state.json"))
    dl.download_all([_video(str(i)) for i in (1, 2, 3)])
    times = sorted(t for _, t in FakeYdl.calls)
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= 0.14 for g in gaps), gaps


def test_build_ydl_opts(tmp_path):
    config = DownloadConfig(
        output_dir=tmp_path, cookies_file=tmp_path / "c.txt", cookies_from_browser="firefox",
        embed_metadata=True, group_by_category=False, extra_ydl_opts={"format": "best"},
    )
    opts = TikTokDownloader(config, DownloadState(tmp_path / "s.json")).build_ydl_opts(_video("1"))
    assert opts["outtmpl"].startswith(str(tmp_path))
    assert "/favorites/" not in opts["outtmpl"]
    assert opts["cookiefile"] == str(tmp_path / "c.txt")
    assert opts["cookiesfrombrowser"] == ("firefox",)
    assert opts["postprocessors"][0]["key"] == "FFmpegMetadata"
    assert opts["format"] == "best"


def test_clean_error_strips_yt_dlp_boilerplate():
    from tiktok_dl.downloader import _clean_error

    exc = Exception(
        "ERROR: [TikTok] 123: Unable to download webpage: HTTP Error 403; please report this issue on "
        "https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template."
    )
    assert _clean_error(exc) == "[TikTok] 123: Unable to download webpage: HTTP Error 403"
    assert _clean_error(Exception("")) == "Exception"
