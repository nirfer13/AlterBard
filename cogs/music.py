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
VoiceChannelID = 1056200069952589924 # Kanał Staśka
#VoiceChannelID = 687630935419912204
LogChannelID = 1057198781206106153
BardID = 1004008220437778523
GuildID = 686137998177206281
votesReq = 6
#votesReq = 2

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

class Player(wavelink.Player):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue.mode = wavelink.QueueMode.loop_all
        self.autoplay = wavelink.AutoPlayMode.enabled
        self.bot = bot

    async def teardown(self):
        """Destroy the player."""
        try:
            await self._destroy()
        except KeyError:
            pass

    async def add_singletrack(self, tracks: wavelink.Search):
        """Add a single track to the queue."""

        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.Playlist):
            # tracks is a playlist...
            raise NoTracksFound

        if len(tracks) > 1:
            for track in tracks:
                if track.length/60/1000 < 9:
                    track: wavelink.Playable = track
                    await self.queue.put_wait(track)
                    break
                else:
                    pass
        else:
            track: wavelink.Playable = tracks[0]
            await self.queue.put_wait(track)

        if not self.playing and not self.queue.is_empty:
            track: wavelink.Playable = tracks[0]
            await self.start_playback()

    async def start_playback(self):
        """Get first track from the queue and start playing."""

        if not self.queue.is_empty:
            track = self.queue.get()
            print(track)
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
            with open(file, "r", encoding="utf8") as f:
                lines = f.read().splitlines()

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
    # self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot ready...")

        await self.delete_bard_messages()
        await self.setup_hook()

    #Check timestamp task
    async def msg1(self, ctx, player: wavelink.Player, party_list: list, fantasy_list: list):
        print("Loop check 1.")
        timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
        actDay = timestamp.strftime("%a")
        print("Actual day: " + str(actDay))

        while True:
            print("Inside infinite loop.")

            timestamp = (dt.datetime.utcnow() + dt.timedelta(hours=2))
            print(timestamp.strftime("%H:%M"))
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
                await player.stop()
                player.queue.reset()
                
                for query in list:
                    query = str(query)
                    print("Single query: " + query)
                    if not self.player.connected:
                        vc: Player = await VoiceChannel.connect(cls=self.player)
                    if query is None:
                        pass
                    else:
                        query = query.strip("<>")
                        try:
                            if not re.match(URL_REGEX, query):
                                tracks: list[wavelink.Playable] = await wavelink.Playable.search(
                                                                                                    query)

                            await self.player.add_singletrack(tracks)
                        except Exception as e:
                            print("Exception: %s", e)

            elif (timestamp.strftime("%a") != "Fri" and actDay == "Fri"):
                
                actDay = timestamp.strftime("%a")

                LogChannel = self.bot.get_channel(LogChannelID)
                VoiceChannel = self.bot.get_channel(VoiceChannelID)
                await VoiceChannel.edit(name="Scena Barda")
                await LogChannel.send("Zmiana playlisty na fantasy.")
                guild = self.bot.get_guild(GuildID)
                userBot = guild.get_member(BardID)
                await userBot.edit(nick="Bard Stasiek")

                list = fantasy_list
                await player.stop()
                player.queue.reset()
                random.shuffle(list)
                
                for query in list:
                    query = str(query)
                    print("Single query: " + query)
                    if not self.player.connected:
                        vc: Player = await VoiceChannel.connect(cls=self.player)
                    if query is None:
                        pass
                    else:
                        query = query.strip("<>")
                        try:
                            if not re.match(URL_REGEX, query):
                                tracks: list[wavelink.Playable] = await wavelink.Playable.search(
                                                                                                query)

                            await self.player.add_singletrack(tracks)
                        except Exception as e:
                            print("Exception: %s", e)
            print("Loop check 2.")
            await asyncio.sleep(3600)

    async def setup_hook(self) -> None:
        # Wavelink 2.0 has made connecting Nodes easier... Simply create each Node
        # and pass it to NodePool.connect with the client/bot.
        node = wavelink.Node(uri='http://127.0.0.1:2333', password='youshallnotpass')
        await wavelink.Pool.connect(nodes=[node], client=self.bot)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """Give info that node is ready"""

        print(f"Node {node} is ready!")
        voice_channel = self.bot.get_channel(VoiceChannelID)
        print("Channel acquired.")

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
            await VoiceChannel.edit(name="Vixapol!!!")
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
        msg = await channel.fetch_message(1177811269164748872)
        ctx = await self.bot.get_context(msg)
        await channel.send("Bard gotowy do śpiewania!")
        self.player = Player(bot=self.bot)
        vc: Player = await VoiceChannel.connect(cls=self.player)

        for query in list:
            query = str(query)
            print("Single query: " + query)
            if not self.player.connected:
                vc: Player = await VoiceChannel.connect(cls=self.player)
            if query is None:
                pass
            else:
                query = query.strip("<>")
                try:
                    if not re.match(URL_REGEX, query):
                        tracks: wavelink.Search = await wavelink.Playable.search(query, source= wavelink.TrackSource.YouTube)
                    await self.player.add_singletrack(tracks)
                except Exception as e:
                    print("Exception: %s", e)

        # Check timestamp and start task
        self.task = self.bot.loop.create_task(self.msg1(ctx, self.player, party_list, fantasy_list))

    @commands.command("play")
    async def play(self, ctx: commands.Context, *, search: str) -> None:
        """Simple play command."""

        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        tracks: list[wavelink.Playable] = await wavelink.Playable.search(search)
        if not tracks:
            await ctx.send(f'Przepraszam, nie mogę znaleźć podanego utworu: `{search}`')
            return

        print(tracks[0])
        track: wavelink.Playable = tracks[0]

        await vc.play(track)
        print("Playing song...")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Show currently playing track."""

        try:
            activity = discord.CustomActivity(f"Odgrywa: {payload.track.title}")
            await self.player.queue.put_wait(self.player.current)
            count = len(str(self.player.queue)[2:-2].split('\", \"'))
            print(f"Zostało: {count}")
            await self.bot.change_presence(status=discord.Status.do_not_disturb,
                                        activity=activity)
        except:
            print("Error during start of the track.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Get next track after finishing previous one."""
        print("Track finished.")
    #     await self.player.start_playback()

        if not self.player.playing:
            await self.player.start_playback()
            print("RESTART")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and self.player:
            voice_channel = self.bot.get_channel(VoiceChannelID)
            current_voice_channel = self.player.bot.voice_clients[0].channel

            if current_voice_channel.id != VoiceChannelID and not [m for m in current_voice_channel.members if not m.bot]:
            
                print("Changing voice channel automatically.")
                channel = await self.player.move_to(voice_channel)

    async def is_channel(ctx):
        return ctx.channel.id == CommandChannelID or ctx.channel.id == 1057198781206106153
    
    async def delete_bard_messages(self):
        """Delete bard vote messages."""

        vote_channel = self.bot.get_channel(VoteChannelID)
        counter = 0
        async for message in vote_channel.history(limit=15):
            if message.author == self.bot.user:
                await message.delete()

        print(f"MESSAGES COUNT {counter}")

    async def singme(self, ctx, player: wavelink.Player):
        print("Player changing the voice channel.")
        voice_channel = self.bot.get_channel(VoiceChannelID)
        channel = await player.move_to(ctx.author.channel)

    async def check_track(self, ctx,
                          player: wavelink.Player,
                          query: str,
                          file: str="fantasy_list.txt"):

        with open(file, "r", encoding="utf8") as f:
            lines = f.read().splitlines()

        if query in lines:
            await ctx.send("<@" + str(ctx.author.id) + ">, mam już taki utwór w repertuarze, więc musisz wybrać coś innego.")
            raise DuplicatedTrack

        if len(query.split()) <= 1:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu podaj w cudzysłowie np. *$fantasy \"Wildstar - Drusera's Theme / Our Perception of Beauty\"* .")
            raise InvalidTrackName

        if len(query) < 10:
            await ctx.send("<@" + str(ctx.author.id) + "> Tytuł utworu jest za krótki. Spróbuj coś dłuższego.")
            raise InvalidTrackName

        query = query.strip("<>")

        if not re.match(URL_REGEX, query):
            tracks: list[wavelink.Playable] = await wavelink.Playable.search(
                                                                                query)

        track = await self.player.get_track(ctx, tracks, file)

        if track is None:
            return None

        if track.length/60/1000 > 9:
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

                with open(file, "a", encoding="utf8") as file_object:
                    file_object.write(f"\n{query}")
                Channel = self.bot.get_channel(CommandChannelID)
                await Channel.send("Utwór " + str(query.title) + " dopisany do repertuaru " + playlist + " <a:PepoG:936907752155021342>.")
                if add:
                    if query is not None:
                        print("Player")
                        player.queue.put(query)
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

    @commands.command(name="fantasy")
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addfantasy_command(self, ctx, query: str):
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, self.player, query, "fantasy_list.txt")
        print("Checked")
        if check is not None:
            await self.voting(ctx, self.player, check, "fantasy_list.txt")
        else:
            pass

    @addfantasy_command.error
    async def addfantasy_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        if isinstance(error, commands.MissingRequiredArgument):
            print("Invoke error.")
            await ctx.send("<@" + str(ctx.author.id) + "> Coś źle napisałeś. Wpisz $fantasy \"Tytuł utworu\".")

    @commands.command(name="party", aliases=["impreza"])
    @commands.check(is_channel)
    @commands.cooldown(2, 60*60*23, commands.BucketType.user)
    async def addparty_command(self, ctx, query: str):
        await ctx.message.add_reaction("▶")

        check = await self.check_track(ctx, self.player, query, "party_list.txt")
        print("Track checked")
        if check is not None:
            await self.voting(ctx, self.player, check, "party_list.txt")
        else:
            await ctx.send("<@" + str(ctx.author.id) + "> Wystąpił problem, spróbuj jeszcze raz.")
            pass

    @addparty_command.error
    async def addparty_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
            await ctx.send('Poczekaj na odnowienie komendy! Zostało ' + str(round(error.retry_after/60/60, 2)) + ' godzin/y <:Bedge:970576892874854400>.')
        if isinstance(error, commands.MissingRequiredArgument):
            print("Invoke error.")
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

        #await self.player.queue.put_wait(self.player.current)
        #await self.player.skip()
        await self.player.start_playback()
        #await self.player.stop()
        await ctx.send("Kolejny utwór w kolejce...")

    @next_command.error
    async def next_command_cooldown(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print("Command on cooldown.")
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
        embed.add_field(name="Aktualnie gra", value=self.player.current.title, inline=False)

        print(str(self.player.queue))

        if upcoming := str(self.player.queue)[8:-3].split("\", \""):
            embed.add_field(
                name="Następny",
                value="\n".join(t for t in upcoming[:show]),
                inline=False
            )

        msg = await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
