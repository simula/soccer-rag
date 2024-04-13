from src.extractor import create_extractor
from src.sql_chain import create_agent
ex = create_extractor()
ag = create_agent(llm_model="gpt-3.5-turbo-0125", verbose=False)
# ag = create_agent(llm_model = "gpt-4-0125-preview")

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
