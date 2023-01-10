import asyncio
import datetime as dt
import json
import random
import re
import typing as t

import discord
import wavelink
from discord.ext import commands, tasks

global VoteChannelID, AnnouceChannelID, CommandChannelID, VoiceChannelID, LogChannelID, BardID, GuildID, votesReq
#VoteChannelID = 1028340292895645696 #Debug
VoteChannelID = 1059731255786229770
#AnnouceChannelID = 1028340292895645696 #Debug
AnnouceChannelID = 696932659833733131
#CommandChannelID = 1057198781206106153 #Debug
CommandChannelID = 776379796367212594
VoiceChannelID = 1056200069952589924
LogChannelID = 1057198781206106153
BardID = 1004008220437778523
GuildID = 686137998177206281
votesReq = 6

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

    async def get_track(self, ctx, tracks, file: str="fantasy_list.txt"):
        if not tracks:
            LogChannel = self.bot.get_channel(LogChannelID)
            await ctx.send("Zewnętrzny serwer muzyczny prawdopodobnie jest obciążony i nie mógł odnaleźć utworu. Spróbuj jeszcze raz.")
            await LogChannel.send("Nie znaleziono track.")
            raise NoTracksFound

        if len(tracks) == 1:
            return tracks[0]
        else:
            if (track := await self.choose_track(ctx, tracks, file)) is not None:
                return track

    async def choose_track(self, ctx, tracks, file: str="fantasy_list.txt"):
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
        else:
            await msg.delete()
            with open(file, "r") as f:
                lines = f.read().splitlines()

            if tracks[OPTIONS[reaction.emoji]].title in lines:
                await ctx.send("<@" + str(ctx.author.id) + ">, mam już taki utwór w repertuarze, więc musisz wybrać coś innego.")
                raise DuplicatedTrack
                return None
            else:
                return tracks[OPTIONS[reaction.emoji]]

