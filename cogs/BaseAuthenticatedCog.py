from typing import Union

from discord import User
from discord.ext.commands import Cog, Context


async def not_connected(ctx: Context):
    await ctx.send("You're not connected.\nPlease use `!connect` to connect to the bot.")


class BaseAuthenticatedCog(Cog):
    user: Union[User, None] = None

    def __init__(self, user: Union[User, None]):
        super().__init__()
        self.user = user

    async def _check_user(self, ctx: Context) -> bool:
        """Check if user is connected to the bot"""
        if self.user != ctx.author:
            await not_connected(ctx)
            return True
        else:
            return False
