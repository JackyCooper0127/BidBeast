from typing import Dict

import feedparser
from discord import User
from discord.ext import commands
from discord.ext.commands import Bot, Cog

from db import SUPABASE


class SessionCog(Cog):
    """ Encapsulates persistent user data """
    bot: Bot
    user: User
    searches: list[str]
    last_entries: Dict[str, list[feedparser.FeedParserDict]]

    def __init__(self, bot: Bot, user: User):
        self.bot = bot
        self.user = user
        self.searches = []
        self.last_entries = {}

        self._add_row()
        self._fetch_searches()

    def update_entry(self, search: str, entry: list[feedparser.FeedParserDict]):
        if search not in self.last_entries:
            self.last_entries[search] = []
        self.last_entries[search] = entry

    def _add_row(self):
        try:
            SUPABASE.table('bid_beast_users').insert({'id': self.user.id}).execute()
        except Exception:
            pass

    def _fetch_searches(self):
        response = SUPABASE.table('bid_beast_users').select('searches').eq('id', self.user.id).execute()
        searches = response.data[0]['searches']
        if not searches:
            return
        self.searches = searches
        print("User data fetched")

    def _add_search(self, search: str):
        if search in self.searches:
            return
        self.searches.append(search)

        print('updating searches')
        SUPABASE.table('bid_beast_users') \
            .update({'searches': self.searches}) \
            .eq('id', self.user.id) \
            .execute()

    def _remove_search(self, search: str):
        self.searches.remove(search)
        SUPABASE.table('bid_beast_users').delete().eq('id', self.user.id).eq('searches', search).execute()

    @commands.command('searches')
    async def list_searches(self, ctx):
        """List current searches"""
        await self.user.send(f'Current searches: {self.searches}')

    @commands.command('add')
    async def add_search_link(self, ctx, link: str):
        """Add link to local searches"""
        self._add_search(link)

        await self.user.send(f'Added {link} to local searches')
        await self.user.send(f'Current searches: {self.searches}')
