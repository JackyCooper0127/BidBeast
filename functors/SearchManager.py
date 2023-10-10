from typing import Iterator

import feedparser
from discord import User

from db import SUPABASE
from helpers import retry_on_error


class SearchManager(object):
    """ This functor should replace SessionCog and manage feed URLs for a given user.

    Its API exposes methods to add and remove searches to be called by bot commands.

    The `__call__()` method fetches and returns the raw job feed and is an alias for `fetch_feed()`.
    """
    feed_urls: list[str] = []
    user: User

    def __init__(self, user: User):
        self.user = user

        self._add_user()
        self._get_feed_urls()

    def _get_feed_urls(self):
        """ Populate `feed_urls` for current user """
        response = SUPABASE.table('bid_beast_users').select('searches').eq('id', self.user.id).execute()
        feed_urls = response.data[0]['searches']
        if not feed_urls:
            return
        self.feed_urls = feed_urls
        print("User data fetched")

    def _add_user(self):
        """ Add user row to user table.

        If a row already exists for current user, no change is made.
        """
        SUPABASE.table('bid_beast_users').upsert({'id': self.user.id}).execute()

    def remove_url(self, search: str):
        """ Remove a url from user's feed urls """
        self._get_feed_urls()       # ensure `feed_urls` is updated
        self.feed_urls.remove(search)
        SUPABASE.table('bid_beast_users').update({'searches': self.feed_urls}).eq('id', self.user.id).execute()

    def add_url(self, url: str):
        """ Add feed url """
        if url in self.feed_urls:
            return
        self.feed_urls.append(url)

        print('updating searches')
        SUPABASE.table('bid_beast_users') \
            .update({'searches': self.feed_urls}) \
            .eq('id', self.user.id) \
            .execute()

    @retry_on_error()
    def __call__(self) -> list[dict]:
        """ Fetch and parse all RSS feeds """
        entries: list[dict] = []
        for url in self.feed_urls:
            feed = feedparser.parse(url)
            for entry in feed['entries']:
                entries.append(entry)
        return entries
