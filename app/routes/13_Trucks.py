import math
import pandas as pd
import streamlit as st
from ui.datatable import render_datatable
from db import fetch_all, fetch_data, execute_query, fetch_one

VEHICLE_STATUS_OPTIONS = ["Active", "Maintenance", "Decommissioned"]


def fetch_trucks(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT 
            t.id, 
            t.license_plate, 
            s.store_name, 
            t.capacity, 
            t.vehicle_status,
            COALESCE(r.route_name, 'Unassigned') AS route_name
        FROM trucks AS t
        INNER JOIN stores AS s ON t.store_id = s.id
        LEFT JOIN routes AS r ON t.route_id = r.id
        ORDER BY t.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))


@st.dialog("Create Truck")
def create_truck_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    if not stores:
        st.error("Please create at least one store before adding trucks.")
        return

    store_options = {str(s.id): s.store_name for s in stores}
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC")
    route_options = {"None": "None"}
    route_options.update({str(r.id): r.route_name for r in routes})

    with st.form("create_truck_form"):
        plate = st.text_input("License Plate")
        selected_store = st.selectbox("Store", options=list(store_options.keys()), format_func=lambda x: store_options[x])
        capacity = st.number_input("Capacity (Volume/Weight units)", min_value=1.0, max_value=10000.0, value=100.0, step=10.0)
        status = st.selectbox("Vehicle Status", options=VEHICLE_STATUS_OPTIONS, index=0)
        selected_route = st.selectbox("Assigned Route (Optional)", options=list(route_options.keys()), format_func=lambda x: route_options[x])

        if st.form_submit_button("Save Truck"):
            if not plate.strip():
                st.error("License plate is required.")
                return

            route_id_val = int(selected_route) if selected_route != "None" else None
            execute_query(
                """
                INSERT INTO trucks (store_id, license_plate, capacity, vehicle_status, route_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (int(selected_store), plate.strip().upper(), float(capacity), status, route_id_val),
            )
            st.success("Truck registered successfully!")
            st.rerun()


@st.dialog("Edit Truck")
def edit_truck_dialog(truck_id: int):
    truck = fetch_one("SELECT * FROM trucks WHERE id = %s", (truck_id,))
    if not truck:
        st.error("Truck not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    store_options = {str(s.id): s.store_name for s in stores}
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC")
    route_options = {"None": "None"}
    route_options.update({str(r.id): r.route_name for r in routes})

    with st.form("edit_truck_form"):
        new_plate = st.text_input("License Plate", value=truck.license_plate)
        curr_store_id = str(truck.store_id)
        selected_store = st.selectbox(
            "Store",
            options=list(store_options.keys()),
            format_func=lambda x: store_options[x],
            index=list(store_options.keys()).index(curr_store_id) if curr_store_id in store_options else 0,
        )
        new_capacity = st.number_input(
            "Capacity", min_value=1.0, max_value=10000.0, value=float(truck.capacity), step=10.0
        )
        new_status = st.selectbox(
            "Vehicle Status",
            options=VEHICLE_STATUS_OPTIONS,
            index=VEHICLE_STATUS_OPTIONS.index(truck.vehicle_status) if truck.vehicle_status in VEHICLE_STATUS_OPTIONS else 0,
        )
        curr_route_id = str(truck.route_id) if truck.route_id is not None else "None"
        selected_route = st.selectbox(
            "Assigned Route",
            options=list(route_options.keys()),
            format_func=lambda x: route_options[x],
            index=list(route_options.keys()).index(curr_route_id) if curr_route_id in route_options else 0,
        )

        if st.form_submit_button("Save Changes"):
            if not new_plate.strip():
                st.error("License plate cannot be blank.")
                return

            route_id_val = int(selected_route) if selected_route != "None" else None
            execute_query(
                """
                UPDATE trucks 
                SET store_id = %s, license_plate = %s, capacity = %s, vehicle_status = %s, route_id = %s 
                WHERE id = %s
                """,
                (int(selected_store), new_plate.strip().upper(), float(new_capacity), new_status, route_id_val, truck_id),
            )
            st.success("Truck updated!")
            st.rerun()


@st.dialog("Confirm Deletion")
def delete_truck_dialog(truck_id: int, plate: str):
    st.warning(f"Are you sure you want to delete truck **{plate}** (ID: {truck_id})?")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM trucks WHERE id = %s", (truck_id,))
            st.rerun()
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


st.set_page_config(page_title="Truck Management", layout="wide")
st.title("Truck Management")


@st.fragment
def page_body():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM trucks")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(
            data=fetch_trucks,
            total_count=total_count,
            key="trucks_table",
        )

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", use_container_width=True, disabled=(selected_row is None)):
                edit_truck_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", use_container_width=True, disabled=(selected_row is None)):
                delete_truck_dialog(int(selected_row[0]["id"]), str(selected_row[0]["license_plate"]))
        with c4:
            if st.button("Create", use_container_width=True):
                create_truck_dialog()


page_body()