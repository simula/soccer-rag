from typing import Optional

from langchain.chains import create_extraction_chain_pydantic
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_extraction_chain
from copy import deepcopy
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
import os
import difflib
import ast
import json
import re
from thefuzz import process
# Set up logging
import logging

from dotenv import load_dotenv

load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
# Save the log to a file
handler = logging.FileHandler('extractor.log')
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
# os.environ["ANTHROPIC_API_KEY"] = os.getenv('ANTHROPIC_API_KEY')

if os.getenv('LANGSMITH'):
    os.environ['LANGCHAIN_TRACING_V2'] = 'true'
    os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
    os.environ[
        'LANGCHAIN_API_KEY'] = os.getenv("LANGSMITH_API_KEY")
    os.environ['LANGCHAIN_PROJECT'] = os.getenv('LANGSMITH_PROJECT')
db_uri = os.getenv('DATABASE_PATH')
db_uri = f"sqlite:///{db_uri}"
db = SQLDatabase.from_uri(db_uri)

# from langchain_anthropic import ChatAnthropic
class Extractor():
    # llm = ChatOpenAI(model_name="gpt-4-0125-preview", temperature=0)
    #gpt-3.5-turbo
    def __init__(self, model="gpt-3.5-turbo-0125", schema_config=None, custom_extractor_prompt=None):
        # model = "gpt-4-0125-preview"
        if custom_extractor_prompt:
            cust_promt = ChatPromptTemplate.from_template(custom_extractor_prompt)

        self.llm = ChatOpenAI(model=model, temperature=0)
        # self.llm = ChatAnthropic(model="claude-3-opus-20240229", temperature=0)
        self.schema = schema_config or {}
        self.chain = create_extraction_chain(self.schema, self.llm, prompt=cust_promt)

    def extract(self, query):
        return self.chain.invoke(query)


