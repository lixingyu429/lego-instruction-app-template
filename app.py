import streamlit as st

# Title
st.title("Student Login Portal")

# Session state setup
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Login screen
if not st.session_state.logged_in:
    user_id = st.text_input("Enter your User ID")
    password = st.text_input("Enter your Password", type="password")
    
    if st.button("Login"):
        if password == "lego123":  # You can replace with your own logic
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
        else:
            st.error("Invalid password.")
else:
    # After login
    st.success(f"Welcome, {st.session_state.user_id}!")
    st.write(f"Your User ID is: **{st.session_state.user_id}**")
