import math
import pandas as pd
import streamlit as st
from ui.datatable import render_datatable
from db import fetch_all, fetch_data, get_connection, execute_query, fetch_one


def fetch_stores(limit: int, offset: int) -> pd.DataFrame:
    query = f"""
        SELECT s.id, s.store_name, s.address, m.name AS manager_name
        FROM stores AS s
        LEFT JOIN users AS m ON s.manager_id = m.id
        ORDER BY id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Store")
def create_store_dialog():
    form = st.form("create_store_form")
    name = form.text_input("Store Name")
    address = form.text_area("Address")
    managers = fetch_all("SELECT id, name FROM users WHERE role = 'store_manager'")
    manager_options = {str(manager.id): manager.name for manager in managers}
    selected_manager = form.selectbox("Assign Manager", options=list(manager_options.keys()), format_func=lambda x: manager_options[x] if x in manager_options else "Select a Manager")
    if form.form_submit_button("Save Store") and name and address:
        execute_query(
            "INSERT INTO stores (store_name, address, manager_id) VALUES (%s, %s, %s)",
            (name.strip(), address.strip(), selected_manager)
        )
        st.success("Store added successfully!")
        st.rerun()

@st.dialog("Edit Store")
def edit_store_dialog(store_id: int):
    store = fetch_one("SELECT * FROM stores WHERE id = %s", (store_id,))
    if not store:
        st.error("Store not found.")
        return

    with st.form("edit_store_form"):
        new_name = st.text_input("Store Name", value=store.store_name)
        new_address = st.text_area("Address", value=store.address)
        managers = fetch_all("SELECT id, name FROM users WHERE role = 'store_manager'")
        manager_options = {str(manager.id): manager.name for manager in managers}
        new_manager = st.selectbox("Assign Manager", options=list(manager_options.keys()), format_func=lambda x: manager_options[x] if x in manager_options else "Select a Manager", index=list(manager_options.keys()).index(str(store.manager_id)) if str(store.manager_id) in manager_options else 0)
        if st.form_submit_button("Save Changes"):
            execute_query(
                "UPDATE stores SET store_name = %s, address = %s, manager_id = %s WHERE id = %s",
                (new_name.strip(), new_address.strip(), new_manager, store_id)
            )
            st.success("Store updated!")
            st.rerun()

@st.dialog("Confirm Deletion")
def delete_store_dialog(store_id: int, store_name: str):
    st.warning(f"Are you sure you want to permanently delete **{store_name}** (ID: {store_id})?")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM stores WHERE id = %s", (store_id,))
            st.rerun()
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

st.set_page_config(page_title="Store Management", layout="wide")
st.title("Store Management")

@st.fragment
def page_body():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM stores")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(
            data=fetch_stores,
            total_count=total_count,
            key="stores_table",
        )

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", use_container_width=True, disabled=(selected_row is None)):
                edit_store_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", use_container_width=True, disabled=(selected_row is None)):
                delete_store_dialog(int(selected_row[0]["id"]), str(selected_row[0]["store_name"]))
        with c4:
            if st.button("Create", use_container_width=True):
                create_store_dialog()

page_body()
