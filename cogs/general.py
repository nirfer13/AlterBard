from discord.ext import commands
import logging
import discord
from datetime import datetime, timezone

import datetime
import sys

logger = logging.getLogger(__name__)

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

    # Just debug action, printing to console when ready and logged in.
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Ready.')
        logger.info('Logged in as: %s', self.bot.user)
        logger.info('ID: %s', self.bot.user.id)

async def setup(bot):
    await bot.add_cog(general(bot))
