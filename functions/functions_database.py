from discord.ext import commands
import discord
import asyncio

import datetime
import os
import urllib.parse as urlparse
import psycopg2
import asyncpg

from asyncpg.pool import create_pool
from discord.ext import commands

#Import Globals
from globals.globalvariables import DebugMode

# database bag for functions
class functions_database(commands.Cog, name="functions_database"):
    def __init__(self, bot):
        self.bot = bot

    global create_db_pool
    async def create_db_pool(self):
        try:
            #Establishing the connection
            if DebugMode == True:
                self.bot.pg_con = await asyncpg.create_pool(database="d2am99h8cekkeo", user="hkheidzoebbhxe", password='d545d32cdd85d3018184ff7f82a9129180f577ed9e03e71f9fe05e93d9cd19ee', host='ec2-63-35-156-160.eu-west-1.compute.amazonaws.com')
            else:
                self.bot.pg_con = await asyncpg.create_pool(database="d6png7v0gjdfrj", user="qwkoyntirvkqzn", password='a9950dd4d12a84078a2b5ba4ca8220edffbb381c0dd53cdd21babd3fb7da0b91', host='ec2-34-248-169-69.eu-west-1.compute.amazonaws.com')
            print("Connected to database. Pool created.")
            #Creating a cursor object using the cursor() method
        except:
            print ("I am unable to connect to the database.")
        #dbCursor = dbConnection.cursor()
        #print ("Cursor created.")

    # ==================================== FUNCTIONS FOR DATABASES =======================================================================

    #===== Create Tables

    global createBossTable
    async def createBossTable(self):
        #Doping BOSS table if already exists.
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS BOSS")
        #Creating table as per requirement
        sql ='''CREATE TABLE BOSS(
           ID NUMERIC,
           RARITY NUMERIC,
           RESPAWN_TIME TIMESTAMP,
           RESPAWN_STARTED BOOLEAN
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table created successfully.")
        dt = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        d = dt.replace(microsecond=0)
        print('INSERT INTO BOSS (ID, RARITY, RESPAWN_TIME, RESPAWN_STARTED) VALUES ({},{},\'{}\',{});'.format(str(0), str(1) , str(d), str(True)))
        await self.bot.pg_con.execute('INSERT INTO BOSS (ID, RARITY, RESPAWN_TIME, RESPAWN_STARTED) VALUES ({},{},\'{}\',{});'.format(str(0), str(1) , str(d), str(True)))
        print("Data inserted into Database.")

    global createRecordTable
    async def createRecordTable(self):
        #Doping RECORD table if already exists.
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS RECORD")
        #Creating table as per requirement
        sql ='''CREATE TABLE RECORD(
           ID NUMERIC,
           RECORD_TIME VARCHAR(255),
           NICK VARCHAR(255)
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table RECORD created successfully.")
        defaultRecord = '00:00:20.000'
        defaultNick = 'Nieznajomy'
        print('INSERT INTO RECORD (ID, RECORD_TIME, NICK) VALUES ({},\'{}\',\'{}\');'.format(str(0), defaultRecord, defaultNick))
        await self.bot.pg_con.execute('INSERT INTO RECORD (ID, RECORD_TIME, NICK) VALUES ({},\'{}\',\'{}\');'.format(str(0), defaultRecord, defaultNick))
        print("Data inserted into Record Database.")


    global createHistoryTable
    async def createHistoryTable(self):
        #Doping History table if already exists.
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS HISTORY")
        #Creating table as per requirement
        sql ='''CREATE TABLE HISTORY(
           ID NUMERIC,
           FIGHT_TIME VARCHAR(255),
           NICK VARCHAR(255)
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table HISTORY created successfully.")
        defaultTime = '2020-05-27 15:00:00'
        defaultNick = 'Nieznajomy'
        print('INSERT INTO HISTORY (ID, FIGHT_TIME, NICK) VALUES ({},\'{}\',\'{}\');'.format(str(0), defaultTime, defaultNick))
        await self.bot.pg_con.execute('INSERT INTO HISTORY (ID, FIGHT_TIME, NICK) VALUES ({},\'{}\',\'{}\');'.format(str(0), defaultTime, defaultNick))
        print("Data inserted into History Database.")

    global createRankingTable
    async def createRankingTable(self):
        #Doping Ranking table if already exists.
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS RANKING")
        #Creating table as per requirement
        sql ='''CREATE TABLE RANKING (
           ID VARCHAR(255) PRIMARY KEY,
           NICK VARCHAR(255),
           POINTS NUMERIC
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table RANKING created successfully.")
        print('INSERT INTO RANKING (NICK, POINTS) VALUES ({},\'{}\',{});'.format("291836779495948288","Andrzej", 3))
        print('INSERT INTO RANKING (NICK, POINTS) VALUES ({},\'{}\',{});'.format("368517986870493204", "Rafal", 10))
        await self.bot.pg_con.execute('INSERT INTO RANKING (ID, NICK, POINTS) VALUES ({},\'{}\',{});'.format("291836779495948288","Andrzej", 3))
        await self.bot.pg_con.execute('INSERT INTO RANKING (ID, NICK, POINTS) VALUES ({},\'{}\',{});'.format("368517986870493204","Rafal", 10))
        print("Data inserted into RANKING Database.")

    global resetRankingTable
    async def resetRankingTable(self):
        #Doping Ranking table if already exists.
        await self.bot.pg_con.execute("DROP TABLE IF EXISTS RANKING")
        #Creating table as per requirement
        sql ='''CREATE TABLE RANKING (
           ID VARCHAR(255) PRIMARY KEY,
           NICK VARCHAR(255),
           POINTS NUMERIC
        )'''
        await self.bot.pg_con.execute(sql)
        print("Table RANKING created successfully (empty).")

    # ====== Update Tables

    global updateBossTable
    async def updateBossTable(self, ctx, BossRarity, respawnTime, ResumeSpawn):
        #Database Update
        print("Conversion...")
        intRespawnTime = int(respawnTime)
        print("To datetime...")
        Time = datetime.datetime.utcnow() + datetime.timedelta(hours=2) + datetime.timedelta(seconds=intRespawnTime)
        d = Time.replace(microsecond=0)
        print("Time before database write: " + str(type(d)))
        print("Save resume before database write: " + str(type(ResumeSpawn)))
        print("Boss rarity before database write: " + str(type(BossRarity)))
        print("Trying to update Database...")
        print("UPDATE BOSS SET ID = {}, RARITY = {}, RESPAWN_TIME = \'{}\', RESPAWN_STARTED = {} WHERE ID = 0".format(str(0), str(BossRarity), str(d), str(ResumeSpawn)))
        await self.bot.pg_con.execute('UPDATE BOSS SET ID = {}, RARITY = {}, RESPAWN_TIME = \'{}\', RESPAWN_STARTED = {} WHERE ID = 0'.format(str(0), str(BossRarity) , str(d), str(ResumeSpawn)))
        print("Data updated in Database.")

    global updateRecordTable
    async def updateRecordTable(self, ctx, Nick, recordTime_MM_SS_MS):
        #Database Update
        #test conversion
        stringRecord = str(recordTime_MM_SS_MS).lstrip(' ')
        print("Saved record: "+ stringRecord)
        print("Time before database write: " + stringRecord)
        print("Trying to update Database...")
        print("UPDATE RECORD SET ID = {}, RECORD_TIME = \'{}\', NICK = \'{}\' WHERE ID = 0".format(str(0), str(recordTime_MM_SS_MS), str(Nick)))
        await self.bot.pg_con.execute("UPDATE RECORD SET ID = {}, RECORD_TIME = \'{}\', NICK = \'{}\' WHERE ID = 0".format(str(0), str(recordTime_MM_SS_MS), str(Nick)))
        #print("Data updated in Record Database.")

    global updateHistoryTable
    async def updateHistoryTable(self, ctx, Nick, fightTime):
        #Database Update
        stringRecord = str(fightTime)
        print("Time before database write: " + stringRecord)
        print("Trying to update Database...")
        print("UPDATE HISTORY SET ID = {}, FIGHT_TIME = \'{}\', NICK = \'{}\' WHERE ID = 0".format(str(0), str(fightTime), str(Nick)))
        await self.bot.pg_con.execute("UPDATE HISTORY SET ID = {}, FIGHT_TIME = \'{}\', NICK = \'{}\' WHERE ID = 0".format(str(0), str(fightTime), str(Nick)))
        #print("Data updated in Record Database.")

    global updateRankingTable
    async def updateRankingTable(self, ctx, ID, points):
        #Database Update
        print("Checking if user exists...")
        sql=("SELECT ID, NICK, POINTS FROM RANKING WHERE ID = \'{}\';".format(str(ID)))
        check = await self.bot.pg_con.fetch(sql)
        if check:
            print("User exists.")
            #Add points
            print(check)
            allPoints = check[0][2] + int(points)
            print("UPDATE RANKING SET POINTS = {} WHERE ID = \'{}\'".format(str(allPoints), str(ID)))
            await self.bot.pg_con.execute("UPDATE RANKING SET POINTS = {} WHERE ID = \'{}\'".format(str(allPoints), str(ID)))
        else:
            print("Adding new record.")
            #Add new record
            user = self.bot.get_user(int(ID))
            await self.bot.pg_con.execute('INSERT INTO RANKING (ID, NICK, POINTS) VALUES ({},\'{}\',{});'.format(str(ID),user.name, points))
        print("Ranking database updated.")

    # ====== Read Tables

    global readBossTable
    async def readBossTable(self, ctx):
        #Database Reading
        dbBossRead = await self.bot.pg_con.fetch("SELECT RARITY, RESPAWN_TIME, RESPAWN_STARTED FROM boss")
        #spawnTimestamp = datetime.datetime.strptime(str(dbBossRead[0][2]).rstrip(), "%Y-%m-%d %H:%M:%S")
        print("Rarity read from database: " + str(dbBossRead[0][0]))
        print("Respawn time read from database: " + str(dbBossRead[0][1]))
        print("Resume read from database: " + str(dbBossRead[0][2]))
        return dbBossRead[0][0], dbBossRead[0][1], dbBossRead[0][2]

    global readRecordTable
    async def readRecordTable(self, ctx):
        #Database Reading
        dbBossRead = await self.bot.pg_con.fetch("SELECT RECORD_TIME, NICK FROM RECORD")
        print("Nick read from database: " + str(dbBossRead[0][1]))
        print("Record time read from database: " + str(dbBossRead[0][0]))
        return dbBossRead[0][0], dbBossRead[0][1]

    global readHistoryTable
    async def readHistoryTable(self, ctx):
        #Database Reading
        dbBossRead = await self.bot.pg_con.fetch("SELECT FIGHT_TIME, NICK FROM HISTORY")
        print("Nick read from database: " + str(dbBossRead[0][1]))
        print("Fight time read from database: " + str(dbBossRead[0][0]))
        return dbBossRead[0][0], dbBossRead[0][1]

    #Check ranking
    global readRankingTable
    async def readRankingTable(self, ctx):
        #Database Reading
        dbRankingRead = await self.bot.pg_con.fetch("SELECT ID, NICK, POINTS FROM RANKING ORDER BY POINTS DESC LIMIT 10")
        x = 1
        rankingString = ""
        for Person in dbRankingRead:
            user = self.bot.get_user(int(Person[0]))
            if user:
                rankingString += str(x) + ". **" + user.name + "** - " + str(Person[2]) + " pkt.\n"
                print("ID: " + Person[0])
                print("Points: " + str(Person[2]))
                print("Nick: " + str(Person[1]))
                x+=1

        #Embed create   
        emb=discord.Embed(title='Ranking łowców potworów!', url='https://www.altermmo.pl/wp-content/uploads/SwordV2_Transparent-1.png', description=rankingString, color=0xFF0000)
        emb.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/SwordV2_Transparent-1.png')
        emb.set_footer(text='Sezon kończy się w każdy poniedziałek o 15!')
        await ctx.send(embed=emb)

    #Check weekly ranking
    global readSummaryRankingTable
    async def readSummaryRankingTable(self, ctx):
        #Database Reading
        dbRankingRead = await self.bot.pg_con.fetch("SELECT ID, NICK, POINTS FROM RANKING ORDER BY POINTS DESC LIMIT 10")
        x = 1
        rankingString = ""
        for Person in dbRankingRead:
            user = self.bot.get_user(int(Person[0]))
            if user:
                rankingString += str(x) + ". **" + user.name + "** - " + str(Person[2]) + " pkt.\n"
                print("ID: " + Person[0])
                print("Points: " + str(Person[2]))
                print("Nick: " + str(Person[1]))
                x+=1

        #Embed create   
        emb=discord.Embed(title='Ranking łowców potworów na koniec sezonu!', url='https://www.altermmo.pl/wp-content/uploads/SwordV2_Transparent-1.png', description=rankingString, color=0xFF0000)
        emb.set_thumbnail(url='https://www.altermmo.pl/wp-content/uploads/SwordV2_Transparent-1.png')
        emb.set_footer(text='Ranga Rzeźnika potworów została przydzielona!')
        await ctx.send(embed=emb)
        try:
            winnerID = int(dbRankingRead[0][0])
            print(winnerID)
        except:
            print ("I am unable to select Boss Slayer. Alter is Default boss slayer")
            winnerID = 291836779495948288
        return winnerID






def setup(bot):
    bot.add_cog(functions_database(bot))
