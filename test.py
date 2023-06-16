import os

from langchain.llms import OpenAI
from langchain import PromptTemplate, LLMChain

from config import *

template = """Question: {question}

Answer: Let's think step by step."""

prompt = PromptTemplate(template=template, input_variables=["question"])
llm = OpenAI()
llm_chain = LLMChain(prompt=prompt, llm=llm)
question = "What NFL team won the Super Bowl in the year Justin Beiber was born?"

response = llm_chain.run(question)



print("...done")