import streamlit as st
import openai

# Title
st.title("LEGO Instruction Assistant")

# Session state setup
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Login screen
if not st.session_state.logged_in:
    user_id = st.text_input("Enter your User ID")
    password = st.text_input("Enter your Password", type="password")
    
    if st.button("Login"):
        if password == "lego123":  # Replace with your own logic
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
        else:
            st.error("Invalid password.")
else:
    st.success(f"Welcome, {st.session_state.user_id}!")
    st.write(f"Your User ID is: **{st.session_state.user_id}**")

    st.markdown("---")
    st.header("Ask your LEGO Assistant")

    # Set your OpenAI API key (use Streamlit secrets for security in deployment)
    openai.api_key = st.secrets["OPENAI_API_KEY"]

    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []

    user_input = st.text_input("Type your question here:")

    if st.button("Send") and user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Call GPT-4o
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for LEGO instructions. Answer clearly and help students follow the steps."}
            ] + st.session_state.messages
        )

        reply = response["choices"][0]["message"]["content"]
        st.session_state.messages.append({"role": "assistant", "content": reply})

    # Display conversation
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.write(f"👤 You: {msg['content']}")
        else:
            st.write(f"🤖 Assistant: {msg['content']}")