import streamlit as st
import time
import warnings
warnings.filterwarnings("ignore")
from openai import OpenAI, RateLimitError, APIError, Timeout

# Title
st.title("LEGO Instruction Assistant")

# Add image below the title
st.image("truck-review.gif", use_column_width=True)

# Session state setup
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Login screen
if not st.session_state.logged_in:
    user_id = st.text_input("Enter your User ID")
    password = st.text_input("Enter your Password", type="password")

    if st.button("Login"):
        if password == "lego123":
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
        else:
            st.error("Invalid password.")
else:
    st.success(f"Welcome, {st.session_state.user_id}!")
    st.write(f"Your User ID is: **{st.session_state.user_id}**")

    st.markdown("---")
    st.header("Ask your LEGO Assistant")

    # Initialize OpenAI client
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display messages using chat-like UI
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Collect user input at the bottom
    user_input = st.chat_input("Type your question here:")

    if user_input:
        # Append user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Retry mechanism
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": "You are a helpful assistant for LEGO instructions. Answer clearly and guide students step by step."}] + st.session_state.messages
                )
                reply = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reply})
                with st.chat_message("assistant"):
                    st.markdown(reply)
                break  # success

            except RateLimitError:
                st.warning(f"Rate limit reached. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2

            except (APIError, Timeout) as e:
                st.error(f"API error occurred: {str(e)}")
                break

            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
                break
