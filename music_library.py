"""Local music library: the radio plays files from disk, not YouTube streams.

Streaming every track from YouTube around the clock is exactly the traffic
YouTube flags as a bot - the August 2026 Lavalink logs are full of "This video
requires login", 403s and broken stream ciphers, burner account or not. The
playlists are fixed, curated lists, so each track is downloaded once with
yt-dlp and Lavalink plays the file. YouTube is only touched when a track is
proposed, voted in, or its file is missing.

Files are named after the video, not the title: music/<youtube id>.<ext>, or
music/x_<hash of the URL>.<ext> for anything else (SoundCloud). The playlist
files keep their "Title<TAB>URL" format unchanged - the URL alone says which
file belongs to an entry.

Everything here blocks (network, disk, ffmpeg): the bot calls it through
asyncio.to_thread, tools/download_library.py directly.
"""

import dataclasses
import hashlib
import logging
import re
from pathlib import Path

import imageio_ffmpeg
import yt_dlp

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent
LIBRARY_DIR = REPO / "music"

# Optional cookies.txt (Netscape format) exported from the burner account's
# browser. Downloads work without it from this machine (checked 2026-10-25);
# it is here for the day YouTube starts asking this IP to sign in.
COOKIES_FILE = REPO / "BotTokens" / "youtube_cookies.txt"

# Mirrors MAX_TRACK_MINUTES in cogs/music.py.
MAX_TRACK_MINUTES = 9

# SoundCloud answers Go+ tracks with a 30-second preview, which is not the
# track anybody asked for.
MIN_TRACK_SECONDS = 35

# How many results a search offers to choose from - matches the five
# reaction options of the chooser in cogs/music.py.
SEARCH_RESULTS = 5

AUDIO_EXTENSIONS = ("webm", "m4a", "opus", "ogg", "mp3", "flac", "wav", "mp4")

_YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([\w-]{11})"
)

# yt-dlp messages meaning the upload itself is gone - only then is another one
# searched for by title. A block ("Sign in to confirm you're not a bot") must
# not swap a correct link for whatever the search happens to rank first.
_GONE_MARKERS = (
    "unavailable",
    "available in your country",
    "private video",
    "has been removed",
    "has been terminated",
    "no longer available",
    "copyright",
    "http error 404",
)


class LibraryError(Exception):
    pass


class SearchFailed(LibraryError):
    pass


class DownloadFailed(LibraryError):
    def __init__(self, message: str, gone: bool = False):
        super().__init__(message)
        # True when the upload no longer exists, as opposed to a block or a
        # network hiccup that a later retry may well get past.
        self.gone = gone


@dataclasses.dataclass
class Candidate:
    """A search result, shaped like the parts of wavelink.Playable the vote uses."""

    title: str
    uri: str
    length: int  # milliseconds, like Playable.length
    artwork: str = None
    source: str = "youtube"

    def __str__(self) -> str:
        return self.title


class _YtDlpLog:
    """Route yt-dlp's output into our logging instead of the console."""

    def debug(self, message):
        logger.debug(message)

    def info(self, message):
        logger.debug(message)

    def warning(self, message):
        # imageio-ffmpeg ships ffmpeg without ffprobe. yt-dlp mentions that on
        # every SoundCloud download and then fixes the file correctly anyway.
        if "ffprobe" in message:
            logger.debug(message)
        else:
            logger.warning(message)

    def error(self, message):
        # Raised right after as DownloadError, which the caller logs.
        logger.debug(message)


def _options(**extra) -> dict:
    options = {
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "logger": _YtDlpLog(),
        # YouTube's player challenges need a JavaScript runtime. Node is
        # installed on this machine; deno, yt-dlp's default, is not.
        "js_runtimes": {"node": {}},
        # SoundCloud serves HLS, which without ffmpeg ends up as a broken
        # DASH m4a that Lavalink reads as 10 seconds long. The pip-installed
        # binary keeps the bot free of a system-wide ffmpeg install.
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
    }

    if COOKIES_FILE.is_file():
        options["cookiefile"] = str(COOKIES_FILE)

    options.update(extra)
    return options


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def track_key(url: str) -> str:
    """The file name (without extension) a URL's audio is stored under."""

    if match := _YOUTUBE_ID.search(url):
        return match.group(1)

    return "x_" + hashlib.sha1(url.strip().encode("utf8")).hexdigest()[:16]


