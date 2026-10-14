# tiktok-dl

Download **all of your saved (favorited) TikTok videos** to your computer, with
resumable progress, retry of failures and tidy filenames.

TikTok does not expose your Saved list publicly, so this tool reads it from the
official **"Download your data"** export that TikTok gives you, then fetches each
video with [yt-dlp](https://github.com/yt-dlp/yt-dlp). You can also feed it a
plain list of URLs.

## Installation

Requires Python 3.9+ and, optionally, `ffmpeg` (for `--embed-metadata`).

```bash
git clone https://github.com/dhillrigo/Tiktok-dl.git
cd Tiktok-dl
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Step 1 – request your data from TikTok

1. In the TikTok app: **Profile → ☰ → Settings and privacy → Account → Download your data**
   (on the web: <https://www.tiktok.com/setting/download-your-data>).
2. Choose **JSON** (TXT works too) and request the file.
3. Wait for TikTok to prepare it (usually a few hours, can be a couple of days),
   then download the zip from the same page and unzip it. You will get a file
   named something like `user_data_tiktok.json`.

The export contains a `Favorite Videos` section with the link and date of
every video you saved, plus your likes, watch history and share history.

## Step 2 – download

```bash
# See what was found in the export
tiktok-dl list --export user_data_tiktok.json --with-dates

# Download every saved video into ./downloads/favorites/
tiktok-dl download --export user_data_tiktok.json

# Saved + liked videos, 3 at a time, with metadata sidecars
tiktok-dl download --export user_data_tiktok.json --category favorites likes -j 3 --metadata
```

Files are named `YYYY-MM-DD_<creator>_<video id>.mp4` (change with `--template`,
which accepts any yt-dlp output template).

### Resuming and retrying

Progress is recorded in `downloads/.tiktok-dl-state.json`. Re-running the same
command skips everything already on disk, so you can interrupt with Ctrl-C at
any time. Videos that failed are listed at the end and written to
`downloads/failed.txt`; retry them with:

```bash
tiktok-dl download --export user_data_tiktok.json --retry-failed
# or
tiktok-dl download --urls downloads/failed.txt

# Inspect the state file
tiktok-dl status            # or: tiktok-dl status --failed
```

Some failures are permanent: the creator deleted the video, made it private, or
the account was banned. Those will fail every time.

If many videos fail with "Unable to download webpage" or HTTP 403 errors, TikTok
is probably blocking plain requests. Install the impersonation extra so yt-dlp
can look like a real browser, and keep yt-dlp up to date (TikTok changes often):

```bash
pip install -e ".[impersonate]"
pip install -U yt-dlp
```

### Private, age-restricted or region-locked videos

Pass your logged-in session cookies so TikTok treats the request as you:

```bash
tiktok-dl download --export user_data_tiktok.json --cookies-from-browser chrome
# or export cookies.txt with a browser extension and use --cookies cookies.txt
```

### Other options

| Flag | Purpose |
| --- | --- |
| `--urls FILE` / positional URLs | download from a list of links instead of (or as well as) the export |
| `--category favorites likes history shared` | which export lists to use (default `favorites`) |
| `-o DIR`, `--flat` | output folder; `--flat` skips the per-category sub-folder |
| `-j N`, `--delay S` | parallel downloads (default 2) and minimum seconds between starts (default 1) |
| `--metadata`, `--thumbnail`, `--embed-metadata` | keep `.info.json`, thumbnail, or embed tags into the mp4 |
| `--limit N`, `--dry-run` | try things out on a few videos first |
| `--proxy URL`, `--retries N`, `--restrict-filenames`, `-v` | the usual |

Be gentle: TikTok rate-limits aggressive clients. The defaults (2 workers,
1 second between starts) are a safe starting point for a few thousand videos.

## Project layout

```
tiktok_dl/
├── cli.py            argparse front-end: download / list / status
├── config.py         DownloadConfig dataclass
├── models.py         SavedVideo, DownloadResult, enums
├── urls.py           TikTok URL recognition and normalisation
├── sources/
│   ├── base.py       VideoSource interface + dedupe()
│   ├── export.py     parser for the TikTok data export (JSON and TXT)
│   └── urlfile.py    one-URL-per-line text files
├── downloader.py     yt-dlp wrapper: thread pool, throttle, result objects
├── state.py          resumable state file
└── report.py         end-of-run summary and failed.txt
tests/                pytest suite (no network needed)
```

To extend it with a new source (for example scraping a collection page), implement
`VideoSource.videos()` and wire it into `cli.collect_videos`.

## Development

```bash
pip install -e .[dev]
pytest
```

## Disclaimer

Only download content you have the right to keep. This tool is for personal
archiving of your own saved list and is not affiliated with TikTok.
