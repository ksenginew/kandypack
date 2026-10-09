import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_routes(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT r.id, r.route_name, s.store_name, r.service_area, r.max_delivery_time_hrs
        FROM routes AS r
        JOIN stores AS s ON r.store_id = s.id
        ORDER BY r.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Route")
def create_route_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    if not stores:
        st.error("Create a store first.")
        return
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("create_route_form"):
        name = st.text_input("Route Name")
        store_id = st.selectbox("Store", options=list(store_map.keys()), format_func=lambda x: store_map[x])
        service_area = st.text_input("Service Area")
        max_time = st.number_input("Max Delivery Time (Hours)", min_value=0.25, max_value=48.0, value=4.0, step=0.5)

        if st.form_submit_button("Save Route"):
            if not name.strip() or not service_area.strip():
                st.error("Route name and service area are required.")
                return
            execute_query(
                "INSERT INTO routes (route_name, store_id, service_area, max_delivery_time_hrs) VALUES (%s, %s, %s, %s);",
                (name.strip(), int(store_id), service_area.strip(), float(max_time))
            )
            st.success("Route created!")
            st.rerun()

@st.dialog("Edit Route")
def edit_route_dialog(route_id: int):
    route = fetch_one("SELECT * FROM routes WHERE id = %s;", (route_id,))
    if not route:
        st.error("Route not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("edit_route_form"):
        name = st.text_input("Route Name", value=route.route_name)
        store_id = st.selectbox("Store", options=list(store_map.keys()), format_func=lambda x: store_map[x], index=list(store_map.keys()).index(str(route.store_id)) if str(route.store_id) in store_map else 0)
        service_area = st.text_input("Service Area", value=route.service_area)
        max_time = st.number_input("Max Delivery Time (Hours)", min_value=0.25, max_value=48.0, value=float(route.max_delivery_time_hrs), step=0.5)

        if st.form_submit_button("Update Route"):
            execute_query(
                "UPDATE routes SET route_name = %s, store_id = %s, service_area = %s, max_delivery_time_hrs = %s WHERE id = %s;",
                (name.strip(), int(store_id), service_area.strip(), float(max_time), route_id)
            )
            st.success("Route updated!")
            st.rerun()

@st.dialog("Delete Route")
def delete_route_dialog(route_id: int, route_name: str):
    st.warning(f"Are you sure you want to delete route **{route_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM routes WHERE id = %s;", (route_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_routes_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM routes;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_routes, total_count=total_count, key="routes_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_route_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_route_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_route_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_route_dialog(int(selected_row[0]["id"]), str(selected_row[0]["route_name"]))
        with c4:
            if st.button("Create", key="create_route_btn", use_container_width=True):
                create_route_dialog()