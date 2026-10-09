import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_truck_schedules(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT ts.id, t.license_plate, r.route_name, d.employee_name AS driver,
               a.employee_name AS assistant, ts.start_timestamp, ts.end_timestamp, ts.duration_hours
        FROM truck_schedules AS ts
        JOIN trucks AS t ON ts.truck_id = t.id
        JOIN routes AS r ON ts.route_id = r.id
        JOIN employees AS d ON ts.driver_id = d.id
        LEFT JOIN employees AS a ON ts.assistant_id = a.id
        ORDER BY ts.start_timestamp DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Truck Schedule")
def create_truck_schedule_dialog():
    trucks = fetch_all("SELECT id, license_plate FROM trucks WHERE vehicle_status = 'Active' ORDER BY license_plate ASC;")
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC;")
    drivers = fetch_all("SELECT id, employee_name FROM employees WHERE employee_role = 'DRIVER' AND employee_status = 'Available' ORDER BY employee_name ASC;")
    assistants = fetch_all("SELECT id, employee_name FROM employees WHERE employee_role = 'ASSISTANT' AND employee_status = 'Available' ORDER BY employee_name ASC;")

    if not trucks or not routes or not drivers:
        st.error("Active trucks, routes, and available drivers are required.")
        return

    truck_map = {str(t.id): t.license_plate for t in trucks}
    route_map = {str(r.id): r.route_name for r in routes}
    driver_map = {str(d.id): d.employee_name for d in drivers}
    assistant_map = {str(a.id): a.employee_name for a in assistants}

    with st.form("create_truck_sched_form"):
        truck_id = st.selectbox("Truck", options=list(truck_map.keys()), format_func=lambda x: truck_map[x])
        route_id = st.selectbox("Route", options=list(route_map.keys()), format_func=lambda x: route_map[x])
        driver_id = st.selectbox("Driver", options=list(driver_map.keys()), format_func=lambda x: driver_map[x])
        assistant_id = st.selectbox("Assistant", options=["None"] + list(assistant_map.keys()), format_func=lambda x: assistant_map.get(x, "None"))

        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start Date", value=datetime.date.today())
            start_time = st.time_input("Start Time", value=datetime.time(8, 0))
        with c2:
            end_date = st.date_input("End Date", value=datetime.date.today())
            end_time = st.time_input("End Time", value=datetime.time(16, 0))

        if st.form_submit_button("Schedule Dispatch"):
            start_ts = datetime.datetime.combine(start_date, start_time)
            end_ts = datetime.datetime.combine(end_date, end_time)
            if end_ts <= start_ts:
                st.error("End time must be strictly after start time.")
                return

            asst = None if assistant_id == "None" else int(assistant_id)
            execute_query(
                """
                INSERT INTO truck_schedules (truck_id, route_id, driver_id, assistant_id, start_timestamp, end_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (int(truck_id), int(route_id), int(driver_id), asst, start_ts, end_ts)
            )
            st.success("Truck schedule created!")
            st.rerun()

@st.dialog("Delete Truck Schedule")
def delete_truck_schedule_dialog(schedule_id: int):
    st.warning(f"Delete Truck Schedule #{schedule_id}?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM truck_schedules WHERE id = %s;", (schedule_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_truck_schedules_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM truck_schedules;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_truck_schedules, total_count=total_count, key="truck_sched_datatable")

    with toolbar_container:
        c1, c2, c3 = st.columns([1, 7, 1])
        with c1:
            if st.button("Delete", key="delete_truck_sched_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_truck_schedule_dialog(int(selected_row[0]["id"]))
        with c3:
            if st.button("Create", key="create_truck_sched_btn", use_container_width=True):
                create_truck_schedule_dialog()