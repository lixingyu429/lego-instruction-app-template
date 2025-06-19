import streamlit as st
import time
import re
import os
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

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "page_number" in msg:
                page_path = f"manuals/page_{msg['page_number']}.png"
                if os.path.exists(page_path):
                    st.image(page_path, caption=f"Manual Page {msg['page_number']}", use_column_width=True)

    # User input at bottom
    user_input = st.chat_input("Type your question here:")

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Detect if user requested a manual page (e.g., "page 3")
        page_match = re.search(r'page\s*(\d+)', user_input, re.IGNORECASE)
        requested_page = int(page_match.group(1)) if page_match else None

        if requested_page:
            page_path = f"manuals/page_{requested_page}.png"
            if os.path.exists(page_path):
                # Append assistant message with page info
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Here is manual page {requested_page}.",
                    "page_number": requested_page
                })
                with st.chat_message("assistant"):
                    st.markdown(f"Here is manual page {requested_page}:")
                    st.image(page_path, caption=f"Manual Page {requested_page}", use_column_width=True)
            else:
                with st.chat_message("assistant"):
                    st.markdown(f"Sorry, manual page {requested_page} does not exist.")
        else:
            # If no manual page requested, query OpenAI
            max_retries = 5
            retry_delay = 2
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant for LEGO instructions. Answer clearly and guide students step by step."}
                        ] + st.session_state.messages
                    )
                    reply = response.choices[0].message.content
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    with st.chat_message("assistant"):
                        st.markdown(reply)
                    break  # success, exit retry loop

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
