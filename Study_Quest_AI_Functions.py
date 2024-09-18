
from langchain.text_splitter import RecursiveCharacterTextSplitter
import google.generativeai as genai
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import streamlit as st
import requests
import random
import json
import re
import os


#Configure this one to True if deployed on streamlit community cloud or on local machine
#This helps change the json file and api key loading
is_streamlit_deployed = False

if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {}

if is_streamlit_deployed:
    st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"] = st.secrets["GOOGLE_GEN_AI_API_KEY"]
else:
    load_dotenv(dotenv_path='cred.env')  # This method will read key-value pairs from a .env file and add them to environment variable.
    st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"] = os.getenv('GOOGLE_GEN_AI_API_KEY')

def extract_and_parse_json(text):
    # Find the first opening and the last closing curly brackets
    start_index = text.find('[')
    end_index = text.rfind(']')
    
    if start_index == -1 or end_index == -1 or end_index < start_index:
        return None, False  # Proper JSON structure not found

    # Extract the substring that contains the JSON
    json_str = text[start_index:end_index + 1]

    try:
        # Attempt to parse the JSON
        parsed_json = json.loads(json_str)
        return parsed_json, True
    except json.JSONDecodeError:
        return None, False  # JSON parsing failed
    
def validate_and_convert_json(json_input, type_of_question):

    def is_valid_question(data):
        if type_of_question == "multiple_choice":
            return is_valid_multiple_choice_question(data)
        elif type_of_question == "identification":
            return is_valid_identification_question(data)
        elif type_of_question == "true_false":
            return is_valid_true_false_question(data)
        else:
            raise ValueError("type of question doesn't yet exist")  
        return False

    def is_valid_multiple_choice_question(data):
        # Check for the presence of all required keys
        return (
            "question" in data and
            "choices" in data and
            "answer" in data and
            "a" in data["choices"] and
            "b" in data["choices"] and
            "c" in data["choices"] and
            "d" in data["choices"] and
            isinstance(data["answer"], str) and
            data["answer"] in ['a', 'b', 'c', 'd']
        )
    
    def is_valid_identification_question(data):
        return(
            "question" in data and
            "answer" in data
        )
    
    def is_valid_true_false_question(data):
        return (
            "question" in data and
            "answer" in data and 
            isinstance(data["answer"], bool)  # Checks if the type of data["answer"] is boolean
        )

    # If the input is already a dictionary, validate it directly
    if isinstance(json_input, dict):
        valid = is_valid_question(json_input)
        return json_input, valid
    
    # If it's a string, attempt to parse it as JSON
    try:
        data = json.loads(json_input)
        valid = is_valid_question(data)
        return data, valid
    except (json.JSONDecodeError, TypeError) as e:
        return None, False  # Return None and False if parsing fails or keys are missing


def read_uploaded_files(files):
    content = ""
    for file in files:
        if file.type == "application/pdf":
            reader = PdfReader(file)
            for page in reader.pages:
                content += page.extract_text()
        elif file.type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            content += file.getvalue().decode("utf-8")
    return content

def split_text(content):
    # Define custom separators
    separators = ["\n\n", ". ", "\n•\n", "\n-\n", "\n", "\t"]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=8000, chunk_overlap=200, separators=separators)  # Expected words for an 8k context length LLaMA3:8b model local
    texts = text_splitter.split_text(content)
    return texts

def distribute_questions(num_questions, num_groups):
    base_questions = num_questions // num_groups
    remainder = num_questions % num_groups
    distribution = [base_questions] * num_groups
    for i in range(remainder):
        distribution[i] += 1
    return distribution

