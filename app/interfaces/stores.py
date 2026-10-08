import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_stores(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT s.id, s.store_name, s.address, m.name AS manager_name
        FROM stores AS s
        LEFT JOIN users AS m ON s.manager_id = m.id
        ORDER BY s.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Store")
def create_store_dialog():
    managers = fetch_all("SELECT id, name FROM users WHERE role = 'store_manager' ORDER BY name ASC")
    manager_options = {str(m.id): m.name for m in managers}

    with st.form("create_store_form"):
        name = st.text_input("Store Name")
        address = st.text_area("Address")
        selected_manager = st.selectbox(
            "Assign Manager",
            options=["None"] + list(manager_options.keys()),
            format_func=lambda x: manager_options.get(x, "Unassigned")
        )
        if st.form_submit_button("Save Store") and name and address:
            mgr_id = None if selected_manager == "None" else selected_manager
            execute_query(
                "INSERT INTO stores (store_name, address, manager_id) VALUES (%s, %s, %s);",
                (name.strip(), address.strip(), mgr_id)
            )
            st.success("Store added successfully!")
            st.rerun()

@st.dialog("Edit Store")
def edit_store_dialog(store_id: int):
    store = fetch_one("SELECT * FROM stores WHERE id = %s;", (store_id,))
    if not store:
        st.error("Store not found.")
        return

    managers = fetch_all("SELECT id, name FROM users WHERE role = 'store_manager' ORDER BY name ASC")
    manager_options = {str(m.id): m.name for m in managers}
    current_mgr = str(store.manager_id) if store.manager_id else "None"

    with st.form("edit_store_form"):
        new_name = st.text_input("Store Name", value=store.store_name)
        new_address = st.text_area("Address", value=store.address)
        all_opts = ["None"] + list(manager_options.keys())
        new_manager = st.selectbox(
            "Assign Manager",
            options=all_opts,
            format_func=lambda x: manager_options.get(x, "Unassigned"),
            index=all_opts.index(current_mgr) if current_mgr in all_opts else 0
        )
        if st.form_submit_button("Save Changes"):
            mgr_id = None if new_manager == "None" else new_manager
            execute_query(
                "UPDATE stores SET store_name = %s, address = %s, manager_id = %s WHERE id = %s;",
                (new_name.strip(), new_address.strip(), mgr_id, store_id)
            )
            st.success("Store updated!")
            st.rerun()

@st.dialog("Confirm Store Deletion")
def delete_store_dialog(store_id: int, store_name: str):
    st.warning(f"Are you sure you want to permanently delete store **{store_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM stores WHERE id = %s;", (store_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_stores_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM stores;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_stores, total_count=total_count, key="stores_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_store_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_store_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_store_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_store_dialog(int(selected_row[0]["id"]), str(selected_row[0]["store_name"]))
        with c4:
            if st.button("Create", key="create_store_btn", use_container_width=True):
                create_store_dialog()