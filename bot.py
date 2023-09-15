import discord
from discord.ext import commands

from cogs.MainCog import MainCog


intents = discord.Intents.default()
intents.message_content = True

# Initialize Discord client and RSS feed URL
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.add_cog(MainCog(bot))
