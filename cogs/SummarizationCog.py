from asyncio import gather
from typing import ClassVar, NoReturn
from uuid import UUID

from discord.ext import tasks
from discord.ext.commands import Cog
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from sqlalchemy import null

from db import SUPABASE


def _summarize_chain() -> LLMChain:
    prompt = PromptTemplate.from_template("""
    You are a consultant for a freelance contractor. You have the ability to infer the tasks and skills required for a
    given job even if the description given by the client is ambiguous or does not use the correct terminology or skips
    over important parts. You also have insight into the type of relationship a potential client will have with a
    freelancer based on the job description they provide.
    
    Description:
    ```
    {description}
    ```
    
    Summarize the given the job description into a brief overview of the expected outcomes,
    the expectations of the prospective client, and skill requirements.
    
    The resulting summary should be 2 paragraphs or less.
    """)

    return LLMChain(llm=ChatOpenAI(temperature=.2, model_name="gpt-3.5-turbo"),
                    output_key='summary',
                    prompt=prompt, )


class SummarizationCog(Cog):
    """ Generates summaries for job descriptions.

    These summaries are used as context in the few-shot prompt when evaluating new jobs descriptions.
    """
    chain: ClassVar[LLMChain] = _summarize_chain()

    async def cog_load(self) -> None:
        # start loops
        self.loop.start()

    @tasks.loop(minutes=5)
    async def loop(self):
        await self.process_jobs()

    @classmethod
    async def process_jobs(cls):
        """ Summarize jobs in db that have not been summarized """
        results = SUPABASE.table('potential_jobs') \
            .select('id, desc') \
            .is_('summary', null()) \
            .execute() \
            .data

        if results:
            await cls._process(results)

    @classmethod
    async def _process(cls, descriptions: list[dict]):
        ids = []
        routines = []

        for job in descriptions:
            ids.append(job['id'])
            routines.append(cls.chain.arun({'description': job['desc']}))

        summaries = await gather(*routines)

        for uuid, summary in zip(ids, summaries):
            SUPABASE.table('potential_jobs') \
                .update({'summary': summary}) \
                .eq('id', uuid) \
                .execute()
