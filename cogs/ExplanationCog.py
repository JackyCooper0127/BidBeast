from typing import ClassVar, NoReturn
from uuid import UUID

from discord.ext import tasks
from discord.ext.commands import Cog
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI

from models import ExplanationModel, Like
from db import SUPABASE


def translate_like(val: Like) -> str:
    if val == Like.LIKE:
        return "would like to bid"
    elif val == Like.DISLIKE:
        return "would not like to bid"
    else:
        raise ValueError(f"Don't know how to translate '{repr(val)}'")


def _explain_chain() -> LLMChain:
    prompt = PromptTemplate.from_template("""
    You are a consultant for a freelance contractor. You have the ability to infer the tasks and skills required for a
    given job even if the description given by the client is ambiguous or does not use the correct terminology or skips
    over important parts.
    
    Title:
    {title}
    
    Description:
    {description}
    
    The reasons I {like} this job are because:
    {reasons}
    
    Using provided reasons and the given job description, state my preferences for future jobs to bid on as a
    comma-separated list in the first person.
    Eg: `I like jobs that work with python, I like jobs that have a definite endpoint` 
    Eg: `I do not like jobs that are unclear, I do not like jobs that work with C#`
    """)

    return LLMChain(llm=ChatOpenAI(temperature=.2, model_name="gpt-3.5-turbo"),
                    output_key='explanation',
                    prompt=prompt, )


class ExplanationCog(Cog):
    """ Generates the `explanation` field for `ExplanationModel` objects. """
    chain: ClassVar[LLMChain] = _explain_chain()
    query_cache: dict[UUID, ExplanationModel]

    def __init__(self):
        self.query_cache = {}

    async def cog_load(self) -> None:
        # start loops
        self.explain_loop.start()

    @tasks.loop(minutes=5)
    async def explain_loop(self):
        self.fetch_jobs()
        await self.generate_explanations()

    def fetch_jobs(self):
        """ Retrieve jobs from db that do not have any explanation """
        results = SUPABASE.table('potential_jobs') \
            .select('id, title, desc, link, like, reasons') \
            .eq('explanation', '') \
            .execute()
        data = results.data
        if data:
            for job in data:
                uuid = job['id']

                explanation = ExplanationModel(uuid)
                explanation.add_job(job['title'], job['desc'], job['link'])
                explanation.add_feedback(uuid, job['reasons'], job['like'])

                self.query_cache[uuid] = explanation

    async def generate_explanations(self) -> NoReturn:
        while self.query_cache:
            uuid, model = self.query_cache.popitem()
            await self._explain(uuid, model)

    async def _explain(self, uuid: UUID, model: ExplanationModel) -> NoReturn:
        """ Explain why a job is good or bad """
        explanation = await self.chain.arun({'title': model.job.title,
                                             'description': model.job.description,
                                             'like': translate_like(model.feedback.like),
                                             'reasons': model.feedback.reasons})
        SUPABASE.table('potential_jobs') \
            .update({'explanation': explanation}) \
            .eq('id', uuid) \
            .execute()

        print(f"Generated explanation: {explanation}")
