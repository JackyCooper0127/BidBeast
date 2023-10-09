from typing import ClassVar

from postgrest import SyncRequestBuilder

from db import SUPABASE
from functors.Summarizer import Summarizer
from models import Job


class NewJobsHandler(object):
    """ A dedicated handler class for new jobs.

    This class will handle storing new jobs in supabase and generating embeddings.
    """
    _table: ClassVar[SyncRequestBuilder] = SUPABASE.table('potential_jobs')
    _summarizer: ClassVar[Summarizer] = Summarizer()

    @classmethod
    def _store_job(cls, jobs: list[Job]):
        """ Store job data in supabase """
        formatted = []
        for i in jobs:
            row = {
                'title': i.title,
                'desc': i.description,
                'link': i.link,
                'summary': i.summary
            }
            formatted.append(row)
        cls._table.insert(formatted).execute()

    @classmethod
    async def __call__(cls, jobs: list[Job]):
        # generate description summary
        await cls._summarizer(jobs)

        cls._store_job(jobs)
        # TODO: generate embeddings
