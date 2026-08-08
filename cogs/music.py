import asyncio
import logging
import datetime as dt
import json
import os
import random
import tempfile
import typing as t

import discord
import wavelink
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

global VoteChannelID, AnnouceChannelID, CommandChannelID, VoiceChannelID, LogChannelID, BardID, GuildID, votesReq
#VoteChannelID = 1028340292895645696 #Debug
VoteChannelID = 1059731255786229770
#AnnouceChannelID = 1028340292895645696 #Debug
AnnouceChannelID = 696932659833733131
#CommandChannelID = 1057198781206106153 #Debug
CommandChannelID = 776379796367212594
VoiceChannelID = 1056200069952589924 # Stasiek's channel
#VoiceChannelID = 687630935419912204
LogChannelID = 1057198781206106153
BardID = 1004008220437778523
GuildID = 686137998177206281
votesReq = 6
#votesReq = 2

# Every track comes from YouTube - Lavalink's built-in sources are disabled
# in application.yml and the youtube-plugin handles search and playback.
YT_SOURCE = wavelink.TrackSource.YouTube

# Tracks longer than this many minutes never make it into the repertoire.
MAX_TRACK_MINUTES = 9

# How many failures in a row mean a YouTube outage rather than a single
# taken-down video. Wavelink disables autoplay for good after 3 consecutive
# errors, so we step in before that happens.
FAILURE_THRESHOLD = 3

# How long to keep the radio silent after a detected YouTube outage.
FAILURE_COOLDOWN = 120

# Lavalink reports frame statistics roughly once a minute. This many reports in
# a row with zero frames sent, while a track is supposedly playing, means the
# audio is going nowhere and the voice connection needs rebuilding.
SILENT_STATS_LIMIT = 3

# Names the bot gives its voice channel. Setting a topic as well was dropped:
# this server's blocked-word filter refused every variant tried, so the feature
# only produced warnings.
CHANNEL_NAME_FANTASY = "Scena Barda"
CHANNEL_NAME_PARTY = "Vixapol!!!"
CHANNEL_NAME_PARTY_SWITCH = "MORDOWNIA!!!"

# The party playlist takes over on Friday afternoon and runs until Friday ends,
# so it goes back to fantasy at midnight. Monday is 0, so Friday is 4.
PARTY_WEEKDAY = 4
PARTY_START_HOUR = 16

# How often the scheduler checks whether it is time to switch. A minute keeps
# the switch punctual - the old hourly check could be a full hour late.
PLAYLIST_CHECK_SECONDS = 60

# Votes in progress are kept here so a restart does not orphan them.
PENDING_VOTES_FILE = "pending_votes.json"

# How long a vote stays open before it is dropped.
VOTE_TIMEOUT_HOURS = 12

OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}
VOTES = {
    "✅": 0,
    "❌": 1
}

async def search_youtube(query: str) -> wavelink.Search:
    """Search YouTube for a track.

    Playable.search detects URLs on its own and skips the search prefix for
    them, so this one function handles both plain titles and ready links.
    """

    return await wavelink.Playable.search(query.strip("<>"), source=YT_SOURCE)

def local_now() -> dt.datetime:
    """Local wall-clock time.

    The old code used utcnow() + 2 hours, which hardcodes Polish summer time
    and is an hour off all winter. datetime.now() follows the machine's own
    zone including its DST changes, which is what "Friday at 16:00" means.
    """

    return dt.datetime.now()

def is_party_time(now: dt.datetime = None) -> bool:
    """Whether the party playlist should be on air at this moment."""

    now = now or local_now()

    return now.weekday() == PARTY_WEEKDAY and now.hour >= PARTY_START_HOUR

def read_playlist_lines(file: str) -> list:
    """Read a playlist file, dropping blank lines."""

    with open(file, encoding="utf8") as handle:
        return [line for line in handle.read().splitlines() if line.strip()]

def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))

def parse_playlist_entry(line: str) -> tuple:
    """Split a playlist line into a display title and an optional exact URL.

    Voted-in tracks are stored as "Title<TAB>URL" so the radio replays exactly
    the video that won the vote, instead of whatever a title search happens to
    rank first. Older title-only entries are still valid and simply come back
    with no URL, which makes the two formats mixable in one file.
    """

    line = line.strip()

    title, tab, tail = line.rpartition("\t")
    if tab and _is_url(tail.strip()):
        return title.strip(), tail.strip()

    # Tolerate an entry pasted by hand as "Title https://..." with a space.
    title, space, tail = line.rpartition(" ")
    if space and _is_url(tail):
        return title.strip(), tail

    return line, None

def format_entry(title: str, uri: str = None) -> str:
    """Render one playlist line: the title stays first so the file remains
    readable and editable by hand, with the URL pinned after a tab."""

    return f"{title}\t{uri}" if uri else title

def format_playlist_entry(track: wavelink.Playable) -> str:
    return format_entry(track.title, track.uri)

