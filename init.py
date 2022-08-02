import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os


from globals.globalvariables import DebugMode


# token and other needed variables will be hidden in .env file
load_dotenv()
description = 'AlterMMO Discord Bard Bot, Development in progres'
intents = discord.Intents.default()
intents.members = True

#commands prefix == #
bot = commands.Bot(
    command_prefix='$',
    description=description,
    intents=intents)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send('Poczekaj na odnowienie komendy!')

#loads cogs as extentions to bot
if __name__ == '__main__':
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            extension = file[:-3]
            try:
                bot.load_extension(f"cogs.{extension}")
                print(f"Loaded extension '{extension}'")
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"
                print(f"Failed to load extension {extension}\n{exception}")
    bot.run(os.environ.get("TOKEN"))


