import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

VEHICLE_STATUSES = ["Active", "Maintenance", "Decommissioned"]

def fetch_trucks(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT t.id, t.license_plate, s.store_name, r.route_name, t.capacity, t.vehicle_status
        FROM trucks AS t
        JOIN stores AS s ON t.store_id = s.id
        LEFT JOIN routes AS r ON t.route_id = r.id
        ORDER BY t.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Truck")
def create_truck_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC;")
    if not stores:
        st.error("Please configure stores first.")
        return

    store_map = {str(s.id): s.store_name for s in stores}
    route_map = {str(r.id): r.route_name for r in routes}

    with st.form("create_truck_form"):
        plate = st.text_input("License Plate")
        store_id = st.selectbox("Store", options=list(store_map.keys()), format_func=lambda x: store_map[x])
        capacity = st.number_input("Capacity (m³ / kg)", min_value=0.1, value=50.0, step=1.0)
        status = st.selectbox("Status", VEHICLE_STATUSES, index=0)
        route_id = st.selectbox("Default Route (Optional)", options=["None"] + list(route_map.keys()), format_func=lambda x: route_map.get(x, "None"))

        if st.form_submit_button("Register Truck"):
            if not plate.strip():
                st.error("License plate required.")
                return
            r_id = None if route_id == "None" else int(route_id)
            execute_query(
                "INSERT INTO trucks (license_plate, store_id, capacity, vehicle_status, route_id) VALUES (%s, %s, %s, %s, %s);",
                (plate.strip().upper(), int(store_id), float(capacity), status, r_id)
            )
            st.success("Truck registered!")
            st.rerun()

@st.dialog("Edit Truck")
def edit_truck_dialog(truck_id: int):
    truck = fetch_one("SELECT * FROM trucks WHERE id = %s;", (truck_id,))
    if not truck:
        st.error("Truck not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC;")
    store_map = {str(s.id): s.store_name for s in stores}
    route_map = {str(r.id): r.route_name for r in routes}
    current_route = str(truck.route_id) if truck.route_id else "None"

    with st.form("edit_truck_form"):
        plate = st.text_input("License Plate", value=truck.license_plate)
        store_id = st.selectbox("Store", options=list(store_map.keys()), format_func=lambda x: store_map[x], index=list(store_map.keys()).index(str(truck.store_id)) if str(truck.store_id) in store_map else 0)
        capacity = st.number_input("Capacity", min_value=0.1, value=float(truck.capacity), step=1.0)
        status = st.selectbox("Status", VEHICLE_STATUSES, index=VEHICLE_STATUSES.index(truck.vehicle_status) if truck.vehicle_status in VEHICLE_STATUSES else 0)
        route_opts = ["None"] + list(route_map.keys())
        route_id = st.selectbox("Assigned Route", options=route_opts, format_func=lambda x: route_map.get(x, "None"), index=route_opts.index(current_route) if current_route in route_opts else 0)

        if st.form_submit_button("Update Truck"):
            r_id = None if route_id == "None" else int(route_id)
            execute_query(
                "UPDATE trucks SET license_plate = %s, store_id = %s, capacity = %s, vehicle_status = %s, route_id = %s WHERE id = %s;",
                (plate.strip().upper(), int(store_id), float(capacity), status, r_id, truck_id)
            )
            st.success("Truck updated!")
            st.rerun()

@st.dialog("Delete Truck")
def delete_truck_dialog(truck_id: int, plate: str):
    st.warning(f"Are you sure you want to delete truck **{plate}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM trucks WHERE id = %s;", (truck_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_trucks_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM trucks;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_trucks, total_count=total_count, key="trucks_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_truck_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_truck_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_truck_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_truck_dialog(int(selected_row[0]["id"]), str(selected_row[0]["license_plate"]))
        with c4:
            if st.button("Create", key="create_truck_btn", use_container_width=True):
                create_truck_dialog()