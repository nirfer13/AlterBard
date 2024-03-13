import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio

from globals.globalvariables import DebugMode

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

    print("Bot is starting...")
    for file in os.listdir("C:\\Programowanie\\AlterBard\\cogs"):
        if file.endswith(".py"):
            extension = file[:-3]
            try:
                await bot.load_extension(f"cogs.{extension}")
                print(f"Loaded extension '{extension}'")
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"
                print(f"Failed to load extension {extension}\n{exception}")

if __name__ == "__main__":
    asyncio.run(main())
    bot.run(os.environ.get("TOKEN"))
    print("Bot started successfully.")
