from typing import Union

import discord
import feedparser
from discord.ext.commands.bot import Bot
from discord.ext import commands, tasks
from markdownify import markdownify


class Job(object):
    """Job object to store title and description"""
    title: str
    description: str

    def __init__(self, title: str, description: str):
        self.title = title
        self.description = description


class FeedCog(commands.Cog):
    bot: Bot
    searches: list[str]
    user: Union[discord.User, None]

    def __init__(self, bot: Bot):
        print("Initializing FeedCog")
        self.bot = bot
        self.searches = []
        self.user = None

    @staticmethod
    def extract_job(entry: feedparser.FeedParserDict) -> Job:
        """ Prepare RSS entry

        :param entry: extracts title and summary from RSS entry

        :return: combined title and summary
        """
        title = entry['title'].replace('\n - Upwork', '')
        summary = markdownify(entry['summary_detail']['value'])

        return Job(title, summary)

    @commands.command('connect')
    async def connect(self, ctx):
        """Connect the bot to the channel"""
        if self.user is not None:
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

    @tasks.loop(seconds=60)
    async def fetch_feed(self):
        """Fetch RSS feed and send to Discord"""
        print("Task is running")
        if not self.searches:
            self.fetch_feed.stop()
            await self.user.send("No searches. Stopped fetching RSS feed.")
            print("No searches")
            return
        for link in self.searches:
            feed = feedparser.parse(link)

            for entry in feed['entries']:
                job = self.extract_job(entry)
                await self.user.send('# Title')
                await self.user.send(job.title)
                await self.user.send('\n')
                await self.user.send('# Description')
                await self.user.send(job.description)
