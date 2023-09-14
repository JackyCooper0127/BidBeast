import os
from supabase import Client, create_client

from FeedCog import Job


url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")


class StoreJobFunctor(object):
    """Singleton functor which stores job data on supabase"""
    client: Client

    def __init__(self):
        self.client = create_client(url, key)

    def _check_duplicate(self, job: Job):
        """ Checks if job is already stored

        :param job: job to be checked
        """
        identical = self.client.table('potential_jobs').select('title').eq('title', job.title).execute()
        try:
            if len(identical['data']) > 0:
                return True
        except KeyError:
            pass
        return False

    async def __call__(self, job: Job):
        """ Stores job data on supabase

        :param job: job to be stored
        """
        if self._check_duplicate(job):
            print('Duplicate job given')
            return

        self.client.table('potential_jobs').insert({
            'title': job.title,
            'description': job.description
        }).execute()
