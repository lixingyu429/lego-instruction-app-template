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
- Previous Step: {context['previous_step']}
"""
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

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# --- Custom Styling ---
st.markdown("""
    <style>
    .centered-container {
        max-width: 800px;
        margin: auto;
        padding: 1rem;
        background-color: #ffffff;
    }
    .floating-tracker {
        position: fixed;
        top: 25%;
        right: 2rem;
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 0 10px rgba(0,0,0,0.2);
        max-width: 250px;
        z-index: 100;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Student Assembly Assistant")

left, center, right = st.columns([1, 2, 1])

with center:
    group_num = st.number_input("Enter your student group number:", min_value=1, step=1)

    if group_num:
        group_tasks = df[df['Student Group'] == group_num]
        if group_tasks.empty:
            st.error(f"No subtasks found for Group {group_num}.")
        else:
            st.success(f"Welcome, Group {group_num}! You have {len(group_tasks)} subtask(s).")

            if 'task_idx' not in st.session_state:
                st.session_state.task_idx = 0
                st.session_state.step = 0
                st.session_state.subassembly_confirmed = False
                st.session_state.finalassembly_confirmed_pages = set()
                st.session_state.previous_step_confirmed = False
                st.session_state.collected_parts_confirmed = False

            current_task = group_tasks.iloc[st.session_state.task_idx]
            context = {
                "subtask_name": current_task["Subtask Name"],
                "subassembly": current_task["Subassembly"],
                "final_assembly": current_task["Final Assembly"],
                "bag": current_task["Bag"],
                "previous_step": None,
                "current_image": None,
            }

            # Toggle Progress Tracker
            show_tracker = st.checkbox("📊 Show Progress Tracker", value=True)

            if show_tracker:
                progress_html = f"""
                <div class="floating-tracker">
                    <h4>🛍️ Progress Tracker</h4>
                    <p><b>Subtask:</b> {context['subtask_name']}</p>
                    <p><b>Bag:</b> {context['bag']}</p>
                    <hr>
                    <b> Collect Parts:</b> {'✅' if st.session_state.collected_parts_confirmed else '❌'}<br>
                """

                if context['subassembly']:
                    progress_html += "<b> Subassembly:</b><br>"
                    for page in context['subassembly']:
                        completed = st.session_state.subassembly_confirmed
                        progress_html += f"&nbsp;&nbsp;&nbsp;Page {page}: {'✅' if completed else '❌'}<br>"

                if context['final_assembly']:
                    progress_html += "<b> Final Assembly:</b><br>"
                    for page in context['final_assembly']:
                        done = page in st.session_state.finalassembly_confirmed_pages
                        progress_html += f"&nbsp;&nbsp;&nbsp;Page {page}: {'✅' if done else '❌'}<br>"

                if st.session_state.step == 4:
                    progress_html += "<b> Handover:</b> ✅"

                progress_html += "</div>"
                st.markdown(progress_html, unsafe_allow_html=True)

        # Step 1: Collect parts
        if st.session_state.step == 0:
            st.subheader("Step 1: Collect required parts")
            part_img = f"combined_subtasks/{context['subtask_name']}.png"
            context['current_image'] = part_img
            show_image(part_img, "Parts Required")
            if st.button("I have collected all parts"):
                st.session_state.collected_parts_confirmed = True
                st.session_state.step = 1
                st.rerun()
            user_question = st.text_input("Ask any questions:")
            if user_question and user_question.lower() != 'n':
                answer = call_chatgpt(user_question, context)
                show_gpt_response(answer)

        # Step 2: Subassembly
        elif st.session_state.step == 1:
            if context['subassembly']:
                st.subheader("Step 2: Perform subassembly")
                for page in context['subassembly']:
                    manual_path = f"manuals/page_{page}.png"
                    context['current_image'] = manual_path
                    show_image(manual_path, f"Subassembly - Page {page}")
                if st.button("I have completed the subassembly"):
                    st.session_state.subassembly_confirmed = True
                    st.session_state.step = 2
                    st.rerun()
                user_question = st.text_input("Ask a question about the subassembly or type 'n' if not ready:")
                if user_question and user_question.lower() != 'n':
                    answer = call_chatgpt(user_question, context)
                    show_gpt_response(answer)
            else:
                st.write("No subassembly required for this subtask.")
                st.session_state.subassembly_confirmed = True
                st.session_state.step = 2
                st.rerun()

        # Step 3: Receive from previous group
        elif st.session_state.step == 2:
            idx = df.index.get_loc(current_task.name)
            if idx > 0:
                prev_row = df.iloc[idx - 1]
                context['previous_step'] = prev_row['Subtask Name']
                st.subheader(f"Step 3: Receive product from Group {prev_row['Student Group']} ({prev_row['Subtask Name']})")
                if st.button("I have received the product from the previous group"):
                    st.session_state.previous_step_confirmed = True
                    st.session_state.step = 3
                    st.rerun()
                user_question = st.text_input("Ask a question about receiving or type 'n' if not ready:")
                if user_question and user_question.lower() != 'n':
                    answer = call_chatgpt(user_question, context)
                    show_gpt_response(answer)
            else:
                st.write("You are the first group — no prior handover needed.")
                st.session_state.previous_step_confirmed = True
                st.session_state.step = 3
                st.rerun()

        # Step 4: Final Assembly
        elif st.session_state.step == 3:
            st.subheader("Step 4: Perform the final assembly")
            subassembly_pages = set(context['subassembly']) if context['subassembly'] else set()
            final_assembly_pages = context['final_assembly']
            for page in final_assembly_pages:
                manual_path = f"manuals/page_{page}.png"
                context['current_image'] = manual_path
                if page in subassembly_pages:
                    st.markdown(f"### ⚠️ Final Assembly - Page {page} (Already part of subassembly)")
                    show_image(manual_path, f"Page {page} Details")
                    if page not in st.session_state.finalassembly_confirmed_pages:
                        if st.button(f"Confirm subassembled part is ready for page {page}"):
                            st.session_state.finalassembly_confirmed_pages.add(page)
                            st.rerun()
                else:
                    show_image(manual_path, f"Final Assembly - Page {page}")
                    if page not in st.session_state.finalassembly_confirmed_pages:
                        if st.button(f"Confirm completed Final Assembly - Page {page}"):
                            st.session_state.finalassembly_confirmed_pages.add(page)
                            st.rerun()
            if len(st.session_state.finalassembly_confirmed_pages) == len(final_assembly_pages):
                st.success("All final assembly pages completed!")
                st.session_state.step = 4
                st.rerun()
            user_question = st.text_input("Ask a question about the final assembly or type 'n' if not ready:")
            if user_question and user_question.lower() != 'n':
                answer = call_chatgpt(user_question, context)
                show_gpt_response(answer)

        # Step 5: Handover
        elif st.session_state.step == 4:
            idx = df.index.get_loc(current_task.name)
            if idx + 1 < len(df):
                next_row = df.iloc[idx + 1]
                st.subheader(f"Final Step: Please hand over the product to Group {next_row['Student Group']} ({next_row['Subtask Name']})")
            else:
                st.subheader("🎉 You are the final group — no further handover needed.")
            st.success("✅ Subtask complete. Great work!")
            if st.button("Next Subtask"):
                if st.session_state.task_idx + 1 < len(group_tasks):
                    st.session_state.task_idx += 1
                    st.session_state.step = 0
                    st.session_state.subassembly_confirmed = False
                    st.session_state.finalassembly_confirmed_pages = set()
                    st.session_state.previous_step_confirmed = False
                    st.session_state.collected_parts_confirmed = False
                    st.rerun()
                else:
                    st.info("You have completed all your subtasks.")