def generate_a_multiple_question(text, starting_number, type_of_test, additional_note):
    multiple_question_json = {}
    prompt_successful = False

    prompt = f"""
    Given the following text/content:
    ----------------------
    {text}
    ----------------------

    Generate me a multiple choice question in a JSON format. Please strictly follow the format below!!!:

    ```json
    {{
        "question":<question>,
        "choices":{{
            "a":<choice a>,
            "b":<choice b>,
            "c":<choice c>,
            "d":<choice d>
        }}
        "answer":<answer in small letter>
    }}
    ```

    Additional Notes: {additional_note}
    """

    while not prompt_successful:
        chat_log = [
            {"role": "system", "content": "You are tasked to create questions based on a specific content/text for students that are trying to study."},
            {"role": "user", "content": prompt}
        ]
        result = ollama.chat(model="llama3", messages=chat_log)
        multiple_question_response = result["message"]["content"]  # Ensure you parse this correctly based on the actual API response
        
        print(f"Question Number: {starting_number}")
        print(f"Multiple Question Response: \n\n {multiple_question_response}")
        #Extract and check if its a valid multiple question json
        multiple_question_json, multiple_question_parsed_successfully = extract_and_parse_json(multiple_question_response)
        print(multiple_question_json, multiple_question_parsed_successfully)
        
        if multiple_question_parsed_successfully == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #Assumes it passes the if condition above
        multiple_question_json_cleaned, multiple_question_valid_json = validate_and_convert_json(multiple_question_json, type_of_test)
        print(multiple_question_json_cleaned, multiple_question_valid_json)

        if multiple_question_valid_json == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #If question parsed and validated succesfully
        multiple_question_json = multiple_question_json_cleaned
        prompt_successful = True # Exit while loop if question processed successfully

    #Populate the mulitple question json format
    multiple_question = {
        "question_number":f"{starting_number}",
        "type_of_test":f"{type_of_test}",
        "question":multiple_question_json["question"],
        "choices":multiple_question_json["choices"],
        "answer":multiple_question_json["answer"]
    }

    return multiple_question



def generate_an_identification_question(text, starting_number, type_of_test, additional_note):
    identifcation_question_json = {}
    prompt_successful = False

    prompt = f"""

    Given the following text/content:
    ----------------------
    {text}
    ----------------------

    Generate me an identification question in a JSON format. Please strictly follow the format below!!!:

    ```json
    {{
        "question":<question>,
        "answer": <answer>
    }}
    ```

    Additional Notes: {additional_note}
    """

    while not prompt_successful:
        chat_log = [
            {"role": "system", "content": "You are tasked to create questions based on a specific content/text for students that are trying to study."},
            {"role": "user", "content": prompt}
        ]
        result = ollama.chat(model="llama3", messages=chat_log)
        identifcation_question_response = result["message"]["content"]  # Ensure you parse this correctly based on the actual API response
        
        print(f"Question Number: {starting_number}")
        print(f"Identification Question Response: \n\n {identifcation_question_response}")
        #Extract and check if its a valid multiple question json
        identifcation_question_json, identifcation_question_parsed_successfully = extract_and_parse_json(identifcation_question_response)
        print(identifcation_question_json, identifcation_question_parsed_successfully)
        
        if identifcation_question_parsed_successfully == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #Assumes it passes the if condition above
        identifcation_question_json_cleaned, identifcation_question_valid_json = validate_and_convert_json(identifcation_question_json, type_of_test)
        print(identifcation_question_json_cleaned, identifcation_question_valid_json)

        if identifcation_question_valid_json == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #If question parsed and validated succesfully
        identifcation_question_json = identifcation_question_json_cleaned
        prompt_successful = True # Exit while loop if question processed successfully

    #Populate the mulitple question json format
    identification_question = {
        "question_number":f"{starting_number}",
        "type_of_test":f"{type_of_test}",
        "question":identifcation_question_json["question"],
        "answer":identifcation_question_json["answer"]
    }

    return identification_question

def generate_a_true_false_question(text, starting_number, type_of_test, additional_note):
    true_false_question_json = {}
    prompt_successful = False

    prompt = f"""
    Given the following text/content:
    ----------------------
    {text}
    ----------------------

    Generate me a true or false question in a JSON format. Please strictly follow the format below!!!:

    ```json
    {{
        "question":<question>,
        "answer": <boolean>
    }}
    ```

    Additional Notes: {additional_note}
    """

    while not prompt_successful:
        chat_log = [
            {"role": "system", "content": "You are tasked to create questions based on a specific content/text for students that are trying to study."},
            {"role": "user", "content": prompt}
        ]
        result = ollama.chat(model="llama3", messages=chat_log)
        true_false_question_response = result["message"]["content"]  # Ensure you parse this correctly based on the actual API response
        
        print(f"Question Number: {starting_number}")
        print(f"True False Response: \n\n {true_false_question_response}")
        #Extract and check if its a valid multiple question json
        true_false_question_json, true_false_question_parsed_successfully = extract_and_parse_json(true_false_question_response)
        print(true_false_question_json, true_false_question_parsed_successfully)
        
        if true_false_question_parsed_successfully == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #Assumes it passes the if condition above
        true_false_question_json_cleaned, true_false_question_valid_json = validate_and_convert_json(true_false_question_json, type_of_test)
        print(true_false_question_json_cleaned, true_false_question_valid_json)

        if true_false_question_valid_json == False:
            print(f"Error Parsing Question Number {starting_number}")
            continue #If unsucessfull parsing was done on the salary, try again

        #If question parsed and validated succesfully
        true_false_question_json = true_false_question_json_cleaned
        prompt_successful = True # Exit while loop if question processed successfully

    #Populate the mulitple question json format
    true_false_question = {
        "question_number":f"{starting_number}",
        "type_of_test":f"{type_of_test}",
        "question":true_false_question_json["question"],
        "answer":true_false_question_json["answer"]
    }

    return true_false_question

