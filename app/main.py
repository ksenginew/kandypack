import streamlit as st
from auth import register_user, login_user

st.set_page_config(page_title="Auth Portal", page_icon="🔐", layout="centered")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

if st.session_state.authenticated:
    st.success(f"Logged in as **{st.session_state.user}**")
    st.button("Sign Out", on_click=logout, type="primary")
    pg = st.navigation([
        st.Page("./routes/0_Dashboard.py"),
        st.Page("./routes/11_Stores.py"),
        st.Page("./routes/12_Routes.py"),
        st.Page("./routes/13_Trucks.py"),
        st.Page("./routes/14_Employees.py"),
        st.Page("./routes/1_Master_Data_and_Fleet.py"),
        st.Page("./routes/2_Customer_Order_Processing.py"),
        st.Page("./routes/3_Railway_Bulk_Transport.py"),
        st.Page("./routes/4_Last_Mile_Road_Delivery.py"),
        st.Page("./routes/5_Delivery_Status_Tracking.py"),
        st.Page("./routes/6_Reporting_and_Analytics.py")
    ])
    pg.run()

else:
    st.title("Welcome")
    tab_signin, tab_signup = st.tabs(["Sign In", "Sign Up"])

    with tab_signin:
        with st.form("signin_form", clear_on_submit=False):
            email_in = st.text_input("Email", placeholder="name@example.com")
            password_in = st.text_input("Password", type="password")
            submit_signin = st.form_submit_button("Sign In", use_container_width=True)

            if submit_signin:
                user, message = login_user(email_in, password_in)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    with tab_signup:
        with st.form("signup_form", clear_on_submit=True):
            new_name = st.text_input("Name", placeholder="John Doe")
            new_email = st.text_input("Email", placeholder="name@example.com")
            new_pass = st.text_input("Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")
            submit_signup = st.form_submit_button("Create Account", use_container_width=True)

            if submit_signup:
                user, message = register_user(new_name, new_email, new_pass, confirm_pass)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
