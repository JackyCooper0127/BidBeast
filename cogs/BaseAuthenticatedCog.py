from typing import Union

from discord import User
from discord.ext.commands import Cog, Context
from abc import ABCMeta


async def not_connected(ctx: Context):
    await ctx.send("You're not connected.\nPlease use `!connect` to connect to the bot.")


class BaseAuthenticatedCog(Cog, ABCMeta):
    user: Union[User, None]

    async def _check_user(self, ctx: Context) -> bool:
        """Check if user is connected to the bot"""
        if self.user != ctx.author:
            await not_connected(ctx)
            return True
        else:
            return False
