from operator import itemgetter
from typing import ClassVar

from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableMap

from db import SUPABASE
from models import FeedbackModel, Job

_str_parser = StrOutputParser()
_fb_parser = PydanticOutputParser(pydantic_object=FeedbackModel)

_preamble = """You will be assisting a freelancer with editing automatically generated feedback on potential 
contracts. This feedback consists of statements describing the freelancer, their preference, or the terms of the 
potential contract. These statements are used to determine if the potential contract is worthy of the freelancers 
attention. Some of these statements are inaccurate, as they misrepresent the skills, knowledge and preferences of the 
freelancer."""

_decompose_prompt = PromptTemplate.from_template("""{{preamble}}

You will be given comments made by the freelancer (myself) that describes corrections to be made to automatically generated feedback. Each clause or sentence might contain more than one piece of information. Please parse the user-provided comments into a list of statements or facts.

Each statement will be one of the following:
- "the freelancer will bid this job"
- "the freelancer will not bid this job"
- a pro, or positive, appealing aspects of the potential contract or skills, knowledge or experience that the freelancer has. Prepend with "pro: "
- a con, or negative, unappealing aspects of the potential contract or skills, knowledge or experience that the freelancer does not have. Prepend with "con: "

There might be multiple pros/cons. Each pro or con will always to be prepended with "pro: " or "con: " respectively.

Here are the user provided comments:
```{{comments}}```

Only return a flat, bulleted list of short statements and nothing more.""",
                                                 template_format='jinja2',
                                                 partial_variables={'preamble': _preamble})

_viability_prompt = PromptTemplate.from_template("""You're an assistant to a freelancer and have ability of extracting key information from a list of facts.

You will be given a list of facts about the freelancer and a biased value representing whether the freelancer should place a bid on the contract or not. The list of facts you're given may or may not contain a string which indicates if the freelancer actually wants to bid the job or not.

For each item in the list of facts:
- if there is a statement with "will not bid", return `0`.
- if there is a statement with "will bid", return `1`. Do not add the statement to either `pros` or `cons`.
- if no statement contains either "will not bid" or "will bid", then return the default value listed below.

Here is the default value to use:
```{{orig_viability}}```

Here is the list of facts about the freelancer:
{{facts}}

Only return the integer `0` or `1` depending on the list of facts or the default value provided by the freelancer.
""",
                                                 template_format='jinja2')

_addition_prompt = PromptTemplate.from_template("""You are an assistant to a freelance contractor and are able to see the deficiencies between a list of facts and a biased list of pros/cons describing a potential contract.

You will be given a list of facts about the freelancer as list of pros/cons. These lists represent facts that need to be added to the biased list of pros and cons about the potential contract. You will be aggregating what additions to the `pros` and `cons` list needs to be made. Do not propose the removal of any statement.

For each item in the list of facts:
- ignore any statement that is not prepended with 'pro: ' or 'con: '
- add any statement prepended with 'pro: ' to the `pros` list.
- add any statement prepended with 'con: ' to the `cons` list.

Do not update or propose any change change the `viability` attribute. Do not propose the removal of any statement.

This is the biased list of pros:
```{{pros}}```

This is the biased list of cons:
```{{cons}}```

Here are the comments provided by the freelancer:
{{facts}}

Only return bullet points of what additions need to be made to the `pros` list and `cons` list on the python object to reflect the freelancer's comments. Do not return the modified object.

Each bullet point should be formatted in the following way:
'- Add "X" to `cons`'
'- Add "X" to `pros`'

(where "X" is the statement to be added)

If there are no statements to add, return "No additions necessary".
""",
                                                template_format='jinja2')

_removal_prompt = PromptTemplate.from_template("""You are an assistant to a freelancer who is able to determine conflicts between a list of facts about the freelancer, and biased statements about a potential contract.

You will be given facts about the freelancer as 2 lists containing pros/cons. The biased information is contained in a python object with a `pros` list attribute and a `cons` list attribute. Any statement prepended with 'pro: ' might conflict with a statement contained in the `cons` list; any statement prepended with 'con: ' might conflict with a statement contained in the `pros` list. Determine what removals need to be made so that the information aligns.

If a biased list is empty, then there is no conflict.

Here is the the list of facts about the freelancer:
{{facts}}

Here is a biased list of `pros`:
```{{pros}}```

Here is a biased list of `cons`:
```{{cons}}```

Only return a list of aggregated bullet points of what removals need to be made to the biased `pros` list and the biased `cons` list to align with the list of facts. Only return the removals necessary, and not the modified lists themselves.

Each bullet point should be formatted in the following way:
'- Remove "X" from `cons`'
'- Remove "X" from `pros`'

(where "X" is the statement to be removed)

If there is no conflicting information, return "No removals necessary".
""",
                                               template_format='jinja2')

_modify_prompt = PromptTemplate.from_template("""You are an assistant to a freelancer and have the ability to interpret a list of facts which represent changes that need to be made to biased lists.

You will be given list of facts that need to be added and a list of statements that need to be made removed. You will be directly modifying the object by, adding or removing statements to the `pros` list or `cons` list, or modifying the `viability` value.

Output the modified object in proper Python syntax and nothing more.

Here are the facts that need to be added:
```{{additions}}``` 

Here are the statements that need to be removed:
```{{removals}}``` 

Set the `viability` attribute to this value:
```{{viability}}```

Here is the biased `pros` list:
```{{pros}}```

Here is the biased `cons` list:
```{{cons}}```

{{format_instructions}}
""",
                                              partial_variables={'format_instructions':
                                                                 _fb_parser.get_format_instructions()},
                                              template_format='jinja2')


class ReviewChain:
    """ This functor edits a `FeedbackModel` based on user-provided comments.

    The intent is for the user to edit the `FeedbackModel` via a simple message.
    """
    _llm: ClassVar[ChatOpenAI] = ChatOpenAI(model_name='gpt-3.5-turbo')

    _decompose_chain = _decompose_prompt | _llm | _str_parser
    _addition_chain = _addition_prompt | _llm | _str_parser
    _removal_chain = _removal_prompt | _llm | _str_parser
    _viability_chain = _viability_prompt | _llm | _str_parser
    _input_chain = RunnableMap(
        facts=_decompose_chain,
        cons=itemgetter('cons'),
        pros=itemgetter('pros'),
        orig_viability=itemgetter('viability')
    )
    modify_chain = (_input_chain | {
        'additions': _addition_chain,
        'removals': _removal_chain,
        'pros': itemgetter('pros'),
        'cons': itemgetter('cons'),
        'viability': _viability_chain
    } | _modify_prompt | _llm | _fb_parser)

    @classmethod
    def __call__(cls, feedback: FeedbackModel, comments: str) -> FeedbackModel:
        if comments == 'skip':
            return feedback

        return cls.modify_chain.invoke({
            'pros': feedback.pros,
            'cons': feedback.cons,
            'viability': feedback.viability,
            'comments': comments})
