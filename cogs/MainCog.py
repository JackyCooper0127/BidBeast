from typing import Union, Optional

import discord
from discord.ext.commands.bot import Bot
from discord.ext import commands

from cogs.BaseAuthenticatedCog import BaseAuthenticatedCog
from cogs.JobFeedCog import JobFeedCog
from cogs.FeedbackCog import FeedbackCog
from cogs.ReviewCog import ReviewCog


class MainCog(BaseAuthenticatedCog):
    bot: Bot
    job_feed: Union[JobFeedCog, None] = None
    feedback: Union[FeedbackCog, None] = None
    review: Union[ReviewCog, None] = None

    def __init__(self, bot: Bot):
        super().__init__(None)
        print("Initializing MainCog")
        self.bot = bot

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

        # setup review
        self.review = ReviewCog(self.user)
        await self.bot.add_cog(self.review)

    # Feed commands

    @commands.group('feed',
                    help='manage job searches')
    async def feed(self, ctx):
        if await self._check_user(ctx):
            await ctx.send("User is not authenticated")
            return

        if ctx.invoked_subcommand is None:
            await ctx.send("No sub-command given. Use `!help feed` to learn about available commands.")

    @feed.command('add',
                  aliases=['a'],
                  help='add RSS URL to poll group')
    async def add_search(self, ctx, *args):
        await self.job_feed.searches.add_url(args[0])

    @feed.command('remove',
                  aliases=['rm'],
                  help='remove RSS URL from poll group')
    async def remove_search(self, ctx, *args):
        await ctx.send("This function has not been implemented yet")

    @feed.command('searches',
                  aliases=['s'],
                  help='list current searches (RSS URLs)')
    async def list_searches(self, ctx):
        await ctx.send(f"Current searches:\n{self.job_feed.searches.feed_urls}")

    @feed.command('enable',
                  aliases=['e'],
                  help='enable background loop to look for and notify about relevant jobs')
    async def enable_feed(self, _: commands.Context):
        await self.job_feed.enable_loop()

    @feed.command('disable',
                  aliases=['d'],
                  help='disable background loop to look for and notify about relevant jobs')
    async def disable_feed(self, _: commands.Context):
        await self.job_feed.disable_loop()

    @feed.command('status',
                  aliases=['st'],
                  help='return status of background loop')
    async def feed_status(self, ctx):
        await self.job_feed.status(ctx)

    @feed.command('recent',
                  aliases=['r'],
                  help='fetch and list recent jobs from db (in hours)')
    async def load_recent(self, ctx: commands.Context, hours: Optional[int] = 12):
        await ctx.send(f"Loading viable jobs from the last {hours} hours")
        self.job_feed.load_recent(hours)
        await self.job_feed.list_cache()

    @feed.command('list',
                  aliases=['l'],
                  help='list all relevant jobs stored in cache')
    async def list_feed(self, _: commands.Context, number: Optional[int] = None):
        if number:
            await self.job_feed.list_details(number)
        else:
            await self.job_feed.list_cache()

    @feed.command('clear',
                  aliases=['c'],
                  help='clear current cache of relevant jobs')
    async def clear_feed(self, ctx):
        await self.job_feed.clear_cache()

    # Feedback commands

    @commands.group('feedback',
                    help='manage and provide feedback for ambiguous jobs')
    async def feedback(self, ctx):
        if await self._check_user(ctx):
            await ctx.send("User is not authenticated")
            return

        if ctx.invoked_subcommand is None:
            await ctx.send("No sub-command given. Use `!help feed` to learn about available commands.")

    @feedback.command('process',
                      aliases=['p'],
                      help='begin to process feedback for jobs that could not be automatically evaluated')
    async def process_feedback(self, ctx):
        await self.feedback.begin()

    @feedback.command('quit',
                      aliases=['q'],
                      help='quit from processing feedback')
    async def quit_feedback(self, ctx):
        await self.feedback.exit_conversation()

    @feedback.command('enable',
                      aliases=['e'],
                      help='enable background loop for processing feedback')
    async def enable_feedback(self, ctx):
        await self.feedback.exit_conversation()

    @feedback.command('disable',
                      aliases=['d'],
                      help='disable background loop for processing feedback')
    async def disable_feedback(self, ctx):
        await self.feedback.exit_conversation()

    @feedback.command('status',
                      aliases=['s'],
                      help='return status of background feedback notification task')
    async def fetch_feedback(self, ctx):
        await self.feedback.status()

    @feedback.command('fetch',
                      aliases=['f'],
                      help='update local cache of ambiguous jobs that require feedback')
    async def feedback_status(self, ctx):
        await self.feedback.status()
