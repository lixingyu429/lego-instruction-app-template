import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64

# --- OpenAI Setup ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Please set your OPENAI_API_KEY environment variable!")
    st.stop()
client = OpenAI(api_key=api_key)

# --- Load Data ---
CSV_FILE = "lego_subtasks.csv"
if not os.path.exists(CSV_FILE):
    st.error(f"CSV file '{CSV_FILE}' not found.")
    st.stop()

df = pd.read_csv(CSV_FILE)
df['Subassembly'] = df['Subassembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])
df['Final Assembly'] = df['Final Assembly'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else [])

# --- Helper Functions ---

def show_image(image_path, caption=""):
    if os.path.exists(image_path):
        img = Image.open(image_path)
        st.image(img, caption=caption, use_column_width=True)
    else:
        st.warning(f"Image not found: {image_path}")

def call_chatgpt(user_question, context):
    # Collect all images (subassembly + final assembly)
    image_messages = []
    for page in context.get('subassembly', []):
        path = f"manuals/page_{page}.png"
        if os.path.exists(path):
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}
            })
    for page in context.get('final_assembly', []):
        path = f"manuals/page_{page}.png"
        if os.path.exists(path):
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}
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

# --- UI Setup ---
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Initialize session state for team info
if "team_num" not in st.session_state or "student_name" not in st.session_state:
    st.header("Welcome to the Assembly Task")
    team_num_input = st.number_input("Enter your student team number:", min_value=1, step=1)
    student_name_input = st.text_input("Enter your name:")
    if student_name_input and team_num_input:
        st.session_state.team_num = team_num_input
        st.session_state.student_name = student_name_input
        st.success("Information saved. You can proceed.")
        st.experimental_rerun()
    else:
        st.warning("Please enter both your name and team number to continue.")
    st.stop()

# Initialize chat popup states
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Sidebar progress tracker
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
                completed = st.session_state.get('subassembly_confirmed', False)
                st.markdown(f"- Page {page}: {'✅' if completed else '❌'}")
        if current_task_preview['Final Assembly']:
            st.markdown("**Final Assembly:**")
            for page in current_task_preview['Final Assembly']:
                done = page in st.session_state.get('finalassembly_confirmed_pages', set())
                st.markdown(f"- Page {page}: {'✅' if done else '❌'}")
        if st.session_state.get('step', 0) == 4:
            st.markdown("**Handover:** ✅")

# Main app area
team_num = st.session_state.team_num
student_name = st.session_state.student_name
team_tasks = df[df['Student Team'] == team_num]

if team_tasks.empty:
    st.error(f"No subtasks found for Team {team_num}.")
    st.stop()

if 'task_idx' not in st.session_state:
    st.session_state.task_idx = 0
    st.session_state.step = 0
    st.session_state.subassembly_confirmed = False
    st.session_state.finalassembly_confirmed_pages = set()
    st.session_state.previous_step_confirmed = False
    st.session_state.collected_parts_confirmed = False

current_task = team_tasks.iloc[st.session_state.task_idx]
context = {
    "subtask_name": current_task["Subtask Name"],
    "subassembly": current_task["Subassembly"],
    "final_assembly": current_task["Final Assembly"],
    "bag": current_task["Bag"],
    "previous_step": None,
    "current_image": None,
}

