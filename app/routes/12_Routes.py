import math
import pandas as pd
import streamlit as st
from ui.datatable import render_datatable
from db import fetch_all, fetch_data, execute_query, fetch_one


def fetch_routes(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT 
            r.id, 
            r.route_name, 
            s.store_name, 
            r.service_area, 
            r.max_delivery_time_hrs
        FROM routes AS r
        INNER JOIN stores AS s ON r.store_id = s.id
        ORDER BY r.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))


@st.dialog("Create Route")
def create_route_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    if not stores:
        st.error("Please create at least one store before creating routes.")
        return

    store_options = {str(s.id): s.store_name for s in stores}

    with st.form("create_route_form"):
        selected_store_id = st.selectbox(
            "Store",
            options=list(store_options.keys()),
            format_func=lambda x: store_options.get(x, "Select Store"),
        )
        route_name = st.text_input("Route Name")
        service_area = st.text_input("Service Area")
        max_delivery_time = st.number_input(
            "Max Delivery Time (Hours)", min_value=0.25, max_value=72.0, value=2.0, step=0.25
        )

        submitted = st.form_submit_button("Save Route")
        if submitted:
            if not route_name.strip() or not service_area.strip():
                st.error("Route name and service area are required.")
                return

            execute_query(
                """
                INSERT INTO routes (store_id, route_name, service_area, max_delivery_time_hrs)
                VALUES (%s, %s, %s, %s)
                """,
                (int(selected_store_id), route_name.strip(), service_area.strip(), float(max_delivery_time)),
            )
            st.success("Route created successfully!")
            st.rerun()


@st.dialog("Edit Route")
def edit_route_dialog(route_id: int):
    route = fetch_one("SELECT * FROM routes WHERE id = %s", (route_id,))
    if not route:
        st.error("Route not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    store_options = {str(s.id): s.store_name for s in stores}
    current_store_id = str(route.store_id)

    with st.form("edit_route_form"):
        selected_store_id = st.selectbox(
            "Store",
            options=list(store_options.keys()),
            format_func=lambda x: store_options.get(x, "Select Store"),
            index=list(store_options.keys()).index(current_store_id) if current_store_id in store_options else 0,
        )
        new_name = st.text_input("Route Name", value=route.route_name)
        new_area = st.text_input("Service Area", value=route.service_area)
        new_max_time = st.number_input(
            "Max Delivery Time (Hours)",
            min_value=0.25,
            max_value=72.0,
            value=float(route.max_delivery_time_hrs),
            step=0.25,
        )

        if st.form_submit_button("Save Changes"):
            if not new_name.strip() or not new_area.strip():
                st.error("Route name and service area are required.")
                return

            execute_query(
                """
                UPDATE routes 
                SET store_id = %s, route_name = %s, service_area = %s, max_delivery_time_hrs = %s 
                WHERE id = %s
                """,
                (int(selected_store_id), new_name.strip(), new_area.strip(), float(new_max_time), route_id),
            )
            st.success("Route updated!")
            st.rerun()


@st.dialog("Confirm Deletion")
def delete_route_dialog(route_id: int, route_name: str):
    st.warning(f"Are you sure you want to permanently delete **{route_name}** (ID: {route_id})?")
    st.caption("Warning: Deleting this route will cascade or invalidate linked orders and trucks.")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM routes WHERE id = %s", (route_id,))
            st.rerun()
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


st.set_page_config(page_title="Route Management", layout="wide")
st.title("Route Management")


@st.fragment
def page_body():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM routes")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(
            data=fetch_routes,
            total_count=total_count,
            key="routes_table",
        )

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", use_container_width=True, disabled=(selected_row is None)):
                edit_route_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", use_container_width=True, disabled=(selected_row is None)):
                delete_route_dialog(int(selected_row[0]["id"]), str(selected_row[0]["route_name"]))
        with c4:
            if st.button("Create", use_container_width=True):
                create_route_dialog()


page_body()
