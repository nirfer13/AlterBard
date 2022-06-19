from discord.ext import commands
import discord
from datetime import datetime, timezone

import datetime
import sys
sys.path.insert(1, './functions/')
import functions_general

# general bag for commands that does not fit anywhere else

class general(commands.Cog, name="general"):
    def __init__(self, bot):
        self.bot = bot

    # Check if the bot is alive.
    @commands.command(name="ping", brief="Check if bot is alive")
    @commands.has_permissions(administrator=True)
    async def ping(self, ctx):
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"The bot latency is {round(self.bot.latency * 1000)}ms.",
            color=0x42F34C)
        await ctx.send(embed=embed)
		
	# saving history channel to .txt format, defualt file will be name channelHistory and only 100 messages will be saved
    # both parameters can be changed in commands params
    # simple formmating userName | channelName | message
    @commands.command(brief="Saves messages from current channel to txt, default amount of messages == 100")
    @commands.has_permissions(administrator=True)
    async def saveToTxt(self, ctx, limit: int = 100):
        text_channel_list = []
        guild = ctx.guild
        messages = await ctx.channel.history(limit=limit).flatten()
        reverseMessages = messages.reverse()
        now = datetime.datetime.utcnow() # current date and time
        file_name = now.strftime("%m_%d_%Y_%H_%M_%S")
        with open(file_name + ".txt", "a+", encoding="utf-8") as f:
            for message in messages:
                splittedString = message.content.split("\n", 1)
                first = "<h2><strong>"+ splittedString[0]+"</strong></h2>\n"
                second = ""
                try:
                    second = splittedString[1]
                except:
                    pass
                     
                print(
                    f"{first + second} \n\n",
                    file=f)
        print("last: ", limit, " were saved to file with name: " + file_name)
    

    # command to clear channel
    @commands.command(name="clear", pass_context = True, brief="Clear channel messages")
    @commands.has_permissions(administrator=True)
    async def clear(self, ctx):
        await functions_general.fClear(self, ctx)
    
    # Just debug action, printing to console when ready and logged in.
    @commands.Cog.listener()
    async def on_ready(self):
        print('ready')
        print('Logged in as:  ', self.bot.user)
        print('ID:  ', self.bot.user.id)

def setup(bot):
    bot.add_cog(general(bot))
