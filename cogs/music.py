import asyncio
import datetime as dt
import json
import random
import re
import typing as t

import discord
import wavelink
from discord.ext import commands

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
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

class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0

    @property
    def is_empty(self):
        return not self._queue

    @property
    def first_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    @property
    def current_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[self.position]

    @property
    def upcoming(self):
        if not self._queue:
            raise QueueIsEmpty
        
        return self._queue[self.position +1:]

    @property
    def history(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[:self.position]

    @property
    def length(self):
        return len(self._queue)

    def add(self, *args):
        self._queue.extend(args)

    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty

        self.position += 1

        if self.position > len(self._queue)-1:
            self.position = 0

        return self._queue[self.position]

    def empty(self):
        self._queue.clear()


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.destroy()
        except KeyError:
            pass

    async def add_singletrack(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
        else:
            self.queue.add(tracks[0])
            await ctx.send(f"Dodano {tracks[0].title} do kolejki.")

        if not self.is_playing and not self.queue.is_empty:
            await self.start_playback()

    async def start_playback(self):
        await self.play(self.queue.first_track)

    async def advance(self):
        try:
            if(track := self.queue.get_next_track()) is not None:
                await self.play(track)
        except QueueIsEmpty:
            pass

    async def get_track(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if len(tracks) == 1:
            return tracks[0]
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None:
                return track

    async def choose_track(self, ctx, tracks):
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
        embed.set_footer(text=f"Dodany przez {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()
        else:
            await msg.delete()
            return tracks[OPTIONS[reaction.emoji]]

class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes()) 

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot ready...")

        #Weekly ranking task create
        #self.task2 = self.bot.loop.create_task(self.msg1())
        await asyncio.sleep(15)
        voice_channel = self.bot.get_channel(1056200069952589924)
        print("Channel acquired.")

        #Create Fantasy Playlist
        with open('fantasy_list.txt') as f:
            fantasy_list = f.read().splitlines()

        #Create Party Playlist
        with open('party_list.txt') as g:
            party_list = g.read().splitlines()

        #Check timestamp and start task
        self.task = self.bot.loop.create_task(self.msg1())

        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        if timestamp.strftime("%a") == "Fri":
            list = party_list
            #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Pi\u0105tkowa Vixa"))
        else:
            list = fantasy_list
            #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Klimaty RPG"))
        random.shuffle(list)
        #print(list)

        #function to get context
        channel = self.bot.get_channel(1057198781206106153)
        msg = await channel.fetch_message(1057204065706188820)
        ctx = await self.bot.get_context(msg)
        await ctx.send("Bard gotowy do śpiewania!")

        player = self.get_player(ctx)
        print("Player ready...")
        channel = await player.connect(ctx, voice_channel)

        for query in list:
            query = str(query)
            print("Single query: " +query)
            if not player.is_connected:
                await player.connect(ctx)

            if query is None:
                pass

            else:
                query = query.strip("<>")
                if not re.match(URL_REGEX, query):
                    query = f"ytsearch: {query}"
                await player.add_singletrack(ctx, await self.wavelink.get_tracks(query))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            if not [m for m in before.channel.members if not m.bot]:
                pass

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node '{node.identifier}' ready.")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        await payload.player.advance()

    #Check timestamp task
    async def msg1(self):
        while self.is_playing == True:
            global list
            print("Loop check 1.")
            timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
            if timestamp.strftime("%a") == "Fri":
                list = party_list
                # Setting `Playing ` status
                #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Pi\u0105tkowa Vixa"))
            else:
                list = fantasy_list
                # Setting `Playing ` status
                #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Klimaty RPG"))
            random.shuffle(list)
            
            # wait some time before another loop. Don't make it more than 60 sec or it will skip
            print("Loop check 2.")
            await asyncio.sleep(600)

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Komendy nie są dostępne w wiadomościach prywatnych.")
            return False

        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        print("Starting node..")
        nodes = {
            "MAIN" : {
                "host": "127.0.0.1",
                "port": 2333,
                "rest_uri": "http://127.0.0.1:2333",
                "password": "youshallnotpass",
                "identifier": "MAIN",
                "region": "europe"
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            print("isinstance")
            print(obj.guild.id)
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            print("not isinstance")
            return self.wavelink.get_player(obj.id, cls=Player)

    async def check_track(self, ctx, player: wavelink.Player, query: str, file: str="fantasy_list.txt"):
        
        with open(file, "r") as f:
            lines = f.read().splitlines()

        if len(query.split()) <= 1:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"*.")
            raise InvalidTrackName
            return False

        if query in lines:
            await ctx.send("<@" + str(ctx.author.id) + "> Utwór już występuje w playliście, więc nie został dopisany.")
            raise DuplicatedTrack
            return False

        query = query.strip("<>")
        if not re.match(URL_REGEX, query):
            query = f"ytsearch: {query}"

        query = await player.get_track(ctx, await self.wavelink.get_tracks(query))

        if query is None:
            return False
        
        if query.duration/60/1000 > 9:
            await ctx.send("<@" + str(ctx.author.id) + "> Utwór jest za długi! Wybierz utwór krótszy niż 8 minut.")
            raise LongTrack
            return False

        return True

    async def bard_support(self, ctx):
    
    # function to add to JSON
        filename="authors_list.json"
        with open(filename,'r+') as file:
            # First we load existing data into a dict.
            file_data = json.load(file)
            # Sets file's current position at offset.
            file.seek(0)

            id = str(ctx.author.id)
            if id in file_data.keys():
                print("Id in file.")
                file_data[id] += 1
                if file_data[id] >= 5:
                    print("Rola dodana.")
                    role = discord.utils.get(ctx.guild.roles, id=1054138582811549776)
                    user = ctx.guild.get_member(int(id))
                    await user.add_roles(role)
            else:
                print("Id not in file.")
                file_data[id] = 1

            print(file_data)
            json_object = json.dumps(file_data, indent=4)
            file.write(json_object)
 
        await ctx.send("<@" + str(ctx.author.id)+ ">, Twój utwór został pomyślnie dodany do playlisty. Pomogłeś Staśkowi " + str(file_data[id]) + " razy!")
        if file_data[id] == 5:
            await ctx.send("Za wkład w muzyczny rozwój naszego barda otrzymałeś specjalną rangę!")

    async def voting(self, ctx, player: wavelink.Player, query: wavelink.Track, file: str="fantasy_list.txt"):

        if file == "fantasy_list.txt":
            playlist = "fantasy"
        elif file == "party_list.txt":
            playlist = "impreza"
        else:
            playlist = "test"

        def _check(r, u):
            return(
                r.emoji in VOTES.keys()
                and r.message.id == msg.id
            )

        embed = discord.Embed(
            title="Czy chcecie dodać utwór do playlisty " + playlist + "?",
            description=(f"\nPamiętacje, że w playliście powinny znaleźć się utwory, które wpasowują się w tematykę i nie są nadto specyficzne.\n\nProponowany utwór: **{query}**\nPrzesłuchajcie i zagłosujcie!"),
            color=ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_footer(text=f"Dodana przez {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        cache_msg = discord.utils.get(self.bot.cached_messages, id=msg.id)
        for emoji in list(VOTES.keys()):
            await msg.add_reaction(emoji)

        posReaction = 0
        negReaction = 0
        try:
            while (posReaction < 5 and negReaction < 5):
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=60*60*8, check=_check)
                    print(cache_msg.reactions)
                    posReaction = cache_msg.reactions[0].count
                    negReaction = cache_msg.reactions[1].count

            if posReaction >=5:
                await msg.delete()
                await ctx.message.delete()

                player.queue.add(query)

                await self.bard_support(ctx)

                with open(file, "a") as file_object:
                    file_object.write(f"\n{query}")
                await ctx.send(f"Utwór " + query + " dopisany do playlisty " + playlist + ".")
            else:
                await msg.delete()
                await ctx.message.delete()

        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()

    @commands.command(name="connect")
    async def connect_command(self, ctx, *, channel: t.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        channel = await player.connect(ctx, channel)
        await ctx.send(f"Connected to {channel.name}.")

    @connect_command.error
    async def connect_command_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send("Już połączono z kanałem głosowym.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("Brak odpowiedniego kanału głosowego.")

    @commands.command(name="disconnect")
    async def disconnect_command(self, ctx):
        player = self.get_player(ctx)
        await player.teardown()
        await ctx.send("Disconnect.")

    @commands.command(name="play")
    async def play_command(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)

        if query is None:
            pass

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch: [query]"

            await player.add_singletrack(ctx, await self.wavelink.get_tracks(query))

    @commands.command(name="radio")
    async def radio_command(self, ctx):

        #Define globals
        global list, party_list, fantasy_list
        global voice_channel

        voice_channel = self.bot.get_channel(1056200069952589924)
        print("Channel acquired.")

        #Create Fantasy Playlist
        with open('fantasy_list.txt') as f:
            fantasy_list = f.read().splitlines()

        #Create Party Playlist
        with open('party_list.txt') as g:
            party_list = g.read().splitlines()

        #Check timestamp and start task
        self.task = self.bot.loop.create_task(self.msg1())

        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        if timestamp.strftime("%a") == "Fri":
            list = party_list
            #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Pi\u0105tkowa Vixa"))
        else:
            list = fantasy_list
            #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Klimaty RPG"))
        random.shuffle(list)
        print(list)

        player = self.get_player(ctx)
        channel = await player.connect(ctx, voice_channel)

        for query in list:
            query = str(query)
            if not player.is_connected:
                await player.connect(ctx)

            if query is None:
                pass

            else:
                query = query.strip("<>")
                if not re.match(URL_REGEX, query):
                    query = f"ytsearch: {query}"
                print(type(query))
                await player.add_singletrack(ctx, await self.wavelink.get_tracks(query))

    @commands.command(name="stop")
    async def stop_command(self, ctx):
        player =self.get_player(ctx)
        player.queue.empty()
        await player.stop()
        await ctx.send("Muzyka wstrzymana.")

    @commands.command(name="next", aliases=["skip", "nastepna"])
    async def next_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.upcoming:
            raise NoMoreTracks

        await player.stop()
        await ctx.send("Kolejny utwór w kolejce...")

    @commands.command(name="queue", aliases=["kolejka", "playlist", "playlista"])
    async def queue_command(self, ctx, show: t.Optional[int] = 10):
        player = self.get_player(ctx)

        if player.queue.is_empty:
            raise QueueIsEmpty
        
        embed = discord.Embed(
            title="Kolejka",
            description=f"Pokazuje następne {show} utworów.",
            color=ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Informacje o kolejce")
        embed.set_footer(text=f"Dodane przez {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.add_field(name="Aktualnie gra", value=player.queue.current_track.title, inline=False)
        if upcoming := player.queue.upcoming:
            embed.add_field(
                name="Następny",
                value="\n".join(t.title for t in upcoming[:show]),
                inline=False
            )

        msg = await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("Kolejka jest pusta.")

    @commands.command(name="dodaj")
    @commands.has_permissions(administrator=True)
    async def addsong_command(self, ctx, query: t.Optional[str], playlist: bool=True):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)

        if query is None:
            pass

        else:
            query = query.strip("<>")
            textToFile = query
            if not re.match(URL_REGEX, query):
                query = f"ytsearch: {query}"

            await player.add_singletrack(ctx, await self.wavelink.get_tracks(query))

        strQuery = str(query)
        if playlist:
            file = "fantasy_list.txt"
        else:
            file = "party_list.txt"

        with open(file, "a") as file_object:
            # Append 'hello' at the end of file
            file_object.write(f"\n{textToFile}")
        await ctx.send(f"Utwór dopisany do pliku {file}.")

    @commands.command(name="fantasy")
    async def addfantasy_command(self, ctx, query: t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)
        else:
            check = await self.check_track(ctx, player, query, "fantasy_list.txt")
            if check:
                await self.voting(ctx, player, query, "fantasy_list.txt")
            else:
                pass

    @commands.command(name="party", aliases=["impreza"])
    async def addparty_command(self, ctx, query: t.Optional[str]):
        player = self.get_player(ctx)

        if not player.is_connected:
            await player.connect(ctx)
        else:
            check = await self.check_track(ctx, player, query, "party_list.txt")
            if check:
                await self.voting(ctx, player, query, "party_list.txt")
            else:
                pass

    @addfantasy_command.error
    async def addfantasy_error(self, ctx, error):
        if isinstance(error, commands.ExpectedClosingQuoteError) or isinstance(error, commands.CommandInvokeError):
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"*.")

    @addparty_command.error
    async def addfantasy_error(self, ctx, error):
        if isinstance(error, commands.ExpectedClosingQuoteError) or isinstance(error, commands.CommandInvokeError):
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"*.")
    
def setup(bot):
    bot.add_cog(Music(bot))