import streamlit as st
import pandas as pd
import os
import ast
from PIL import Image
from openai import OpenAI
import base64

# --- Inject CSS for fixed-position ChatGPT assistant ---
st.markdown(
    """
    <style>
    /* container for the floating assistant */
    .fixed-chat {
        position: fixed;
        top: 80px;          /* adjust this to move up/down */
        right: 20px;        /* adjust this to move left/right */
        width: 300px;       /* width of the assistant panel */
        max-height: calc(100% - 100px);
        overflow-y: auto;   /* scroll inside panel if content overflows */
        z-index: 1000;      /* above other Streamlit elements */
        background-color: #ffffff;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    /* hide default Streamlit column padding so panel hugs the edge */
    .fixed-chat .css-1l406b7 { padding: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

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
            b64 = base64.b64encode(open(img_path, "rb").read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
            })
    for page in context.get('final_assembly', []):
        img_path = f"manuals/page_{page}.png"
        if os.path.exists(img_path):
            b64 = base64.b64encode(open(img_path, "rb").read()).decode()
            image_messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
            })

    messages = [
        {"role": "system", "content": "You are a helpful assistant for a student performing a physical assembly task."},
        {"role": "user", "content": [
            {"type": "text", "text": f"""
You are helping a student on subtask: {context['subtask_name']}.
They asked: \"{user_question}\"

Additional info:
- Bag: {context['bag']}
- Subassembly Pages: {context['subassembly']}
- Final Assembly Pages: {context['final_assembly']}
- Previous Step: {context['previous_step']}
"""}
        ] + image_messages}
    ]

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# --- Main flow (welcome & task logic) ---
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

with st.sidebar:
    st.header("Progress Tracker")
    st.markdown(f"**Student:** {st.session_state.student_name}")
    st.markdown(f"**Team:** {st.session_state.team_num}")
    preview = df[df['Student Team'] == st.session_state.team_num]
    if 'task_idx' in st.session_state and not preview.empty:
        cur = preview.iloc[st.session_state.task_idx]
        st.markdown(f"**Subtask:** {cur['Subtask Name']}")
        st.markdown(f"**Bag:** {cur['Bag']}")
        st.markdown(f"**Parts Collected:** {'✅' if st.session_state.get('collected_parts_confirmed', False) else '❌'}")
        # … show subassembly & final assembly status similarly …

left, center = st.columns([1, 3])

with center:
    # … all your step-by-step UI from Step 1 through handover …
    pass  # (Keep your existing logic here.)

# --- Floating ChatGPT assistant ---
# We wrap the expander in a div with our .fixed-chat class so it stays put
st.markdown('<div class="fixed-chat">', unsafe_allow_html=True)
with st.expander("💬 ChatGPT Assistant", expanded=True):
    step_keys = ["q_step0", "q_step1", "q_step2", "q_step3"]
    current_step = st.session_state.get("step", 0)
    if current_step in range(len(step_keys)):
        key = step_keys[current_step]
        user_question = st.text_input("Ask ChatGPT a question:", key=key)
        if user_question and user_question.lower() != 'n':
            # build context same way your main code does...
            context = {
                "subtask_name": st.session_state.get("current_task_name", ""),
                "subassembly": st.session_state.get("current_subassembly", []),
                "final_assembly": st.session_state.get("current_final_assembly", []),
                "bag": st.session_state.get("current_bag", ""),
                "previous_step": st.session_state.get("previous_step_name", None)
            }
            answer = call_chatgpt(user_question, context)
            show_gpt_response(answer)
    else:
        st.write("No active step for ChatGPT questions.")
st.markdown('</div>', unsafe_allow_html=True)
