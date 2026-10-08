import hashlib
import pandas as pd
import streamlit as st
from auth import register_user
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

USER_ROLES = ["admin", "sales", "logistics", "store_manager", "user"]

def fetch_users(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT id::text, name, email, role, email_verified, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create User")
def create_user_dialog():
    with st.form("create_user_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", USER_ROLES, index=USER_ROLES.index("user"))

        if st.form_submit_button("Create User"):
            if not name.strip() or not email.strip() or not password:
                st.error("Name, email, and password are required.")
                return
            register_user(name.strip(), email.strip(), password, role)
            st.success("User created successfully!")
            st.rerun()

@st.dialog("Edit User")
def edit_user_dialog(user_id: str):
    user = fetch_one("SELECT * FROM users WHERE id = %s;", (user_id,))
    if not user:
        st.error("User not found.")
        return

    with st.form("edit_user_form"):
        role = st.selectbox("Role", USER_ROLES, index=USER_ROLES.index(user.role) if user.role in USER_ROLES else 0)

        if st.form_submit_button("Save Changes"):
            execute_query("UPDATE users role = %s WHERE id = %s;", (role, user_id))
            st.success("User updated!")
            st.rerun()

@st.dialog("Confirm User Deletion")
def delete_user_dialog(user_id: str, user_name: str):
    st.warning(f"Are you sure you want to delete user **{user_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM users WHERE id = %s;", (user_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_users_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM users;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_users, total_count=total_count, key="users_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_user_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_user_dialog(str(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_user_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_user_dialog(str(selected_row[0]["id"]), str(selected_row[0]["name"]))
        with c4:
            if st.button("Create", key="create_user_btn", use_container_width=True):
                create_user_dialog()