def find_local(url: str):
    """Return the downloaded file for this URL, or None."""

    key = track_key(url)

    # Exact names only: yt-dlp's own leftovers (.part, .temp.m4a) of an
    # interrupted download must not pass for a finished file.
    for extension in AUDIO_EXTENSIONS:
        path = LIBRARY_DIR / f"{key}.{extension}"
        if path.is_file() and path.stat().st_size > 0:
            return path

    return None


def _candidate(entry: dict, source: str):
    duration = entry.get("duration")
    url = entry.get("webpage_url") or entry.get("url")

    # No duration means a live stream; under the minimum, a preview clip.
    if not duration or duration < MIN_TRACK_SECONDS or not url or not entry.get("title"):
        return None

    # Not simply the last one: for a pasted link yt-dlp hands the list over
    # unsorted, and the last entry there is a tiny frame grab.
    thumbnails = entry.get("thumbnails") or []
    best = max(thumbnails, default=None,
               key=lambda thumb: (thumb.get("preference") or 0, thumb.get("width") or 0))

    return Candidate(
        title=entry["title"],
        uri=url,
        length=int(duration * 1000),
        artwork=best.get("url") if best else entry.get("thumbnail"),
        source=source,
    )


def _search(prefix: str, query: str, source: str) -> list:
    with yt_dlp.YoutubeDL(_options(extract_flat="in_playlist")) as ydl:
        result = ydl.extract_info(f"{prefix}{SEARCH_RESULTS}:{query}", download=False)

    found = (_candidate(entry, source) for entry in (result or {}).get("entries") or [])
    return [candidate for candidate in found if candidate]


def _describe(url: str) -> list:
    """Turn a pasted link into a one-element result list."""

    with yt_dlp.YoutubeDL(_options()) as ydl:
        info = ydl.extract_info(url, download=False, process=False)

    # A playlist link has entries instead of a duration and is refused here,
    # as it always was.
    info = info or {}
    candidate = _candidate(info, info.get("extractor_key", "link").lower())
    if candidate:
        # The canonical link rather than the pasted one: youtu.be/...?t=42
        # and watch?v=... are the same track, and duplicate detection compares
        # URLs as plain strings.
        candidate.uri = info.get("webpage_url") or url
    return [candidate] if candidate else []


def search(query: str) -> list:
    """Find candidates for a query: YouTube first, SoundCloud as the fallback.

    SoundCloud is only asked when YouTube fails or has nothing usable - its
    catalogue of game soundtracks is far patchier, but it is a second source
    that YouTube's blocks do not reach.
    """

    if is_url(query):
        try:
            return _describe(query)
        except yt_dlp.utils.DownloadError as exc:
            raise SearchFailed(str(exc)) from exc

    try:
        if found := _search("ytsearch", query, "youtube"):
            return found
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("YouTube search for '%s' failed: %s - trying SoundCloud.", query, exc)

    try:
        return _search("scsearch", query, "soundcloud")
    except yt_dlp.utils.DownloadError as exc:
        raise SearchFailed(str(exc)) from exc


def download(url: str) -> Path:
    """Download one URL into the library, unless it is already there."""

    if existing := find_local(url):
        return existing

    LIBRARY_DIR.mkdir(exist_ok=True)

    options = _options(
        # Opus from YouTube, AAC from SoundCloud: both are formats Lavalink
        # decodes from a file, so nothing gets re-encoded.
        format="bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
        outtmpl=str(LIBRARY_DIR / f"{track_key(url)}.%(ext)s"),
    )

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        gone = any(marker in message.lower() for marker in _GONE_MARKERS)
        raise DownloadFailed(message, gone=gone) from exc

    if (path := find_local(url)) is None:
        raise DownloadFailed(f"yt-dlp finished, but no file appeared for {url}")

    return path


def fetch(title: str, url: str = None) -> tuple:
    """Make sure a playlist entry has a file; return (path, its URL).

    The URL returned differs from the one given when the entry had none, or
    when its upload is gone - a title search then picks the replacement, and
    the caller should pin it into the playlist so the search is not repeated.
    """

    if url:
        try:
            return download(url), url
        except DownloadFailed as exc:
            if not exc.gone:
                raise
            logger.warning("'%s' is gone (%s) - searching for another upload.", title, exc)

    try:
        candidates = search(title)
    except SearchFailed as exc:
        raise DownloadFailed(f"Search for '{title}' failed: {exc}") from exc

    for candidate in candidates:
        if candidate.length / 60 / 1000 < MAX_TRACK_MINUTES:
            return download(candidate.uri), candidate.uri

    raise DownloadFailed(f"Nothing usable found for '{title}'.", gone=True)
