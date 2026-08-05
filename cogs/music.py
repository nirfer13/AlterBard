import asyncio
import logging
import datetime as dt
import json
import random
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

# Names the bot gives its voice channel. The note emoji marks it as the music
# channel at a glance in the channel list. Discord rate-limits channel renames
# to two per ten minutes, which is why these are only set on startup and on the
# Friday playlist switch.
CHANNEL_NAME_FANTASY = "🎵・Scena Barda・🎵"
CHANNEL_NAME_PARTY = "🎶・Vixapol!!!・🎶"
CHANNEL_NAME_PARTY_SWITCH = "🎶・MORDOWNIA!!!・🎶"

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

def format_playlist_entry(track: wavelink.Playable) -> str:
    """Render a track for storage: the title stays first so the file remains
    readable and editable by hand, with the URL pinned after a tab."""

    if track.uri:
        return f"{track.title}\t{track.uri}"

    return track.title

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

        if not self.playing:
            await self.start_playback()

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
    # self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Bot ready...")

        await self.delete_bard_messages()
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

    #Check timestamp task
    async def msg1(self, player: wavelink.Player, party_list: list, fantasy_list: list):
        logger.debug("Loop check 1.")
        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        actDay = timestamp.strftime("%a")
        logger.info("Actual day: %s", actDay)

        while True:
            logger.debug("Inside infinite loop.")

            timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
            logger.debug("Current time: %s", timestamp.strftime("%H:%M"))
            if timestamp.strftime("%a") == "Fri" and actDay != "Fri":
                actDay = "Fri"

                LogChannel = self.bot.get_channel(LogChannelID)
                VoiceChannel = self.bot.get_channel(VoiceChannelID)
                AnnouceChannel = self.bot.get_channel(AnnouceChannelID)
                await VoiceChannel.edit(name=CHANNEL_NAME_PARTY_SWITCH)
                await LogChannel.send("Zmiana playlisty na imprezową.")
                await AnnouceChannel.send("HALO, HALO! TUTAJ DJ STACHU! JESTEŚCIE GOTOWI? Zapraszam na <#" + str(VoiceChannelID) + "> imprezę <:OOOO:982215120199507979> <a:RainbowPls:882184531917037608>!")
                guild = self.bot.get_guild(GuildID)
                userBot = guild.get_member(BardID)
                await userBot.edit(nick="DJ Stachu")

                list = party_list
                random.shuffle(list)
                await player.stop()
                player.queue.reset()

                await self.load_playlist(list, VoiceChannel)

            elif (timestamp.strftime("%a") != "Fri" and actDay == "Fri"):
                
                actDay = timestamp.strftime("%a")

                LogChannel = self.bot.get_channel(LogChannelID)
                VoiceChannel = self.bot.get_channel(VoiceChannelID)
                await VoiceChannel.edit(name=CHANNEL_NAME_FANTASY)
                await LogChannel.send("Zmiana playlisty na fantasy.")
                guild = self.bot.get_guild(GuildID)
                userBot = guild.get_member(BardID)
                await userBot.edit(nick="Bard Stasiek")

                list = fantasy_list
                await player.stop()
                player.queue.reset()
                random.shuffle(list)

                await self.load_playlist(list, VoiceChannel)

            logger.debug("Loop check 2.")
            await asyncio.sleep(3600)

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

        #Create Fantasy Playlist
        with open('fantasy_list.txt', encoding="utf8") as f:
            fantasy_list = f.read().splitlines()

        #Create Party Playlist
        with open('party_list.txt', encoding="utf8") as g:
            party_list = g.read().splitlines()

        LogChannel = self.bot.get_channel(LogChannelID)
        VoiceChannel: discord.VoiceChannel = self.bot.get_channel(VoiceChannelID)
        guild = self.bot.get_guild(GuildID)
        userBot = guild.get_member(BardID)

        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        if timestamp.strftime("%a") == "Fri":
            list = party_list
            await VoiceChannel.edit(name=CHANNEL_NAME_PARTY)
            await LogChannel.send("Zmiana playlisty na imprezową.")
            await userBot.edit(nick="DJ Stachu")
        else:
            list = fantasy_list
            await VoiceChannel.edit(name=CHANNEL_NAME_FANTASY)
            await LogChannel.send("Zmiana playlisty na fantasy.")
            await userBot.edit(nick="Bard Stasiek")

        random.shuffle(list)

        await LogChannel.send("Bard gotowy do śpiewania!")
        self.player = Player(bot=self.bot)
        vc: Player = await VoiceChannel.connect(cls=self.player)

        added, skipped = await self.load_playlist(list, VoiceChannel)
        await LogChannel.send(f"Załadowano {added} utworów z YouTube, pominięto {len(skipped)}.")

        if not added:
            await LogChannel.send(
                "Nie udało się załadować **żadnego** utworu z YouTube. "
                "Sprawdź logi Lavalinka - najczęściej oznacza to przeterminowany "
                "youtube-plugin albo brak autoryzacji OAuth."
            )

        # Check timestamp and start task
        self.task = self.bot.loop.create_task(self.msg1(self.player, party_list, fantasy_list))

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
        except discord.HTTPException as exc:
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
        """Delete bard vote messages."""

        vote_channel = self.bot.get_channel(VoteChannelID)
        counter = 0
        async for message in vote_channel.history(limit=15):
            if message.author == self.bot.user:
                await message.delete()
                counter += 1

        logger.info("Deleted %s bard vote messages.", counter)

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


    async def bard_support(self, ctx, users: set, author: discord.User, success: bool):

        filename="authors_list.json"
        Channel = self.bot.get_channel(CommandChannelID)

        with open(filename,'r+', encoding="utf8") as file:
            # First we load existing data into a dict.
            file_data = json.load(file)

            for user in users:
                id = str(user.id)
                if id != str(author.id):
                    if id in file_data.keys():
                        file_data[id] += 0.25
                    else:
                        file_data[id] = 0.25

            if success:
                id = str(author.id)
                if id in file_data.keys():
                    file_data[id] += 1
                else:
                    file_data[id] = 1

            json_object = json.dumps(file_data, indent=4)
            # Sets file's current position at offset.
            file.seek(0)
            file.truncate(0) # need '0' when using r+
            file.write(json_object)

            role1 = discord.utils.get(ctx.guild.roles, id=1054138582811549776) #Pomagier
            role2 = discord.utils.get(ctx.guild.roles, id=1059766781889228820) #Mlodszy Bard
            role3 = discord.utils.get(ctx.guild.roles, id=1059766769524424714) #Zastepca Barda

            for user in users:
                id = str(user.id)
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
            await Channel.send("<@" + str(author.id)+ ">, Twój utwór został pomyślnie dodany do mojego repertuaru. Pomogłeś mi " + str(file_data[str(author.id)]) + " razy!")

    async def voting(self, ctx, player: wavelink.Player, query, file: str="fantasy_list.txt"):
        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        add = False
        if file == "fantasy_list.txt":
            if timestamp.strftime("%a") != "Fri":
                add = True
            playlist = "FANTASY <:Up:912798893304086558><:Loot:912797849916436570>"
            embedurl='https://www.altermmo.pl/wp-content/uploads/altermmo-5-112-1.png'
            color = 0x77ff00
        elif file == "party_list.txt":
            if timestamp.strftime("%a") == "Fri":
                add = True
            playlist = "IMPREZA <a:RainbowPls:882184531917037608><a:RainbowPls:882184531917037608><a:RainbowPls:882184531917037608>"
            embedurl='https://www.altermmo.pl/wp-content/uploads/Drunk.png'
            color = 0xff0011
        else:
            playlist = "test"
            embedurl='https://www.altermmo.pl/wp-content/uploads/altermmo-2-112.png'
            color = 0xffffff

        def _check(r, u):
            return(
                r.emoji in VOTES.keys()
                and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Czy chcecie dodać utwór do playlisty " + playlist + "?",
            description=(f"\nPamiętacje, że w playliście powinny znaleźć się utwory, które wpasowują się w tematykę i nie są nadto specyficzne.\n\nProponowany utwór: **{query}**\nLink: {query.uri}"),
            color=color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_image(url=query.thumb)
        embed.set_footer(text=f"Dodana przez {ctx.author.display_name}", icon_url=ctx.author.avatar)
        Channel = self.bot.get_channel(VoteChannelID)
        msg = await Channel.send(embed=embed)
        cache_msg = discord.utils.get(self.bot.cached_messages, id=msg.id)

        for emoji in list(VOTES.keys()):
            await msg.add_reaction(emoji)

        posReaction = 0
        negReaction = 0
        try:
            while (posReaction < votesReq and negReaction < votesReq):
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=60*60*12, check=_check)
                    posReaction = cache_msg.reactions[0].count
                    negReaction = cache_msg.reactions[1].count
                    logger.debug("Reactions: %s %s", posReaction, negReaction)

            if posReaction >= votesReq:
                logger.info("Positive reactions won.")
                reactions = cache_msg.reactions[0]
                reacters = set()
                logger.debug("Reactions: %s", reactions)
                async for user in reactions.users():
                    reacters.add(user)
                logger.debug("Voters: %s", reacters)
                await msg.delete()
                await self.bard_support(ctx, reacters, ctx.author, True)

                # Store the URL alongside the title, so this exact video comes
                # back on every restart rather than the top search hit.
                with open(file, "a", encoding="utf8") as file_object:
                    file_object.write(f"\n{format_playlist_entry(query)}")
                Channel = self.bot.get_channel(CommandChannelID)
                await Channel.send("Utwór " + str(query.title) + " dopisany do repertuaru " + playlist + " <a:PepoG:936907752155021342>.")
                if add:
                    if query is not None:
                        logger.debug("Player")
                        player.queue.put(query)
                        #await Channel.send(f"Dodano {query} do kolejki.")             

            else:
                logger.info("Negative reactions won.")
                reactions = cache_msg.reactions[1]
                reacters = set()
                async for user in reactions.users():
                    reacters.add(user)
                await self.bard_support(ctx, reacters, ctx.author, False)
                await msg.delete()

        except asyncio.TimeoutError:
            await msg.delete()

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
