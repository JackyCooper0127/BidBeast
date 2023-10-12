from enum import IntEnum
from typing import Union, List, Optional, Iterator
from uuid import UUID, uuid4

from langchain.pydantic_v1 import BaseModel, Field

from db import SUPABASE


class Viability(IntEnum):
    NULL = -1
    DISLIKE = 0
    LIKE = 1


class FeedbackModel(BaseModel):
    pros: List[str] = Field(description="appealing aspects of this job", default=[])
    cons: List[str] = Field(description="unappealing aspects of this job", default=[])
    viability: Viability = Field(description="final decision to bid or not", default=Viability.NULL)

    def upload(self, uuid: UUID):
        SUPABASE.table('potential_jobs') \
            .update({'viability': self.viability.value,
                     'pros': self.pros,
                     'cons': self.cons,
                     'reviewed': True
                     }) \
            .eq('id', uuid) \
            .execute()


class Job(object):
    """ Job object to store title and description """
    id: UUID
    title: str
    description: str
    link: str
    summary: str = ''
    feedback: Union[FeedbackModel, None] = None

    def __init__(self, title: str, description: str, link: str):
        self.id = uuid4()
        self.title = title
        self.description = description
        self.link = link

    def __repr__(self):
        return self.title

    def summary_repr(self, index: Optional[int] = None) -> str:
        prefix = '##'
        if index is not None:
            prefix += f" {index+1}."
        return f"{prefix} {self.title}\n{self.summary}\n\n{self.link}"

    def detailed_repr(self) -> Iterator[str]:
        yield f"\n\n# {self.title}\n"

        # divide description into chunks of 2000 characters
        chunk_len = 2000
        for i in range(0, len(self.description), chunk_len):
            yield f"\n{self.description[i:i + chunk_len]}"
