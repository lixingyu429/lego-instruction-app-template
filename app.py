import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64

# version 3
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

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "show_chatgpt_box" not in st.session_state:
    st.session_state.show_chatgpt_box = True

# Initialize session state for steps
if "task_idx" not in st.session_state:
    st.session_state.task_idx = 0
    st.session_state.step = 0
    st.session_state.subassembly_confirmed = False
    st.session_state.finalassembly_confirmed_pages = set()
    st.session_state.previous_step_confirmed = False
    st.session_state.collected_parts_confirmed = False

# UI and logic
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Welcome and Input
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

# Progress Tracker
with st.sidebar:
    st.header("Progress Tracker")
    st.markdown(f"**Student:** {st.session_state.student_name}")
    st.markdown(f"**Team:** {st.session_state.team_num}")
    team_tasks = df[df['Student Team'] == st.session_state.team_num]
    if not team_tasks.empty:
        current_task = team_tasks.iloc[st.session_state.task_idx]
        st.markdown(f"**Subtask:** {current_task['Subtask Name']}")
        st.markdown(f"**Bag:** {current_task['Bag']}")
        st.markdown(f"**Collect Parts:** {'✅' if st.session_state.get('collected_parts_confirmed', False) else '❌'}")
        if current_task['Subassembly']:
            st.markdown("**Subassembly:**")
            for page in current_task['Subassembly']:
                st.markdown(f"- Page {page}: {'✅' if st.session_state.get('subassembly_confirmed', False) else '❌'}")
        if current_task['Final Assembly']:
            st.markdown("**Final Assembly:**")
            for page in current_task['Final Assembly']:
                st.markdown(f"- Page {page}: {'✅' if page in st.session_state.get('finalassembly_confirmed_pages', set()) else '❌'}")
        if st.session_state.get('step', 0) == 4:
            st.markdown("**Handover:** ✅")

