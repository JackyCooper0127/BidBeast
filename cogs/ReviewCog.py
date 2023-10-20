from abc import ABC, abstractmethod
from typing import Union, Dict, Callable
from uuid import UUID

from discord import User, Message
from discord.ext import tasks
from discord.ext.commands import Cog, Context, group

from cogs.BaseAuthenticatedCog import BaseAuthenticatedCog
from handlers import get_yes_no
from helpers import retry_on_error
from models import FeedbackModel, Job, Viability


class ReviewInputHandler(ABC):
    """ Abstract strategy for handling input """
    user: User
    feedback: FeedbackModel

    def __init__(self, user: User, feedback: FeedbackModel):
        self.user = user
        self.feedback = feedback

    @abstractmethod
    async def prompt_text(self):
        pass

    @abstractmethod
    async def parse_msg(self, msg):
        pass

    @abstractmethod
    def next(self) -> Union['ReviewInputHandler', None]:
        pass


class ViabilityHandler(ReviewInputHandler):
    async def prompt_text(self):
        msg = ("## Viability\n\n"
               f'### Automated Value:\n{self.feedback.viability.text}\n\n'
               "Would you bid on this job? (yes/no)")
        await self.user.send(msg)

    async def parse_msg(self, message):
        like = await get_yes_no(message)
        if like is True:
            self.feedback.viability = Viability.LIKE
        elif like is False:
            self.feedback.viability = Viability.DISLIKE

    def next(self) -> 'ReviewInputHandler':
        return ProsHandler(self.user, self.feedback)


class ProsHandler(ReviewInputHandler):
    async def prompt_text(self):
        pros = '\n'.join([f"- {i}" for i in self.feedback.pros])
        msg = ("## Pros\n"
               "What do you like about this job?\n")
        if pros:
            msg += (f"### Generated Values:\n{pros}\n"
                    "Separate each comment with a new line.\n"
                    "Enter 'skip' if you're satisfied with the generated output above.\n"
                    "Enter 'none' if to submit no comments.")
        else:
            msg += ("Separate each comment with a new line.\n"
                    "Enter 'skip' or 'none' if there are no comments you'd like to add.")
        await self.user.send(msg)

    async def parse_msg(self, message):
        stripped = message.content.strip()
        lower = stripped.lower()
        if lower == 'skip':
            return
        elif lower == 'none':
            self.feedback.pros = []
            return
        lines = stripped.split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide positive aspects about this job description.")
            raise ValueError("Invalid response")
        self.feedback.pros = lines

    def next(self) -> 'ReviewInputHandler':
        return ConsHandler(self.user, self.feedback)


class ConsHandler(ReviewInputHandler):
    async def prompt_text(self):
        cons = '\n'.join([f"- {i}" for i in self.feedback.cons])
        msg = ("## Cons\n"
               "What do you *not* like about this job?\n")
        if cons:
            msg += (f"### Generated Values:\n{cons}\n"
                    "Separate each comment with a new line.\n"
                    "Enter 'skip' if you're satisfied with the generated output above.\n"
                    "Enter 'none' if to submit no comments.")
        else:
            msg += ("Separate each comment with a new line.\n"
                    "Enter 'skip' or 'none' if there are no comments you'd like to add.")
        await self.user.send(msg)

    async def parse_msg(self, message):
        stripped = message.content.strip()
        lower = stripped.lower()
        if lower == 'skip':
            return
        elif lower == 'none':
            self.feedback.cons = []
            return
        lines = stripped.split('\n')
        if not lines:
            await self.user.send("Invalid response. Please provide the negative aspects about this job description.")
            raise ValueError("Invalid response")
        self.feedback.cons = lines

    def next(self) -> None:
        return None


