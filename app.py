import os
from src.extractor import create_extractor
from src.sql_chain import create_agent
from dotenv import load_dotenv
import chainlit as cl
import json
# Loading the environment variables
load_dotenv(".env")
# Create the extractor and agent

model = os.getenv('OPENAI_MODEL')
# Check if model exists, if not, set it to default
# if not model:
#     model = "gpt-3.5-turbo-0125"



interactive_key_done= False if os.getenv('INTERACTIVE_OPENAI_KEY', None) else True

if interactive_key_done:
    ex = create_extractor()
    ag = create_agent(llm_model=model)
else:
    ex= None
    ag = None

from chainlit.input_widget import Select

@cl.on_settings_update
async def setup_agent(settings):
    global interactive_key_done
    # if cl.user_session.get("openai_api_key") == os.environ["OPENAI_API_KEY"]:
    os.environ["OPENAI_API_KEY"]= ""
    await cl.Message("OpenAI API Key cleared, start a new chat to set new key!").send()
    interactive_key_done= False


@cl.on_chat_start
async def on_chat_start():
    global ex, ag, interactive_key_done
    if not interactive_key_done:
        res =  await cl.AskUserMessage(content=" 🔑 Input your OPENAI_API_KEY from https://platform.openai.com/account/api-keys", timeout=10).send()
        if res:
            await cl.Message(
                content=f"⌛ Checking if provided OpenAI API key works. Please wait...",
            ).send()
            cl.user_session.set("openai_api_key", res.get("output"))
            try:
                os.environ["OPENAI_API_KEY"] = res.get("output")
                ex = create_extractor()
                ag = create_agent(llm_model=model)
                interactive_key_done= True
                await cl.Message(author="Socccer-RAG", content="✅ Voila! ⚽ Socccer-RAG warmed up and ready to go! You can start a fresh chat session from New Chat").send()
                await cl.Message("💡Remeber to clear your keys when you are done. To remove/change you OpenAI API key, click on the settings icon on the left of the chat box.").send()
            except Exception as e:
                await cl.Message(
                    content=f"❌Error: {e}. \n 🤗 Please Start new chat to set correct key.",
                ).send()
                return
    await cl.ChatSettings([Select(id="Setting",label="Remove/change current OpenAI API Key?",values=["Click Confirm:"],)]).send()

            # ag = create_agent(llm_model = "gpt-4-0125-preview")



def extract_func(user_prompt: str):
    """

    Parameters
    ----------
    user_prompt: str

    Returns
    -------
    A dictionary of extracted properties
    """
    extracted = ex.extract_chainlit(user_prompt)
    return extracted
def validate_func(properties:dict):  # Auto validate as much as possible
    """
    Parameters
    ----------
    extracted properties: dict

    Returns
    -------
    Two dictionaries:
    1. validated: The validated properties
    2. need_input: Properties that need human validation
    """
    validated, need_input = ex.validate_chainlit(properties)
    return validated, need_input

def human_validate_func(human, validated, user_prompt):
    """

    Parameters
    ----------
    human - Human validated properties in the form of a list of dictionaries
    validated - Validated properties in the form of a dictionary
    user_prompt - The user prompt

    Returns
    -------
    The cleaned prompt with updated values
    """
    for item in human:
        # Iterate through key-value pairs in the current dictionary
        for key, value in item.items():
            if value == "":
                continue
            # Check if the key exists in the validated dictionary
            if key in validated:
                # Append the value to the existing list
                validated[key].append(value)
            else:
                # Create a new key with the value as a new list
                validated[key] = [value]
    val_list = [validated]

    return ex.build_prompt_chainlit(val_list, user_prompt)

def no_human(validated, user_prompt):
    """
    In case there is no need for human validation, this function will be called
    Parameters
    ----------
    validated
    user_prompt

    Returns
    -------
    Updated prompt
    """
    return ex.build_prompt_chainlit([validated], user_prompt)


def ask(text):
    """
    Calls the SQL Agent to get the final answer
    Parameters
    ----------
    text

    Returns
    -------
    The final answer
    """
    ans, const = ag.ask(text)
    return {"output": ans["output"]}, 12


@cl.step
async def Cleaner(text):  # just for printing
    return text


@cl.step
async def LLM(cleaned_prompt):  # just for printing
    ans, const = ask(cleaned_prompt)
    return ans, const


@cl.step
async def Choice(text):
    return text

@cl.step
async def Extractor(user_prompt):
    extracted_values = extract_func(user_prompt)
    return extracted_values


@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def main(message: cl.Message):
    global interactive_key_done
    if not interactive_key_done:
        await cl.Message(
            content=f"Please set the OpenAI API key first by starting a new chat.",
        ).send()
        return
    user_prompt = message.content # Get the user prompt
    # extracted_values = extract_func(user_prompt)
    #
    # json_formatted = json.dumps(extracted_values, indent=4)
    extracted_values = await Extractor(user_prompt)
    json_formatted = json.dumps(extracted_values, indent=4)
    # Print the extracted values in json format
    await cl.Message(author="Extractor", content=f"Extracted properties:\n```json\n{json_formatted}\n```").send()
    # Try to validate everything
    validated, need_input = validate_func(extracted_values)
    await cl.Message(author="Validator", content=f"Extracted properties will now be validated against the database.").send()
    if need_input:
        # If we need validation, we will ask the user to select the correct value
        for element in need_input:
            key = next(iter(element))  # Get the first key in the dictionary
            # Present user with options to choose from
            actions = [
                cl.Action(name="option", value=value, label=value)
                for value in element['top_matches']
            ]
            await cl.Message(author="Resolver", content=f"Need to identify the correct value for {key}: ").send()
            res = await cl.AskActionMessage(author="Resolver",
                content=f"Which one do you mean for {key}?", 
                actions=actions
            ).send()
            selected_value = res.get("value") if res else ""
            element[key] = selected_value
            element.pop("top_matches")
            await Choice("Options were "+ ", ".join([action.label for action in actions]))
        # Get the cleaned prompt
        cleaned_prompt = human_validate_func(need_input, validated, user_prompt)
    else:
        cleaned_prompt = no_human(validated, user_prompt)
    # Print the cleaned prompt
    cleaner_message = cl.Message(author="Cleaner", content=f"New prompt is as follows:\n{cleaned_prompt}")
    await cleaner_message.send()

    # Call the SQL agent to get the final answer
    # ans, const = ask(cleaned_prompt)  # Get the final answer from some function
    await cl.Message(content=f"I will now query the database for information.").send()
    ans, const = await LLM(cleaned_prompt)
    await cl.Message(content=f"This is the final answer: \n\n{ans['output']}").send()
