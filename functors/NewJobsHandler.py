from typing import ClassVar

from postgrest import SyncRequestBuilder

from db import SUPABASE
from models import Job


class NewJobsHandler(object):
    """ A dedicated handler class for new jobs.

    This class will handle storing new jobs in supabase and generating embeddings.
    """
    _table: ClassVar[SyncRequestBuilder] = SUPABASE.table('potential_jobs')

    @classmethod
    def _store_job(cls, jobs: list[Job]):
        """ Store job data in supabase """
        formatted = []
        for i in jobs:
            row = {
                'title': i.title,
                'desc': i.description,
                'link': i.link
            }
            formatted.append(row)
        cls._table.insert(formatted).execute()

    @classmethod
    def __call__(cls, jobs: list[Job]):
        cls._store_job(jobs)
        # TODO: generate embeddings
