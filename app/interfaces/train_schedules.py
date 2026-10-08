import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_train_schedules(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT ts.id, s.store_name AS destination_store, ts.departure_timestamp, ts.max_capacity,
               COUNT(ta.id) AS allocated_items
        FROM train_schedules AS ts
        JOIN stores AS s ON ts.destination_store_id = s.id
        LEFT JOIN train_allocations AS ta ON ts.id = ta.train_id
        GROUP BY ts.id, s.store_name
        ORDER BY ts.departure_timestamp ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Train Schedule")
def create_train_schedule_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    if not stores:
        st.error("Create stores first.")
        return
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("create_train_sched_form"):
        store_id = st.selectbox("Destination Store", options=list(store_map.keys()), format_func=lambda x: store_map[x])
        c1, c2 = st.columns(2)
        with c1:
            dep_date = st.date_input("Departure Date", min_value=datetime.date.today())
        with c2:
            dep_time = st.time_input("Departure Time", value=datetime.time(8, 0))
        capacity = st.number_input("Max Capacity (m³)", min_value=1.0, value=500.0, step=10.0)

        if st.form_submit_button("Create Schedule"):
            dep_ts = datetime.datetime.combine(dep_date, dep_time)
            execute_query(
                "INSERT INTO train_schedules (destination_store_id, departure_timestamp, max_capacity) VALUES (%s, %s, %s);",
                (int(store_id), dep_ts, float(capacity))
            )
            st.success("Train schedule created!")
            st.rerun()

@st.dialog("Edit Train Schedule")
def edit_train_schedule_dialog(train_id: int):
    train = fetch_one("SELECT * FROM train_schedules WHERE id = %s;", (train_id,))
    if not train:
        st.error("Schedule not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("edit_train_sched_form"):
        store_id = st.selectbox("Destination Store", options=list(store_map.keys()), format_func=lambda x: store_map[x], index=list(store_map.keys()).index(str(train.destination_store_id)) if str(train.destination_store_id) in store_map else 0)
        c1, c2 = st.columns(2)
        with c1:
            dep_date = st.date_input("Departure Date", value=train.departure_timestamp.date() if train.departure_timestamp else datetime.date.today())
        with c2:
            dep_time = st.time_input("Departure Time", value=train.departure_timestamp.time() if train.departure_timestamp else datetime.time(8, 0))
        capacity = st.number_input("Max Capacity", min_value=1.0, value=float(train.max_capacity), step=10.0)

        if st.form_submit_button("Update Schedule"):
            dep_ts = datetime.datetime.combine(dep_date, dep_time)
            execute_query(
                "UPDATE train_schedules SET destination_store_id = %s, departure_timestamp = %s, max_capacity = %s WHERE id = %s;",
                (int(store_id), dep_ts, float(capacity), train_id)
            )
            st.success("Schedule updated!")
            st.rerun()

@st.dialog("Delete Train Schedule")
def delete_train_schedule_dialog(train_id: int):
    st.warning(f"Delete Train Schedule #{train_id} and all related allocations?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM train_schedules WHERE id = %s;", (train_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_train_schedules_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM train_schedules;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_train_schedules, total_count=total_count, key="train_schedules_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_train_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_train_schedule_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_train_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_train_schedule_dialog(int(selected_row[0]["id"]))
        with c4:
            if st.button("Create", key="create_train_btn", use_container_width=True):
                create_train_schedule_dialog()