from Study_Quest_AI_Functions import read_uploaded_files, generate_questions  # Ensure the function names match exactly
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import json
import os

# Initialize API keys
if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {}

is_streamlit_deployed = True  # Set this to True if deployed on Streamlit Cloud

if is_streamlit_deployed:
    st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"] = st.secrets["GOOGLE_GEN_AI_API_KEY"]
else:
    load_dotenv(dotenv_path='cred.env')  # Ensure 'cred.env' is in your project directory
    st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"] = os.getenv('GOOGLE_GEN_AI_API_KEY')

# Check if the API key was loaded successfully
if not st.session_state["api_keys"]["GOOGLE_GEN_AI_API_KEY"]:
    st.error("API key for Google Generative AI not found. Please check your credentials.")

# Center the logo image
col1, col2, col3 = st.columns(3)

with col1:
    st.write(' ')

with col2:
    st.image("Study_Quest_AI_Logo.png", width=200)

with col3:
    st.write(' ')

st.markdown("<h1 style='text-align: center; color: white;'>Study Quest AI</h1>", unsafe_allow_html=True)
st.markdown("""
### Unlock Your Learning Potential with StudyQuest AI!
Transform your PDFs into interactive quizzes and questionnaires, making memorization and studying easier than ever. Perfect for students aiming to master their subjects, Study Quest AI helps you create customized study materials in just a few clicks.
**Start your quest for knowledge today!**
""")

uploaded_files = st.file_uploader("Upload Study Documents", accept_multiple_files=True, type=["pdf", "doc", "docx"], key="file_uploader")

st.markdown("#### Enter the number of questions for each type of test:")
# Arrange the inputs in a single row using columns
col1, col2, col3 = st.columns(3)

with col1:
    multiple_choice = st.number_input("Multiple Choice:", min_value=0, value=1, key='multiple_choice')

with col2:
    identification = st.number_input("Identification:", min_value=0, value=1, key='identification')

with col3:
    true_false = st.number_input("True or False:", min_value=0, value=1, key='true_false')

additional_notes = st.text_area("Enter additional notes", height=200, max_chars=200)
st.write("""
You can enter additional notes that you would like for the model to consider when picking and creating your questionnaires/quiz.
- Would you like to use or highlight a more specific topic?
- Would you like to include dates or locations in the questionnaire?
""")


if 'starting_number' not in st.session_state:
    st.session_state["starting_number"] = 0

if 'total_questions' not in st.session_state:
    st.session_state['total_questions'] = 0

if 'questions_progress_bar' not in st.session_state:
    st.session_state['questions_progress_bar'] = None

if "all_questions" not in st.session_state:
    st.session_state["all_questions"] = []

if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = {}

if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = False

if "scoring_history" not in st.session_state:
    st.session_state["scoring_history"] = {}

# Ensure scoring_history is initialized whenever all_questions is available
if "all_questions" in st.session_state and st.session_state["all_questions"]:
    if "scoring_history" not in st.session_state or len(st.session_state["scoring_history"]) != len(st.session_state["all_questions"]):
        st.session_state["scoring_history"] = {}
        for idx, question in enumerate(st.session_state["all_questions"]):
            st.session_state["scoring_history"][idx] = {
                "question": question,
                "times_wrong": 0
            }

if st.button("Generate"):
    if uploaded_files:
        st.session_state['total_questions'] = multiple_choice + identification + true_false
        st.write(f"Total Questions to Generate: {st.session_state['total_questions']}")
        st.session_state['questions_progress_bar'] = st.progress(0, text="Generating your questions. Please wait..")
        content = read_uploaded_files(uploaded_files)
        num_questions = {
            "multiple_choice": multiple_choice,
            "identification": identification,
            "true_false": true_false
        }
        all_questions = generate_questions(content, num_questions, additional_note=additional_notes)
        
        # Update progress bar to complete
        st.session_state['questions_progress_bar'].progress(100)
        st.session_state['questions_progress_bar'].empty()  # Remove the progress bar
        st.success("Question generation complete!")

        # Initialize scoring history
        for idx, question in enumerate(all_questions):
            st.session_state["scoring_history"][idx] = {
                "question": question,
                "times_wrong": 0
            }

        st.session_state["all_questions"] = all_questions
        st.session_state["user_answers"] = {}
        st.session_state["edit_mode"] = False