def load_pending_votes() -> list:
    """Read the votes that were still open when the bot last stopped."""

    try:
        with open(PENDING_VOTES_FILE, "r", encoding="utf8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as exc:
        # A corrupt file must not stop the bot from starting; the worst case is
        # that a few votes have to be cast again.
        logger.warning("Could not read %s: %s", PENDING_VOTES_FILE, exc)
        return []

def save_json_atomically(path: str, data) -> None:
    """Write JSON so that an interrupted write cannot destroy the old file.

    Writing straight into the target truncates it first, so a crash or a power
    cut mid-write leaves it empty or half-written. authors_list.json holds the
    entire helper ranking, which is not something to lose that way. Writing to
    a temporary file and renaming is atomic, on Windows too.
    """

    directory = os.path.dirname(os.path.abspath(path)) or "."

    with tempfile.NamedTemporaryFile("w", encoding="utf8", dir=directory,
                                     delete=False, suffix=".tmp") as handle:
        temporary = handle.name
        try:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            # The original file is safe either way, but a failed write must not
            # leave its half-finished temporary behind to pile up.
            handle.close()
            os.unlink(temporary)
            raise

    os.replace(temporary, path)

def save_pending_votes(records: list) -> None:
    save_json_atomically(PENDING_VOTES_FILE, records)

def count_votes(message: discord.Message) -> tuple:
    """Count the yes/no reactions on a vote message.

    Reactions are matched by emoji instead of by position: the old code read
    reactions[0] and reactions[1], which silently misreads the tally as soon as
    somebody adds an unrelated reaction first.
    """

    yes = no = 0

    for reaction in message.reactions:
        emoji = str(reaction.emoji)
        if emoji == "✅":
            yes = reaction.count
        elif emoji == "❌":
            no = reaction.count

    return yes, no

async def collect_reacters(message: discord.Message, emoji: str) -> set:
    """Everyone who reacted to the message with the given emoji."""

    voters = set()

    for reaction in message.reactions:
        if str(reaction.emoji) != emoji:
            continue
        async for user in reaction.users():
            voters.add(user)

    return voters

def read_playlist_titles(file: str) -> list:
    """Return only the titles from a playlist file, ignoring any stored URLs.

    Duplicate detection compares titles, so it has to look past the URL half
    of an entry.
    """

    with open(file, "r", encoding="utf8") as handle:
        return [
            parse_playlist_entry(line)[0]
            for line in handle.read().splitlines()
            if line.strip()
        ]

class AlreadyConnectedToChannel(commands.CommandError):
    pass

class NoVoiceChannel(commands.CommandError):
    pass

class QueueIsEmpty(commands.CommandError):
    pass

class NoTracksFound(commands.CommandError):
    pass

class NoMoreTracks(commands.CommandError):
    pass

class DuplicatedTrack(commands.CommandError):
    pass

class InvalidTrackName(commands.CommandError):
    pass

class LongTrack(commands.CommandError):
    pass

class Player(wavelink.Player):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # With loop_all, once the whole playlist has been played wavelink moves
        # the tracks from history back into the queue - the radio never stops.
        self.queue.mode = wavelink.QueueMode.loop_all
        # partial, not enabled: wavelink should play *our* playlist in order
        # instead of topping it up with YouTube recommendations that never went
        # through the vote and do not fit the mood.
        self.autoplay = wavelink.AutoPlayMode.partial
        self.bot = bot

    async def teardown(self):
        """Destroy the player."""
        try:
            await self._destroy()
        except KeyError:
            pass

    async def add_singletrack(self, tracks: wavelink.Search) -> wavelink.Playable:
        """Add a single track to the queue."""

        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.Playlist):
            # tracks is a playlist...
            raise NoTracksFound

        # Take the first result within the length limit - longer hits are
        # usually hour-long compilations rather than the track we asked for.
        track = next(
            (t for t in tracks if t.length / 60 / 1000 < MAX_TRACK_MINUTES),
            None
        )

        if track is None:
            raise LongTrack

        await self.queue.put_wait(track)

        # Deliberately does not start playback. Loading a playlist takes about
        # 25 seconds, and starting whenever nothing happened to be playing cut
        # the current track off part-way through the load. The caller starts it
        # once instead.
        return track

    async def start_playback(self):
        """Get first track from the queue and start playing."""

        if self.queue.is_empty:
            return

        track = self.queue.get()
        logger.info("Now playing: %s", track)
        await self.play(track)

    async def get_track(self, ctx, tracks, file: str="fantasy_list.txt") -> wavelink.Playable:
        """Show currently playing track."""
        if not tracks:
            LogChannel = self.bot.get_channel(LogChannelID)
            await ctx.send("Zewnętrzny serwer muzyczny prawdopodobnie jest obciążony i nie mógł " +
                           "odnaleźć utworu. Spróbuj jeszcze raz.")
            await LogChannel.send("Nie znaleziono track.")
            raise NoTracksFound

        if len(tracks) == 1:
            return tracks[0]
        else:
            if (track := await self.choose_track(ctx, tracks, file)) is not None:
                return track

    async def choose_track(self, ctx, tracks, file: str="fantasy_list.txt"):
        """Choose one track when multiple were found."""
        def _check(r, u):
            return (
                r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Znaleziono kilka odpowiadających propozycji. Wybierz jedną.",
            description=(
                "\n".join(
                    f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
                    for i, t in enumerate(tracks[:5])
                )
            ),
            colour=ctx.author.colour,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_footer(text=f"Dodany przez {ctx.author.display_name}",
                         icon_url=ctx.author.avatar)

        msg = await ctx.send(embed=embed)

        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
        else:
            await msg.delete()
            lines = read_playlist_titles(file)

            if tracks[OPTIONS[reaction.emoji]].title in lines:
                await ctx.send("<@" + str(ctx.author.id) + ">, " +
                               "mam już taki utwór w repertuarze, więc musisz wybrać coś innego.")
                raise DuplicatedTrack
            else:
                return tracks[OPTIONS[reaction.emoji]]

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Client = bot
        self.wavelink = wavelink
        self.player = None
        # How many tracks in a row failed to play.
        self._failed_tracks = 0
        # Makes sure only one radio recovery attempt runs at a time.
        self._recovery_lock = asyncio.Lock()
        # on_ready runs again on every reconnect; startup must only run once.
        self._votes_restored = False
        # Consecutive Lavalink stat reports with no audio frames sent.
        self._silent_stats = 0
    # self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Bot ready...")

        # on_ready fires again after every reconnect, and restarting the
        # watchers each time would count the same vote several times over.
        if self._votes_restored:
            return
        self._votes_restored = True

        await self.delete_bard_messages()
        await self.restore_pending_votes()
        await self.setup_hook()

    async def load_playlist(self, playlist: list, voice_channel: discord.VoiceChannel):
        """Search YouTube for every playlist entry and queue it.

        Returns (number of tracks added, list of skipped queries).
        """

        added = 0
        skipped = []

        # queue.reset() on a playlist switch puts the queue mode back to
        # "normal". Without restoring loop_all the radio would play the
        # playlist once and fall silent, as the queue never returns from history.
        self.player.queue.mode = wavelink.QueueMode.loop_all

        for line in playlist:
            line = str(line).strip()
            if not line:
                continue

            title, url = parse_playlist_entry(line)

            if not self.player.connected:
                await voice_channel.connect(cls=self.player)

            try:
                await self.queue_entry(title, url)
                added += 1

                # Start once, on the first track that made it into the queue.
                # Everything after that is autoplay's job.
                if added == 1 and not self.player.playing:
                    await self.player.start_playback()
            except NoTracksFound:
                # YouTube returned nothing - e.g. the video was taken down.
                logger.warning("No results for: %s", title)
                skipped.append(title)
            except LongTrack:
                logger.warning("All results too long (>%s min): %s", MAX_TRACK_MINUTES, title)
                skipped.append(title)
            except wavelink.WavelinkException as exc:
                # A Lavalink/YouTube side error - it must not block the rest.
                logger.warning("Lavalink could not handle '%s': %s", title, exc, exc_info=True)
                skipped.append(title)

        logger.info("Loaded %s tracks, skipped %s.", added, len(skipped))
        if skipped:
            logger.info("Skipped: %s", " | ".join(skipped[:10]))

        return added, skipped

    async def set_channel_look(self, channel: discord.VoiceChannel, name: str):
        """Rename the voice channel without ever failing the caller.

        Discord can refuse a rename - a blocked word, a rate limit - and that
        must not abort startup. It used to: the exception propagated out of
        on_wavelink_node_ready, so the playlist never loaded and the radio
        stayed silent over a purely cosmetic detail.
        """

        try:
            await channel.edit(name=name)
        except discord.HTTPException as exc:
            logger.warning("Could not set the channel name: %s", exc)

    async def queue_entry(self, title: str, url: str = None):
        """Queue one playlist entry, preferring its pinned URL.

        The fallback to a title search is what keeps the radio from losing a
        track permanently: a pinned video can be taken down, made private or
        geo-blocked, and then only a fresh search will find another upload.
        """

        if url:
            try:
                await self.player.add_singletrack(await search_youtube(url))
                return
            except (NoTracksFound, LongTrack, wavelink.WavelinkException) as exc:
                logger.warning(
                    "Pinned link failed for '%s' (%s): %s - falling back to a search.",
                    title, url, exc
                )

        await self.player.add_singletrack(await search_youtube(title))

    async def playlist_scheduler(self):
        """Swap between the fantasy and party playlists on schedule.

        This runs as a detached task, so an unhandled exception would end the
        switching for good - and silently, because nothing awaits it. Every
        iteration is therefore guarded: a failed switch is logged and retried
        on the next tick instead of killing the schedule until a restart.
        """

        party_on = is_party_time()
        logger.info("Playlist scheduler running. Party playlist on air: %s.", party_on)

        while True:
            await asyncio.sleep(PLAYLIST_CHECK_SECONDS)

            try:
                should_party = is_party_time()
                if should_party == party_on:
                    continue

                logger.info("Switching to the %s playlist.",
                            "party" if should_party else "fantasy")
                await self.switch_playlist(to_party=should_party)
                party_on = should_party
            except Exception:
                # party_on is deliberately left untouched, so the switch is
                # attempted again on the next tick.
                logger.exception("Playlist switch failed, retrying in %s s.",
                                 PLAYLIST_CHECK_SECONDS)

    async def switch_playlist(self, to_party: bool):
        """Put the other playlist on air."""

        LogChannel = self.bot.get_channel(LogChannelID)
        VoiceChannel = self.bot.get_channel(VoiceChannelID)
        guild = self.bot.get_guild(GuildID)

        file = "party_list.txt" if to_party else "fantasy_list.txt"

        # Re-read from disk rather than reuse the lists loaded at startup:
        # anything voted in during the week would otherwise be missing until
        # the next restart.
        entries = read_playlist_lines(file)
        random.shuffle(entries)

        await self.set_channel_look(
            VoiceChannel,
            CHANNEL_NAME_PARTY_SWITCH if to_party else CHANNEL_NAME_FANTASY)
        await self.set_bot_nick(guild, "DJ Stachu" if to_party else "Bard Stasiek")
        await self.announce(
            LogChannel,
            "Zmiana playlisty na imprezową." if to_party else "Zmiana playlisty na fantasy.")

        if to_party:
            await self.announce(
                self.bot.get_channel(AnnouceChannelID),
                "HALO, HALO! TUTAJ DJ STACHU! JESTEŚCIE GOTOWI? Zapraszam na <#"
                + str(VoiceChannelID)
                + "> imprezę <:OOOO:982215120199507979> <a:RainbowPls:882184531917037608>!")

        await self.player.stop()
        self.player.queue.reset()
        await self.load_playlist(entries, VoiceChannel)

    async def announce(self, channel, message: str):
        """Send a message, treating a missing channel as a warning not a crash.

        A None channel here used to take the whole scheduler down with an
        AttributeError, and with it every future playlist switch.
        """

        if channel is None:
            logger.warning("Channel unavailable, message not sent: %s", message)
            return

        try:
            await channel.send(message)
        except discord.HTTPException as exc:
            logger.warning("Could not send a message: %s", exc)

    async def set_bot_nick(self, guild, nick: str):
        """Rename the bot on the server, tolerating a cache miss."""

        member = guild.get_member(BardID) if guild is not None else None

        if member is None:
            logger.warning("Bot member %s not in cache, nickname unchanged.", BardID)
            return

        try:
            await member.edit(nick=nick)
        except discord.HTTPException as exc:
            logger.warning("Could not change the nickname: %s", exc)

    async def setup_hook(self) -> None:
        # Wavelink 2.0 has made connecting Nodes easier... Simply create each Node
        # and pass it to NodePool.connect with the client/bot.
        node = wavelink.Node(uri='http://127.0.0.1:2333', password='youshallnotpass')
        await wavelink.Pool.connect(nodes=[node], client=self.bot)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """Give info that node is ready"""

        logger.info("Node ready: %s", getattr(node, "node", node))
        voice_channel = self.bot.get_channel(VoiceChannelID)
        logger.info("Channel acquired.")

        LogChannel = self.bot.get_channel(LogChannelID)
        VoiceChannel: discord.VoiceChannel = self.bot.get_channel(VoiceChannelID)
        guild = self.bot.get_guild(GuildID)

        # The same rule the scheduler uses. Judging by the weekday alone meant
        # a restart on Friday morning already put the party playlist on air,
        # hours before it was due.
        party_on = is_party_time()

        if party_on:
            entries = read_playlist_lines("party_list.txt")
            await self.set_channel_look(VoiceChannel, CHANNEL_NAME_PARTY)
            await self.announce(LogChannel, "Zmiana playlisty na imprezową.")
            await self.set_bot_nick(guild, "DJ Stachu")
        else:
            entries = read_playlist_lines("fantasy_list.txt")
            await self.set_channel_look(VoiceChannel, CHANNEL_NAME_FANTASY)
            await self.announce(LogChannel, "Zmiana playlisty na fantasy.")
            await self.set_bot_nick(guild, "Bard Stasiek")

        random.shuffle(entries)

        await self.announce(LogChannel, "Bard gotowy do śpiewania!")
        self.player = Player(bot=self.bot)
        vc: Player = await VoiceChannel.connect(cls=self.player)

        added, skipped = await self.load_playlist(entries, VoiceChannel)
        await self.announce(
            LogChannel,
            f"Załadowano {added} utworów z YouTube, pominięto {len(skipped)}.")

        if not added:
            await self.announce(
                LogChannel,
                "Nie udało się załadować **żadnego** utworu z YouTube. "
                "Sprawdź logi Lavalinka - najczęściej oznacza to przeterminowany "
                "youtube-plugin."
            )

        # Watches the clock and swaps the playlist at the scheduled time.
        self.task = self.bot.loop.create_task(self.playlist_scheduler())

    @commands.command("play")
    async def play(self, ctx: commands.Context, *, search: str) -> None:
        """Simple play command."""

        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        tracks: wavelink.Search = await search_youtube(search)
        if not tracks:
            await ctx.send(f'Przepraszam, nie mogę znaleźć podanego utworu: `{search}`')
            return

        logger.debug("Found track: %s", tracks[0])
        track: wavelink.Playable = tracks[0]

        await vc.play(track)
        logger.info("Playing song...")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Show currently playing track."""

        # A track started, so the earlier errors were one-offs.
        self._failed_tracks = 0

        # We do not refill the queue by hand here: with QueueMode.loop_all
        # wavelink puts the played track into history itself and moves history
        # back into the queue once it empties. A manual put_wait duplicated
        # every single track.
        player = payload.player or self.player
        left = len(player.queue) if player else 0
        logger.info("Now playing: %s | queued: %s", payload.track.title, left)

        try:
            activity = discord.CustomActivity(f"Odgrywa: {payload.track.title}")
            await self.bot.change_presence(status=discord.Status.do_not_disturb,
                                        activity=activity)
        except (discord.DiscordException, ConnectionError) as exc:
            # Not just HTTPException: while the gateway is reconnecting this
            # raises ConnectionResetError, which used to escape the handler and
            # be reported as an unhandled error on every such reconnect.
            logger.warning("Could not set the presence: %s", exc)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Get next track after finishing previous one."""
        logger.info("Track ended (%s).", payload.reason)

        # Only react to the radio - the $play command builds its own player.
        if not self.is_radio_player(payload.player):
            return

        # Wavelink's autoplay starts the next track. All that is left here is a
        # safety net for the case where the player ends up with nothing playing.
        if payload.reason in ("replaced", "stopped"):
            return

        await asyncio.sleep(2)

        if not self.player.playing and not self._recovery_lock.locked():
            logger.warning("Autoplay did not move on - restarting the radio manually.")
            await self.player.start_playback()

    @commands.Cog.listener()
    async def on_wavelink_websocket_closed(self, payload: wavelink.WebsocketClosedEventPayload):
        """Discord closed the voice websocket.

        This is the failure that leaves the bot sitting in the channel in
        silence: Lavalink keeps decoding and the queue keeps advancing, so the
        log looks perfectly healthy, but the audio has nowhere to go. Nothing
        listened for this event before, so the radio stayed mute until somebody
        noticed by ear and restarted it.
        """

        logger.warning("Voice websocket closed: %s (reason: %s, by remote: %s).",
                       payload.code, payload.reason, payload.by_remote)

        if self.is_radio_player(payload.player):
            await self.reconnect_voice()

    @commands.Cog.listener()
    async def on_wavelink_stats_update(self, payload: wavelink.StatsEventPayload):
        """Catch a player that reports playing while sending no audio.

        The websocket-closed event covers the case Discord tells us about. This
        is the safety net for silence it does not announce.
        """

        if self.player is None or not self.player.playing:
            self._silent_stats = 0
            return

        # frames is None when Lavalink has nothing to report, which is not the
        # same as reporting zero - only an explicit zero counts as silence.
        if payload.frames is None or payload.frames.sent > 0:
            self._silent_stats = 0
            return

        self._silent_stats += 1
        logger.warning("A track is playing but no audio frames were sent (%s/%s).",
                       self._silent_stats, SILENT_STATS_LIMIT)

        if self._silent_stats >= SILENT_STATS_LIMIT:
            self._silent_stats = 0
            logger.error("The radio has gone silent - rebuilding the voice connection.")
            await self.reconnect_voice()

    async def reconnect_voice(self):
        """Rebuild the voice connection while keeping the queue intact."""

        if self._recovery_lock.locked():
            return

        async with self._recovery_lock:
            channel = self.bot.get_channel(VoiceChannelID)
            if channel is None or self.player is None:
                logger.warning("Cannot reconnect: no channel or no player.")
                return

            logger.info("Reconnecting to %s.", channel)

            try:
                # Moving to the same channel makes Discord hand out a fresh
                # voice session, which wavelink forwards to Lavalink. The player
                # and its queue survive - a disconnect/connect cycle would
                # destroy the player and lose everything queued.
                await self.player.move_to(channel)
            except (discord.HTTPException, wavelink.WavelinkException) as exc:
                logger.warning("Voice reconnect failed: %s", exc)
                return

            await asyncio.sleep(5)

            if not self.player.playing:
                await self.player.start_playback()

    def is_radio_player(self, player) -> bool:
        """Whether the event belongs to the radio player, not a one-off $play one."""

        return self.player is not None and (player is None or player is self.player)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        """A track blew up during playback."""

        if self.is_radio_player(payload.player):
            await self.handle_track_failure(payload.track, str(payload.exception))

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        """A track stopped returning audio data."""

        if self.is_radio_player(payload.player):
            await self.handle_track_failure(payload.track, f"utwór zaciął się ({payload.threshold} ms)")

    async def handle_track_failure(self, track: wavelink.Playable, reason: str) -> None:
        """React to a track that could not be played.

        A single miss (a taken-down video) is normal - autoplay simply moves
        on. Several in a row mean a YouTube outage: without a pause autoplay
        burns through the whole queue in seconds, and after three errors
        wavelink disables autoplay for good and the radio goes quiet.
        """

        self._failed_tracks += 1
        logger.error("Playback error on '%s': %s (consecutive: %s)", track, reason, self._failed_tracks)

        if self._failed_tracks < FAILURE_THRESHOLD or self._recovery_lock.locked():
            return

        async with self._recovery_lock:
            player = self.player
            if player is None:
                return

            previous_mode = player.autoplay
            player.autoplay = wavelink.AutoPlayMode.disabled
            await player.stop(force=True)

            LogChannel = self.bot.get_channel(LogChannelID)
            if LogChannel is not None:
                await LogChannel.send(
                    f"{self._failed_tracks} utworów z rzędu nie dało się odtworzyć "
                    f"(ostatni błąd: `{reason[:200]}`). Milknę na {FAILURE_COOLDOWN}s. "
                    "Jeśli to się powtarza, sprawdź wersję youtube-plugin w application.yml."
                )

            await asyncio.sleep(FAILURE_COOLDOWN)

            # Wavelink counts its own errors and after three in a row stops
            # playing anything - and it never resets that counter by itself.
            # Without this the radio stays silent until the bot is restarted.
            if hasattr(player, "_error_count"):
                player._error_count = 0

            self._failed_tracks = 0
            player.autoplay = previous_mode
            await player.start_playback()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or self.player is None:
            return

        # The player may still have no channel (e.g. while the bot starts up) -
        # it is then None or the MISSING sentinel, so we test for truthiness.
        current_voice_channel = self.player.channel
        if not current_voice_channel:
            return

        voice_channel = self.bot.get_channel(VoiceChannelID)

        if current_voice_channel.id != VoiceChannelID and not [m for m in current_voice_channel.members if not m.bot]:

            logger.info("Changing voice channel automatically.")
            await self.player.move_to(voice_channel)

    async def is_channel(ctx):
        return ctx.channel.id == CommandChannelID or ctx.channel.id == 1057198781206106153
    
    async def delete_bard_messages(self):
        """Delete leftover bard vote messages, keeping the live ones."""

        vote_channel = self.bot.get_channel(VoteChannelID)
        if vote_channel is None:
            return

        # Votes still running must survive this sweep - otherwise the restart
        # that restore_pending_votes is meant to recover from would itself
        # delete the very messages being recovered.
        pending = {record["message_id"] for record in load_pending_votes()}

        counter = 0
        async for message in vote_channel.history(limit=15):
            if message.author == self.bot.user and message.id not in pending:
                await message.delete()
                counter += 1

        logger.info("Deleted %s bard vote messages, kept %s still running.",
                    counter, len(pending))

    async def singme(self, ctx, player: wavelink.Player):
        logger.info("Player changing the voice channel.")
        voice_channel = self.bot.get_channel(VoiceChannelID)
        channel = await player.move_to(ctx.author.channel)

    async def check_track(self, ctx,
                          player: wavelink.Player,
                          query: str,
                          file: str="fantasy_list.txt"):

        lines = read_playlist_titles(file)

        if query in lines:
            await ctx.send("<@" + str(ctx.author.id) + ">, mam już taki utwór w repertuarze, więc musisz wybrać coś innego.")
            raise DuplicatedTrack

        if len(query.split()) <= 1:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"* .")
            raise InvalidTrackName

        if len(query) < 10:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu jest za krótki. Spróbuj coś dłuższego.")
            raise InvalidTrackName

        try:
            tracks: wavelink.Search = await search_youtube(query)
        except wavelink.WavelinkException as exc:
            logger.warning("Search for '%s' failed: %s", query, exc, exc_info=True)
            await ctx.send("Nie udało mi się teraz zapytać YouTube'a. Spróbuj za chwilę.")
            raise NoTracksFound

        track = await self.player.get_track(ctx, tracks, file)

        if track is None:
            return None

        if track.length/60/1000 > MAX_TRACK_MINUTES:
            await ctx.send("<@" + str(ctx.author.id) + ">, utwór jest za długi! Wybierz utwór krótszy niż 8 minut.")
            raise LongTrack

        return track
    
    async def check_bard_support(self, ctx):
        
        filename="authors_list.json"

        with open(filename,'r', encoding="utf8") as file:
            # First we load existing data into a dict.
            file_data = json.load(file)

            id = str(ctx.author.id)
            if id in file_data.keys():
                pass
            else:
                file_data[id] = 0

        await ctx.send("<@" + str(ctx.author.id)+ ">, pomogłeś mi " + str(file_data[id]) + " razy! Dziena! <:peepoBlush:984769061340737586>")

    async def ranking_bard_support(self, ctx):
        
        filename="authors_list.json"

        with open(filename,'r', encoding="utf8") as file:
            # First we load existing data into a dict.
            file_data = json.load(file)

            id = str(ctx.author.id)
            if id in file_data.keys():
                pass
            else:
                file_data[id] = 0

            ranking = dict(sorted(file_data.items(), key=lambda item: item[1], reverse=True))

        rankingString = ""
        x=1
        for Person in ranking.items():
            user = self.bot.get_user(int(Person[0]))
            if user:
                rankingString += str(x) + ". **" + user.name + "** - " + str(Person[1]) + " pkt.\n"
                x+=1
                if x >= 11:
                    break

        #Embed create   
        emb=discord.Embed(title='Ranking pomocników barda Staśka!', description=rankingString, color=0xCE7E00)
        emb.set_thumbnail(url="https://www.altermmo.pl/wp-content/uploads/BardLogo.png")
        emb.set_footer(text='Oby gust muzyczny był z Wami!')
        await ctx.send(embed=emb)


    async def bard_support(self, users: set, author_id: int, success: bool):
        """Award points for taking part in a vote and hand out the roles.

        Takes an author id rather than a Context: a vote restored after a
        restart has no Context to speak of, only what was written to disk.
        """

        filename="authors_list.json"
        Channel = self.bot.get_channel(CommandChannelID)
        guild = self.bot.get_guild(GuildID)

        if guild is None:
            logger.warning("Guild %s unavailable - skipping the vote rewards.", GuildID)
            return

        with open(filename,'r', encoding="utf8") as file:
            # First we load existing data into a dict.
            file_data = json.load(file)

        for user in users:
            id = str(user.id)
            if id != str(author_id):
                if id in file_data.keys():
                    file_data[id] += 0.25
                else:
                    file_data[id] = 0.25

        if success:
            id = str(author_id)
            if id in file_data.keys():
                file_data[id] += 1
            else:
                file_data[id] = 1

        save_json_atomically(filename, file_data)

        role1 = discord.utils.get(guild.roles, id=1054138582811549776) #Pomagier
        role2 = discord.utils.get(guild.roles, id=1059766781889228820) #Mlodszy Bard
        role3 = discord.utils.get(guild.roles, id=1059766769524424714) #Zastepca Barda

        for reacter in users:
            id = str(reacter.id)
            # reaction.users() yields User objects, which have no roles.
            # Roles can only be granted to a Member of this guild.
            user = guild.get_member(reacter.id)
            if user is None:
                continue
            if id in file_data.keys() and user.id != 1004008220437778523:
                if file_data[id] >= 5 and file_data[id] < 20 and role1 not in user.roles:
                    await user.add_roles(role1)
                    await Channel.send("<@" + str(user.id) + ">! Za wkład w mój muzyczny rozwój otrzymałeś rangę mojego pomagiera! Kto wie, pomagaj mi dalej, a być może czeka Cię nagroda. <:Siur:717731500883181710>")
                if file_data[id] >= 20 and file_data[id] < 50 and role2 not in user.roles:
                    await user.remove_roles(role1)
                    await user.add_roles(role2)
                    await Channel.send("<@" + str(user.id) + ">! Widzę,że nie odpuszczasz. W nagrodę dostałeś rangę Młodszego Barda! Może już wystarczy? <:Kermitpls:790963160106008607>")
                if file_data[id] >= 50 and role3 not in user.roles:
                    await user.remove_roles(role2)
                    await user.add_roles(role3)
                    await Channel.send("<@" + str(user.id) + ">! Czekaj... Czy Ty chcesz mnie wygryźć? Dobra, możesz być moim zastępcą, ok? <:MonkaS:882181709100097587> ")

        if success:
            await Channel.send("<@" + str(author_id)+ ">, Twój utwór został pomyślnie dodany do mojego repertuaru. Pomogłeś mi " + str(file_data[str(author_id)]) + " razy!")

    async def voting(self, ctx, player: wavelink.Player, query, file: str="fantasy_list.txt"):
        # Whether the accepted track goes straight into the queue is decided
        # when the vote ends, by playlist_is_live - a vote can run for hours and
        # cross into a different day than the one it started on.
        if file == "fantasy_list.txt":
            playlist = "FANTASY <:Up:912798893304086558><:Loot:912797849916436570>"
            embedurl='https://www.altermmo.pl/wp-content/uploads/altermmo-5-112-1.png'
            color = 0x77ff00
        elif file == "party_list.txt":
            playlist = "IMPREZA <a:RainbowPls:882184531917037608><a:RainbowPls:882184531917037608><a:RainbowPls:882184531917037608>"
            embedurl='https://www.altermmo.pl/wp-content/uploads/Drunk.png'
            color = 0xff0011
        else:
            playlist = "test"
            embedurl='https://www.altermmo.pl/wp-content/uploads/altermmo-2-112.png'
            color = 0xffffff

        embed = discord.Embed(
            title="Czy chcecie dodać utwór do playlisty " + playlist + "?",
            description=(f"\nPamiętacje, że w playliście powinny znaleźć się utwory, które wpasowują się w tematykę i nie są nadto specyficzne.\n\nProponowany utwór: **{query}**\nLink: {query.uri}"),
            color=color,
            timestamp=dt.datetime.utcnow()
        )
        # artwork, not thumb: wavelink renamed it in 3.0, and the old name
        # raised AttributeError here - which killed $fantasy and $party right
        # before the vote was posted, so nothing ever appeared on the channel.
        # It can still be None, hence the per-playlist image as a fallback.
        embed.set_image(url=query.artwork or embedurl)
        embed.set_footer(text=f"Dodana przez {ctx.author.display_name}", icon_url=ctx.author.avatar)
        Channel = self.bot.get_channel(VoteChannelID)
        msg = await Channel.send(embed=embed)

        for emoji in list(VOTES.keys()):
            await msg.add_reaction(emoji)

        deadline = dt.datetime.now(dt.timezone.utc).timestamp() + VOTE_TIMEOUT_HOURS * 3600
        record = {
            "message_id": msg.id,
            "author_id": ctx.author.id,
            "file": file,
            "title": query.title,
            "uri": query.uri,
            "playlist": playlist,
            "expires_at": deadline,
        }

        # Persist before watching: if the bot dies a second later, the vote is
        # still recoverable from disk.
        self.remember_vote(record)

        await self.watch_vote(record)

    def remember_vote(self, record: dict) -> None:
        records = load_pending_votes()
        records.append(record)
        save_pending_votes(records)

    def forget_vote(self, message_id: int) -> None:
        records = [r for r in load_pending_votes() if r["message_id"] != message_id]
        save_pending_votes(records)

    async def restore_pending_votes(self) -> None:
        """Pick up votes that were still open when the bot last stopped.

        Without this the message stayed on Discord with nobody listening: the
        wait_for that drove a vote lived only in memory, so a restart silently
        abandoned every vote in progress.
        """

        records = load_pending_votes()
        if not records:
            return

        logger.info("Restoring %s pending vote(s) after a restart.", len(records))
        for record in records:
            self.bot.loop.create_task(self.watch_vote(record))

    async def watch_vote(self, record: dict) -> None:
        """Watch one vote message until it is decided or expires.

        Counts come from re-fetching the message rather than from the message
        cache. The cache is empty for anything posted before a restart, which
        is exactly the case this has to survive - and it also means votes cast
        while the bot was down are counted the moment it comes back.
        """

        channel = self.bot.get_channel(VoteChannelID)
        if channel is None:
            logger.warning("Vote channel %s unavailable.", VoteChannelID)
            return

        message_id = record["message_id"]

        while True:
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                logger.info("Vote message %s no longer exists - dropping it.", message_id)
                self.forget_vote(message_id)
                return
            except discord.HTTPException as exc:
                logger.warning("Could not fetch vote message %s: %s", message_id, exc)
                return

            yes, no = count_votes(message)
            logger.debug("Vote %s: %s for, %s against.", message_id, yes, no)

            if yes >= votesReq or no >= votesReq:
                await self.resolve_vote(record, message, accepted=yes >= votesReq)
                return

            remaining = record["expires_at"] - dt.datetime.now(dt.timezone.utc).timestamp()
            if remaining <= 0:
                logger.info("Vote %s expired.", message_id)
                await self.delete_quietly(message)
                self.forget_vote(message_id)
                return

            try:
                await self.bot.wait_for(
                    "raw_reaction_add",
                    timeout=remaining,
                    # raw, not the cached variant: the message may predate the
                    # current session and would never match otherwise.
                    check=lambda p: p.message_id == message_id and str(p.emoji) in VOTES,
                )
            except asyncio.TimeoutError:
                logger.info("Vote %s timed out.", message_id)
                try:
                    message = await channel.fetch_message(message_id)
                    await self.delete_quietly(message)
                except discord.HTTPException:
                    pass
                self.forget_vote(message_id)
                return

    async def resolve_vote(self, record: dict, message: discord.Message, accepted: bool) -> None:
        """Apply the outcome of a finished vote."""

        emoji = "✅" if accepted else "❌"
        voters = await collect_reacters(message, emoji)

        logger.info("Vote %s decided: %s.", record["message_id"],
                    "accepted" if accepted else "rejected")

        await self.delete_quietly(message)
        self.forget_vote(record["message_id"])

        await self.bard_support(voters, record["author_id"], accepted)

        if not accepted:
            return

        with open(record["file"], "a", encoding="utf8") as handle:
            handle.write(f"\n{format_entry(record['title'], record.get('uri'))}")

        Channel = self.bot.get_channel(CommandChannelID)
        if Channel is not None:
            await Channel.send("Utwór " + record["title"] + " dopisany do repertuaru "
                               + record.get("playlist", "") + " <a:PepoG:936907752155021342>.")

        # Only drop it into the queue if that playlist is the one on air right
        # now - the day may well have changed while the vote was running.
        if self.player is not None and self.playlist_is_live(record["file"]):
            try:
                tracks = await search_youtube(record.get("uri") or record["title"])
                if tracks:
                    self.player.queue.put(tracks[0])
            except wavelink.WavelinkException as exc:
                logger.warning("Could not queue the accepted track: %s", exc)

    async def delete_quietly(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except discord.HTTPException as exc:
            logger.debug("Could not delete message %s: %s", message.id, exc)

    def playlist_is_live(self, file: str) -> bool:
        """Whether this playlist is the one the radio is playing right now."""

        if file == "party_list.txt":
            return is_party_time()
        if file == "fantasy_list.txt":
            return not is_party_time()

        return False

    @commands.command(name="fantasy")
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addfantasy_command(self, ctx, query: str):
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, self.player, query, "fantasy_list.txt")
        logger.debug("Checked")
        if check is not None:
            await self.voting(ctx, self.player, check, "fantasy_list.txt")
        else:
            pass

    @addfantasy_command.error
    async def addfantasy_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            logger.info("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        if isinstance(error, commands.MissingRequiredArgument):
            logger.info("Invoke error.")
            await ctx.send("<@" + str(ctx.author.id) + "> Coś źle napisałeś. Wpisz $fantasy \"Tytuł utworu\".")

    @commands.command(name="party", aliases=["impreza"])
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addparty_command(self, ctx, query: str):
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, self.player, query, "party_list.txt")
        logger.debug("Track checked")
        if check is not None:
            await self.voting(ctx, self.player, check, "party_list.txt")
        else:
            await ctx.send("<@" + str(ctx.author.id) + "> Wystąpił problem, spróbuj jeszcze raz.")
            pass

    @addparty_command.error
    async def addparty_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            logger.info("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        if isinstance(error, commands.MissingRequiredArgument):
            logger.info("Invoke error.")
            await ctx.send("<@" + str(ctx.author.id) + "> Coś źle napisałeś. Wpisz $party \"Tytuł utworu\".")

    @commands.command(name="singme", aliases=["zagrajmi"])
    @commands.check(is_channel)
    async def singme_command(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send('Brak kanału głosowego, do którego mogę dołączyć.')

        await self.player.move_to(channel)

    @commands.command(name="next", aliases=["skip", "nastepna"])
    #@commands.cooldown(1, 60*30, commands.BucketType.user)
    @commands.check(is_channel)
    async def next_command(self, ctx):

        # skip() ends the current track and autoplay starts the next one - that
        # way the track lands in history and comes back on the next lap.
        await self.player.skip(force=True)
        await ctx.send("Kolejny utwór w kolejce...")

    @next_command.error
    async def next_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            logger.info("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60, 2)) + ' minut <:Bedge:970576892874854400>.')

    @commands.command(name="bardranking", aliases=["rankingbarda"])
    @commands.check(is_channel)
    async def bardrankingcommand(self, ctx):
        await self.ranking_bard_support(ctx)

    @commands.command(name="bardcheck", aliases=["ilepomoglem"])
    @commands.check(is_channel)
    async def bardcheck_command(self, ctx):
        await self.check_bard_support(ctx)

    @commands.command(name="queue", aliases=["kolejka", "playlist", "playlista"])
    @commands.check(is_channel)
    async def queue_command(self, ctx, show: t.Optional[int] = 10):

        if self.player.queue.is_empty:
            raise QueueIsEmpty

        embed = discord.Embed(
            title="Kolejka",
            description=f"Pokazuje następne {show} utworów.",
            color=ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Informacje o kolejce")
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar)
        current = self.player.current
        embed.add_field(name="Aktualnie gra",
                        value=current.title if current else "nic",
                        inline=False)

        # The queue is iterable - titles used to be pulled out by slicing the
        # queue's repr(), which fell apart on titles containing quotes.
        if upcoming := [track.title for track in self.player.queue][:show]:
            embed.add_field(
                name="Następny",
                value="\n".join(upcoming),
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
