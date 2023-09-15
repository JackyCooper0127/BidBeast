import asyncio
from typing import Union, Iterator, ClassVar, Optional
from html import unescape

import discord
import feedparser
from discord.ext.commands.bot import Bot
from discord.ext import commands, tasks
from markdownify import markdownify

from cogs.FeedbackCog import FeedbackCog
from cogs.SessionCog import SessionCog
from functors.StoreJobFunctor import StoreJobFunctor
from job import Job


class FeedCog(commands.Cog):
    bot: Bot
    user: Union[discord.User, None]
    store: ClassVar[StoreJobFunctor] = StoreJobFunctor()
    session: Union[SessionCog, None]
    feedback: Union[FeedbackCog, None]

    def __init__(self, bot: Bot):
        print("Initializing FeedCog")
        self.bot = bot
        self.user = None
        self.session = None
        self.feedback = None

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
        for entries in self.last_entries.values():
            for entry in entries:
                yield self._extract_job(entry)

    @property
    def searches(self):
        return self.session.searches

    @property
    def last_entries(self):
        return self.session.last_entries

    @commands.command('connect')
    async def connect(self, ctx):
        """Connect the bot to the channel"""
        if self.user == ctx.author:
            await ctx.send("You're already connected silly!")
            return
        self.user = ctx.author
        self.session = SessionCog(self.bot, ctx.author)
        await self.bot.add_cog(self.session)
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

    @commands.command('list')
    async def list_entries(self, ctx):
        """List current entries"""
        if not self.jobs:
            await ctx.send("No jobs")
            return
        for job in self.jobs:
            await ctx.send(f'{job.link}')

    @commands.command('feedback')
    async def feedback(self, ctx, action: Optional[str]):
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
            await ctx.send("Invalid action. Please use 'start' or 'stop'")

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
            try:
                if entries == self.last_entries[link]:
                    print("No new entries")
                    return
            except KeyError:
                self.session.update_entry(link, entries)

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
        await self.user.send(job.link)
