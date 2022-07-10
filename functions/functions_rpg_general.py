from discord.ext import commands
import discord
import asyncio
import random
import pycord

import time
import datetime

#Import Globals
from globals.globalvariables import DebugMode

class functions_rpg_general(commands.Cog, name="functions_rpg_general"):
    def __init__(self, bot):
        self.bot = bot

    #CREATE NEW CHARACTER
    global createCharacter
    async def createCharacter(self, ctx, playerID):
        print("Creating character.")
        #CHECK IF USER EXISTS IN DATABASE
        print("Checking if user exists...")
        sql=("SELECT ID, NICK FROM RPG_GENERAL WHERE ID = \'{}\';".format(str(playerID)))
        check = await self.bot.pg_con.fetch(sql)
        #User Exists
        if check:
            embed=discord.Embed(title='Bohater istnieje!', url='https://www.altermmo.pl/wp-content/uploads/Icon47.png', description="Stworzyłeś już bohatera wcześniej. Możesz podglądnąć swój profil wpisując *#profil*. Być może w przyszłości pojawi się możliwość zmiany klasy.", color=0x00C1C7)
            embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon47.png')
            botMessage = await ctx.channel.send(embed=embed)
        else:
            warriorEmoji = "<:RPGWarrior:995576809666134046>"
            mageEmoji = "<:RPGMage:995577415462047765>"
            rogueEmoji = "<:RPGRogue:995577306745679942>"
            clericEmoji = "<:RPGCleric:995577107642073098>"

            #Embed create
            desc1 = "Chcesz zostać bohaterem, jakiego ten Discord nie widział <@" + str(playerID) + ">? <:GigaChad:970665721321381958>\n\nPo stworzeniu swojego profilu będziesz mógł zdobywać doświadczenie, wykonywać zadania czy zbierać i ulepszać ekwipunek, aby pokonywać coraz trudniejsze potwory. <:Up:912798893304086558>\n\n**Pierwszym krokiem jest wybranie klasy:**\n\n"
            desc2 = warriorEmoji + " **Wojownik** - To ten, który przyjmie na klatę najwięcej obrażeń i wciąż będzie szedł w Twoją stronę, a gdy już dojdzie...\n"
            desc3 = mageEmoji + " **Mag** - Woli trzymać się z tyłu, bo tam w spokoju może przygotować potężne zaklęcia, które spopielą lub zamrożą przeciwników.\n"
            desc4 = rogueEmoji + " **Łotrzyk** - Cichy zabójca, który nie przepada za wrogimi toporami czy kulami ognia i dlatego po prostu ich zwinnie unika.\n"
            desc5 = clericEmoji + " **Kleryk** - Chciałby wszystkim pomagać przez leczenie i rzucanie zaklęć wspierających, jednak świat jest jaki jest i dlatego postanowił się dostosować.\n"
            desc6 = "\n**Wybierz reakcję odpowiadającą danej klasie!**"
            embed=discord.Embed(title='Tworzenie postaci', url='https://www.altermmo.pl/wp-content/uploads/Icon47.png', description=desc1 + desc2 + desc3 + desc4 + desc5 + desc6, color=0x00C1C7)
            embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon47.png')
            embed.set_footer(text='Powodzenia!')
            botMessage = await ctx.channel.send(embed=embed)

            await botMessage.add_reaction(warriorEmoji)
            await botMessage.add_reaction(mageEmoji)
            await botMessage.add_reaction(rogueEmoji)
            await botMessage.add_reaction(clericEmoji)
            await botMessage.add_reaction("🔴")

            def check(reaction, user):
                print(str(reaction.emoji))
                return user == ctx.author and str(reaction.emoji) in [warriorEmoji, mageEmoji, rogueEmoji, clericEmoji, "🔴"]

            print("Waiting for reaction")
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=90, check=check)
                print(str(type(reaction)))
            except:
                await botMessage.delete()
                embed=discord.Embed(title='Spróbuj później!', url='https://www.altermmo.pl/wp-content/uploads/Icon47.png', description="Daj znać, gdy się zastanowisz i po prostu spróbuj później.", color=0x00C1C7)
                embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon47.png')
                botMessage = await ctx.channel.send(embed=embed)
        
            x = str(reaction.emoji)
            if str(reaction.emoji) == warriorEmoji:
                playerClass = "Wojownik"
            elif str(reaction.emoji) == mageEmoji:
                playerClass = "Mag"
            elif str(reaction.emoji) == rogueEmoji:
                playerClass = "Łotrzyk"
            elif str(reaction.emoji) == clericEmoji:
                playerClass = "Kleryk"
            else:
                embed=discord.Embed(title='Spróbuj później!', url='https://www.altermmo.pl/wp-content/uploads/Icon47.png', description="Daj znać, gdy się zastanowisz i po prostu spróbuj później.", color=0x00C1C7)
                embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon47.png')
                botResponseMsg = await ctx.channel.send(embed=embed)

            await botMessage.delete()
            await newtoRpgGeneral(self, ctx, ctx.author.id, playerClass)


    global checkGeneralProfile
    async def checkGeneralProfile(self, ctx):
        print("Checking profile...")
        #CHECK IF USER EXISTS IN DATABASE
        print("Checking if user exists...")
        print(ctx.author.id)
        sql=("SELECT ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL FROM RPG_GENERAL WHERE ID = \'{}\';".format(str(ctx.author.id)))
        check = await self.bot.pg_con.fetch(sql)
        print(check)
        if check:
            print("User exists!")
            check = check[0]
            print(check[2])
            if check[2] == "Wojownik":
                url1="https://www.altermmo.pl/wp-content/uploads/Icon17.png"
            elif check[2] == "Mag":
                url1="https://www.altermmo.pl/wp-content/uploads/Icon21.png"
            elif check[2] == "Łotrzyk":
                url1="https://www.altermmo.pl/wp-content/uploads/Icon39.png"
            elif check[2] == "Kleryk":
                url1="https://www.altermmo.pl/wp-content/uploads/Icon20.png"
            else:
                url1="https://www.altermmo.pl/wp-content/uploads/Icon17.png"

            user = self.bot.get_user(ctx.author.id)

            print("Preparing Description...")
            desc1 = "**POZIOM:** " + str(check[4])
            desc2 = "\n**DOŚWIADCZENIE:** " + str(check[3]) + "/5000" #TODO

            #TODO
            desc3 = "\n\n<:RPGHP:995641654616805396> **HP:** " + "10/10"
            desc4 = "\n<:RPGMana:995641689899286568> **MANA:** " + "10/15"

            desc45 = "\n\n<:RPGStats:995642897787523072> **STATYSTYKI**"
            desc5 = "\nSIŁA: " + "10"
            desc6 = "\nZRĘCZNOŚĆ: " + "5"
            desc7 = "\nINTELIGENCJA: " + "5"
            desc8 = "\nWYTRZYMAŁOŚĆ: " + "10"

            desc89 = "\n\n<:RPGAddStat:995642835531472956> **DODATKOWE STATYSTYKI**"
            desc9 = "\nATAK: " + "10"
            desc10 = "\nUNIK: " + "10 %"
            desc11 = "\nSZANSA NA KRYT.: " + "36 %"
            desc12 = "\nODBIJANIE OBR.: " + "5 %"
            desc13 = "\nREFLEKS: " + "0.5 sekundy"
            desc14 = "\nSZANSA NA DODATKOWY DROP: " + "15 %"

            descript = desc1 + desc2 + desc3 + desc4 + desc45 + desc5 + desc6 + desc7 + desc8 + desc89 + desc9 + desc10 + desc11 + desc12 + desc13 +desc14

            embed=discord.Embed(title='Bohater ' + str(user.name), url=url1, description=descript, color=0x00C1C7)
            embed.set_thumbnail(url=url1)
            await ctx.channel.send(embed=embed)
        else:
            embed=discord.Embed(title='Bohater nie istnieje!', url='https://www.altermmo.pl/wp-content/uploads/Icon47.png', description="Nie stworzyłeś jeszcze swojego bohatera. Możesz to zrobić wpisując komendę **#start**!", color=0x00C1C7)
            embed.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon47.png')
            botMessage = await ctx.channel.send(embed=embed)

    #============================ RPG GENERAL DATABASE ==============================

    #generate RPG Database
    global createRpgGeneralTable
    async def createRpgGeneralTable(self, ctx):
        #Droping General RPG table if already exists.
        print("Trying to create RPG Database.")
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS RPG_GENERAL")
        print("RPG Database dropped.")
        #Creating table as per requirement
        sql ='''CREATE TABLE RPG_GENERAL (
           ID VARCHAR(255) PRIMARY KEY,
           NICK VARCHAR(255),
           CURRENT_CLASS VARCHAR(255),
           EXPERIENCE INT,
           LEVEL INT
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table RPG_GENERAL created successfully.")
        #print('INSERT INTO RPG_GENERAL (ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL) VALUES ({},\'{}\',\'{}\',{},{});'.format("291836779495948288","Andrzej", "Warrior", "50", "2"))
        #await self.bot.pg_con.execute('INSERT INTO RPG_GENERAL (ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL) VALUES ({},\'{}\',\'{}\',{},{});'.format("291836779495948288","Andrzej", "Wojownik", "50", "2"))
        #print("Data inserted into RPG_GENERAL Database.")

    global newtoRpgGeneral
    async def newtoRpgGeneral(self, ctx, playerID, playerClass):
        #Database Update
        user = self.bot.get_user(playerID)
        print("Trying to update Database...")
        print('INSERT INTO RPG_GENERAL (ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL) VALUES ({},\'{}\',\'{}\',{},{});'.format(str(playerID), user.name, str(playerClass), 0, 1))
        await self.bot.pg_con.execute('INSERT INTO RPG_GENERAL (ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL) VALUES (\'{}\',\'{}\',\'{}\',{},{});'.format(str(playerID), user.name, str(playerClass), 0, 1))
        print("Data inserted in General RPG Database.")

    global readRpgGeneral
    async def readRpgGeneral(self, ctx):
        #Database Reading
        print("Trying to read RPG General Database...")
        dbRpgRead = await self.bot.pg_con.fetch("SELECT ID, NICK, CURRENT_CLASS, EXPERIENCE, LEVEL FROM RPG_GENERAL ORDER BY LEVEL DESC LIMIT 10")
        x = 1
        rankingString = ""
        for Person in dbRpgRead:
            user = self.bot.get_user(int(Person[0]))
            if user:
                rankingString += str(x) + ". **" + user.name + "** - Klasa: " + str(Person[2]) + " ("+ str(Person[4]) + " poziom)\n"
                print("ID: " + Person[0])
                print("Class: " + str(Person[2]))
                print("Nick: " + str(Person[1]))
                print("Level: " + str(Person[4]))
                print("Exp: " + str(Person[3]))
                x+=1

        #Embed create   
        emb=discord.Embed(title='Ranking bohaterów!', url='https://www.altermmo.pl/wp-content/uploads/Icon24.png', description=rankingString, color=0x00C1C7)
        emb.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/Icon24.png')
        await ctx.send(embed=emb)


def setup(bot):
    bot.add_cog(functions_rpg_general(bot))
