import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_train_allocations(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT ta.id, ta.train_id, s.store_name AS train_destination, ta.order_item_id,
               p.product_name, oi.item_lifecycle_status, ta.created_at
        FROM train_allocations AS ta
        JOIN train_schedules AS ts ON ta.train_id = ts.id
        JOIN stores AS s ON ts.destination_store_id = s.id
        JOIN order_items AS oi ON ta.order_item_id = oi.id
        JOIN products AS p ON oi.product_id = p.id
        ORDER BY ta.id DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Allocate Item to Train")
def create_allocation_dialog():
    trains = fetch_all("""
        SELECT ts.id, s.store_name, ts.departure_timestamp
        FROM train_schedules AS ts
        JOIN stores AS s ON ts.destination_store_id = s.id
        WHERE ts.departure_timestamp >= CURRENT_TIMESTAMP
        ORDER BY ts.departure_timestamp ASC;
    """)
    unallocated_items = fetch_all("""
        SELECT oi.id, p.product_name, oi.order_id
        FROM order_items AS oi
        JOIN products AS p ON oi.product_id = p.id
        LEFT JOIN train_allocations AS ta ON oi.id = ta.order_item_id
        WHERE ta.id IS NULL AND oi.item_lifecycle_status IN ('PLACED', 'SCHEDULED')
        LIMIT 100;
    """)

    if not trains or not unallocated_items:
        st.error("No upcoming train schedules or unallocated order items found.")
        return

    train_options = {str(t.id): f"Train #{t.id} -> {t.store_name} ({t.departure_timestamp.strftime('%Y-%m-%d %H:%M')})" for t in trains}
    item_options = {str(item.id): f"Item #{item.id} ({item.product_name}, Order #{item.order_id})" for item in unallocated_items}

    with st.form("create_train_alloc_form"):
        train_id = st.selectbox("Select Train Schedule", options=list(train_options.keys()), format_func=lambda x: train_options[x])
        item_id = st.selectbox("Select Unallocated Item", options=list(item_options.keys()), format_func=lambda x: item_options[x])

        if st.form_submit_button("Allocate"):
            execute_query(
                "INSERT INTO train_allocations (train_id, order_item_id) VALUES (%s, %s);",
                (int(train_id), int(item_id))
            )
            execute_query("UPDATE order_items SET item_lifecycle_status = 'SCHEDULED' WHERE id = %s;", (int(item_id),))
            st.success("Item allocated to train!")
            st.rerun()

@st.dialog("Delete Train Allocation")
def delete_allocation_dialog(alloc_id: int):
    st.warning(f"Remove Allocation #{alloc_id}?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Remove", type="primary", use_container_width=True):
            execute_query("DELETE FROM train_allocations WHERE id = %s;", (alloc_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_train_allocations_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM train_allocations;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_train_allocations, total_count=total_count, key="train_alloc_datatable")

    with toolbar_container:
        c1, c2, c3 = st.columns([1, 7, 1])
        with c1:
            if st.button("Delete", key="delete_train_alloc_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_allocation_dialog(int(selected_row[0]["id"]))
        with c3:
            if st.button("Allocate Item", key="create_train_alloc_btn", use_container_width=True):
                create_allocation_dialog()