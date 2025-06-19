import streamlit as st
import time
import re
import os
from openai import OpenAI, RateLimitError, APIError, Timeout

st.title("LEGO Instruction Assistant")

st.image("truck-review.gif", use_column_width=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

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

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Show chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Show manual page if present
            if "page_number" in msg:
                page_path = f"manuals/page_{msg['page_number']}.png"
                if os.path.exists(page_path):
                    st.image(page_path, caption=f"Manual Page {msg['page_number']}", use_column_width=True)

    user_input = st.chat_input("Type your question here:")

    if user_input:
        # Append user message and show it
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # System prompt instructs GPT to include page number explicitly in response
                system_prompt = (
                    "You are a helpful assistant for LEGO instructions. "
                    "Answer clearly and guide students step-by-step. "
                    "If the user asks about a manual page, include a line exactly like "
                    "'PageNumber: X' where X is the page number. "
                    "If no page is referenced, include 'PageNumber: None' in your response."
                )

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt}
                    ] + st.session_state.messages
                )
                reply = response.choices[0].message.content

                # Extract page number from GPT reply
                page_match = re.search(r"PageNumber:\s*(\d+)", reply)
                page_number = int(page_match.group(1)) if page_match else None

                # Remove the 'PageNumber: X' line from the reply text before displaying
                reply_text = re.sub(r"PageNumber:\s*\d+", "", reply).strip()

                # Append assistant message with optional page number info
                message_entry = {"role": "assistant", "content": reply_text}
                if page_number is not None:
                    message_entry["page_number"] = page_number

                st.session_state.messages.append(message_entry)

                # Show assistant reply
                with st.chat_message("assistant"):
                    st.markdown(reply_text)

                    # If GPT included a page number, try to display that manual page image
                    if page_number is not None:
                        page_path = f"manuals/page_{page_number}.png"
                        if os.path.exists(page_path):
                            st.image(page_path, caption=f"Manual Page {page_number}", use_column_width=True)
                        else:
                            st.markdown(f"⚠️ Manual page {page_number} does not exist.")

                break  # exit retry loop on success

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
