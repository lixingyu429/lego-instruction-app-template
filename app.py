import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64

# Page config
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Please set your OPENAI_API_KEY environment variable!")
    st.stop()

client = OpenAI(api_key=api_key)

# Load DataFrame
CSV_FILE = "lego_subtasks.csv"
if not os.path.exists(CSV_FILE):
    st.error(f"CSV file '{CSV_FILE}' not found in the app directory.")
    st.stop()

df = pd.read_csv(CSV_FILE)
df['Subassembly'] = df['Subassembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])
df['Final Assembly'] = df['Final Assembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])

def show_image(image_path, caption=""):
    if os.path.exists(image_path):
        img = Image.open(image_path)
        st.image(img, caption=caption, use_column_width=True)
    else:
        st.warning(f"Image not found: {image_path}")

def show_gpt_response(answer):
    st.markdown(f"""
    <div style='text-align: left; padding: 10px; background-color: #e8f0fe; border-left: 5px solid #4285f4; border-radius: 8px; margin-bottom: 1em;'>
        🧠 <strong>ChatGPT says:</strong><br>{answer}
    </div>
    """, unsafe_allow_html=True)

def call_chatgpt(user_question, context):
    image_messages = []

    for page in context.get('subassembly', []):
        img_path = f"manuals/page_{page}.png"
        if os.path.exists(img_path):
            with open(img_path, "rb") as img_file:
                image_content = base64.b64encode(img_file.read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_content}",
                    "detail": "high"
                }
            })

    for page in context.get('final_assembly', []):
        img_path = f"manuals/page_{page}.png"
        if os.path.exists(img_path):
            with open(img_path, "rb") as img_file:
                image_content = base64.b64encode(img_file.read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_content}",
                    "detail": "high"
                }
            })

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
- Previous Step: {context['previous_step']}
"""
                }
            ] + image_messages
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()

# Initial input page
if "team_num" not in st.session_state or "student_name" not in st.session_state:
    st.header("Welcome to the Assembly Task")
    team_num_input = st.number_input("Enter your student team number:", min_value=1, step=1)
    student_name_input = st.text_input("Enter your name:")
    if student_name_input and team_num_input:
        st.session_state.team_num = team_num_input
        st.session_state.student_name = student_name_input
        st.success("Information saved. You can proceed.")
        st.rerun()
    else:
        st.warning("Please enter both your name and team number to continue.")
    st.stop()

# Layout split
left, center, right = st.columns([1.2, 2.5, 1.3])

# Sidebar: Progress Tracker
with left:
    st.header("Progress Tracker")
    st.markdown(f"**Student:** {st.session_state.student_name}")
    st.markdown(f"**Team:** {st.session_state.team_num}")

    team_tasks_preview = df[df['Student Team'] == st.session_state.team_num]
    if 'task_idx' in st.session_state and not team_tasks_preview.empty:
        current_task_preview = team_tasks_preview.iloc[st.session_state.task_idx]
        st.markdown(f"""
        **Subtask:** {current_task_preview['Subtask Name']}  
        **Bag:** {current_task_preview['Bag']}  
        **Collect Parts:** {'✅' if st.session_state.get('collected_parts_confirmed', False) else '❌'}
        """)
        if current_task_preview['Subassembly']:
            st.markdown("**Subassembly:**")
            for page in current_task_preview['Subassembly']:
                completed = st.session_state.get('subassembly_confirmed', False)
                st.markdown(f"- Page {page}: {'✅' if completed else '❌'}")
        if current_task_preview['Final Assembly']:
            st.markdown("**Final Assembly:**")
            for page in current_task_preview['Final Assembly']:
                done = page in st.session_state.get('finalassembly_confirmed_pages', set())
                st.markdown(f"- Page {page}: {'✅' if done else '❌'}")
        if st.session_state.get('step', 0) == 4:
            st.markdown("**Handover:** ✅")

# Center: Main task flow
with center:
    exec(open("main_task_logic.py").read())  # Or inline your full main task code block here

# Right: ChatGPT Assistant
with right:
    st.header("💬 ChatGPT Assistant")
    st.markdown("Ask a question about your current step.")
    step_keys = ["q_step0", "q_step1", "q_step2", "q_step3", "q_step4"]
    current_step = st.session_state.get("step", 0)

    if current_step in range(len(step_keys)):
        key = step_keys[current_step]
        user_question = st.text_input("Your question to ChatGPT:", key=key)
        if user_question and user_question.lower() != 'n':
            context = st.session_state.get("context", {})
            if context:
                answer = call_chatgpt(user_question, context)
                show_gpt_response(answer)
    else:
        st.info("No active step to ask about.")
