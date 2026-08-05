import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
import os
import asyncio
from pathlib import Path

from bot_logging import setup_logging
from globals.globalvariables import DebugMode

logger = logging.getLogger(__name__)

# token and other needed variables will be hidden in .env file
load_dotenv()
description = 'AlterMMO Discord Bard Bot, Development in progres'
intents = discord.Intents.all()
intents.members = True

#commands prefix == $
bot = commands.Bot(
    command_prefix='$',
    description=description,
    intents=intents)

async def on_error(self, err, *args, **kwargs):
    raise

async def on_command_error(self, ctx, exc):
    raise getattr(exc, "original", exc)

#loads cogs as ext>
async def main():
    """Main bot applicaiton is starting."""

    logger.info("Bot is starting...")
    # Resolved from this file's location rather than hardcoded: the listdir sits
    # outside the try below, so a wrong path crashes the bot before it starts,
    # and the repo lives under a different path on every machine.
    cogs_dir = Path(__file__).resolve().parent / "cogs"
    for file in os.listdir(cogs_dir):
        if file.endswith(".py"):
            extension = file[:-3]
            try:
                await bot.load_extension(f"cogs.{extension}")
                logger.info("Loaded extension '%s'", extension)
            except Exception:
                # exc_info keeps the traceback, which is the part that says
                # *why* a cog failed to import.
                logger.exception("Failed to load extension %s", extension)

if __name__ == "__main__":
    setup_logging(DebugMode)
    asyncio.run(main())
    # log_handler=None stops discord.py from installing its own handler on top
    # of ours, which would duplicate every line and bypass the log file.
    bot.run(os.environ.get("TOKEN"), log_handler=None)
    logger.info("Bot stopped.")