class Retriever():
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.table = config.get('db_table')
        self.column = config.get('db_column')
        self.pk_column = config.get('pk_column')
        self.numeric = config.get('numeric', False)
        self.response = []
        self.query = f"SELECT {self.column} FROM {self.table}"
        self.augmented_table = config.get('augmented_table', None)
        self.augmented_column = config.get('augmented_column', None)
        self.augmented_fk = config.get('augmented_fk', None)

    def query_as_list(self):
        # Execute the query
        response = self.db.run(self.query)
        response = [el for sub in ast.literal_eval(response) for el in sub if el]
        if not self.numeric:
            response = [re.sub(r"\b\d+\b", "", string).strip() for string in response]
        self.response = list(set(response))
        # print(self.response)
        return self.response

    def get_augmented_items(self, prompt):
        if self.augmented_table is None:
            return None
        else:
            # Construct the query to search for the prompt in the augmented table
            query = f"SELECT {self.augmented_fk} FROM {self.augmented_table} WHERE LOWER({self.augmented_column}) = LOWER('{prompt}')"

            # Execute the query
            fk_response = self.db.run(query)
            if fk_response:
                # Extract the FK value
                fk_response = ast.literal_eval(fk_response)
                fk_value = fk_response[0][0]
                query = f"SELECT {self.column} FROM {self.table} WHERE {self.pk_column} = {fk_value}"
                # Execute the query
                matching_response = self.db.run(query)
                # Extract the matching response
                matching_response = ast.literal_eval(matching_response)
                matching_response = matching_response[0][0]
                return matching_response
            else:
                return None

    def find_close_matches(self, target_string, n=3, method="difflib", threshold=70):
        """
        Find and return the top n close matches to target_string in the database query results.

        Args:
        - target_string (str): The string to match against the database results.
        - n (int): Number of top matches to return.

        Returns:
        - list of tuples: Each tuple contains a match and its score.
        """
        # Ensure we have the response list populated
        if not self.response:
            self.query_as_list()

        # Find top n close matches
        if method == "fuzzy":
            # Use the fuzzy_string method to get matches and their scores
            # If the threshold is met, return the best match; otherwise, return all matches meeting the threshold
            top_matches = self.fuzzy_string(target_string, limit=n, threshold=threshold)


        else:
            # Use difflib's get_close_matches to get the top n matches
            top_matches = difflib.get_close_matches(target_string, self.response, n=n, cutoff=0.2)

        return top_matches

    def fuzzy_string(self, prompt, limit, threshold=80, low_threshold=30):

        # Get matches and their scores, limited by the specified 'limit'
        matches = process.extract(prompt, self.response, limit=limit)


        filtered_matches = [match for match in matches if match[1] >= threshold]

        # If no matches meet the threshold, return the list of all matches' strings
        if not filtered_matches:
            # Return matches above the low_threshold
            # Fix for wrong properties being returned
            return [match[0] for match in matches if match[1] >= low_threshold]


        # If there's only one match meeting the threshold, return it as a string
        if len(filtered_matches) == 1:
            return filtered_matches[0][0]  # Return the matched string directly

        # If there's more than one match meeting the threshold or ties, return the list of matches' strings
        highest_score = filtered_matches[0][1]
        ties = [match for match in filtered_matches if match[1] == highest_score]

        # Return the strings of tied matches directly, ignoring the scores
        m = [match[0] for match in ties]
        if len(m) == 1:
            return m[0]
        return [match[0] for match in ties]

    def fetch_pk(self, property_name, property_value):
        # Some properties do not have a primary key
        # Return the property value if no primary key is specified
        pk_list = []

        # Check if the property_value is a list; if not, make it a list for uniform processing
        if not isinstance(property_value, list):
            property_value = [property_value]

        # Some properties do not have a primary key
        # Return None for each property_value if no primary key is specified
        if self.pk_column is None:
            return [None for _ in property_value]

        for value in property_value:
            query = f"SELECT {self.pk_column} FROM {self.table} WHERE {self.column} = '{value}' LIMIT 1"
            response = self.db.run(query)

            # Append the response (PK or None) to the pk_list
            pk_list.append(response)

        return pk_list


def setup_retrievers(db, schema_config):
    # retrievers = {}
    # for prop, config in schema_config["properties"].items():
    #     retrievers[prop] = Retriever(db=db, config=config)
    # return retrievers

    retrievers = {}
    # Iterate over each property in the schema_config's properties
    for prop, config in schema_config["properties"].items():
        # Access the 'items' dictionary for the configuration of the array's elements
        item_config = config['items']
        # Create a Retriever instance using the item_config
        retrievers[prop] = Retriever(db=db, config=item_config)
    return retrievers


def extract_properties(prompt, schema_config, custom_extractor_prompt=None):
    """Extract properties from the prompt."""
    # modify schema_conf to only include the required properties
    schema_stripped = {'properties': {}}
    for key, value in schema_config['properties'].items():
        schema_stripped['properties'][key] = {
            'type': value['type'],
            'items': {'type': value['items']['type']}
        }

    extractor = Extractor(schema_config=schema_stripped, custom_extractor_prompt=custom_extractor_prompt)
    extraction_result = extractor.extract(prompt)
    # print("Extraction Result:", extraction_result)

    if 'text' in extraction_result and extraction_result['text']:
        properties = extraction_result['text']
        return properties
    else:
        print("No properties extracted.")
        return None


