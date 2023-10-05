from typing import ClassVar, Union, Iterator

import discord
from discord.ext import tasks
from discord.ext.commands import Cog, Bot

from functors.FeedParser import FeedParser
from functors.NewJobsHandler import NewJobsHandler
from functors.SearchManager import SearchManager


class JobFeedCog(Cog):
    parser: ClassVar[FeedParser] = FeedParser()
    searches: Union[SearchManager, None]
    handler: ClassVar[NewJobsHandler] = NewJobsHandler()
    user: discord.User

    def __init__(self, user: discord.User):
        self.user = user
        self.searches = SearchManager(user)

    async def cog_load(self):
        await self.enable_loop()

    @tasks.loop(seconds=60 * 5)
    async def fetch_feed(self):
        """ Fetch RSS feed and process new jobs """
        try:
            assert self.searches is not None
        except AssertionError:
            raise ValueError("`JobFeedCog` was not properly instantiated. `searches` is `None`")

        raw_feed = self.searches()
        new_jobs = self.parser(raw_feed)
        self.handler(new_jobs)

    async def enable_loop(self):
        """Start the fetching RSS feed"""
        self.fetch_feed.start()
        await self.user.send("> Started to fetch RSS feeds")

    async def disable_loop(self):
        """Stop the fetching RSS feed"""
        self.fetch_feed.stop()
        await self.user.send("> Stopped fetching RSS feed")

    async def status(self, ctx):
        if self.fetch_feed.is_running():
            await ctx.send("> Fetching RSS feed")
        else:
            await ctx.send("> Not fetching RSS feed")
