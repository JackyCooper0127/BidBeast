from enum import IntEnum
from typing import Union, List
from uuid import UUID
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
                     'cons': self.cons
                     }) \
            .eq('id', uuid) \
            .execute()


class Feedback(object):
    uuid: UUID
    reasons: list[str]
    like: Viability

    def __init__(self, uuid: UUID, reasons: list[str] = None, like: Viability = Viability.NULL):
        self.uuid = uuid
        self.reasons = reasons
        self.like = like

    def upload(self):
        SUPABASE.table('potential_jobs') \
            .update({'like': self.like.value,
                     'reasons': self.reasons
                     }) \
            .eq('id', self.uuid) \
            .execute()


class Job(object):
    """Job object to store title and description"""
    title: str
    description: str
    link: str

    def __init__(self, title: str, description: str, link: str):
        self.title = title
        self.description = description
        self.link = link

    def __repr__(self):
        return self.title


class ExplanationModel(object):
    """
    Uses LLM to expand explanation on why job will not be bid.

    This data will be used to detect if other jobs should be bid or not.
    """
    uuid: UUID
    job: Union[Job, None]
    feedback: Union[Feedback, None]
    explanation: str

    def __init__(self, uuid):
        self.uuid = uuid
        self.job = None
        self.feedback = None

    def add_job(self, *args):
        """ Builder function that adds job to

        :param args:
        :return:
        """
        self.job = Job(*args)

    def add_feedback(self, *args):
        self.feedback = Feedback(*args)

    def upload(self):
        SUPABASE.table('potential_jobs') \
            .update({'explanation': self.explanation}) \
            .eq('id', self.uuid) \
            .execute()