def recheck_property_value(properties, property_name, retrievers, input_func):
    while True:
        new_value = input_func(f"Enter new value for {property_name} or type 'quit' to stop: ")
        if new_value.lower() == 'quit':
            break  # Exit the loop and do not update the property

        new_top_matches = retrievers[property_name].find_close_matches(new_value, n=3)
        if new_top_matches:
            # Display new top matches and ask for confirmation or re-entry
            print("\nNew close matches found:")
            for i, match in enumerate(new_top_matches, start=1):
                print(f"[{i}] {match}")
            print("[4] Re-enter value")
            print("[5] Quit without updating")

            selection = input_func("Select the best match (1-3), choose 4 to re-enter value, or 5 to quit: ")
            if selection in ['1', '2', '3']:
                selected_match = new_top_matches[int(selection) - 1]
                properties[property_name] = selected_match  # Update the dictionary directly
                print(f"Updated {property_name} to {selected_match}")
                break  # Successfully updated, exit the loop
            elif selection == '5':
                break  # Quit without updating
            # Loop will continue if user selects 4 or inputs invalid selection
        else:
            print("No close matches found. Please try again or type 'quit' to stop.")


def check_and_update_properties(properties_list, retrievers, method="fuzzy", input_func=input):
    """
    Checks and updates the properties in the properties list based on close matches found in the database.
    The function iterates through each property in each property dictionary within the list,
    finds close matches for it in the database using the retrievers, and updates the property
    value based on user selection.

    Args:
        properties_list (list of dict): A list of dictionaries, where each dictionary contains properties
            to check and potentially update based on database matches.
        retrievers (dict): A dictionary of Retriever objects keyed by property name, used to find close matches in the database.
        input_func (function, optional): A function to capture user input. Defaults to the built-in input function.

    The function updates the properties_list in place based on user choices for updating property values
    with close matches found by the retrievers.
    """

    for index, properties in enumerate(properties_list):
        for property_name, retriever in retrievers.items():  # Iterate using items to get both key and value
            property_values = properties.get(property_name, [])
            if not property_values:  # Skip if the property is not present or is an empty list
                continue

            updated_property_values = []  # To store updated list of values

            for value in property_values:
                if retriever.augmented_table:
                    augmented_value = retriever.get_augmented_items(value)
                    if augmented_value:
                        updated_property_values.append(augmented_value)
                        continue
                # Since property_value is now expected to be a list, we handle each value individually
                top_matches = retriever.find_close_matches(value, method=method, n=3)

                # Check if the closest match is the same as the current value
                if top_matches and top_matches[0] == value:
                    updated_property_values.append(value)
                    continue

                if not top_matches:
                    updated_property_values.append(value)  # Keep the original value if no matches found
                    continue

                if type(top_matches) == str and method == "fuzzy":
                    # If the top_matches is a string, it means that the threshold was met and only one item was returned
                    # In this case, we can directly update the property with the top match
                    updated_property_values.append(top_matches)
                    properties[property_name] = updated_property_values
                    continue

                print(f"\nCurrent {property_name}: {value}")
                for i, match in enumerate(top_matches, start=1):
                    print(f"[{i}] {match}")
                print("[4] Enter new value")

                # hmm = input_func(f"Fix for Pycharm, press enter to continue")

                choice = input_func(f"Select the best match for {property_name} (1-4): ")
                if choice in ['1', '2', '3']:
                    selected_match = top_matches[int(choice) - 1]
                    updated_property_values.append(selected_match)  # Update with the selected match
                    print(f"Updated {property_name} to {selected_match}")
                elif choice == '4':
                    # Allow re-entry of value for this specific item
                    recheck_property_value(properties, property_name, value, retrievers, input_func)
                    # Note: Implement recheck_property_value to handle individual value updates within the list
                else:
                    print("Invalid selection. Property not updated.")
                    updated_property_values.append(value)  # Keep the original value

            # Update the entire list for the property after processing all values
            properties[property_name] = updated_property_values


# Function to remove duplicates
def remove_duplicates(dicts):
    seen = {}  # Dictionary to keep track of seen values for each key
    for d in dicts:
        for key in list(d.keys()):  # Use list to avoid RuntimeError for changing dict size during iteration
            value = d[key]
            if key in seen and value == seen[key]:
                del d[key]  # Remove key-value pair if duplicate is found
            else:
                seen[key] = value  # Update seen values for this key
    return dicts