def generate_questions_for_group(text, num_questions, additional_note, chunk_number):
    questions_list = []


    print("Generating questions...")

    prompt = f"""
    Given the following academic text below, I'd like you to generate some questions on different types of test.

    Academic text:

    {text}
    --------------------------------
    
    I'd like you to generate these types of test of questions with the corresponding number of questions for each type of text:
    1) Identification: {num_questions["identification"]} questions
    2) Multiple Choice: {num_questions["multiple_choice"]} questions
    3) True or False: {num_questions["true_false"]} questions

    Note: The arrangement of the type of test should be random

    Please give your output or answer using the example following json format:

    ```json
    [
        {{
        "type_of_test":"identification",
        "question":<question>,
        "answer": <answer>
        }},
        {{
        "type_of_test":"true_false",
        "question":<question>,
        "answer": <boolean>
        }},
        {{
        "type_of_test":"multiple_choice",
        "question":<question>,
        "choices":{{
            "a":<choice a>,
            "b":<choice b>,
            "c":<choice c>,
            "d":<choice d>
            }}
        "answer": <letter only in (lowercase letter)>
        }}
    ]
    ```json

    Notes:
    - You can generate the type of test of the questions in no particular order as long as you generated the required number of questions per type of test.
    - Double check the accuracy of the answers of the questions based on the academic text or content.
    
    Additional Notes:
    {additional_note}
    """

    genai.configure(api_key=st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"])
    # Choose a model that's appropriate for your use case.
    model = genai.GenerativeModel('gemini-1.5-flash',
        generation_config=genai.GenerationConfig(
        temperature=0.8,
        response_mime_type = "application/json"
    ))


    print("")
    response_json_valid = False
    max_attempts = 3
    parsed_result = None

    while not response_json_valid and max_attempts > 0: ## Wait till the response json is valid
        response = model.generate_content(prompt).text
        parsed_result, response_json_valid = extract_and_parse_json(response)
        if response_json_valid == False:
            print(f"Failed to validate and parse json for chunk text group {chunk_number}... Trying again...")
            max_attempts = max_attempts - 1 

        print(f"Parsed Results for chunk text group {chunk_number}: {parsed_result}")
        
    
    return parsed_result

def generate_questions(content, num_questions, additional_note):
    texts = split_text(content)
    num_groups = len(texts)

    distributed_questions = {
        "multiple_choice": distribute_questions(num_questions['multiple_choice'], num_groups),
        "identification": distribute_questions(num_questions['identification'], num_groups),
        "true_false": distribute_questions(num_questions['true_false'], num_groups)
    }

    all_questions = []
    total_questions_generated = {
        "multiple_choice": 0,
        "identification": 0,
        "true_false": 0
    }

    starting_question_number = 1
    st.session_state["starting_number"] = starting_question_number
    for i, text in enumerate(texts):

        print(f"Text group {i}:")
        print(texts)
        print("\n\n")

        if (total_questions_generated["multiple_choice"] >= num_questions["multiple_choice"] and
            total_questions_generated["identification"] >= num_questions["identification"] and
            total_questions_generated["true_false"] >= num_questions["true_false"]):
            break
        
        group_questions = {
            "multiple_choice": min(distributed_questions["multiple_choice"][i], num_questions["multiple_choice"] - total_questions_generated["multiple_choice"]),
            "identification": min(distributed_questions["identification"][i], num_questions["identification"] - total_questions_generated["identification"]),
            "true_false": min(distributed_questions["true_false"][i], num_questions["true_false"] - total_questions_generated["true_false"])
        }

        total_questions = group_questions["multiple_choice"] + group_questions["identification"] + group_questions["true_false"]
        print(f"Group Questions: {group_questions}")
        print(f"Total Questions: {total_questions}")

        questions = generate_questions_for_group(text, group_questions, additional_note=additional_note, chunk_number=i)
        print(questions)
        all_questions.extend(questions)
        
        
        total_questions_generated["multiple_choice"] += group_questions["multiple_choice"]
        total_questions_generated["identification"] += group_questions["identification"]
        total_questions_generated["true_false"] += group_questions["true_false"]

    print("Final JSON extracted \n ------------------------")
    print(all_questions)
    return all_questions
