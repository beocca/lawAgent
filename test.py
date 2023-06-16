import os

from langchain.llms import OpenAI
from langchain import PromptTemplate, LLMChain

from config import *

template = """Question: What NFL team won the Super Bowl in the year Justin Beiber was born?
Answer: Let's think step by step."""

prompt = PromptTemplate(template=template, input_variables=list())
llm = OpenAI(model="text-curie-001")



r = llm.generate([template]).generations[0][0].text
quit()

llm_chain = LLMChain(prompt=prompt, llm=llm)
question = "What NFL team won the Super Bowl in the year Justin Beiber was born?"

response = llm_chain.run()



print("...done")