def fetch_pks(properties_list, retrievers):
    all_pk_attributes = []  # Initialize a list to store dictionaries of _pk attributes for each item in properties_list

    # Iterate through each properties dictionary in the list
    for properties in properties_list:
        pk_attributes = {}  # Initialize a dictionary for the current set of properties
        for property_name, property_value in properties.items():
            if property_name in retrievers:
                # Fetch the primary key using the retriever for the current property
                pk = retrievers[property_name].fetch_pk(property_name, property_value)
                # Store it in the dictionary with a modified key name
                pk_attributes[f"{property_name}_pk"] = pk

        # Add the dictionary of _pk attributes for the current set of properties to the list
        all_pk_attributes.append(pk_attributes)

    # Return a list of dictionaries, where each dictionary contains _pk attributes for a set of properties
    return all_pk_attributes


def update_prompt(prompt, properties, pk, properties_original):
    # Replace the original prompt with the updated properties and pk
    prompt = prompt.replace("{{properties}}", str(properties))
    prompt = prompt.replace("{{pk}}", str(pk))
    return prompt


def update_prompt_enhanced(prompt, properties, pk, properties_original):
    updated_info = ""
    for prop, pk_info, prop_orig in zip(properties, pk, properties_original):
        for key in prop.keys():
            # Extract original and updated values
            orig_values = prop_orig.get(key, [])
            updated_values = prop.get(key, [])

            # Ensure both original and updated values are lists for uniform processing
            if not isinstance(orig_values, list):
                orig_values = [orig_values]
            if not isinstance(updated_values, list):
                updated_values = [updated_values]

            # Extract primary key detail for this key, handling various pk formats carefully
            pk_key = f"{key}_pk"  # Construct pk key name based on the property key
            pk_details = pk_info.get(pk_key, [])
            if not isinstance(pk_details, list):
                pk_details = [pk_details]

            for orig_value, updated_value, pk_detail in zip(orig_values, updated_values, pk_details):
                pk_value = None
                if isinstance(pk_detail, str):
                    pk_value = pk_detail.strip("[]()").split(",")[0].replace("'", "").replace('"', '')

                update_statement = ""
                # Skip updating if there's no change in value to avoid redundant info
                if orig_value != updated_value and pk_value:
                    update_statement = f"\n- {orig_value} (now referred to as {updated_value}) has a primary key: {pk_value}."
                elif orig_value != updated_value:
                    update_statement = f"\n- {orig_value} (now referred to as {updated_value})."
                elif pk_value:
                    update_statement = f"\n- {orig_value} has a primary key: {pk_value}."

                updated_info += update_statement

    if updated_info:
        prompt += "\nUpdated Information:" + updated_info

    return prompt


def prompt_cleaner(prompt, db, schema_config):
    """Main function to clean the prompt."""

    retrievers = setup_retrievers(db, schema_config)

    properties = extract_properties(prompt, schema_config)
    # Keep original properties for later use
    properties_original = deepcopy(properties)
    # Remove duplicates - Happens when there are more than one player or team in the prompt
    properties = remove_duplicates(properties)
    if properties:
        check_and_update_properties(properties, retrievers)

        pk = fetch_pks(properties, retrievers)
    properties = update_prompt_enhanced(prompt, properties, pk, properties_original)

    return properties, pk