left, center, right = st.columns([1, 2, 1])
with center:
    # Step 0: Collect parts
    if st.session_state.step == 0:
        st.subheader("Step 1: Collect required parts")
        part_img = f"combined_subtasks/{context['subtask_name']}.png"
        context['current_image'] = part_img
        show_image(part_img, "Parts Required")

        if not st.session_state.get('collected_parts_confirmed', False):
            if st.button("I have collected all parts"):
                st.session_state.collected_parts_confirmed = True
                st.session_state.step = 1
                st.experimental_rerun()
        else:
            st.info("You can ask questions using the ChatGPT popup icon at the bottom-right.")

    # Step 1: Subassembly
    elif st.session_state.step == 1:
        if context['subassembly']:
            st.subheader("Step 2: Perform subassembly")
            for page in context['subassembly']:
                manual_path = f"manuals/page_{page}.png"
                context['current_image'] = manual_path
                show_image(manual_path, f"Subassembly - Page {page}")

            if not st.session_state.get('subassembly_confirmed', False):
                if st.button("I have completed the subassembly"):
                    st.session_state.subassembly_confirmed = True
                    st.session_state.step = 2
                    st.experimental_rerun()
            else:
                st.info("You can ask questions using the ChatGPT popup icon at the bottom-right.")
        else:
            st.write("No subassembly required for this subtask.")
            st.session_state.subassembly_confirmed = True
            st.session_state.step = 2
            st.experimental_rerun()

    # Step 2: Receive product
    elif st.session_state.step == 2:
        idx = df.index.get_loc(current_task.name)
        if idx > 0:
            prev_row = df.iloc[idx - 1]
            context['previous_step'] = prev_row['Subtask Name']
            giver_team = prev_row['Student Team']
            receiver_team = team_num
            receive_img_path = f"handling-image/receive-t{giver_team}-t{receiver_team}.png"

            st.subheader(f"Receive the semi-finished product from Team {giver_team}")
            show_image(receive_img_path)

            if not st.session_state.get('previous_step_confirmed', False):
                if st.button("I have received the product from the previous team"):
                    st.session_state.previous_step_confirmed = True
                    st.session_state.step = 3
                    st.experimental_rerun()
            else:
                st.info("You can ask questions using the ChatGPT popup icon at the bottom-right.")
        else:
            st.write("You are the first team — no prior handover needed.")
            st.session_state.previous_step_confirmed = True
            st.session_state.step = 3
            st.experimental_rerun()

    # Step 3: Final assembly
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
                        st.experimental_rerun()
            else:
                show_image(manual_path, f"Final Assembly - Page {page}")
                if page not in st.session_state.finalassembly_confirmed_pages:
                    if st.button(f"Confirm completed Final Assembly - Page {page}"):
                        st.session_state.finalassembly_confirmed_pages.add(page)
                        st.experimental_rerun()

        if len(st.session_state.finalassembly_confirmed_pages) == len(final_assembly_pages):
            st.success("All final assembly pages completed!")
            st.session_state.step = 4
            st.experimental_rerun()

        st.info("You can ask questions using the ChatGPT popup icon at the bottom-right.")

    # Step 4: Final handover
    elif st.session_state.step == 4:
        idx = df.index.get_loc(current_task.name)
        if idx + 1 < len(df):
            next_row = df.iloc[idx + 1]
            receiver_team = next_row['Student Team']
            giver_team = team_num
            give_img_path = f"handling-image/give-t{giver_team}-t{receiver_team}.png"

            st.subheader(f"Final Step: Handover the semi-finished product to Team {receiver_team}")
            show_image(give_img_path)
        else:
            st.subheader("🎉 You are the final team — no further handover needed.")

        st.success("✅ Subtask complete. Great work!")
        if st.button("Next Subtask"):
            if st.session_state.task_idx + 1 < len(team_tasks):
                st.session_state.task_idx += 1
                st.session_state.step = 0
                st.session_state.subassembly_confirmed = False
                st.session_state.finalassembly_confirmed_pages = set()
                st.session_state.previous_step_confirmed = False
                st.session_state.collected_parts_confirmed = False
                st.experimental_rerun()
            else:
                st.info("You have completed all your subtasks.")

# --- Chat Popup UI ---

# CSS styles for chat toggle button and chat popup window
st.markdown("""
<style>
.chat-toggle-button {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background-color: #4285f4;
    color: white;
    border-radius: 50%;
    width: 60px;
    height: 60px;
    font-size: 30px;
    border: none;
    cursor: pointer;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}
.chat-popup {
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 360px;
    max-height: 500px;
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 10px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    z-index: 1000;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.chat-header {
    background-color: #4285f4;
    color: white;
    padding: 10px;
    font-weight: bold;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.chat-messages {
    flex-grow: 1;
    padding: 10px;
    overflow-y: auto;
    font-size: 14px;
    background-color: #f9f9f9;
}
.chat-input-area {
    border-top: 1px solid #ddd;
    padding: 10px;
    display: flex;
    gap: 8px;
}
.chat-message-user {
    color: #333;
    margin-bottom: 8px;
}
.chat-message-assistant {
    color: #4285f4;
    margin-bottom: 8px;
}
.close-btn {
    cursor: pointer;
    font-weight: bold;
    font-size: 20px;
    user-select: none;
}
</style>
""", unsafe_allow_html=True)

# Toggle chat popup state
def toggle_chat():
    st.session_state.chat_open = not st.session_state.chat_open
    st.experimental_rerun()

# Chat toggle button
toggle_label = "💬" if not st.session_state.chat_open else "✖️"
if st.button(toggle_label, key="chat_toggle_button", help="Toggle ChatGPT popup", css_class="chat-toggle-button"):
    toggle_chat()

# Render chat popup if open
if st.session_state.chat_open:
    with st.container():
        st.markdown("""
        <div class="chat-popup">
            <div class="chat-header">
                ChatGPT Assistant
                <span class="close-btn" onclick="document.querySelector('button[key=chat_toggle_button]').click()">×</span>
            </div>
        """, unsafe_allow_html=True)

        # Display messages
        messages_html = ""
        for msg in st.session_state.chat_messages:
            role = msg["role"]
            content = msg["content"].replace("\n", "<br>")
            css_class = "chat-message-user" if role == "user" else "chat-message-assistant"
            messages_html += f'<div class="{css_class}"><strong>{role.title()}:</strong> {content}</div>'
        st.markdown(f'<div class="chat-messages">{messages_html}</div>', unsafe_allow_html=True)

        # Chat input form
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_input("Your question:", placeholder="Ask ChatGPT...", key="chat_input_box")
            submit = st.form_submit_button("Send")
            if submit and user_input.strip():
                # Add user message
                st.session_state.chat_messages.append({"role": "user", "content": user_input.strip()})
                # Call GPT
                response = call_chatgpt(user_input.strip(), context)
                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                st.experimental_rerun()

        st.markdown("</div>", unsafe_allow_html=True)
