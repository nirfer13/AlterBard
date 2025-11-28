import os
import urllib.parse

from globals.globalvariables import MUSIC_HTTP_BASE, MUSIC_SHARE

def build_playlist_from_folder() -> list[str]:
    """
    Scans the network folder and returns a list of FULL HTTP URLs
    pointing to each .mp3 file on the local HTTP server.

    1. Collect .mp3 files from the network share.
    2. URL-encode filenames (spaces, unicode chars).
    3. Build HTTP URLs that Wavelink/Lavalink can load directly.
    """
    files = [
        f for f in os.listdir(MUSIC_SHARE)
        if f.lower().endswith(".mp3") and os.path.isfile(os.path.join(MUSIC_SHARE, f))
    ]

    # Encode filenames for safe inclusion in a URL
    urls = [f"{MUSIC_HTTP_BASE}/{urllib.parse.quote(f)}" for f in files]
    return urls