class PromptCleaner:
    """
    A class designed to clean and process prompts by extracting properties, removing duplicates,
    and updating these properties based on a predefined schema configuration and database interactions.

    Attributes:
        db: A database connection object used to execute queries and fetch data.
        schema_config: A dictionary defining the schema configuration for the extraction process.
        schema_config = {
            "properties": {
                # Property name
                "person_name": {"type": "string", "db_table": "players", "db_column": "name", "pk_column": "hash",
                                    # if mostly numeric, such as 2015-2016 set true
                                "numeric": False},
                "team_name": {"type": "string", "db_table": "teams", "db_column": "name", "pk_column": "id",
                              "numeric": False},
                              # Add more as needed
            },
            # Parameter to extractor, if person_name is required, add it here and the extractor will
            # return an error if it is not found
            "required": [],
        }

    Methods:
        clean(prompt): Cleans the given prompt by extracting and updating properties based on the database.
            Returns a tuple containing the updated properties and their primary keys.
    """

    def __init__(self, db=db, schema_config=None, custom_extractor_prompt=None):
        """
        Initializes the PromptCleaner with a database connection and a schema configuration.

        Args:
            db: The database connection object to be used for querying. (if none, it will use the default db)
            schema_config: A dictionary defining properties and their database mappings for extraction and updating.
        """
        self.db = db
        self.schema_config = schema_config
        self.retrievers = setup_retrievers(self.db, self.schema_config)
        self.cust_extractor_prompt = custom_extractor_prompt

    def clean(self, prompt, return_pk=False, test=False, verbose = False):
        """
        Processes the given prompt to extract properties, remove duplicates, update the properties
        based on close matches within the database, and fetch primary keys for these properties.

        The method first extracts properties from the prompt using the schema configuration,
        then checks these properties against the database to find and update close matches.
        It also fetches primary keys for the updated properties where applicable.

        Args:
            prompt (str): The prompt text to be cleaned and processed.
            return_pk (bool): A flag to indicate whether to return primary keys along with the properties.
            test (bool): A flag to indicate whether to return the original properties for testing purposes.
            verbose (bool): A flag to indicate whether to return the original properties for debugging.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is the original prompt, with updated information that excist in the db.
                - The second element is a list of dictionaries, each containing primary keys for the properties,
                  where applicable.

        """
        if self.cust_extractor_prompt:

            properties = extract_properties(prompt, self.schema_config, self.cust_extractor_prompt)

        else:
            properties = extract_properties(prompt, self.schema_config)
        # Keep original properties for later use
        properties_original = deepcopy(properties)
        if test:
            return properties_original
        # Remove duplicates - Happens when there are more than one player or team in the prompt
        # properties = remove_duplicates(properties)
        pk = None
        if properties:
            check_and_update_properties(properties, self.retrievers)
            pk = fetch_pks(properties, self.retrievers)
        properties = update_prompt_enhanced(prompt, properties, pk, properties_original)



        if return_pk:
            return properties, pk
        elif verbose:
            return properties, properties_original
        else:
            return properties


def load_json(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        return json.load(file)


def create_extractor(schema: str = "src/conf/schema.json", db: SQLDatabase = db_uri):
    schema_config = load_json(schema)
    db = SQLDatabase.from_uri(db)
    pre_prompt = """Extract and save the relevant entities mentioned \
                    in the following passage together with their properties.
                    
                    Only extract the properties mentioned in the 'information_extraction' function. 
                    
                    The questions are soccer related. game_event are things like yellow cards, goals, assists, freekick ect.
                    Generic properties like, "description", "home team", "away team", "game" ect should NOT be extracted.
                    
                    If a property is not present and is not required in the function parameters, do not include it in the output.
                    If no properties are found, return an empty list.
                    
                    Here are some exampels:
                    'How many goals did Henry score for Arsnl in the 2015 season?'
                    person_name': ['Henry'], 'team_name': [Arsnl],'year_season': ['2015'],
                    
                    Passage:
                    {input}
    """

    return PromptCleaner(db, schema_config, custom_extractor_prompt=pre_prompt)


if __name__ == "__main__":


    schema_config = load_json("src/conf/schema.json")
    # Add game and league to the schema_config

    # prompter = PromptCleaner(db, schema_config, custom_extractor_prompt=extract_prompt)
    prompter = create_extractor("src/conf/schema.json", "sqlite:///data/games.db")
    prompt= prompter.clean("Give me goals, shots on target, shots off target and corners from the game between ManU and Swansa")


    print(prompt)