if st.session_state["all_questions"]:
    st.header("Quiz")

    # Toggle edit mode
    edit_button_label = "Switch to Edit Mode" if not st.session_state["edit_mode"] else "Exit Edit Mode"
    if st.button(edit_button_label):
        st.session_state["edit_mode"] = not st.session_state["edit_mode"]

    # Inform the user about the current mode
    if st.session_state["edit_mode"]:
        st.info("You are now in Edit Mode. Make changes to your questions and answers below.")
    else:
        st.info("You are in Quiz Mode. Answer the questions and submit your responses.")

    # Begin form only if not in edit mode
    if not st.session_state["edit_mode"]:
        with st.form(key='quiz_form'):
            for idx, question in enumerate(st.session_state["all_questions"]):
                st.write(f"**Question {idx+1}:**")
                st.write(question["question"])
                if question["type_of_test"] == "multiple_choice":
                    options = [f"{key.upper()}: {val}" for key, val in question["choices"].items()]
                    answer = st.radio("Choose an option:", options=options, key=f"answer_{idx}")
                    st.session_state["user_answers"][idx] = answer.split(":")[0].strip().lower()
                elif question["type_of_test"] == "true_false":
                    answer = st.radio("Choose True or False:", options=["True", "False"], key=f"answer_{idx}")
                    st.session_state["user_answers"][idx] = True if answer == "True" else False
                elif question["type_of_test"] == "identification":
                    answer = st.text_input("Your Answer:", key=f"answer_{idx}")
                    st.session_state["user_answers"][idx] = answer

            submit_button = st.form_submit_button(label='Submit')

        # Inside the result processing after submit_button is clicked
        if submit_button:
            st.header("Results")
            score = 0
            total = len(st.session_state["all_questions"])
            for idx, question in enumerate(st.session_state["all_questions"]):
                user_answer = st.session_state["user_answers"].get(idx, None)
                correct = False
                # Code to check if the answer is correct
                if question["type_of_test"] == "multiple_choice":
                    correct_answer = question["answer"]
                    if user_answer == correct_answer:
                        correct = True
                elif question["type_of_test"] == "true_false":
                    correct_answer = question["answer"]
                    if user_answer == correct_answer:
                        correct = True
                elif question["type_of_test"] == "identification":
                    correct_answer = question["answer"].strip().lower()
                    if user_answer.strip().lower() == correct_answer:
                        correct = True
                if correct:
                    st.write(f"Question {idx+1}: Correct ✅")
                    score += 1
                else:
                    st.write(f"Question {idx+1}: Incorrect ❌")
                    st.write(f"Your Answer: {user_answer}")
                    st.write(f"Correct Answer: {question['answer']}")
                    # Update scoring history
                    if idx in st.session_state["scoring_history"]:
                        st.session_state["scoring_history"][idx]["times_wrong"] += 1
                    else:
                        st.session_state["scoring_history"][idx] = {
                            "question": question,
                            "times_wrong": 1
                        }
            st.write(f"**Your Score: {score} out of {total}**")
    else:
        # Editing mode
        for idx, question in enumerate(st.session_state["all_questions"]):
            st.write(f"**Question {idx+1}:**")
            question_text = st.text_area(f"Edit Question {idx+1}", value=question["question"], key=f"edit_question_{idx}")
            question["question"] = question_text
            if question["type_of_test"] == "multiple_choice":
                for choice_key in ["a", "b", "c", "d"]:
                    choice_text = st.text_input(f"Choice {choice_key.upper()} for Question {idx+1}", value=question["choices"][choice_key], key=f"edit_choice_{choice_key}_{idx}")
                    question["choices"][choice_key] = choice_text
                correct_answer = st.selectbox(f"Correct Answer for Question {idx+1}", options=["a", "b", "c", "d"], index=["a", "b", "c", "d"].index(question["answer"]), key=f"edit_correct_{idx}")
                question["answer"] = correct_answer
            elif question["type_of_test"] == "true_false":
                correct_answer = st.selectbox(f"Correct Answer for Question {idx+1}", options=["True", "False"], index=0 if question["answer"] == True else 1, key=f"edit_correct_tf_{idx}")
                question["answer"] = True if correct_answer == "True" else False
            elif question["type_of_test"] == "identification":
                correct_answer = st.text_input(f"Correct Answer for Question {idx+1}", value=question["answer"], key=f"edit_correct_id_{idx}")
                question["answer"] = correct_answer

    # Export questions and scoring history
    if st.button("Export Questions and Scoring History"):
        export_data = {
            "questions": st.session_state["all_questions"],
            "scoring_history": st.session_state["scoring_history"]
        }
        json_data = json.dumps(export_data, indent=4)
        st.download_button(label="Download JSON", data=json_data, file_name="questions_and_history.json", mime="application/json")

    # Import questions and scoring history
    imported_file = st.file_uploader("Import Questions and Scoring History", type=["json"], key="import_file")
    if imported_file is not None:
        imported_data = json.load(imported_file)
        st.session_state["all_questions"] = imported_data.get("questions", [])
        st.session_state["scoring_history"] = imported_data.get("scoring_history", {})
        st.success("Questions and scoring history imported successfully!")
