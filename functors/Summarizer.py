from asyncio import gather
from typing import ClassVar
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI

from db import SUPABASE
from models import Job


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


class Summarizer:
    """ Generates summaries for job descriptions.

    These summaries are used as context in the few-shot prompt when evaluating new jobs descriptions.
    """
    chain: ClassVar[LLMChain] = _summarize_chain()

    @classmethod
    async def _process(cls, jobs: list[Job]):
        routines = []

        for job in jobs:
            routines.append(cls.chain.arun({'description': job.description}))

        summaries = await gather(*routines)
        for job, summary in zip(jobs, summaries):
            job.summary = summary

    @classmethod
    async def __call__(cls, jobs: list[Job]):
        print(f"Generating summaries for {len(jobs)} jobs...")
        await cls._process(jobs)
        print("Summaries complete!")