class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes()) 

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot ready...")

        await asyncio.sleep(15)
        voice_channel = self.bot.get_channel(VoiceChannelID)
        print("Channel acquired.")

        #Create Fantasy Playlist
        with open('fantasy_list.txt') as f:
            fantasy_list = f.read().splitlines()

        #Create Party Playlist
        with open('party_list.txt') as g:
            party_list = g.read().splitlines()

        LogChannel = self.bot.get_channel(LogChannelID)
        VoiceChannel = self.bot.get_channel(VoiceChannelID)
        guild = self.bot.get_guild(GuildID)
        userBot = guild.get_member(BardID)

        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        if timestamp.strftime("%a") == "Fri":
            list = party_list
            await VoiceChannel.edit(name="TYRALNIA!!!")
            await LogChannel.send("Zmiana playlisty na imprezową.")
            await userBot.edit(nick="DJ Stachu")
        else:
            list = fantasy_list
            await VoiceChannel.edit(name="Scena Barda")
            await LogChannel.send("Zmiana playlisty na fantasy.")
            await userBot.edit(nick="Bard Stasiek")

        random.shuffle(list)

        #function to get context
        channel = self.bot.get_channel(LogChannelID)
        msg = await channel.fetch_message(1057204065706188820)
        ctx = await self.bot.get_context(msg)
        await ctx.send("Bard gotowy do śpiewania!")

        player = self.get_player(ctx)
        print("Player ready...")
        channel = await player.connect(ctx, voice_channel)

        for query in list:
            query = str(query)
            print("Single query: " + query)
            if not player.is_connected:
                await player.connect(ctx)
            if query is None:
                pass
            else:
                query = query.strip("<>")
                if not re.match(URL_REGEX, query):
                    query = f"ytsearch: {query}"
                x=0
                preQuery = None
                while x<5 and preQuery is None:
                    x+=1
                    preQuery = await self.wavelink.get_tracks(query)
                    print(type(preQuery))
                query = preQuery
                await player.add_singletrack(ctx, query)
        
        #Check timestamp and start task
        self.task = self.bot.loop.create_task(self.msg1(ctx, player, party_list, fantasy_list))
        print("Task started.")

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
    async def msg1(self, ctx, player: wavelink.Player, party_list: list, fantasy_list: list):
        print("Loop check 1.")
        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        actDay = timestamp.strftime("%a")
        print("Actual day: " + str(actDay))

        while True:
            print("Inside infinite loop.")

            timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
            if timestamp.strftime("%a") == "Fri" and actDay != "Fri":
                actDay = "Fri"

                LogChannel = self.bot.get_channel(LogChannelID)
                VoiceChannel = self.bot.get_channel(VoiceChannelID)
                AnnouceChannel = self.bot.get_channel(AnnouceChannelID)
                await VoiceChannel.edit(name="MORDOWNIA!!!")
                await LogChannel.send("Zmiana playlisty na imprezową.")
                await AnnouceChannel.send("HALO, HALO! TUTAJ DJ STACHU! JESTEŚCIE GOTOWI? Zapraszam na <#" + str(VoiceChannelID) + "> imprezę <:OOOO:982215120199507979> <a:RainbowPls:882184531917037608>!")
                guild = self.bot.get_guild(GuildID)
                userBot = guild.get_member(BardID)
                await userBot.edit(nick="DJ Stachu")

                list = party_list
                random.shuffle(list)
                player.queue.empty()
                await player.stop()
                
                for query in list:
                    query = str(query)
                    print("Single query: " + query)
                    if not player.is_connected:
                        await player.connect(ctx)
                    if query is None:
                        pass
                    else:
                        query = query.strip("<>")
                        if not re.match(URL_REGEX, query):
                            query = f"ytsearch: {query}"
                        x=0
                        preQuery = None
                        while x<5 and preQuery is None:
                            x+=1
                            preQuery = await self.wavelink.get_tracks(query)
                            print(type(preQuery))
                        query = preQuery
                        await player.add_singletrack(ctx, query)

            elif timestamp.strftime("%a") != "Fri" and actDay == "Fri":
                actDay = timestamp.strftime("%a")

                LogChannel = self.bot.get_channel(LogChannelID)
                VoiceChannel = self.bot.get_channel(VoiceChannelID)
                await VoiceChannel.edit(name="Scena Barda")
                await LogChannel.send("Zmiana playlisty na fantasy.")
                guild = self.bot.get_guild(GuildID)
                userBot = guild.get_member(BardID)
                await userBot.edit(nick="Bard Stasiek")

                list = fantasy_list
                player.queue.empty()
                await player.stop()
                random.shuffle(list)
                
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
                        x=0
                        preQuery = None
                        while x<5 and preQuery is None:
                            x+=1
                            preQuery = await self.wavelink.get_tracks(query)
                            print(type(preQuery))
                        query = preQuery
                        await player.add_singletrack(ctx, query)

            print("Loop check 2.")
            await asyncio.sleep(3600)

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Komendy nie są dostępne w wiadomościach prywatnych.")
            return False

        return True

    async def is_channel(ctx):
        return ctx.channel.id == CommandChannelID or ctx.channel.id == 1057198781206106153

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

        if query in lines:
            await ctx.send("<@" + str(ctx.author.id) + ">, mam już taki utwór w repertuarze, więc musisz wybrać coś innego.")
            raise DuplicatedTrack
            return None

        if len(query.split()) <= 1:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł i wykonawcę utworu podaj w cudzysłowie. Fraza musi mieć więcej niż jedno słowo np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"* .")
            raise InvalidTrackName
            return None

        if len(query) < 10:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu jest za krótki. Spróbuj coś dłuższego.")
            raise InvalidTrackName
            return None

        if not re.match(URL_REGEX, query):
            query = f"ytsearch: {query}"

        x=0
        preQuery = None
        while x<5 and preQuery is None:
            x+=1
            preQuery = await self.wavelink.get_tracks(query)
            print(type(preQuery))
        query = await player.get_track(ctx, preQuery, file)
        print(query.title)
        if query is None:
            return None
        
        if query.duration/60/1000 > 9:
            await ctx.send("<@" + str(ctx.author.id) + ">, utwór jest za długi! Wybierz utwór krótszy niż 8 minut.")
            raise LongTrack
            return None

        return query

    async def check_bard_support(self, ctx):
        
        filename="authors_list.json"

        with open(filename,'r') as file:
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

        with open(filename,'r') as file:
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
                if x >= 6:
                    break

        #Embed create   
        emb=discord.Embed(title='Ranking pomocników barda Staśka!', description=rankingString, color=0xCE7E00)
        emb.set_thumbnail(url="https://www.altermmo.pl/wp-content/uploads/BardLogo.png")
        emb.set_footer(text='Oby gust muzyczny był z Wami!')
        await ctx.send(embed=emb)


    async def bard_support(self, ctx, users: set, author: discord.User, success: bool):
    
        filename="authors_list.json"
        Channel = self.bot.get_channel(CommandChannelID)

        with open(filename,'r+') as file:
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
        embed.set_footer(text=f"Dodana przez {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
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
                    print("Reactions: " + str(posReaction) + " " + str(negReaction))

            if posReaction >= votesReq:
                print("Positive reactions won.")
                reactions = cache_msg.reactions[0]
                reacters = set()
                print(reactions)
                async for user in reactions.users():
                    reacters.add(user)
                print(reacters)
                await msg.delete()
                await self.bard_support(ctx, reacters, ctx.author, True)

                with open(file, "a") as file_object:
                    file_object.write(f"\n{query}")
                Channel = self.bot.get_channel(CommandChannelID)
                await Channel.send("Utwór " + str(query.title) + " dopisany do repertuaru " + playlist + " <a:PepoG:936907752155021342>.")
                if add:
                    if query is not None:
                        print("Player")
                        player.queue.add(query)
                        #await Channel.send(f"Dodano {query} do kolejki.")             
                
            else:
                print("Negative reactions won.")
                reactions = cache_msg.reactions[1]
                reacters = set()
                async for user in reactions.users():
                    reacters.add(user)
                await self.bard_support(ctx, reacters, ctx.author, False)
                await msg.delete()

        except asyncio.TimeoutError:
            await msg.delete()

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
    @commands.has_permissions(administrator=True)
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
        self.task = self.bot.loop.create_task(self.msg1(ctx, player, party_list, fantasy_list))

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
    @commands.has_permissions(administrator=True)
    async def stop_command(self, ctx):
        player =self.get_player(ctx)
        player.queue.empty()
        await player.stop()
        await ctx.send("Muzyka wstrzymana.")

    @commands.command(name="next", aliases=["skip", "nastepna"])
    @commands.cooldown(1, 60*60, commands.BucketType.user)
    @commands.check(is_channel)
    async def next_command(self, ctx):
        player = self.get_player(ctx)

        if not player.queue.upcoming:
            raise NoMoreTracks

        await player.stop()
        await ctx.send("Kolejny utwór w kolejce...")

    @next_command.error
    async def next_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60, 2)) + ' minut <:Bedge:970576892874854400>.')

    @commands.command(name="queue", aliases=["kolejka", "playlist", "playlista"])
    @commands.check(is_channel)
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
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addfantasy_command(self, ctx, query: str):
        player = self.get_player(ctx)
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, player, query, "fantasy_list.txt")
        if check is not None:
            await self.voting(ctx, player, check, "fantasy_list.txt")
        else:
            pass

    @commands.command(name="party", aliases=["impreza"])
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addparty_command(self, ctx, query: str):
        player = self.get_player(ctx) 
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, player, query, "party_list.txt")
        if check is not None:
            await self.voting(ctx, player, check, "party_list.txt")
        else:
            pass

    @addfantasy_command.error
    async def addfantasy_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        if isinstance(error, commands.ExpectedClosingQuoteError):
            await ctx.send("<@" + str(ctx.author.id) + "> Coś źle napisałeś. Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"* <:FeelsOkayMan:794117830822854656>.")

    @addparty_command.error
    async def addparty_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        elif isinstance(error, commands.ExpectedClosingQuoteError):
            await ctx.send("<@" + str(ctx.author.id) + "> Coś źle napisałeś. Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"* <:FeelsOkayMan:794117830822854656>.")  

    @commands.command(name="bardcheck", aliases=["ilepomoglem"])
    @commands.check(is_channel)
    async def bardcheck_command(self, ctx):
        await self.check_bard_support(ctx)

    @commands.command(name="bardranking", aliases=["rankingbarda"])
    @commands.check(is_channel)
    async def bardrankingcommand(self, ctx):
        await self.ranking_bard_support(ctx)

    @commands.command(name="test")
    @commands.has_permissions(administrator=True)
    async def testcommand(self, ctx):
        await ctx.send("<:YEP:882184945135681556> <:Siur:717731500883181710> <a:PepoG:936907752155021342> <:MonkaS:882181709100097587> <:peepoBlush:984769061340737586> <:FeelsOkayMan:794117830822854656>")


def setup(bot):
    bot.add_cog(Music(bot))