# Center panel
left, center, right = st.columns([1, 2, 1])
with center:
    team_tasks = df[df['Student Team'] == st.session_state.team_num]
    if team_tasks.empty:
        st.error(f"No subtasks found for Team {st.session_state.team_num}.")
    else:
        current_task = team_tasks.iloc[st.session_state.task_idx]
        context = {
            "subtask_name": current_task["Subtask Name"],
            "subassembly": current_task["Subassembly"],
            "final_assembly": current_task["Final Assembly"],
            "bag": current_task["Bag"],
            "previous_step": None,
            "current_image": None,
        }

        def show_image(image_path, caption=""):
            if os.path.exists(image_path):
                img = Image.open(image_path)
                st.image(img, caption=caption, use_column_width=True)
            else:
                st.warning(f"Image not found: {image_path}")

        def show_gpt_response(user_question, answer):
            st.session_state.chat_history.append((user_question, answer))
            toggle_label = "🧠 Hide Chat Assistant" if st.session_state.show_chatgpt_box else "🧠 Show Chat Assistant"
            if st.button(toggle_label, key="toggle_chatgpt_visibility"):
                st.session_state.show_chatgpt_box = not st.session_state.show_chatgpt_box
                st.rerun()
            if st.session_state.show_chatgpt_box:
                chat_items = ""
                for q, a in st.session_state.chat_history:
                    chat_items += f"""
                        <div style='margin-bottom: 15px;'>
                            <div style='font-weight: bold;'>🙋 You:</div>
                            <div style='margin-left: 10px;'>{q}</div>
                            <div style='font-weight: bold; margin-top: 5px;'>🧠 ChatGPT:</div>
                            <div style='margin-left: 10px;'>{a}</div>
                        </div>
                        <hr>
                    """
                st.markdown(f"""
                    <div style="
                        position: fixed;
                        bottom: 0;
                        left: 0;
                        width: 100%;
                        height: 300px;
                        background-color: #f0f4ff;
                        border-top: 2px solid #4285f4;
                        padding: 20px;
                        z-index: 9999;
                        box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.15);
                        overflow-y: auto;
                        transition: transform 0.3s ease-in-out;
                    ">
                        <div style="max-height: 100%; overflow-y: auto;">
                            {chat_items}
                        </div>
                    </div>
                    <style>
                        .stApp {{
                            padding-bottom: 330px;
                        }}
                    </style>
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
They asked: \"{{user_question}}\"

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

        # Step logic
        if st.session_state.step == 0:
            st.subheader("Step 1: Collect required parts")
            img_path = f"combined_subtasks/{context['subtask_name']}.png"
            show_image(img_path, "Parts Required")
            if not st.session_state.collected_parts_confirmed:
                if st.button("I have collected all parts"):
                    st.session_state.collected_parts_confirmed = True
                    st.session_state.step = 1
                    st.rerun()
            else:
                user_question = st.text_input("Ask any questions about collecting parts:", key="q0")
                if user_question and user_question.lower() != 'n':
                    answer = call_chatgpt(user_question, context)
                    show_gpt_response(user_question, answer)

        elif st.session_state.step == 1:
            st.subheader("Step 2: Perform subassembly")
            for page in context['subassembly']:
                show_image(f"manuals/page_{page}.png", f"Subassembly - Page {page}")
            if not st.session_state.subassembly_confirmed:
                if st.button("I have completed the subassembly"):
                    st.session_state.subassembly_confirmed = True
                    st.session_state.step = 2
                    st.rerun()
            else:
                user_question = st.text_input("Ask a question about subassembly:", key="q1")
                if user_question and user_question.lower() != 'n':
                    answer = call_chatgpt(user_question, context)
                    show_gpt_response(user_question, answer)

        elif st.session_state.step == 2:
            idx = df.index.get_loc(current_task.name)
            if idx > 0:
                prev_task = df.iloc[idx - 1]
                context['previous_step'] = prev_task['Subtask Name']
                giver_team = prev_task['Student Team']
                show_image(f"handling-image/receive-t{giver_team}-t{st.session_state.team_num}.png")
                st.subheader(f"Receive the semi-finished product from Team {giver_team}")
                if not st.session_state.previous_step_confirmed:
                    if st.button("I have received the product"):
                        st.session_state.previous_step_confirmed = True
                        st.session_state.step = 3
                        st.rerun()
                else:
                    user_question = st.text_input("Ask a question about the handover:", key="q2")
                    if user_question and user_question.lower() != 'n':
                        answer = call_chatgpt(user_question, context)
                        show_gpt_response(user_question, answer)
            else:
                st.write("You are the first team — no handover needed.")
                st.session_state.previous_step_confirmed = True
                st.session_state.step = 3
                st.rerun()

        elif st.session_state.step == 3:
            st.subheader("Step 4: Final Assembly")
            for page in context['final_assembly']:
                show_image(f"manuals/page_{page}.png", f"Final Assembly - Page {page}")
                if page not in st.session_state.finalassembly_confirmed_pages:
                    if st.button(f"Confirm completed page {page}"):
                        st.session_state.finalassembly_confirmed_pages.add(page)
                        st.rerun()
            if len(st.session_state.finalassembly_confirmed_pages) == len(context['final_assembly']):
                st.success("All final assembly steps completed.")
                st.session_state.step = 4
                st.rerun()
            user_question = st.text_input("Ask a question about final assembly:", key="q3")
            if user_question and user_question.lower() != 'n':
                answer = call_chatgpt(user_question, context)
                show_gpt_response(user_question, answer)

        elif st.session_state.step == 4:
            idx = df.index.get_loc(current_task.name)
            if idx + 1 < len(df):
                next_team = df.iloc[idx + 1]['Student Team']
                show_image(f"handling-image/give-t{st.session_state.team_num}-t{next_team}.png")
                st.subheader(f"Handover to Team {next_team}")
            else:
                st.subheader("🎉 Final team — no handover needed.")
            st.success("✅ Subtask complete!")
            if st.button("Next Subtask"):
                if st.session_state.task_idx + 1 < len(team_tasks):
                    st.session_state.task_idx += 1
                    st.session_state.step = 0
                    st.session_state.subassembly_confirmed = False
                    st.session_state.finalassembly_confirmed_pages = set()
                    st.session_state.previous_step_confirmed = False
                    st.session_state.collected_parts_confirmed = False
                    st.rerun()
                else:
                    st.info("You have completed all subtasks.")
