from logging import DEBUG
from discord import channel
from discord.errors import ClientException
from discord.ext import commands, tasks
from datetime import datetime, timedelta

import discord
import asyncio
import random
import time
import datetime
import json
from discord.message import Message

from discord.user import ClientUser
from discord import Client

import sys
from functions.functions_boss import fRandomBossHp
sys.path.insert(1, './functions/')
import functions_general
import functions_boss
import functions_database

#Import Globals
from globals.globalvariables import DebugMode

#Respawn time
global respTime
respTime = 0

#Boss alive
global bossAlive
bossAlive = 0

#Boss rarity
global bossRarity
bossRarity = 0

class message(commands.Cog, name="spawnBoss"):
    def __init__(self, bot):
        self.bot = bot
   

    @commands.Cog.listener()
    async def on_ready(self):
        #Every week ranking check

        #Choose channel to spawn boss
        global ctx
        if DebugMode == True:
            ctx = await functions_boss.getContext(self, 970571647226642442, 984860815842771024)
        else:
            ctx = await functions_boss.getContext(self, 970684202880204831, 988043434470281238)

        global bossAlive, bossRarity, respTime, respawnResume
        bossRar, respawnTime, respawnResume = await functions_database.readBossTable(self, ctx)

        #Weekly ranking task create
        self.task2 = self.bot.loop.create_task(self.msg1(ctx))

        #Check if it is necessary to resume boss spawn
        print("Resume?: " + str(respawnResume))
        if respawnResume == True:
            bossAlive = 1
            bossRarity = int(bossRar)
            respTime = (respawnTime - (datetime.datetime.utcnow() + datetime.timedelta(hours=2))).total_seconds()
            print("Resp time: " + str(respTime))
            print("Task resuming...")
            self.task = self.bot.loop.create_task(self.spawn_task(ctx))
            print("Task resumed.")

    #define every week task
    # 7 days => 24 hour * 7 days = 168
    async def msg1(self, ctx):
        while True:
            timestamp = (datetime.datetime.utcnow() + datetime.timedelta(hours=2))
            if timestamp.strftime("%H:%M UTC %a") == "15:00 UTC Mon":
                print('Weekly ranking summary!')
                winnerID = await functions_database.readSummaryRankingTable(self, ctx)
                print("Winner ID: " + str(winnerID))
                await functions_boss.setBossSlayer(self, ctx, winnerID)
                await functions_database.resetRankingTable(self)
                await ctx.channel.send("<@&985071779787730944>! Ranking za tydzień polowań został zresetowany. Nowa rola <@&983798433590673448> została przydzielona <@" + str(winnerID) + ">! Gratulacje <:GigaChad:970665721321381958>")
                return
            # wait some time before another loop. Don't make it more than 60 sec or it will skip
            await asyncio.sleep(30)
    
    #define Spawn BIG Boss task
    async def spawn_task(self, ctx):
        while True:
            global respTime
            global bossAlive
            global bossRarity
            global respawnResume
            #=== Episode 0
            if bossAlive == 0:
               print("Preparing to channel clear. bossAlive = 0")
               bossAlive = 1
               if DebugMode == False:
                    respTime = random.randint(150,3600)*12
                    #Save Resp to file
                    bossRarity = functions_boss.fBossRarity(respTime)
                    await functions_database.updateBossTable(self, ctx, bossRarity, respTime, True)

                    print("Resp time: " + str(respTime))
                    print("Boss Rarity: " + str(bossRarity))
                    await asyncio.sleep(3600)
               else:
                    respTime = random.randint(15,24)
                    #Save Resp to database
                    bossRarity = functions_boss.fBossRarity(respTime)
                    print("Updating database...")
                    await functions_database.updateBossTable(self, ctx, bossRarity, respTime, True)

                    print("Resp time: " + str(respTime))
                    print("Boss Rarity: " + str(bossRarity))
                    await asyncio.sleep(3)
            #=== Episode 1 - Waiting
            #New Spawn
            if respawnResume == False:
                if bossAlive == 1:
                   bossAlive = 2
                   await functions_general.fClear(self, ctx)
                   print("Channel cleared. bossAlive = 1")
                   async with ctx.typing():
                    await ctx.channel.send('Dookoła rozlega się cisza, jedynie wiatr wzbija w powietrze tumany kurzu...')
                   if DebugMode == False:
                        await asyncio.sleep(respTime)  # time in second
                   else:
                        await asyncio.sleep(respTime)  # time in second

            #Resume Spawn
            else:
                if bossAlive == 1:
                   bossAlive = 2
                   await functions_general.fClear(self, ctx)
                   print("Channel cleared. bossAlive = 1. Resuming.")
                   print("Resume resp time: " + str(respTime))
                   print("Resume boss Rarity: " + str(bossRarity))
                   async with ctx.typing():
                    await ctx.channel.send('Dookoła rozlega się cisza, jedynie wiatr wzbija w powietrze tumany kurzu...')
                   if DebugMode == False:
                        await asyncio.sleep(respTime)  # time in second
                   else:
                        await asyncio.sleep(respTime)  # time in second
                   
               
            #=== Episode 2 - Before fight
            if bossAlive == 2:
               bossAlive = 3

               #Channel Clear
               #await functions_general.fClear(self, ctx)
               print("Channel cleared. bossAlive = 2")
               async with ctx.typing():
                await ctx.channel.send('Wiatr wzmaga się coraz mocniej, z oddali słychać ryk, a ziemią targają coraz mocniejsze wstrząsy... <:MonkaS:882181709100097587>')
               if DebugMode == False:
                    await asyncio.sleep(random.randint(60,120)*5)  # time in second
               else:
                    await asyncio.sleep(random.randint(3,10))  # time in second
            #=== Episode 3 - Boss respawn
            if bossAlive == 3:
                bossAlive = 4
                print("Channel cleared.")
                await functions_general.fClear(self, ctx)
                print("Boss appeared.")
                #Send boss image based on rarity
                global initCommand
                initCommand = "zaatakuj"
                initCommand = await functions_boss.fBossImage(self, ctx, bossRarity)

            else:
                await asyncio.sleep(5) #sleep for a while
    
    #create Spawn Boss task command
    @commands.command(name="startSpawnBoss", brief="Starts spawning boss")
    @commands.has_permissions(administrator=True)
    async def startMessage(self, ctx):
        print("Spawning started!")
        global bossAlive
        bossAlive = 0
        self.task = self.bot.loop.create_task(self.spawn_task(ctx))
        

    # command to stop Spawn Boss task
    @commands.command(pass_context=True, name="stopSpawnBoss", brief="Stops spawning boss")
    @commands.has_permissions(administrator=True)
    async def stopMessage(self, ctx):
        print("Spawning stopped!")
        global bossAlive, respawnResume
        respawnResume = False
        bossAlive = 0
        await functions_database.updateBossTable(self, ctx, 0, 0, False)
        self.task.cancel()

    # command to check Spawn Boss
    @commands.command(pass_context=True, name="checkSpawnBoss", brief="Checking boss spawn time")
    @commands.has_permissions(administrator=True)
    async def checkSpawnMessage(self, ctx):
        await ctx.channel.send("Resp time is " + str(respTime/60/60) + " hours.")


    # command to attack the boss
    @commands.command(pass_context=True, name="zaatakuj", brief="Attacking the boss")
    async def attackMessage(self, ctx):
        if ctx.channel.id == 970684202880204831 or ctx.channel.id == 970571647226642442:
            global bossAlive, bossRarity, respawnResume
            if bossAlive == 4: #or str(ctx.message.author.id) == '291836779495948288':
                bossAlive = 5
                respawnResume = False
                author = discord.User.id
                preFight = False

                try:
                    async with ctx.typing():
                        anotherAtkCmd = await self.bot.wait_for('message', timeout=5)
                    response = str(anotherAtkCmd.content)
                    print(response)
                    if response == "#zaatakuj":
                        preFight = True
                        print("Prefight: " + str(preFight))
                        async with ctx.typing():
                            await asyncio.sleep(2)
                            await ctx.channel.send('"**SPOKÓJ!!!**" - *słyszyscie głos w swojej głowie.* "Zachowajcie resztki honoru i wystawcie do walki najsilniejszego z Was."')
                        initCmd = random.choice(["konstantynopolitańczykówna", "degrengolada", "Antropomorfizacja", "Zjawiskowy", "Opsomaniak", "Egzegeza", "Chasydyzm", "Eksplikacja", "Apoteoza", "Buńczuczny","Konstantynopolitańczykówna", "Degrengolada", "Prokrastynacja", "Wszeteczeństwo", "Melepeta", "Imponderabilia", "Inwariant", "Tromtadracja", "Transcendencja", "Lumpenproletariat"])
                        await asyncio.sleep(6)
                        async with ctx.typing():
                            await ctx.channel.send('"Pierwszy, który PŁYNNIE wypowie zaklęcie, które zaraz zdradzę, będzie godzien walki ze mną!"')
                        await asyncio.sleep(8)
                        async with ctx.typing():
                            await ctx.channel.send('"Zaklęcie to **' + " ".join(initCmd.upper()) + '**"')
                except asyncio.TimeoutError:
                    pass

                if preFight == True:
                    Try = 0
                    try:
                        print("Prefight True")
                        while True:
                            spellCmd = await self.bot.wait_for('message', timeout=6)
                            print ("Wait for event.")
                            response = str(spellCmd.content)
                            if  response.lower() == initCmd.lower():
                                bossHunterID = spellCmd.author
                                await spellCmd.add_reaction("⚔️")
                                break
                            else:
                                Try+=1
                    except asyncio.TimeoutError:
                        async with ctx.typing():
                            await ctx.channel.send('"Pfff... Miernoty. Nikt z Was nie jest godzien."')
                        logChannel = self.bot.get_channel(881090112576962560)
                        await  logChannel.send("Cała grupa nie zdążyła wpisac hasła.")
                        await functions_database.updateBossTable(self, ctx, 0, 0, False)
                        bossAlive = 0
                        
                else:
                    print("Prefight False")
                    bossHunterID = ctx.author
                    print("Boss hunter name: " + bossHunterID.name)
                
                if bossAlive == 5:
                    async with ctx.typing():
                        await ctx.channel.send('Zaatakowałeś bossa <@' + format(bossHunterID.id) + '>! <:REEeee:790963160495947856> Wpisz pojawiające się komendy tak szybko, jak to możliwe! Przygotuj się!')
                    await asyncio.sleep(5)

                    #Start time counting
                    startTime = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
                    #Save resp time and nickname
                    await functions_database.updateHistoryTable(self, ctx, bossHunterID.name, startTime)

                    #Random the message and requested action
                    requestedAction = [("unik", "atak", "paruj", "skok", "biegnij", "turlaj", "czaruj", "blok", "skacz", "akcja"), ("Boss szarżuje na Ciebie! Wpisz **UNIK**", "Boss zawahał się! Teraz! Wpisz **ATAK**", "Boss atakuje, nie masz miejsca na ucieczkę, wpisz **PARUJ**", 
                    "Boss próbuje ataku w nogi, wpisz **SKOK**", "Boss szykuje potężny atak o szerokim zasięgu, wpisz **BIEGNIJ**", "Boss atakuje w powietrzu, wpisz **TURLAJ**", "Boss rzuca klątwę, wpisz **CZARUJ**", "Boss atakuje, nie masz miejsca na ucieczkę, wpisz **BLOK**","Boss próbuje ataku w nogi, wpisz **SKACZ**","Boss szarżuje na Ciebie, zrób coś, wpisz **AKCJA**")]
            
                    bossHP = fRandomBossHp(bossRarity)
                    print("Wylosowane HP bossa: " + str(bossHP))
                    iterator = 0

                    #Define check function
                    channel = ctx.channel
                    def check(ctx):
                        def inner(msg):
                            return (msg.channel == channel) and (msg.author == bossHunterID)
                        return inner


                    #Start whole fight
                    for iterator in range(bossHP): #start boss turn
                        iterator += 1

                        choosenAction = random.randint(0,len(requestedAction[0])-1)
                        #print("Wylosowany numer akcji: " + str(choosenAction))
                        #print("Trzeba wpisac: " + requestedAction[0][choosenAction])

                        try:
                            #Send proper action request on chat
                            await ctx.channel.send(str(iterator) + '. ' + requestedAction[1][choosenAction])

                            #Longer timeout for the first action
                            if iterator == 1:
                                cmdTimeout = 7
                            else:
                                #Timeout depends on boss rarity
                                cmdTimeout = 5 - bossRarity
                            msg = await self.bot.wait_for('message', check=check(ctx), timeout=cmdTimeout)
                            response = str(msg.content)

                            if response.lower() == requestedAction[0][choosenAction]:
                                #Boss killed?
                                if iterator >= bossHP:
                                    bossAlive = 0
                                    await ctx.channel.send('Brawo <@' + format(bossHunterID.id) + '>! Pokonałeś bossa! <:POGGIES:790963160491753502><:POGGIES:790963160491753502><:POGGIES:790963160491753502>')

                                    #Time record
                                    endTime = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
                                    recordTime = endTime - startTime
                                    recordTurnTime = recordTime/bossHP
                                    await ctx.channel.send('Zabicie bossa zajęło Ci: ' + str(recordTime).lstrip('0:00:') + ' sekundy! Jedna tura zajęła Ci średnio ' + str(recordTurnTime).lstrip('0:00:') + ' sekundy!')
                                    previousRecord, Nick = await functions_database.readRecordTable(self, ctx)
                                
                                    if datetime.datetime.strptime(previousRecord, "%H:%M:%S.%f") > datetime.datetime.strptime(str(recordTurnTime), "%H:%M:%S.%f"):
                                        await ctx.channel.send('Pobiłeś rekord i zgarniasz dodatkowe 3000 doświadczenia na discordzie!')
                                        logChannel = self.bot.get_channel(881090112576962560)
                                        await logChannel.send("<@291836779495948288>!   " + bossHunterID.name + " otrzymał: 3000 expa za rekord")
                                        await functions_database.updateRecordTable(self, ctx, bossHunterID.name, recordTurnTime)

                                    #Ranking - add points
                                    print("Boss rarity before adding to ranking: " + str(bossRarity))
                                    if bossRarity == 0:
                                        points = 1
                                    elif bossRarity == 1:
                                        points = 3
                                    elif bossRarity == 2:
                                        points = 6
                                    else:
                                        points = 1
                                    await functions_database.updateRankingTable(self, ctx, bossHunterID.id, points)
                            
                                    #Spawn resume off
                                    await functions_database.updateBossTable(self, ctx, 0, 0, False)                         
                            
                                    #Randomize Loot
                                    dropLoot = await functions_boss.randLoot(self, ctx, bossRarity)                                

                                    #Send info about loot
                                    logChannel = self.bot.get_channel(881090112576962560)
                                    await logChannel.send("<@291836779495948288>!   " + bossHunterID.name + " otrzymał: " + str(dropLoot[0]))
                            
                                else:
                                    print("Good command.")
                            else:
                                await ctx.channel.send('Pomyliłeś się! <:PepeHands:783992337377918986> Boss pojawi się później! <:RIP:912797982917816341>')
                                logChannel = self.bot.get_channel(881090112576962560)
                                await  logChannel.send("<@291836779495948288>!   " + bossHunterID.name + " pomylił się i nie zabił bossa.")
                                await functions_database.updateBossTable(self, ctx, 0, 0, False)
                                bossAlive = 0
                                break
                        
                        except asyncio.TimeoutError:
                            await ctx.channel.send('Niestety nie zdążyłeś! <:Bedge:970576892874854400> Boss pojawi się później! <:RIP:912797982917816341>')
                            logChannel = self.bot.get_channel(881090112576962560)
                            await  logChannel.send("<@291836779495948288>!   " + bossHunterID.name + " nie zdążył wpisać komend i boss uciekł.")
                            await functions_database.updateBossTable(self, ctx, 0, 0, False)
                            bossAlive = 0
                            break
                elif bossAlive == 4:
                    pass
                else:
                    pass
            elif bossAlive == 5:
                pass
            else:
                print("Boss is not alive or attacked!")
                await ctx.channel.send('Nie możesz zaatakować bossa, poczekaj na pojawienie się kolejnego <@' + format(ctx.message.author.id) + '>!')




    # ==================================== COMMANDS FOR USERS =======================================================================

    # command to check boss kill record
    @commands.command(name="rekord")
    async def rekord(self, ctx):
        if ctx.channel.id == 970684202880204831 or ctx.channel.id == 970571647226642442:
            recordTime, Nick = await functions_database.readRecordTable(self, ctx)
            print ("Record database read.")
            await ctx.channel.send('Poprzedni rekord należy do **' + Nick + '** i wynosi średnio **' + recordTime.lstrip('00:') + ' sekundy na turę walki**.')

    # command to check last boss kill
    @commands.command(pass_context=True, name="kiedy", brief="Check previous boss kill time")
    async def lastKillInfoMessage(self, ctx):
        if ctx.channel.id == 970684202880204831 or ctx.channel.id == 970571647226642442:
            fightTime, Nick = await functions_database.readHistoryTable(self, ctx)
            print ("History database read.")
            await ctx.channel.send('Poprzednio boss walczył z **' + Nick + '** i było to **' + fightTime + ' UTC+2**.')

    @commands.command(name="ranking")
    async def readRankingDatabase(self, ctx):
        if ctx.channel.id == 970684202880204831 or ctx.channel.id == 970571647226642442:
            await functions_database.readRankingTable(self, ctx)
            print ("Ranking database read.")

    # command to flex boss slayer
    @commands.command(pass_context=True, name="flex", brief="Boss slayer flex")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def flex(self, ctx):
        my_role = discord.utils.get(ctx.guild.roles, id=983798433590673448)
        print(str(type(ctx.message.author)))
        if my_role in ctx.message.author.roles:
            await functions_boss.flexGif(self, ctx)
            await ctx.channel.send('Potężny <:GigaChad:970665721321381958> <@' + format(ctx.message.author.id) + '> napina swe sprężyste, naoliwione muskuły! Co za widok, robi wrażenie! <:pogu:882182966372106280>')
        else:
            await ctx.channel.send('<:KEKW:936907435921252363> **Miernota** <:2Head:882184634572627978>')

    # command to change color
    @commands.command(pass_context=True, name="kolor", brief="Boss slayer color change")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def kolor(self, ctx, hexColor):
        my_role = discord.utils.get(ctx.guild.roles, id=983798433590673448)
        print(str(type(ctx.message.author)))
        if my_role in ctx.message.author.roles:
            print("Before function to change color.")
            await functions_boss.changeColor(self, ctx, hexColor)
        else:
            await ctx.channel.send('<:KEKW:936907435921252363> **Kpisz sobie, miernoto?** <:2Head:882184634572627978>')

    # ==================================== COMMANDS FOR DEBUG =======================================================================

    # command to change icon
    @commands.command(pass_context=True, name="ikona", brief="Boss slayer icon change")
    @commands.has_permissions(administrator=True)
    #@commands.cooldown(1, 1800, commands.BucketType.user)
    async def changeIcon(self, ctx, hexColor):
        print("Before function to change color.")
        await functions_boss.changeIcon(self, ctx, hexColor)

    # command to debug
    @commands.command(pass_context=True, name="bossslayer")
    @commands.has_permissions(administrator=True)
    async def bossSlayer(self, ctx, userID):
        await functions_boss.setBossSlayer(self, ctx, userID)

    # command to debug
    @commands.command(pass_context=True, name="remind")
    @commands.has_permissions(administrator=True)
    async def remind(self, ctx):
        Channel = self.bot.get_channel(970684202880204831)
        await Channel.send("Potwór oczekuje na zabicie! Wpisz **#zaatakuj**, aby rozpocząć walkę! @here")

    # command to debug
    @commands.command(pass_context=True, name="rarity")
    @commands.has_permissions(administrator=True)
    async def bossRarity(self, ctx, time):
        await ctx.channel.send(str(functions_boss.fBossRarity(time)))

    # command to debug
    @commands.command(pass_context=True, name="image")
    @commands.has_permissions(administrator=True)
    async def bossImage(self, ctx, rarity):
        await functions_boss.fBossImage(self, ctx, rarity)

    # command to debug
    @commands.command(pass_context=True, name="hp")
    @commands.has_permissions(administrator=True)
    async def bossHp(self, ctx, rarity):
        await ctx.channel.send(str(fRandomBossHp(rarity)))

    # command to debug
    @commands.command(pass_context=True, name="respToFile")
    @commands.has_permissions(administrator=True)
    async def respToFile(self, ctx, respawnTime, bossRarity, respawnStarted):
        functions_boss.fSaveRespawnToFile(respawnTime, bossRarity, respawnStarted)
        await ctx.channel.send("File Saved")

    # command to debug
    @commands.command(pass_context=True, name="respFromFile")
    @commands.has_permissions(administrator=True)
    async def respFromFile(self, ctx):
        respawnTime, bossRarity, respawnStarted = functions_boss.fReadRespawnFromFile()
        await ctx.channel.send("Read from file - seconds to spawn: " + str(respawnTime) + ". Boss rarity: " + str(bossRarity) + ". Respawn started?: " + str(respawnStarted))
        
    # command to debug
    @commands.command(pass_context=True, name="spawn")
    @commands.has_permissions(administrator=True)
    async def spawn(self, ctx):
        await functions_boss.fCreateSpawn(self)
        await ctx.channel.send("Spawn created")

    # command to debug
    @commands.command(name="context")
    @commands.has_permissions(administrator=True)
    async def context(self, ctx):
        await functions_boss.getContext(self)

    # ==================================== COMMANDS FOR DATABASE =======================================================================

    @commands.command(name="updateDatabase")
    @commands.has_permissions(administrator=True)
    async def updateDatabase(self, ctx, bossRarity, respTime, respBool):
        await functions_database.updateBossTable(self, ctx, bossRarity, respTime, respBool)
        await ctx.channel.send("Database updated.")

    @commands.command(name="readDatabase")
    @commands.has_permissions(administrator=True)
    async def readDatabase(self, ctx):
        bossRar, respawnTime, respawnResume = await functions_database.readBossTable(self, ctx)
        print ("Database read.")
        await ctx.channel.send("Czy boss będzie wskrzeszony?: " + str(respawnResume))
        await ctx.channel.send("Boss rarity: " + str(bossRar))
        await ctx.channel.send("Czas wskrzeszenia: " + str(respawnTime))

    @commands.command(name="createAllDatabases")
    @commands.has_permissions(administrator=True)
    async def createAllDatabases(self, ctx):
        await functions_database.createBossTable(self)
        await functions_database.createRecordTable(self)
        await functions_database.createHistoryTable(self)
        await ctx.channel.send("Wszystkie bazy danych utworzone!")

    @commands.command(name="createBossDatabase")
    @commands.has_permissions(administrator=True)
    async def createBossDatabase(self, ctx):
        await functions_database.createBossTable(self)
        await ctx.channel.send("Baza danych utworzona.")

    # ====== Record Database Commands to Debug

    @commands.command(name="createRecordDatabase")
    @commands.has_permissions(administrator=True)
    async def createDatabase(self, ctx):
        await functions_database.createRecordTable(self)
        await ctx.channel.send("Baza danych z rekordem utworzona.")

    @commands.command(name="updateRecordDatabase")
    @commands.has_permissions(administrator=True)
    async def updateRecordDatabase(self, ctx, Nick, recordTime_MM_SS_MS):
        await functions_database.updateRecordTable(self, ctx, Nick, recordTime_MM_SS_MS)
        await ctx.channel.send("Baza danych z rekordem zaktualizowana.")

    # ====== History Database Commands to Debug

    @commands.command(name="createHistoryDatabase")
    @commands.has_permissions(administrator=True)
    async def createHistoryDatabase(self, ctx):
        await functions_database.createHistoryTable(self)
        await ctx.channel.send("Baza danych z historią utworzona.")

    @commands.command(name="updateHistoryDatabase")
    @commands.has_permissions(administrator=True)
    async def updateHistoryDatabase(self, ctx, Nick, fightTime):
        await functions_database.updateHistoryTable(self, ctx, Nick, fightTime)
        await ctx.channel.send("Baza danych z historią zaktualizowana.")

    # ====== Ranking Database Commands to Debug

    @commands.command(name="createRankingDatabase")
    @commands.has_permissions(administrator=True)
    async def createRankingDatabase(self, ctx):
        await functions_database.createRankingTable(self)
        await ctx.channel.send("Baza danych z rankingiem utworzona.")

    @commands.command(name="resetRankingDatabase")
    @commands.has_permissions(administrator=True)
    async def resetRankingDatabase(self, ctx):
        await functions_database.resetRankingTable(self)
        await ctx.channel.send("Baza danych z rankingiem zresetowana.")

    @commands.command(name="updateRankingDatabase")
    @commands.has_permissions(administrator=True)
    async def updateRankingDatabase(self, ctx, ID, points):
        print("Starting command...")
        await functions_database.updateRankingTable(self, ctx, ID, points)
        
def setup(bot):
    bot.add_cog(message(bot))
