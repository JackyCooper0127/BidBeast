from typing import Iterator

import feedparser
from discord import User

from db import SUPABASE


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

    def _get_feed_urls(self):
        """ Fetch feed urls for current user """
        response = SUPABASE.table('bid_beast_users').select('searches').eq('id', self.user.id).execute()
        searches = response.data[0]['searches']
        if not searches:
            return
        self.searches = searches
        print("User data fetched")

    def _add_user(self):
        """ Add user row to user table """
        SUPABASE.table('bid_beast_users').upsert({'id': self.user.id}).execute()

    def remove_search(self, search: str):

        self.searches.remove(search)
        SUPABASE.table('bid_beast_users').delete().eq('id', self.user.id).eq('searches', search).execute()

    def add_search(self, link: str):
        """ Add feed link """
        if link in self.searches:
            return
        self.searches.append(link)

        print('updating searches')
        SUPABASE.table('bid_beast_users') \
            .update({'searches': self.searches}) \
            .eq('id', self.user.id) \
            .execute()

    def __call__(self) -> Iterator[feedparser.FeedParserDict]:
        """ Fetch and parse all RSS feeds """
        for url in self.searches:
            feed = feedparser.parse(url)
            yield feed['entries']
