from enum import Enum
from uuid import UUID

from db import SUPABASE


class Like(Enum):
    NULL = -1
    DISLIKE = 0
    LIKE = 1


class Feedback(object):
    uuid: UUID
    reasons: list[str]
    like: Like

    def __init__(self, uuid: UUID):
        self.uuid = uuid
        self.reasons = []
        self.like = Like.NULL

    def upload(self):
        SUPABASE.table('potential_jobs') \
            .update({'like': self.like.value,
                     'reasons': self.reasons
                     }) \
            .eq('id', self.uuid) \
            .execute()
