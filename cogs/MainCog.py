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

        self.job_feed = None
        self.feedback = None

    @commands.command('connect')
    async def connect(self, ctx):
        """Connect the bot to the channel"""
        if self.user == ctx.author:
            await ctx.send("You're already connected silly!")
            return
        self.user = ctx.author

        await ctx.send("Gotcha...")

        # setup job feed
        self.job_feed = JobFeedCog(self.user)
        await self.bot.add_cog(self.job_feed)

        # setup feedback
        self.feedback = FeedbackCog(self.user)
        await self.bot.add_cog(self.feedback)

    @commands.command('feed')
    async def feed(self, ctx, action: Optional[str], *args):
        if await self._check_user(ctx):
            return

        if action == 'add':
            await self.job_feed.searches.add_url(args[0])
        elif action == 'remove':
            await ctx.send(f"This function has not been implemented yet")
        elif action == 'searches':
            await ctx.send(f"Current searches\n: {self.job_feed.searches.feed_urls}")
        elif action == 'enable':
            await self.job_feed.enable_loop()
        elif action == 'disable':
            await self.job_feed.disable_loop()
        elif action == 'status':
            await self.job_feed.status(ctx)
        elif action == 'list':
            await self.job_feed.list_cache()
        elif action == 'clear':
            await self.job_feed.clear_cache()
        else:
            await ctx.send("Invalid action. Please use `add`, `remove`, `list`, `enable`, `disable` or `status`")

    @commands.command('fb')
    async def feedback(self, ctx, action: Optional[str]):
        if await self._check_user(ctx):
            return

        if action == 'process':
            await self.feedback.begin()
        elif action == 'exit':
            await self.feedback.exit_conversation()
        elif action == 'enable':
            await self.feedback.enable_loop()
        elif action == 'disable':
            await self.feedback.disable_loop()
        elif action == 'fetch':
            self.feedback.fetch_jobs()
            await ctx.send(f"Fetched {len(self.feedback.query_cache)} jobs that require feedback.")
        elif action == 'status':
            await self.feedback.status()
        else:
            await ctx.send("Invalid action. Please use `enable`, `disable`, `fetch`, `process`, `exit`, or `status`.")

    async def _check_user(self, ctx) -> bool:
        """Check if user is connected to the bot"""
        if self.user != ctx.author:
            await not_connected(ctx)
            return True
        else:
            return False
