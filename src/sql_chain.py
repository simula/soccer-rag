import logging
import json
import os
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
# Save the log to a file
handler = logging.FileHandler('extractor.log')
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')

if os.getenv('LANGSMITH'):
    os.environ['LANGCHAIN_TRACING_V2'] = 'true'
    os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
    os.environ[
        'LANGCHAIN_API_KEY'] = os.getenv("LANGSMITH_API_KEY")
    os.environ['LANGCHAIN_PROJECT'] = 'master-theses'


def load_json(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        return json.load(file)


class SqlChain:
    def __init__(self, few_shot_prompts: str, llm_model="gpt-3.5-turbo", db_uri="sqlite:///data/games.db", few_shot_k=2, verbose=True):
        self.llm = ChatOpenAI(model=llm_model, temperature=0)
        self.db = SQLDatabase.from_uri(db_uri)
        self.few_shot_k = few_shot_k
        self.few_shot = self._set_up_few_shot_prompts(load_json(few_shot_prompts))
        self.full_prompt = None

        self.agent = create_sql_agent(
            llm=self.llm,
            db=self.db,
            prompt=self.full_prompt,
            max_iterations=10,
            verbose=verbose,
            agent_type="openai-tools",
            # Default to 10 examples - Can be overwritten with the prompt
            top_k=30,
        )


    def _set_up_few_shot_prompts(self, few_shot_prompts: dict) -> None:
        few_shots = SemanticSimilarityExampleSelector.from_examples(
            few_shot_prompts,
            OpenAIEmbeddings(),
            FAISS,
            k=self.few_shot_k,
            input_keys=["input"],
        )
        return few_shots

    def few_prompt_construct(self, query: str, top_k=5, dialect="SQLite") -> str:
        system_prefix = """You are an agent designed to interact with a SQL database.
        Given an input question, create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
        ALWAYS query the database before returning an answer.
        Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most {top_k} results.
        You can order the results by a relevant column to return the most interesting examples in the database.
        Never query for all the columns from a specific table, only ask for the relevant columns given the question.
        You have access to tools for interacting with the database.
        Only use the given tools. Only use the information returned by the tools to construct your final answer.
        You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.
        
        DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

        If the question does not seem related to the database, just return 'I don't know' as the answer.
        DO NOT include information that is not present in the database in your answer.

        Here are some examples of user inputs and their corresponding SQL queries. They are tested and works.
        Use them as a guide when creating your own queries:"""

        SUFFIX = """Begin!

            Question: {input}
            Thought: I should look at the tables in the database to see what I can query.  Then I should query the schema of the most relevant tables.
            I will not stop until I query the database and return the answer.
            {agent_scratchpad}"""

        few_shot_prompt = FewShotPromptTemplate(
            example_selector=self.few_shot,
            example_prompt=PromptTemplate.from_template(
                "User input: {input}\nSQL query: {query}"
            ),
            input_variables=["input", "dialect", "top_k"],
            prefix=system_prefix,
            suffix=SUFFIX,
        )
        full_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate(prompt=few_shot_prompt),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        self.full_prompt = full_prompt.invoke(
            {
                "input": query,
                "top_k": top_k,
                "dialect": dialect,
                "agent_scratchpad": [],
            }
        )
    def prompt_no_few_shot(self, query: str, dialect="SQLite") -> str:
        system_prefix = """You are an agent designed to interact with a SQL database.
        Given an input question, create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
        Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most {top_k} results.
        You can order the results by a relevant column to return the most interesting examples in the database.
        Never query for all the columns from a specific table, only ask for the relevant columns given the question.
        You have access to tools for interacting with the database.
        Only use the given tools. Only use the information returned by the tools to construct your final answer.
        You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

        DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

        If the question does not seem related to the database, just return 'I don't know' as the answer.
        DO NOT include information that is not present in the database in your answer."""

        return f"{system_prefix}\n{query}"




    def ask(self, query: str, few_prompt:bool=True) -> str:
        if few_prompt:
            self.few_prompt_construct(query)
            return self.agent.invoke({"input": self.full_prompt}), self.full_prompt
        else:

            return self.agent.invoke(self.prompt_no_few_shot(query)), self.prompt_no_few_shot(query)




def create_agent(few_shot_prompts: str = "src/conf/sqls.json", llm_model="gpt-3.5-turbo-0125",
                 db_uri="sqlite:///data/games.db", few_shot_k=2, verbose=True):
    """ Create an agent with the given few_shot_prompts, llm_model and db_uri
     Call it with agent.ask(prompt)"""
    return SqlChain(few_shot_prompts, llm_model, db_uri, few_shot_k, verbose)


if __name__ == "__main__":
    chain = SqlChain("src/conf/sqls.json")
    chain.ask("Is Manchester United in the database?", False)
