import asyncio
from typing import ClassVar

from postgrest import SyncRequestBuilder

from db import SUPABASE
from functors.EmbeddingManager import EmbeddingManager
from functors.EvaluationFunctor import EvaluationFunctor
from functors.Summarizer import Summarizer
from models import Job


class NewJobsHandler(object):
    """ A dedicated handler class for new jobs.

    This class will handle storing new jobs in supabase and generating embeddings.
    """
    _table: ClassVar[SyncRequestBuilder] = SUPABASE.table('potential_jobs')
    _summarizer: ClassVar[Summarizer] = Summarizer()
    _evaluator: ClassVar[EvaluationFunctor] = EvaluationFunctor()
    _manager: ClassVar[EmbeddingManager] = EmbeddingManager()

    @classmethod
    def _store_job(cls, jobs: list[Job]):
        """ Store job data in supabase """
        formatted = []
        for i in jobs:
            row = {
                'id': str(i.id),
                'title': i.title,
                'desc': i.description,
                'link': i.link,
                'summary': i.summary
            }
            if i.feedback:
                fb = i.feedback
                row['viability'] = fb.viability.value
                row['pros'] = fb.pros
                row['cons'] = fb.cons
            formatted.append(row)
        cls._table.insert(formatted).execute()

    @classmethod
    async def _evaluate(cls, jobs: list[Job]):
        """ Generate feedback for given list of jobs.

        `FeedbackModel` is returned by `EvaluationFunctor.__call__()` then added to `Job`.
        """
        print(f"Evaluating {len(jobs)} new jobs...")
        coroutines = [cls._evaluator(i.description) for i in jobs]
        results = await asyncio.gather(*coroutines)
        for job, fb in zip(jobs, results):
            job.feedback = fb
        print("Finished evaluating jobs")

    @classmethod
    async def __call__(cls, jobs: list[Job]):
        if jobs:
            print(f"Found {len(jobs)} new jobs")
            coroutines = [
                cls._summarizer(jobs),
                cls._evaluate(jobs),
            ]
            # TODO: notify of valid jobs

            await asyncio.gather(*coroutines)

            await cls._manager(jobs)  # generate embeddings after evaluating

            cls._store_job(jobs)
        else:
            print("No new jobs...")
