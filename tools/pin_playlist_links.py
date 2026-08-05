"""Pin a YouTube link to every playlist entry that still lacks one.

The radio used to resolve each entry by title at startup, which meant it played
whatever YouTube ranked first that day - not necessarily the track that won the
vote. New votes now store "Title<TAB>URL"; this script backfills the entries
that predate that change.

Safe to re-run: entries that already carry a URL are left untouched, and each
file is backed up before it is rewritten.

Requires a running Lavalink (it does the resolving), but not the bot itself -
this talks to the Lavalink REST API directly.

    python tools/pin_playlist_links.py
    python tools/pin_playlist_links.py --dry-run
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLAYLISTS = ["fantasy_list.txt", "party_list.txt"]

LAVALINK = "http://127.0.0.1:2333"
PASSWORD = "youshallnotpass"

# Mirrors MAX_TRACK_MINUTES in cogs/music.py: the radio refuses longer results,
# so pinning one here would only produce an entry it then skips.
MAX_TRACK_MINUTES = 9

# Lavalink is local, but a burst of a few hundred searches still hammers
# YouTube from a single address. A short pause keeps it well-behaved.
DELAY_SECONDS = 0.2


def is_url(value):
    return value.startswith(("http://", "https://"))


def split_entry(line):
    """Return (title, url or None) - same rules as the bot's parser."""

    line = line.strip()

    title, tab, tail = line.rpartition("\t")
    if tab and is_url(tail.strip()):
        return title.strip(), tail.strip()

    title, space, tail = line.rpartition(" ")
    if space and is_url(tail):
        return title.strip(), tail

    return line, None


def search(title):
    """Ask Lavalink for the first acceptable YouTube match, or None."""

    query = urllib.parse.quote(f"ytsearch:{title}")
    request = urllib.request.Request(
        f"{LAVALINK}/v4/loadtracks?identifier={query}",
        headers={"Authorization": PASSWORD},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if payload.get("loadType") not in ("search", "track"):
        return None

    data = payload.get("data") or []
    if isinstance(data, dict):
        data = [data]

    for track in data:
        info = track.get("info", {})
        if info.get("length", 0) / 60 / 1000 < MAX_TRACK_MINUTES and info.get("uri"):
            return info["uri"]

    return None


def check_lavalink():
    try:
        request = urllib.request.Request(
            f"{LAVALINK}/v4/info", headers={"Authorization": PASSWORD}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response).get("version", {}).get("semver", "?")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"Nie mogę połączyć się z Lavalinkiem pod {LAVALINK}: {exc}")
        print("Uruchom go najpierw:  java -jar Lavalink.jar")
        return None


def process(path, dry_run):
    lines = path.read_text(encoding="utf8").splitlines()

    pinned, already, failed = 0, 0, []
    output = []

    for line in lines:
        if not line.strip():
            output.append(line)
            continue

        title, url = split_entry(line)

        if url:
            already += 1
            output.append(line)
            continue

        try:
            found = search(title)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            print(f"  BŁĄD  {title} -> {exc}")
            failed.append(title)
            output.append(line)
            continue

        if found:
            pinned += 1
            # Keep the curated title untouched; only append the link. Replacing
            # it with YouTube's own title would break duplicate detection for
            # entries people already know by name.
            output.append(f"{title}\t{found}")
            print(f"  OK    {title}")
        else:
            failed.append(title)
            output.append(line)
            print(f"  BRAK  {title}")

        time.sleep(DELAY_SECONDS)

    if not dry_run and pinned:
        backup = path.with_suffix(path.suffix + ".bak")
        # newline="\n" keeps the files on LF endings. Without it Python would
        # rewrite every line to CRLF on Windows, turning a handful of pinned
        # links into a diff touching all 189 entries.
        backup.write_text("\n".join(lines) + "\n", encoding="utf8", newline="\n")
        path.write_text("\n".join(output) + "\n", encoding="utf8", newline="\n")
        print(f"  Kopia zapasowa: {backup.name}")

    return pinned, already, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="pokaż, co by się zmieniło, bez zapisu")
    args = parser.parse_args()

    version = check_lavalink()
    if not version:
        return 1

    print(f"Lavalink {version} odpowiada.\n")

    total_pinned, total_already, total_failed = 0, 0, []

    for name in PLAYLISTS:
        path = REPO / name
        if not path.exists():
            print(f"Pomijam {name}: nie ma takiego pliku.")
            continue

        print(f"--- {name} ---")
        pinned, already, failed = process(path, args.dry_run)
        total_pinned += pinned
        total_already += already
        total_failed += failed
        print(f"  Przypięto: {pinned}, miało już link: {already}, bez wyniku: {len(failed)}\n")

    print(f"RAZEM przypięto {total_pinned}, pominięto {total_already} z linkiem.")
    if total_failed:
        print(f"Bez wyniku ({len(total_failed)}) - zostają na wyszukiwaniu po tytule:")
        for title in total_failed:
            print(f"  - {title}")
    if args.dry_run:
        print("\n(dry-run: nic nie zapisano)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
