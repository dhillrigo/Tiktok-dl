from pathlib import Path

from tiktok_dl.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_command(capsys):
    assert main(["list", "--export", str(FIXTURES / "user_data_tiktok.json"), "--with-dates"]) == 0
    out = capsys.readouterr()
    lines = out.out.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("2024-03-17 10:11:12")
    assert "2 video(s)" in out.err


def test_list_combines_sources_and_limit(capsys):
    rc = main([
        "list", "--export", str(FIXTURES / "user_data_tiktok.json"), "--category", "favorites", "likes",
        "--urls", str(FIXTURES / "urls.txt"), "https://www.tiktok.com/@x/video/7300000000000000000", "--limit", "4",
    ])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "https://www.tiktok.com/@_/video/7301234567890123456",
        "https://www.tiktok.com/@_/video/7301234567890123457",
        "https://www.tiktok.com/@_/video/7309999999999999999",
        "https://vm.tiktok.com/ZMabcdefg/",
    ]


def test_download_dry_run(tmp_path, capsys):
    rc = main(["download", "--export", str(FIXTURES / "user_data_tiktok.json"), "-o", str(tmp_path), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2 to download" in out
    assert not (tmp_path / ".tiktok-dl-state.json").exists()


def test_missing_file_is_a_clean_error(tmp_path, capsys):
    rc = main(["download", "--export", str(tmp_path / "missing.json"), "-o", str(tmp_path)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_bad_url_rejected(capsys):
    try:
        main(["list", "https://example.com/video/1"])
    except SystemExit as exc:
        assert "not a TikTok URL" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_status_without_state(tmp_path, capsys):
    assert main(["status", "-o", str(tmp_path)]) == 1
