"""Download every playlist track into music/, so the radio plays from disk.

The bot downloads missing files by itself too, but one at a time with a long
pause, as a background chore. This is the quick way to fill an empty library
in one sitting - and it lists what could not be fetched.

Entries without a link, or whose upload is gone, are found again by title
and the new link is pinned into the playlist (a .bak copy is kept first).

Safe to re-run: files already in music/ are skipped without touching the
network. Stop the bot first - two downloaders writing the same file collide.

    python tools/download_library.py
    python tools/download_library.py --pause 10
"""

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import music_library  # noqa: E402
from cogs.music import read_playlist_entries, replace_entry_url  # noqa: E402

PLAYLISTS = ["fantasy_list.txt", "party_list.txt"]

# Between downloads. Shorter than the bot's pause, since this runs once while
# someone watches it; 190 requests back to back would still be asking for a block.
DEFAULT_PAUSE_SECONDS = 5


def process(path, pause):
    have, fetched, failed = 0, 0, []
    backed_up = False

    for title, url in read_playlist_entries(path):
        if url and music_library.find_local(url):
            have += 1
            continue

        try:
            file, final_url = music_library.fetch(title, url)
        except music_library.LibraryError as exc:
            print(f"  BŁĄD  {title} -> {str(exc).splitlines()[0]}")
            failed.append(title)
            time.sleep(pause)
            continue

        fetched += 1
        print(f"  OK    {title} -> {file.name}")

        if final_url != url:
            if not backed_up:
                shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))
                backed_up = True
            replace_entry_url(str(path), title, url, final_url)
            print(f"        przypięto nowy link: {final_url}")

        time.sleep(pause)

    return have, fetched, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_SECONDS,
                        help="przerwa między pobraniami w sekundach")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="        %(levelname)s %(message)s")

    print(f"Biblioteka: {music_library.LIBRARY_DIR}")
    if music_library.COOKIES_FILE.is_file():
        print(f"Cookies: {music_library.COOKIES_FILE.name}")
    print()

    total_have, total_fetched, total_failed = 0, 0, []

    for name in PLAYLISTS:
        path = REPO / name
        if not path.exists():
            print(f"Pomijam {name}: nie ma takiego pliku.")
            continue

        print(f"--- {name} ---")
        have, fetched, failed = process(path, args.pause)
        total_have += have
        total_fetched += fetched
        total_failed += failed
        print(f"  Było: {have}, pobrano: {fetched}, błędy: {len(failed)}\n")

    print(f"RAZEM pobrano {total_fetched}, już było {total_have}.")
    if total_failed:
        print(f"Nie udało się ({len(total_failed)}) - bot spróbuje ponownie sam:")
        for title in total_failed:
            print(f"  - {title}")

    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
