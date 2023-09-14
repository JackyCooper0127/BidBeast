import asyncio
from collections.abc import Callable
from typing import Union, Iterator, ClassVar
from html import unescape

import discord
import feedparser
from discord.ext.commands.bot import Bot
from discord.ext import commands, tasks
from markdownify import markdownify

from functors.StoreJobFunctor import StoreJobFunctor
from job import Job


class FeedCog(commands.Cog):
    bot: Bot
    searches: list[str]
    user: Union[discord.User, None]
    store: ClassVar[StoreJobFunctor] = StoreJobFunctor()
    last_entries: list[feedparser.FeedParserDict]

    def __init__(self, bot: Bot):
        print("Initializing FeedCog")
        self.bot = bot
        self.searches = []
        self.user = None
        self.last_entries = []

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
        for entry in self.last_entries:
            yield self._extract_job(entry)

    @commands.command('connect')
    async def connect(self, ctx):
        """Connect the bot to the channel"""
        if self.user == ctx.author:
            await ctx.send("You're already connected silly!")
            return
        self.user = ctx.author
        await self.user.send("Gotcha...")

    @commands.command('start', aliases=['start_feed'])
    async def start_feed(self, ctx):
        """Start the fetching RSS feed"""
        self.fetch_feed.start()
        await self.user.send("Started to fetch RSS feed")

    @commands.command('stop', aliases=['stop_feed'])
    async def stop_feed(self, ctx):
        """Stop the fetching RSS feed"""
        self.fetch_feed.stop()
        await self.user.send("Stopped fetching RSS feed")

    @commands.command('status')
    async def status(self, ctx):
        if self.fetch_feed.is_running():
            await self.user.send("Fetching RSS feed")
        else:
            await self.user.send("Not fetching RSS feed")

    @commands.command('add')
    async def add_search_link(self, ctx, link: str):
        """Add link to local searches"""
        self.searches.append(link)
        await self.user.send(f'Added {link} to local searches')
        await self.user.send(f'Current searches: {self.searches}')
        if not self.fetch_feed.is_running():
            await self.user.send("Use the `!start` command to start fetching RSS feed!")

    @commands.command('list')
    async def list_entries(self, ctx):
        """List current entries"""
        if not self.jobs:
            await ctx.send("No jobs")
            return
        for job in self.jobs:
            await ctx.send(f'{job.link}')

    @tasks.loop(seconds=60)
    async def fetch_feed(self):
        """Fetch RSS feed and send to Discord"""
        if not self.searches:
            self.fetch_feed.stop()
            await self.user.send("No searches. Stopped fetching RSS feed.")
            print("No searches")
            return
        for link in self.searches:
            feed = feedparser.parse(link)

            entries = feed['entries']
            if entries == self.last_entries:
                print("No new entries")
                return
            else:
                self.last_entries = entries

            routines = []
            for job in self.jobs:
                if self.store.check_duplicate(job):
                    continue
                routines.append(self._print_job(job))
                routines.append(self.store(job))

            await asyncio.gather(*routines)

    async def _print_job(self, job: Job):
        """ Print job to console

        :param job: job to be printed
        """
        msg = f'### Title:\n{job.title}\n{job.link}'
        await self.user.send(msg)

