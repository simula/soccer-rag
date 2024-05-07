from src.extractor import create_extractor
from src.sql_chain import create_agent
import os
from dotenv import load_dotenv

ex = create_extractor()
load_dotenv(".env")

model = os.getenv('OPENAI_MODEL')

ex = create_extractor()
ag = create_agent(llm_model=model)

def query(prompt):
    clean = ex.clean(prompt)
    return ag.ask(clean)


if __name__ == "__main__":
    while True:
        inp = input("Enter a query: ")
        if inp == "exit":
            break
        ans, _ = query(inp)
        print(ans["output"])
    exit(0)
