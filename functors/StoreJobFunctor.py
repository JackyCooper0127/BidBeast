from collections.abc import Callable
from typing import ClassVar
from supabase import Client
from models import Job
from db import SUPABASE


class StoreJobFunctor(Callable[[Job], None]):
    """Singleton functor which stores job data on supabase"""
    client: ClassVar[Client] = SUPABASE

    @classmethod
    def check_duplicate(cls, job: Job):
        """ Checks if job is already stored

        :param job: job to be checked
        """
        identical = cls.client.table('potential_jobs').select('title').eq('title', job.title).execute()
        try:
            if len(identical.data) > 0:
                return True
        except KeyError:
            pass
        return False

    @classmethod
    async def __call__(cls, job: Job):
        """ Stores job data on supabase without checking for duplicates

        :param job: job to be stored
        """
        cls.client.table('potential_jobs').insert({
            'title': job.title,
            'desc': job.description,
            'link': job.link
        }).execute()
