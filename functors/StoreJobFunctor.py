import os
from collections.abc import Callable

from supabase import Client, create_client

from job import Job


url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")


class StoreJobFunctor(Callable[[Job], None]):
    """Singleton functor which stores job data on supabase"""
    client: Client

    def __init__(self):
        self.client = create_client(url, key)

    def check_duplicate(self, job: Job):
        """ Checks if job is already stored

        :param job: job to be checked
        """
        identical = self.client.table('potential_jobs').select('title').eq('title', job.title).execute()
        try:
            if len(identical.data) > 0:
                return True
        except KeyError:
            pass
        return False

    async def __call__(self, job: Job):
        """ Stores job data on supabase without checking for duplicates

        :param job: job to be stored
        """
        self.client.table('potential_jobs').insert({
            'title': job.title,
            'desc': job.description
        }).execute()
