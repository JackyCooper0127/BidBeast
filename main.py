import discord
import os

from bot import bot

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN') or ""
if DISCORD_TOKEN == "":
    raise Exception("Please add your token to the environment variables.")


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
