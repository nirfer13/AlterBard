﻿from discord.ext import commands
import discord
import asyncio
import random
import json

from datetime import datetime, timedelta

import time
import datetime

# general bag for functions
global DebugMode
DebugMode = False

class functions_boss(commands.Cog, name="functions_boss"):
    def __init__(self, bot):
        self.bot = bot

    #define Loot -> move to function?
    global randLoot
    def randLoot(srarity):
        rarity = int(srarity)

        with open("lootConfig.json", encoding='utf-8') as jsonFile:
            jsonObject = json.loads(jsonFile.read())
                
        lootDescrList = []
        lootWeightList = []
        for loot in jsonObject['loot_details']:
            lootDescrList.append(loot['descr'])
            #Increase only rare rewards
            if loot['weight'] < 5:
                if rarity == 0:
                    lootWeightList.append(loot['weight'])
                elif rarity == 1:
                    lootWeightList.append(loot['weight']*3)
                elif rarity == 2:
                    lootWeightList.append(loot['weight']*6)
                else:
                    lootWeightList.append(loot['weight'])
            else:
                lootWeightList.append(loot['weight'])

        print(lootDescrList)
        print(lootWeightList)

        global dropLoot
        dropLoot = random.choices(lootDescrList, lootWeightList)
                
        #Embed create   
        embed=discord.Embed(title='Boss Drop', url='https://www.altermmo.pl/wp-content/uploads/altermmo-2-112.png', description='Boss wydropił:\n👉 ' + str(dropLoot[0]), color=0xfcdb03)
        embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/altermmo-2-112.png')
        embed.set_footer(text='Gratulacje!')
        return embed, dropLoot    

    #function to send boss image
    global fBossImage
    async def fBossImage(self, ctx, srarity):
        print("Boss spawned. bossAlive = 3")
        rarity = int(srarity)
        #image name
        imageNumber = pow(10,rarity)
        if imageNumber == 1:
            imageNumber = 0
        imageName = "mobs/" + str(random.randint(0,4)+imageNumber) + ".gif"

        #title
        if rarity == 0:
            eTitle = "💀 Zwykły boss! 💀"
        elif rarity == 1:
            eTitle = "💀 Rzadki boss! 💀"
        elif rarity == 2:
            eTitle = "💀 Epicki boss! 💀"
        else:
            eTitle = "💀 Boss! 💀"

        #description
        if rarity == 0:
            eDescr = "Pojawił się zwykły boss! Zabij go natychmiast, żeby zgarnąć nagrody! Wpisz **#zaatakuj**, żeby rozpocząć walkę! ⚔️"
        elif rarity == 1:
            eDescr = "Pojawił się rzadki boss! Zabij go natychmiast, żeby zgarnąć nagrody! Wpisz **#zaatakuj**, żeby rozpocząć walkę! ⚔️"
        elif rarity == 2:
            eDescr = "Pojawił się epicki boss! Zabij go natychmiast, żeby zgarnąć nagrody! Wpisz **#zaatakuj**, żeby rozpocząć walkę! ⚔️"
        else:
            eDescr = "Pojawił się boss! Zabij go natychmiast, żeby zgarnąć nagrody! Wpisz **#zaatakuj**, żeby rozpocząć walkę! ⚔️"

        #color
        if rarity == 0:
            eColor = 0xFFFFFF
        elif rarity == 1:
            eColor = 0x0000FF
        elif rarity == 2:
            eColor = 0x800080
        else:
            eColor = 0xFFFFFF

        #thumb
        if rarity == 0:
            eThumb = 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/google/313/large-green-square_1f7e9.png'
        elif rarity == 1:
            eThumb = 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/google/313/large-blue-square_1f7e6.png'
        elif rarity == 2:
            eThumb = 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/google/313/large-purple-square_1f7ea.png'
        else:
            eThumb = 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/google/313/large-green-square_1f7e9.png'

        #image
        embed = discord.Embed(
            title=eTitle,
            description=eDescr,
            color=eColor)
        embed.set_thumbnail(url=eThumb)
        await ctx.channel.send(file=discord.File(imageName))
        await ctx.send(embed=embed)


    #function to set boss rarity
    global fBossRarity
    def fBossRarity(time):
        iTime = int(time)
        print("Time inside function: " + str(iTime))
        if DebugMode == False:
            if iTime >= 0 and iTime < 43200:
                bossRarity = 0
            elif iTime >= 43200 and iTime < 75600:
                bossRarity = 1
            elif iTime >= 75600 and iTime <= 90000:
                bossRarity = 2
            else:
                bossRarity = 0 
        else:
            if iTime >= 0 and iTime < 12:
                bossRarity = 0
            elif iTime >= 12 and iTime < 21:
                bossRarity = 1
            elif iTime >= 21 and iTime <= 25:
                bossRarity = 2
            else:
                bossRarity = 0        
        #print(iTime)
        
        return bossRarity


    #function to Random BossHP
    global fRandomBossHp
    def fRandomBossHp(bossRarity):
        ibossRarity = int(bossRarity)
        if ibossRarity == 0:
            minHp = 2
            maxHp = 4
        elif ibossRarity == 1:
            minHp = 5
            maxHp = 8
        elif ibossRarity == 2:
            minHp = 9
            maxHp = 12
        else:
            minHp = 2
            maxHp = 4
        bossHP = random.randint(minHp,maxHp)
        return bossHP

    #function to save respawn time to file
    global fSaveRespawnToFile
    def fSaveRespawnToFile (respawnTime, bossRarity, respStarted):
        intRespawnTime = int(respawnTime)
        Time = datetime.datetime.utcnow() + datetime.timedelta(hours=2) + datetime.timedelta(seconds=intRespawnTime)
        with open('respawnTimeInfo.txt', 'w') as f:
            f.write(str(Time) + '\n')
            f.write(str(bossRarity) + '\n')
            f.write(str(respStarted))

    #function to read respawn time from file
    global fReadRespawnFromFile
    def fReadRespawnFromFile ():
        with open('respawnTimeInfo.txt', 'r') as r:
            readLines = r.readlines()
        #line 0
        spawnTimestamp = datetime.datetime.strptime(readLines[0].rstrip('\n'), "%Y-%m-%d %H:%M:%S.%f")
        print(str(spawnTimestamp))
        secondsToSpawn = spawnTimestamp - (datetime.datetime.utcnow() + datetime.timedelta(hours=2))
        #line 1
        bossRarity = readLines[1].rstrip('\n')
        #line 2
        respStarted = readLines[2]

        return secondsToSpawn.total_seconds(), bossRarity, respStarted

    #function to get context
    global getContext
    async def getContext(self, channelID, messageID):
        channel = self.bot.get_channel(channelID)
        msg = await channel.fetch_message(messageID)
        ctx = await self.bot.get_context(msg)
        return ctx






def setup(bot):
    bot.add_cog(functions_boss(bot))
