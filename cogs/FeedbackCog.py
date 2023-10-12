from abc import ABC, abstractmethod
from enum import Enum
from typing import Union, Dict
from uuid import UUID

import discord
from discord.ext import tasks
from discord.ext.commands import Cog
from postgrest.types import CountMethod

from helpers import retry_on_error
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

    def next(self) -> 'FeedbackState':
        if self == FeedbackState.NOTHING:
            return self.WAITING
        elif self == FeedbackState.WAITING:
            return self.PROS
        elif self == FeedbackState.PROS:
            return self.CONS
        else:
            return self.NOTHING


class FeedbackInputHandler(ABC):
    """ Abstract strategy for handling input """
    user: discord.User
    feedback: FeedbackModel

    def __init__(self, user: discord.User, feedback: FeedbackModel):
        self.user = user
        self.feedback = feedback

    @abstractmethod
    async def prompt_text(self, job: Job):
        pass

    @abstractmethod
    async def parse_msg(self, msg):
        pass

    @abstractmethod
    def next(self) -> Union['FeedbackInputHandler', None]:
        pass


class ViabilityHandler(FeedbackInputHandler):

    async def prompt_text(self, job: Job):
        msg = ("## Viability\n"
               "Would you bid on this job? (yes/no)")
        return await self.user.send(msg)

    async def parse_msg(self, message):
        msg = message.content.lower()
        if msg in ['yes', 'y', 'like']:
            self.feedback.viability = Viability.LIKE
        elif msg in ['no', 'n', 'dislike']:
            self.feedback.viability = Viability.DISLIKE
        else:
            await self.user.send("Invalid response. Please respond with 'yes' or 'no'")
            raise ValueError("Invalid response")

    def next(self) -> 'FeedbackInputHandler':
        return ProsHandler(self.user, self.feedback)


class ProsHandler(FeedbackInputHandler):
    async def prompt_text(self, job: Job):
        msg = ("## Pros\n"
               "What do you like about this job?\n"
               "Separate each comment with a new line.")
        await self.user.send(msg)

    async def parse_msg(self, message):
        stripped = message.content.strip()
        if stripped == 'skip':
            return
        lines = stripped.split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide positive aspects about this job description.")
            raise ValueError("Invalid response")
        self.feedback.pros = lines

    def next(self) -> 'FeedbackInputHandler':
        return ConsHandler(self.user, self.feedback)


class ConsHandler(FeedbackInputHandler):
    async def prompt_text(self, job: Job):
        msg = ("## Cons\n"
               "What do you *not* like about this job?\n"
               "Separate each comment with a new line.")
        await self.user.send(msg)

    async def parse_msg(self, message):
        stripped = message.content.strip()
        if stripped == 'skip':
            return
        lines = stripped.split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide the negative aspects about this job description.")
            raise ValueError("Invalid response")
        self.feedback.cons = lines

    def next(self) -> None:
        return None


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
    uuid: Union[UUID, None]
    job: Union[Job, None]

    # cache of jobs that need feedback
    query_cache: Dict[UUID, Job]

    handler: Union[FeedbackInputHandler, None] = None

    def __init__(self, user: discord.User):
        self.user = user
        self.feedback = FeedbackModel()
        self.uuid = None
        self.query_cache = {}

    @property
    def remaining(self):
        return len(self.query_cache)

    async def cog_load(self):
        self.fetch_jobs_loop.start()
        await self.user.send("> Started to fetch jobs that need feedback")

    @retry_on_error()
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

    def _unload_job(self):
        """ Restore buffer to cache.

        This is for when feedback mode is exited prematurely.
        """
        if self.job and self.uuid:
            self.query_cache[self.uuid] = self.job

    def _clear_buffer(self):
        print("Bad response. Restarted feedback")
        self.feedback = FeedbackModel()
        self.job = None
        self.uuid = None

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author != self.user or self.handler is None:
            return
        elif message.content[0] == '!':
            return

        try:
            await self.handler.parse_msg(message)
        except ValueError:
            return
        self.handler = self.handler.next()

        if self.handler:
            await self.handler.prompt_text(self.job)
        else:
            # upload feedback to db
            self.feedback.upload(self.uuid)
            await self.user.send("Feedback submitted. Thanks!\n")
            self._clear_buffer()

            if self.remaining:
                await self._first_message()
            else:
                await self._announce_finished()

    async def _announce_finished(self):
        await self.user.send("So.. it turns out there are no jobs for you to provide feedback on...\n"
                             "...so congrats...\n")
        await self.exit_conversation()

    async def begin(self):
        """ Start conversation with user """
        if not self.remaining:
            await self._announce_finished()
            return

        await self.disable_loop()

        await self.user.send("Let's get started!...\n"
                             "Run `!feedback exit` if you have to leave feedback mode.")
        await self._first_message()

    async def _first_message(self):
        self._load_job()

        for msg in self.job.detailed_repr():
            await self.user.send(msg)

        self.handler = ViabilityHandler(self.user, self.feedback)
        await self.handler.prompt_text(self.job)

    async def exit_conversation(self):
        """ Exit conversation with user """
        self._unload_job()
        await self.user.send("Exiting feedback mode...")
        await self.enable_loop()

    @tasks.loop(hours=1)
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
