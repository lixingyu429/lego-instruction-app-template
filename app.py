import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Please set your OPENAI_API_KEY environment variable!")
    st.stop()

client = OpenAI(api_key=api_key)

# Load your DataFrame from CSV file
CSV_FILE = "lego_subtasks.csv"
if not os.path.exists(CSV_FILE):
    st.error(f"CSV file '{CSV_FILE}' not found in the app directory.")
    st.stop()

df = pd.read_csv(CSV_FILE)
df['Subassembly'] = df['Subassembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])
df['Final Assembly'] = df['Final Assembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Initialize session state variables
if 'task_idx' not in st.session_state:
    st.session_state.task_idx = 0
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'subassembly_confirmed_pages' not in st.session_state:
    st.session_state.subassembly_confirmed_pages = set()
if 'finalassembly_confirmed_pages' not in st.session_state:
    st.session_state.finalassembly_confirmed_pages = set()
if 'previous_step_confirmed' not in st.session_state:
    st.session_state.previous_step_confirmed = False
if 'collected_parts_confirmed' not in st.session_state:
    st.session_state.collected_parts_confirmed = False
if 'group_num' not in st.session_state:
    st.session_state.group_num = 1

def show_image(image_path, caption=""):
    if os.path.exists(image_path):
        img = Image.open(image_path)
        st.image(img, caption=caption, use_container_width=True)
    else:
        st.warning(f"Image not found: {image_path}")

def call_chatgpt(user_question, context):
    image_path = context.get('current_image')
    image_content = None
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            image_content = img_file.read()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant for a student performing a physical assembly task."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
You are helping a student on subtask: {context['subtask_name']}.
They asked: \"{user_question}\"

Additional info:
- Bag: {context['bag']}
- Subassembly Pages: {context['subassembly']}
- Final Assembly Pages: {context['final_assembly']}
- Previous Step: {context['previous_step']}"""
                }
            ]
        }
    ]
    if image_content:
        messages[1]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64.b64encode(image_content).decode()}",
                "detail": "high"
            }
        })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

st.title("Student Assembly Assistant")

with st.sidebar:
    st.header("Progress Tracker")
    group_num_preview = st.session_state.get("group_num", 1)
    group_tasks_preview = df[df['Student Group'] == group_num_preview]
    if 'task_idx' in st.session_state and not group_tasks_preview.empty:
        current_task_preview = group_tasks_preview.iloc[st.session_state.task_idx]
        st.markdown(f"""
        **Subtask:** {current_task_preview['Subtask Name']}  
        **Bag:** {current_task_preview['Bag']}  
        **Collect Parts:** {'✅' if st.session_state.collected_parts_confirmed else '❌'}
        """)
        if current_task_preview['Subassembly']:
            st.markdown("**Subassembly:**")
            for page in current_task_preview['Subassembly']:
                completed = page in st.session_state.subassembly_confirmed_pages
                st.markdown(f"- Page {page}: {'✅' if completed else '❌'}")
        if current_task_preview['Final Assembly']:
            st.markdown("**Final Assembly:**")
            for page in current_task_preview['Final Assembly']:
                done = page in st.session_state.finalassembly_confirmed_pages
                st.markdown(f"- Page {page}: {'✅' if done else '❌'}")
        if st.session_state.step == 4:
            st.markdown("**Handover:** ✅")

left, center, right = st.columns([1, 2, 1])

with center:
    group_num = st.number_input("Enter your student group number:", min_value=1, step=1)
    st.session_state.group_num = group_num

    if group_num:
        group_tasks = df[df['Student Group'] == group_num]
        if group_tasks.empty:
            st.error(f"No subtasks found for Group {group_num}.")
        else:
            st.success(f"Welcome, Group {group_num}! You have {len(group_tasks)} subtask(s).")

            current_task = group_tasks.iloc[st.session_state.task_idx]
            context = {
                "subtask_name": current_task["Subtask Name"],
                "subassembly": current_task["Subassembly"],
                "final_assembly": current_task["Final Assembly"],
                "bag": current_task["Bag"],
                "previous_step": None,
                "current_image": None,
            }

            show_chat = st.toggle("💬 Show ChatGPT Help")
            if show_chat:
                user_question = st.text_input("Ask ChatGPT a question about your current step:")
                if user_question and user_question.lower() != 'n':
                    answer = call_chatgpt(user_question, context)
                    st.markdown(f"""
                    <div style='text-align: left; padding: 10px; background-color: #e8f0fe; border-left: 5px solid #4285f4; border-radius: 8px; margin-bottom: 1em;'>
                        🧠 <strong>ChatGPT says:</strong><br>{answer}
                    </div>
                    """, unsafe_allow_html=True)
