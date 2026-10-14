from pathlib import Path

import pytest

from tiktok_dl.models import VideoCategory
from tiktok_dl.sources import TikTokExportSource, UrlFileSource, dedupe

FIXTURES = Path(__file__).parent / "fixtures"


def test_json_export_defaults_to_favorites():
    videos = list(TikTokExportSource(FIXTURES / "user_data_tiktok.json").videos())
    assert [v.video_id for v in videos] == [
        "7301234567890123456",
        "7301234567890123457",
        "7301234567890123456",
    ]
    assert all(v.category is VideoCategory.FAVORITES for v in videos)
    assert videos[0].saved_at == "2024-03-17 10:11:12"
    assert videos[0].url == "https://www.tiktok.com/@_/video/7301234567890123456"


def test_json_export_other_categories():
    src = TikTokExportSource(
        FIXTURES / "user_data_tiktok.json",
        categories=[VideoCategory.LIKES, VideoCategory.HISTORY, VideoCategory.SHARED],
    )
    by_cat = {v.category: v.video_id for v in src.videos()}
    assert by_cat == {
        VideoCategory.LIKES: "7309999999999999999",
        VideoCategory.HISTORY: "7308888888888888888",
        VideoCategory.SHARED: "7307777777777777777",
    }


def test_json_export_tolerates_renamed_top_level(tmp_path):
    # Newer exports use "Your Activity" and different key casing.
    path = tmp_path / "export.json"
    path.write_text(
        '{"Your Activity": {"Favorite Videos": {"FavoriteVideoList": ['
        '{"date": "2025-01-01", "VideoLink": "https://www.tiktokv.com/share/video/7311111111111111111/"}]}}}',
        encoding="utf-8",
    )
    videos = list(TikTokExportSource(path).videos())
    assert [v.video_id for v in videos] == ["7311111111111111111"]
    assert videos[0].saved_at == "2025-01-01"


def test_txt_export():
    videos = list(TikTokExportSource(FIXTURES / "user_data_tiktok.txt").videos())
    assert [v.video_id for v in videos] == ["7301234567890123456", "7301234567890123457"]
    assert videos[1].saved_at == "2024-03-16 09:08:07"

    likes = list(TikTokExportSource(FIXTURES / "user_data_tiktok.txt", [VideoCategory.LIKES]).videos())
    assert [v.video_id for v in likes] == ["7309999999999999999"]


def test_missing_export_raises():
    with pytest.raises(FileNotFoundError):
        TikTokExportSource(FIXTURES / "nope.json")


def test_url_file_source():
    videos = list(UrlFileSource(FIXTURES / "urls.txt").videos())
    assert [v.url for v in videos] == [
        "https://www.tiktok.com/@_/video/7301234567890123456",
        "https://vm.tiktok.com/ZMabcdefg/",
    ]
    assert videos[1].video_id is None
    assert videos[1].key == videos[1].url


def test_dedupe_keeps_first():
    videos = list(TikTokExportSource(FIXTURES / "user_data_tiktok.json").videos())
    unique = dedupe(videos)
    assert [v.video_id for v in unique] == ["7301234567890123456", "7301234567890123457"]
    assert unique[0].saved_at == "2024-03-17 10:11:12"
