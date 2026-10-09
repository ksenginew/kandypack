import streamlit as st
from auth import register_user, login_user

st.set_page_config(page_title="Rail and Road-based Supply Chain Distribution System", page_icon="🚆", layout="centered")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

if st.session_state.authenticated:
    # Sidebar user profile badge and logout
    user_info = st.session_state.user
    user_role = user_info.role

    with st.sidebar:
        st.write(f"Logged in as **{user_info.name}**")
        st.caption(f"Role: `{user_role.upper()}`")
        st.button("Sign Out", on_click=logout, use_container_width=True)
        st.divider()

    # Domain-organized Navigation Hierarchy
    nav_sections = {
        "Overview": [
            st.Page("routes/00_Dashboard.py", title="Dashboard", icon="📊", default=True),
        ],
        "Sales & Commerce": [
            st.Page("routes/01_Sales_Orders.py", title="Orders & Items", icon="🛒"),
            st.Page("routes/02_Sales_Catalog.py", title="Customers & Products", icon="👥"),
        ],
        "Logistics & Dispatch": [
            st.Page("routes/03_Train_Logistics.py", title="Rail Bulk Manifest", icon="🚆"),
            st.Page("routes/04_Truck_Logistics.py", title="Last-Mile Dispatch", icon="📦"),
        ],
        "Fleet & Operations": [
            st.Page("routes/05_Fleet_Routes.py", title="Fleet & Routes", icon="🚛"),
            st.Page("routes/06_Staff.py", title="Staff & Drivers", icon="👷"),
        ],
    }

    # Add Admin section conditionally based on RBAC
    if user_role == "admin":
        nav_sections["Administration"] = [
            st.Page("routes/07_Admin_Stores.py", title="Store Hubs", icon="🏬"),
            st.Page("routes/08_Admin_Users.py", title="User Access Control", icon="🔑"),
            st.Page("routes/09_Reports.py", title="Reports & Analytics", icon="📈"),
            st.Page("routes/10_Assistant.py", title="Assistant Dashboard", icon="🤖"),
        ]

    # Non-admin users with specific roles can also be filtered if needed
    pg = st.navigation(nav_sections)
    pg.run()

else:
    st.title("Rail and Road-based Supply Chain Distribution System")
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
