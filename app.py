import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64
import hashlib

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

@st.cache_data
def get_encoded_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

def show_image(image_path, caption=""):
    if os.path.exists(image_path):
        img = Image.open(image_path)
        st.image(img, caption=caption, use_container_width=True)
    else:
        st.warning(f"Image not found: {image_path}")

def show_gpt_response(answer):
    st.markdown(f"""
    <div style='text-align: left; padding: 10px; background-color: #e8f0fe; border-left: 5px solid #4285f4; border-radius: 8px; margin-bottom: 1em;'>
        🧠 <strong>AGEMT says:</strong><br>{answer}
    </div>
    """, unsafe_allow_html=True)

def get_question_hash(question, context):
    hash_input = question + str(context)
    return hashlib.md5(hash_input.encode()).hexdigest()

def call_chatgpt(user_question, context):
    image_messages = []

    for page in context.get('subassembly', []) + context.get('final_assembly', []):
        img_path = f"manuals/page_{page}.png"
        image_content = get_encoded_image(img_path)
        if image_content:
            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_content}",
                    "detail": "high"
                }
            })

    messages = [
        {"role": "system", "content": "You are a helpful assistant for a student performing a physical assembly task."},
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

# Sidebar: Progress Tracker + Assistant
with st.sidebar:
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
                done = page in st.session_state.get('subassembly_confirmed_pages', set())
                st.markdown(f"- Page {page}: {'✅' if done else '❌'}")
        if current_task_preview['Final Assembly']:
            st.markdown("**Final Assembly:**")
            for page in current_task_preview['Final Assembly']:
                done = page in st.session_state.get('finalassembly_confirmed_pages', set())
                st.markdown(f"- Page {page}: {'✅' if done else '❌'}")
        if st.session_state.get('step', 0) == 4:
            st.markdown("**Handover:** ✅")

    with st.expander("💬 AGEMT", expanded=False):
        st.markdown("Ask a question about your current step.")
        step_keys = ["q_step0", "q_step1", "q_step2", "q_step3", "q_step4"]
        current_step = st.session_state.get("step", 0)

        if current_step in range(len(step_keys)):
            key = step_keys[current_step]
            user_question = st.text_input("Your question to AGEMT:", key=key)
            if user_question and user_question.lower() != 'n':
                task_idx = st.session_state.get('task_idx', 0)
                current_task = df[df['Student Team'] == st.session_state.team_num].iloc[task_idx]
                context = {
                    "subtask_name": current_task["Subtask Name"],
                    "subassembly": current_task["Subassembly"],
                    "final_assembly": current_task["Final Assembly"],
                    "bag": current_task["Bag"],
                    "previous_step": None,
                }
                q_hash = get_question_hash(user_question, context)
                if q_hash not in st.session_state:
                    answer = call_chatgpt(user_question, context)
                    st.session_state[q_hash] = answer
                show_gpt_response(st.session_state[q_hash])
        else:
            st.info("No active step to ask about.")

# Main layout
left, center, _ = st.columns([1, 2, 1])
with center:
    team_tasks = df[df['Student Team'] == st.session_state.team_num]
    if team_tasks.empty:
        st.error(f"No subtasks found for Team {st.session_state.team_num}.")
        st.stop()

    if 'task_idx' not in st.session_state:
        st.session_state.task_idx = 0
        st.session_state.step = 0
        st.session_state.subassembly_confirmed_pages = set()
        st.session_state.finalassembly_confirmed_pages = set()
        st.session_state.previous_step_confirmed = False
        st.session_state.collected_parts_confirmed = False

    task_idx = st.session_state.task_idx
    step = st.session_state.step
    current_task = team_tasks.iloc[task_idx]
    context = {
        "subtask_name": current_task["Subtask Name"],
        "subassembly": current_task["Subassembly"],
        "final_assembly": current_task["Final Assembly"],
        "bag": current_task["Bag"],
        "previous_step": None,
    }

    # Visual progress bar
    total_steps = 5
    current_progress = min(step / (total_steps - 1), 1.0)
    st.progress(current_progress, text=f"Step {step+1} of {total_steps}")

    if step == 0:
        st.subheader("Step 1: Collect required parts")
        part_img = f"combined_subtasks/{context['subtask_name']}.png"
        show_image(part_img, "Parts Required")
        if not st.session_state.collected_parts_confirmed:
            if st.button("I have collected all parts"):
                st.session_state.collected_parts_confirmed = True
                st.session_state.step = 1
                st.rerun()

    elif step == 1:
        if context['subassembly']:
            st.subheader("Step 2: Perform subassembly")
            for page in context['subassembly']:
                show_image(f"manuals/page_{page}.png", f"Subassembly - Page {page}")
                if page not in st.session_state.subassembly_confirmed_pages:
                    if st.button(f"✅ Confirm completed Subassembly - Page {page}"):
                        st.session_state.subassembly_confirmed_pages.add(page)
                        st.rerun()
            if len(st.session_state.subassembly_confirmed_pages) == len(context['subassembly']):
                st.success("All subassembly pages completed!")
                st.session_state.step = 2
                st.rerun()
        else:
            st.session_state.step = 2
            st.rerun()

    elif step == 2:
        idx = df.index.get_loc(current_task.name)
        if idx > 0:
            prev_row = df.iloc[idx - 1]
            context['previous_step'] = prev_row['Subtask Name']
            giver_team = prev_row['Student Team']
            receiver_team = st.session_state.team_num
            show_image(f"handling-image/receive-t{giver_team}-t{receiver_team}.png")
            if not st.session_state.previous_step_confirmed:
                if st.button("I have received the product from the previous team"):
                    st.session_state.previous_step_confirmed = True
                    st.session_state.step = 3
                    st.rerun()
        else:
            st.session_state.previous_step_confirmed = True
            st.session_state.step = 3
            st.rerun()

    elif step == 3:
        st.subheader("Step 4: Perform the final assembly")
        for page in context['final_assembly']:
            show_image(f"manuals/page_{page}.png", f"Final Assembly - Page {page}")
            if page not in st.session_state.finalassembly_confirmed_pages:
                if st.button(f"Confirm completed Final Assembly - Page {page}"):
                    st.session_state.finalassembly_confirmed_pages.add(page)
                    st.rerun()

        if len(st.session_state.finalassembly_confirmed_pages) == len(context['final_assembly']):
            st.success("All final assembly pages completed!")
            st.session_state.step = 4
            st.rerun()

    elif step == 4:
        idx = df.index.get_loc(current_task.name)
        if idx + 1 < len(df):
            next_row = df.iloc[idx + 1]
            show_image(f"handling-image/give-t{st.session_state.team_num}-t{next_row['Student Team']}.png")
        else:
            st.subheader("🎉 You are the final team — no further handover needed.")
        st.success("✅ Subtask complete. Great work!")
        if st.button("Next Subtask"):
            if st.session_state.task_idx + 1 < len(team_tasks):
                st.session_state.task_idx += 1
                st.session_state.step = 0
                st.session_state.subassembly_confirmed_pages = set()
                st.session_state.finalassembly_confirmed_pages = set()
                st.session_state.previous_step_confirmed = False
                st.session_state.collected_parts_confirmed = False
                st.rerun()
            else:
                st.info("You have completed all your subtasks.")
