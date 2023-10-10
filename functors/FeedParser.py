from html import unescape
from typing import ClassVar

from markdownify import markdownify
from postgrest import SyncRequestBuilder
from postgrest.types import CountMethod

from db import SUPABASE
from helpers import retry_on_error
from models import Job


def _extract_job(entry: dict) -> Job:
    """ Prepare RSS entry

    :param entry: extracts title and summary from RSS entry

    :return: combined title and summary
    """
    title = entry['title'].replace('- Upwork', '')
    summary = markdownify(entry['summary_detail']['value'])
    summary = unescape(summary)

    return Job(title, summary, entry['link'])


class FeedParser(object):
    _table: ClassVar[SyncRequestBuilder] = SUPABASE.table('potential_jobs')

    @classmethod
    @retry_on_error()
    def __call__(cls, entries: list[dict]) -> list[Job]:
        """ Accept new `Job` objects from the raw RSS feed """
        jobs = [_extract_job(i) for i in entries]

        _titles = [i.title for i in jobs]
        _results = cls._table \
            .select('title', count=CountMethod.exact) \
            .in_('title', _titles) \
            .execute()
        duplicates_titles = [i['title'] for i in _results.data]

        incoming = []
        for job in jobs:
            if job.title not in duplicates_titles:
                incoming.append(job)
        return incoming
