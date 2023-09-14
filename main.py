import os
import discord
import feedparser
import asyncio

from discord import Intents
from markdownify import markdownify
from discord.ext import commands

from FeedHandler import FeedHandler

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN') or ""
if DISCORD_TOKEN == "":
    raise Exception("Please add your token to the environment variables.")

intents = discord.Intents.default()
intents.message_content = True

# Initialize Discord client and RSS feed URL
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.add_cog(FeedHandler(bot))


@bot.command('hey', aliases=['pizza', 'punk'])
async def hey(ctx):
    await ctx.send("Do jOO waNn_a PizZa me??")
    await asyncio.sleep(3)
    await ctx.send("That's what I thought...")
    await asyncio.sleep(3)
    await ctx.send("but waaait... I'm just a bot")
    await asyncio.sleep(1)
    await ctx.send("...so like, I can't eat pizza...")


@bot.command('echo')
async def echo(ctx):
    await ctx.send("*echo*... *echo*... *echo*...")

# Start the Discord client
if __name__ == '__main__':
    try:
        bot.run(DISCORD_TOKEN)
    except discord.HTTPException as e:
        if e.status == 429:
            print(
                "The Discord servers denied the connection for making too many requests"
            )
            print(
                "Get help from "
                "https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests"
            )
        else:
            raise e