class ReviewCog(BaseAuthenticatedCog):
    user: User
    # buffers to store feedback for single job
    feedback: FeedbackModel
    uuid: Union[UUID, None]
    job: Union[Job, None]
    _job_fetcher: Callable[[], list[Job]] = Job.fetch_unreviewed

    # cache of jobs that need feedback
    query_cache: Dict[UUID, Job]

    handler: Union[ReviewInputHandler, None] = None

    def __init__(self, user: User):
        super().__init__(user)
        self.user = user
        self.feedback = FeedbackModel()
        self.uuid = None
        self.query_cache = {}

    @property
    def remaining(self):
        return len(self.query_cache)

    async def cog_load(self):
        self.fetch_jobs_loop.start()
        await self.user.send("> Started to fetch jobs that need review")

    @retry_on_error()
    def fetch_jobs(self):
        """ Fetch jobs from supabase that need feedback """
        for job in self._job_fetcher():
            uuid = job.id
            if uuid != self.uuid:
                self.query_cache[uuid] = job

    def _load_job(self):
        """ Load job from cache """
        uuid, job = self.query_cache.popitem()
        self.uuid = uuid
        self.feedback = job.feedback
        self.job = job

    def _unload_job(self):
        """ Restore buffer to cache.

        This is for when feedback mode is exited prematurely.
        """
        if self.job and self.uuid:
            self.query_cache[self.uuid] = self.job

    @Cog.listener()
    async def on_message(self, message: Message):
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
            await self.handler.prompt_text()
        else:
            # upload feedback to db
            self.feedback.upload(self.uuid)
            await self.user.send("Feedback submitted. Thanks!\n")

            if self.remaining:
                await self._first_message()
            else:
                await self._announce_finished()

    async def _announce_finished(self):
        await self.user.send("So.. it turns out there are no jobs for you to provide feedback on...\n"
                             "...so congrats...\n")
        await self.exit_conversation()

    async def _first_message(self):
        self._load_job()

        for msg in self.job.detailed_repr():
            await self.user.send(msg)

        self.handler = ViabilityHandler(self.user, self.feedback)
        await self.handler.prompt_text()

    async def exit_conversation(self):
        """ Exit conversation with user """
        self.handler = None
        self._unload_job()
        await self.user.send("Exiting review mode...")
        await self._enable_loop()

    @tasks.loop(hours=1)
    async def fetch_jobs_loop(self):
        self.fetch_jobs()

    @group('review',
           aliases=['r'],
           help='review, fix and update generated feedback by providing comments')
    async def review(self, ctx: Context):
        if await self._check_user(ctx):
            await ctx.send("User is not authenticated")
            return

        if ctx.invoked_subcommand is None:
            await ctx.send("No sub-command given. Use `!help review` to see available commands.")

    @review.command('process',
                    aliases=['p'],
                    help='begin begin to review, fix and update automatically generated feedback')
    async def process(self, _: Context):
        self.fetch_jobs()
        if not self.remaining:
            await self._announce_finished()
            return

        await self._disable_loop()

        await self.user.send("Let's get started!\n"
                             "Run `!review exit` to leave review mode")
        await self._first_message()

    @review.command('exit',
                    aliases=['quit', 'x', 'q'],
                    help='cancel current input and exit review mode')
    async def exit(self, _: Context):
        await self.exit_conversation()

    @review.command('enable',
                    aliases=['e'],
                    help='enable background loop for processing reviews')
    async def enable_loop(self, _: Context):
        await self._enable_loop()

    async def _enable_loop(self):
        self.fetch_jobs_loop.start()
        await self.user.send("> Started review loop")

    @review.command('disable',
                    aliases=['d'],
                    help='disable background loop for processing reviews')
    async def disable_loop(self, _: Context):
        await self._disable_loop()

    async def _disable_loop(self):
        self.fetch_jobs_loop.cancel()
        self.fetch_jobs_loop.stop()
        await self.user.send("> Stopped review loop")

    @review.command('status',
                    aliases=['s'],
                    help='return status of background notification task for jobs requiring review')
    async def status(self, _: Context):
        if self.fetch_jobs_loop.is_running():
            await self.user.send("> Fetching jobs that require review")
        else:
            await self.user.send("> Not fetching jobs that require review")

    @review.command('fetch',
                    aliases=['f'],
                    help='update local cache of requiring review')
    async def fetch(self, _: Context):
        self.fetch_jobs()
        if self.remaining:
            await self.user.send(f"Found {self.remaining} jobs that need review.\n"
                                 "Use `!review process` to begin processing.")
        else:
            return
