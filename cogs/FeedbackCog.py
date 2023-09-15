from enum import Enum
from typing import Union, Dict
from uuid import UUID

import discord
from discord.ext import tasks
from discord.ext.commands import Cog
from postgrest.types import CountMethod

from cogs.models import Like, Feedback
from db import SUPABASE
from job import Job


class FeedbackState(Enum):
    NOTHING = 0
    WAITING = 1
    REASON = 2
    LIKE = 3


async def _get_yes_no(message: discord.Message) -> Union[bool, None]:
    msg = message.content.lower()
    if msg in ['yes', 'y']:
        return True
    elif msg in ['no', 'n']:
        return False
    else:
        await message.channel.send("Invalid response. Please respond with 'yes' or 'no'")
        return


class FeedbackCog(Cog):
    user: discord.User
    # buffers to store feedback for single job
    feedback: Union[Feedback, None]
    job: Union[Job, None]

    # cache of jobs that need feedback
    query_cache: Dict[UUID, Job]

    state: FeedbackState

    def __init__(self, user: discord.User):
        self.user = user
        self.feedback = None
        self.query_cache = {}

        self.state = FeedbackState.NOTHING

    @property
    def remaining(self):
        return len(self.query_cache)

    async def cog_load(self):
        self.fetch_jobs_loop.start()
        await self.user.send("> Started to fetch jobs that need feedback")

    def fetch_jobs(self):
        """ Fetch jobs from supabase that need feedback """
        results = SUPABASE.table("potential_jobs") \
            .select("id", "title", "desc", count=CountMethod.exact) \
            .eq('like', -1) \
            .execute()
        data = results.data
        if data:
            for job in data:
                self.query_cache[job['id']] = Job(job['title'], job['desc'], '')

    def _load_job(self):
        """ Load job from cache """
        uuid, job = self.query_cache.popitem()
        self.feedback = Feedback(uuid)
        self.job = job

    async def _extract_like(self, message):
        """ Parse like/dislike from message """
        msg = message.content.lower()
        if msg in ['yes', 'y', 'like']:
            self.feedback.like = Like.LIKE
            return
        elif msg in ['no', 'n', 'dislike']:
            self.feedback.like = Like.DISLIKE
            return
        elif msg in ['skip', 'pass', 'next']:
            return

        await self.user.send("Invalid response. Please respond with 'yes', 'no', or 'skip'")
        raise ValueError("Invalid response")

    async def _extract_reason(self, message):
        lines = message.content.strip().split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide your comments on this job description.")
            raise ValueError("Invalid response")
        self.feedback.reasons = lines

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        async def restart_feedback():
            self.feedback = None
            self.job = None
            self.state = FeedbackState.WAITING
            await self.on_message(message)

        if message.author != self.user:
            return
        if self.state == FeedbackState.NOTHING:
            return
        elif self.state == FeedbackState.WAITING:
            await self.user.send("Great! Let's get started.")
            await self.user.send("First, would you bid on this job? (yes/no/skip)")
            self.state = FeedbackState.LIKE
        elif self.state == FeedbackState.LIKE:
            try:
                await self._extract_like(message)
            except ValueError:
                await restart_feedback()
                return
            await self.user.send(
                "Next, provide a few reasons for your decision.\nSeparate each reason with a new line.")
            self.state = FeedbackState.REASON
        elif self.state == FeedbackState.REASON:
            try:
                await self._extract_reason(message)
            except ValueError:
                await restart_feedback()
                return

            # send feedback to supabase
            self.feedback.upload()
            await self.user.send("Feedback submitted. Thanks!\n")

            await self.begin_conversation()

    async def _announce_finished(self):
        await self.user.send("So.. it turns out there are no jobs for you to provide feedback on...\n"
                             "...so congrats...\n")
        await self.exit_conversation()

    async def begin_conversation(self):
        """ Start conversation with user """
        if not self.remaining:
            await self._announce_finished()
            return
        await self.disable_loop()

        self._load_job()

        await self.user.send("\n*# # #*\n"
                             "So you ready to provide feedback?...\n"
                             "Run `!feedback stop` if you have to leave feedback mode.")

        await self.user.send(f"\n*# # #*\n{self.job.title}\n*# # #*\n")

        # divide description into chunks of 2000 characters
        await self.user.send("### Description")
        for i in range(0, len(self.job.description), 2000):
            await self.user.send(f"\n{self.job.description[i:i + 2000]}")

        await self.user.send("\n*# # #*\n"
                             "Would you like to give feedback? (yes/no)\n")
        self.state = FeedbackState.WAITING

    async def exit_conversation(self):
        """ Exit conversation with user """
        await self.user.send("Exiting feedback mode...")
        await self.enable_loop()
        self.state = FeedbackState.NOTHING

    @tasks.loop(seconds=60 * 5)
    async def fetch_jobs_loop(self):
        self.fetch_jobs()
        if self.remaining:
            await self.user.send(f"Found {self.remaining} jobs that need feedback.\n"
                                 "Use `!feedback process` to begin processing.")
        else:
            return

    async def enable_loop(self):
        self.fetch_jobs_loop.start()
        await self.user.send("> Started feedback loop")

    async def disable_loop(self):
        self.fetch_jobs_loop.stop()
        await self.user.send("> Stopped feedback loop")

    async def status(self):
        if self.fetch_jobs_loop.is_running():
            await self.user.send("> Fetching jobs")
        else:
            await self.user.send("> Not fetching jobs")
