from tiktok_dl.urls import canonical_url, extract_video_id, find_urls, is_tiktok_url


def test_extract_video_id_from_various_forms():
    vid = "7301234567890123456"
    for url in [
        f"https://www.tiktok.com/@creator/video/{vid}",
        f"https://www.tiktok.com/@creator.name_x/video/{vid}?is_from_webapp=1&sender_device=pc",
        f"https://www.tiktokv.com/share/video/{vid}/",
        f"https://www.tiktok.com/embed/{vid}",
        f"https://m.tiktok.com/v/{vid}.html",
    ]:
        assert extract_video_id(url) == vid, url


def test_short_links_have_no_id_but_are_tiktok():
    assert extract_video_id("https://vm.tiktok.com/ZMabcdef/") is None
    assert is_tiktok_url("https://vm.tiktok.com/ZMabcdef/")
    assert is_tiktok_url("https://www.tiktok.com/t/ZTabcdef/")
    assert not is_tiktok_url("https://example.com/video/123")


def test_canonical_url():
    assert canonical_url("  https://www.tiktokv.com/share/video/7301234567890123456/ ") == (
        "https://www.tiktok.com/@_/video/7301234567890123456"
    )
    assert canonical_url("https://vm.tiktok.com/ZMabcdef/?utm=x") == "https://vm.tiktok.com/ZMabcdef/"
    assert canonical_url("https://example.com/x") == "https://example.com/x"


def test_find_urls():
    assert find_urls("see https://a.com/x and https://b.com/y.") == ["https://a.com/x", "https://b.com/y"]
