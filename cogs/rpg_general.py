import discord
from discord.errors import ClientException
from discord.ext import commands, tasks

import sys
sys.path.insert(1, './functions/')
import functions_general
import functions_boss
import functions_database
import functions_rpg_general

#Import Globals
from globals.globalvariables import DebugMode

class message(commands.Cog, name="rpg_general"):
    def __init__(self, bot):
        self.bot = bot

    #========================== COMMANDS FOR USERS =======================================

    @commands.command(name="start")
    @commands.has_permissions(administrator=True) #TOREMOVE
    async def createCharacter(self, ctx):
        playerID = ctx.author.id
        print("User ID: " + str(playerID))
        await functions_rpg_general.createCharacter(self, ctx, playerID)

    @commands.command(name="rankinglvl")
    @commands.has_permissions(administrator=True) #TOREMOVE
    async def readRpgGeneral(self, ctx):
        await functions_rpg_general.readRpgGeneral(self, ctx)

    @commands.command(name="profil")
    @commands.has_permissions(administrator=True) #TOREMOVE
    async def checkGeneralProfile(self, ctx):
        await functions_rpg_general.checkGeneralProfile(self, ctx)


    #========================== COMMANDS TO DEBUG =======================================

    @commands.command(name="createRpgGeneralDatabase")
    @commands.has_permissions(administrator=True)
    async def createRpgGeneralDatabase(self, ctx):
        await ctx.channel.send("Baza danych RPG tworzona...")
        await functions_rpg_general.createRpgGeneralTable(self, ctx)
        await ctx.channel.send("Baza danych RPG utworzona.")
        
        
def setup(bot):
    bot.add_cog(message(bot))
