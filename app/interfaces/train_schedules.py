import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query, safe_execute_query
from ui.datatable import render_datatable

def fetch_train_schedules(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT id, destination_store, departure_timestamp, max_capacity, remaining_capacity, allocated_items
        FROM view_train_schedules
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
            success, error = safe_execute_query("DELETE FROM train_schedules WHERE id = %s;", (train_id,))
            if success:
                st.rerun()
            st.error(str(error))
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def allocate_order_items_to_trains():
    success, error = safe_execute_query("CALL allocate_order_items_to_trains();")
    if success:
        st.success("Order items allocated to train schedules.")
        st.rerun()
    st.error(str(error))

@st.dialog("Put Train Items In Transit")
def mark_train_items_in_transit_dialog(train_id: int):
    st.warning(f"Move all scheduled items on Train #{train_id} to in transit?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Dispatch", type="primary", use_container_width=True):
            success, error = safe_execute_query(
                "CALL mark_train_items_in_transit(%s);",
                (train_id,),
            )
            if success:
                st.rerun()
            st.error(str(error))
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_train_schedules_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM view_train_schedules;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_train_schedules, total_count=total_count, key="train_schedules_datatable")

    with toolbar_container:
        selected_train_id = int(selected_row[0]["id"]) if selected_row is not None else None
        train_in_transit = bool(
            selected_train_id
            and fetch_one(
                """
                SELECT 1
                FROM train_allocations AS ta
                JOIN order_items AS oi ON oi.id = ta.order_item_id
                WHERE ta.train_id = %s AND oi.item_lifecycle_status = 'IN_TRANSIT'
                LIMIT 1;
                """,
                (selected_train_id,),
            )
        )
        c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1, 1, 4, 1])
        with c1:
            if st.button("Allocate Items", key="allocate_train_items_btn", use_container_width=True):
                allocate_order_items_to_trains()
        with c2:
            if st.button("Mark In Transit", key="mark_train_transit_btn", use_container_width=True, disabled=(selected_row is None or train_in_transit)):
                mark_train_items_in_transit_dialog(selected_train_id)
        with c3:
            if st.button("Edit", key="edit_train_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_train_schedule_dialog(selected_train_id)
        with c4:
            if st.button("Delete", key="delete_train_btn", use_container_width=True, disabled=(selected_row is None or train_in_transit)):
                delete_train_schedule_dialog(selected_train_id)
        with c6:
            if st.button("Create", key="create_train_btn", use_container_width=True):
                create_train_schedule_dialog()