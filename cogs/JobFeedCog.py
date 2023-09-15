import asyncio
from html import unescape
from typing import ClassVar, Union, Iterator

import discord
import feedparser
from discord.ext import tasks
from discord.ext.commands import Cog, Bot
from markdownify import markdownify

from cogs.SessionCog import SessionCog
from functors.StoreJobFunctor import StoreJobFunctor
from job import Job


class JobFeedCog(Cog):
    bot: Bot
    store: ClassVar[StoreJobFunctor] = StoreJobFunctor()
    session: Union[SessionCog, None]
    user: discord.User

    def __init__(self, bot: Bot, user: discord.User):
        self.user = user
        self.bot = bot
        self.session = SessionCog(bot, user)

    async def cog_load(self):
        await self.enable_loop()

    @staticmethod
    def _extract_job(entry: feedparser.FeedParserDict) -> Job:
        """ Prepare RSS entry

        :param entry: extracts title and summary from RSS entry

        :return: combined title and summary
        """
        title = entry['title'].replace('- Upwork', '')
        summary = markdownify(entry['summary_detail']['value'])
        summary = unescape(summary)

        return Job(title, summary, entry['link'])

    @property
    def jobs(self) -> Iterator[Job]:
        """ Process RSS entries

        :return: list of processed RSS entries
        """
        for entries in self.session.last_entries.values():
            for entry in entries:
                yield self._extract_job(entry)

    @tasks.loop(seconds=60 * 5)
    async def fetch_feed(self):
        """Fetch RSS feed and store in database"""
        for link in self.session.searches:
            feed = feedparser.parse(link)

            entries = feed['entries']
            try:
                if entries == self.session.last_entries[link]:
                    print("No new entries")
                    return
            except KeyError:
                self.session.update_entry(link, entries)

            routines = []
            for job in self.jobs:
                if self.store.check_duplicate(job):
                    continue
                routines.append(self.store(job))

            await asyncio.gather(*routines)

    async def list_entries(self, ctx):
        """List current entries"""
        if not self.jobs:
            await ctx.send("No jobs")
            return
        for job in self.jobs:
            await ctx.send(f'{job.link}')

    async def enable_loop(self):
        """Start the fetching RSS feed"""
        self.fetch_feed.start()
        await self.user.send("> Started to fetch RSS feed")

    async def disable_loop(self):
        """Stop the fetching RSS feed"""
        self.fetch_feed.stop()
        await self.user.send("> Stopped fetching RSS feed")

    async def status(self, ctx):
        if self.fetch_feed.is_running():
            await ctx.send("> Fetching RSS feed")
        else:
            await ctx.send("> Not fetching RSS feed")
