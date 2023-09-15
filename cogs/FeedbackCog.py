import asyncio
from enum import Enum
from typing import Union, Dict
from uuid import UUID

from discord.ext.commands import Cog
from postgrest.types import CountMethod

from db import SUPABASE
from job import Job


class LikeState(Enum):
    NULL = -1
    DISLIKE = 0
    LIKE = 1


class FeedbackModel(object):
    uuid: UUID
    reasons: list[str]
    like: LikeState

    def __init__(self, uuid: UUID):
        self.uuid = uuid
        self.reasons = []
        self.like = LikeState.NULL

    def upload(self):
        SUPABASE.table('potential_jobs') \
            .update({
                'like': self.like.value,
                'reasons': self.reasons
            }) \
            .eq('id', self.uuid) \
            .execute()


class FeedbackState(Enum):
    NOTHING = 0
    WAITING = 1
    REASON = 2
    LIKE = 3


async def _get_yes_no(message) -> Union[bool, None]:
    msg = message['content'].lower()
    if msg in ['yes', 'y']:
        return True
    elif msg in ['no', 'n']:
        return False
    else:
        await message['content'].send("Invalid response. Please respond with 'yes' or 'no'")
        return


class FeedbackCog(Cog):
    # buffers to store feedback for single job
    feedback: Union[FeedbackModel, None]
    job: Union[Job, None]

    # cache of jobs that need feedback
    query_cache: Dict[UUID, Job]

    state: FeedbackState

    def __init__(self, ctx):
        self.ctx = ctx
        self.feedback = None
        self.query_cache = {}

        # populate `query_cache` with jobs from supabase
        self._fetch_jobs()

        self.state = FeedbackState.NOTHING

    async def cog_load(self):
        await self.ctx.send("\n***\n"
                            "So you ready to provide feedback?...\n"
                            "Use `fetch` to fetch jobs that need feedback\n"
                            "Run `!feedback stop` if you have to leave feedback mode."
                            "\n***")
        await self.begin_conversation()

    def _fetch_jobs(self):
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
        self.feedback = FeedbackModel(uuid)
        self.job = job

    async def _extract_like(self, message):
        """ Parse like/dislike from message """
        msg = message['content'].lower()
        if msg in ['yes', 'y', 'like']:
            self.feedback.like = LikeState.LIKE
            return
        elif msg in ['no', 'n', 'dislike']:
            self.feedback.like = LikeState.DISLIKE
            return
        elif msg in ['skip', 'pass', 'next']:
            return

        await message['channel'].send("Invalid response. Please respond with 'yes', 'no', or 'skip'")

    async def _extract_reason(self, message):
        lines = message['content'].strip().split('\n')
        if not lines:
            await message['channel'].send("Invalid response. Please provide your comments on this job description.")
            return
        self.feedback.reasons = lines

    @Cog.listener()
    async def on_message(self, message):
        if message.author != self.ctx.author:
            return
        if self.state == FeedbackState.NOTHING:
            msg = message.content.lower()
            if msg == 'fetch':
                self._fetch_jobs()
                await message.channel.send(f"Fetched {len(self.query_cache)} jobs that require feedback.")
                await message.channel.send(f"Press any key to begin feedback.")
            else:
                await self.begin_conversation()
                self.state = FeedbackState.WAITING
        elif self.state == FeedbackState.WAITING:
            if _get_yes_no(message):
                await self.ctx.send("Great! Let's get started.")
                await self.ctx.send("First, would you bid on this job? (yes/no/skip)")
                self.state = FeedbackState.LIKE
        elif self.state == FeedbackState.LIKE:
            await self._extract_like(message)
            await self.ctx.send("Next, provide a few reasons for your decision.\nSeparate each reason with a new line.")
            self.state = FeedbackState.REASON
        elif self.state == FeedbackState.REASON:
            await self._extract_reason(message)
            # send feedback to supabase
            self.feedback.upload()
            await self.ctx.send("Feedback submitted. Thanks!")
            self.state = FeedbackState.NOTHING

    async def begin_conversation(self):
        """ Start conversation with user """
        if len(self.query_cache) > 0:
            self._load_job()

            await self.ctx.send(f"\n***\n{self.job.title}\n***\n")

            # TODO: split description into multiple messages
            await self.ctx.send(f"### Description"
                                "\n{self.job.description}\n"
                                "***")
            await self.ctx.send(f"Would you like to give feedback? (yes/no)\n")
        else:
            await self.ctx.send("So.. it turns out there are no jobs for you to provide feedback on...")
            await self.ctx.send("...so congrats...")
