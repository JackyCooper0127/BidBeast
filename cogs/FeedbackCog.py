from enum import Enum
from typing import Union, Dict
from uuid import UUID

import discord
from discord.ext import tasks
from discord.ext.commands import Cog
from postgrest.types import CountMethod

from models import Viability, Job, FeedbackModel
from db import SUPABASE


class AspectType(Enum):
    PROS = 'PROS'
    CONS = 'CONS'


class FeedbackState(Enum):
    NOTHING = 0
    WAITING = 1
    LIKE = 2
    PROS = 3
    CONS = 4


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
    feedback: FeedbackModel
    uuid: Union[str, None]
    job: Union[Job, None]

    # cache of jobs that need feedback
    query_cache: Dict[UUID, Job]

    state: FeedbackState

    def __init__(self, user: discord.User):
        self.user = user
        self.feedback = FeedbackModel()
        self.uuid = None
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
            .eq('viability', -1) \
            .execute()
        data = results.data
        if data:
            for job in data:
                uuid = job['id']
                if uuid != self.uuid:
                    self.query_cache[uuid] = Job(job['title'], job['desc'], '')

    def _load_job(self):
        """ Load job from cache """
        uuid, job = self.query_cache.popitem()
        self.uuid = uuid
        self.feedback = FeedbackModel()
        self.job = job

    async def _extract_viability(self, message):
        """ Parse like/dislike from message """
        msg = message.content.lower()
        if msg in ['yes', 'y', 'like']:
            self.feedback.viability = Viability.LIKE
            return
        elif msg in ['no', 'n', 'dislike']:
            self.feedback.viability = Viability.DISLIKE
            return
        elif msg in ['skip', 'pass', 'next']:
            return

        await self.user.send("Invalid response. Please respond with 'yes', 'no', or 'skip'")
        raise ValueError("Invalid response")

    async def _extract_reason(self, message, aspect: AspectType):
        stripped = message.content.strip()
        if stripped == 'skip':
            return
        lines = stripped.split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide your comments on this job description.")
            raise ValueError("Invalid response")
        if aspect == AspectType.PROS:
            self.feedback.pros = lines
        if aspect == AspectType.CONS:
            self.feedback.cons = lines

    async def _restart_buffer(self):
        print("Bad response. Restarted feedback")
        self.feedback = FeedbackModel()
        self.job = None
        self.uuid = None
        self.state = FeedbackState.WAITING

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author != self.user:
            return
        if self.state == FeedbackState.NOTHING:
            return
        elif self.state == FeedbackState.LIKE:
            await self._handle_viability(message)
        elif self.state == FeedbackState.PROS:
            await self._handle_pros(message)
        elif self.state == FeedbackState.CONS:
            await self._handle_cons(message)
            await self.begin_conversation()

    async def _handle_viability(self, message: discord.Message):
        try:
            await self._extract_viability(message)
        except ValueError:
            await self._restart_buffer()
            return

        await self.user.send(
            "Next, provide any appealing aspects of this decision.\nSeparate each reason with a new line.")

        self.state = FeedbackState.PROS

    async def _handle_pros(self, message: discord.Message):
        try:
            await self._extract_reason(message, AspectType.PROS)
        except ValueError:
            await self._restart_buffer()
            return

        await self.user.send(
            "Next, provide any *CONS* or unappealing aspects of this decision.\n"
            "Separate each reason with a new line.")

        self.state = FeedbackState.CONS

    async def _handle_cons(self, message: discord.Message):
        try:
            await self._extract_reason(message, AspectType.CONS)
        except ValueError:
            await self._restart_buffer()
            return

        # send feedback to supabase
        self.feedback.upload(self.uuid)
        await self.user.send("Feedback submitted. Thanks!\n")

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

        await self.user.send(f"\n\n## {self.job.title}\n")

        # divide description into chunks of 2000 characters
        for i in range(0, len(self.job.description), 2000):
            await self.user.send(f"\n{self.job.description[i:i + 2000]}")

        await self.user.send("Great! Let's get started.")
        await self.user.send("First, would you bid on this job? (yes/no/skip)")
        self.state = FeedbackState.LIKE

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
