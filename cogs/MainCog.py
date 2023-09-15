from typing import Union, Optional

import discord
from discord.ext.commands.bot import Bot
from discord.ext import commands

from cogs.JobFeedCog import JobFeedCog
from cogs.FeedbackCog import FeedbackCog


async def not_connected(ctx):
    await ctx.send("You're not connected.\nPlease use `!connect` to connect to the bot.")


class MainCog(commands.Cog):
    bot: Bot
    user: Union[discord.User, None]
    job_feed: Union[JobFeedCog, None]
    feedback: Union[FeedbackCog, None]

    def __init__(self, bot: Bot):
        print("Initializing MainCog")
        self.bot = bot
        self.user = None
        self.feedback = None

    @commands.command('connect')
    async def connect(self, ctx):
        """Connect the bot to the channel"""
        if self.user == ctx.author:
            await ctx.send("You're already connected silly!")
            return
        self.user = ctx.author

        self.job_feed = JobFeedCog(self.bot, self.user)
        await self.bot.add_cog(self.job_feed)

        await self.user.send("Gotcha...")

    @commands.command('feed')
    async def feed(self, ctx, action: Optional[str], *args):
        if not self._check_user(ctx):
            return

        if action == 'add':
            await self.job_feed.session.add_search(ctx, args[0])
        elif action == 'remove':
            await ctx.send(f"This function has not been implemented yet")
        elif action == 'searches':
            await ctx.send(f"Current searches\n: {self.job_feed.session.searches}")
        elif action == 'list':
            await self.job_feed.list_entries(ctx)
        elif action == 'start':
            await self.job_feed.start_feed(ctx)
        elif action == 'stop':
            await self.job_feed.stop_feed(ctx)
        elif action == 'status':
            await self.job_feed.status(ctx)
        else:
            await ctx.send("Invalid action. Please use 'add', 'remove', 'list', 'start' or 'stop'")

    @commands.command('feedback')
    async def feedback(self, ctx, action: Optional[str]):
        if not self._check_user(ctx):
            return

        if action == 'start':
            self.feedback = FeedbackCog(ctx)
            await self.bot.add_cog(self.feedback)
        elif action == 'fetch':
            if self.feedback is not None:
                self.feedback.fetch_jobs()
                await ctx.send(f"Fetched {len(self.feedback.query_cache)} jobs that require feedback.")
            else:
                await ctx.send("Please start feedback mode first.")
        elif action == 'stop':
            self.feedback = None
            await self.bot.remove_cog('FeedbackCog')
            await ctx.send("Stopped feedback")
        else:
            await ctx.send("Invalid action. Please use `start`, `stop`, or `fetch`.")

    async def _check_user(self, ctx) -> bool:
        """Check if user is connected to the bot"""
        if self.user != ctx.author:
            await not_connected(ctx)
            return True
        else:
            return False
