from src.extractor import create_extractor
from src.sql_chain import create_agent
import os
from dotenv import load_dotenv

load_dotenv(".env")

model = os.getenv('OPENAI_MODEL')

ex = create_extractor()
ag = create_agent(llm_model=model)


def query(prompt):
    clean, ver = ex.clean(prompt, verbose=True)
    ans, ver = ag.ask(clean)
    return ans

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Process a user query.")
    parser.add_argument('-q', '--query', type=str, required=True, help='A query string to process')

    args = parser.parse_args()
    ans = query(args.query)
    print(ans["output"])
