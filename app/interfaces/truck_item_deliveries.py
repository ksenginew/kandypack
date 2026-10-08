import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_truck_deliveries(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT tid.id, tid.truck_schedule_id, t.license_plate, tid.order_item_id,
               p.product_name, tid.delivered_at, tid.created_at
        FROM truck_item_deliveries AS tid
        JOIN truck_schedules AS ts ON tid.truck_schedule_id = ts.id
        JOIN trucks AS t ON ts.truck_id = t.id
        JOIN order_items AS oi ON tid.order_item_id = oi.id
        JOIN products AS p ON oi.product_id = p.id
        ORDER BY tid.id DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Assign Item to Truck Delivery")
def create_delivery_assignment_dialog():
    schedules = fetch_all("""
        SELECT ts.id, t.license_plate, r.route_name, ts.start_timestamp
        FROM truck_schedules AS ts
        JOIN trucks AS t ON ts.truck_id = t.id
        JOIN routes AS r ON ts.route_id = r.id
        WHERE ts.end_timestamp >= CURRENT_TIMESTAMP
        ORDER BY ts.start_timestamp ASC;
    """)
    unassigned_items = fetch_all("""
        SELECT oi.id, p.product_name, oi.order_id
        FROM order_items AS oi
        JOIN products AS p ON oi.product_id = p.id
        LEFT JOIN truck_item_deliveries AS tid ON oi.id = tid.order_item_id
        WHERE tid.id IS NULL AND oi.item_lifecycle_status IN ('STORE_RECEIVED', 'SCHEDULED', 'PLACED')
        LIMIT 100;
    """)

    if not schedules or not unassigned_items:
        st.error("Active truck schedules or eligible order items are unavailable.")
        return

    sched_map = {str(s.id): f"Run #{s.id} ({s.license_plate} - {s.route_name})" for s in schedules}
    item_map = {str(i.id): f"Item #{i.id} ({i.product_name}, Order #{i.order_id})" for i in unassigned_items}

    with st.form("create_delivery_assign_form"):
        sched_id = st.selectbox("Truck Schedule", options=list(sched_map.keys()), format_func=lambda x: sched_map[x])
        item_id = st.selectbox("Order Item", options=list(item_map.keys()), format_func=lambda x: item_map[x])

        if st.form_submit_button("Assign Delivery"):
            execute_query(
                "INSERT INTO truck_item_deliveries (truck_schedule_id, order_item_id) VALUES (%s, %s);",
                (int(sched_id), int(item_id))
            )
            execute_query("UPDATE order_items SET item_lifecycle_status = 'OUT_FOR_DELIVERY' WHERE id = %s;", (int(item_id),))
            st.success("Delivery assigned!")
            st.rerun()

@st.dialog("Mark Delivery Status")
def mark_delivered_dialog(delivery_id: int):
    with st.form("mark_delivered_form"):
        delivered = st.checkbox("Mark as Delivered now?", value=True)
        if st.form_submit_button("Update Status"):
            del_val = datetime.datetime.now() if delivered else None
            status_val = "DELIVERED" if delivered else "DELIVERY_FAILED"
            execute_query("UPDATE truck_item_deliveries SET delivered_at = %s WHERE id = %s;", (del_val, delivery_id))
            execute_query(
                """
                UPDATE order_items SET item_lifecycle_status = %s 
                WHERE id = (SELECT order_item_id FROM truck_item_deliveries WHERE id = %s);
                """,
                (status_val, delivery_id)
            )
            st.success("Delivery status updated!")
            st.rerun()

@st.dialog("Delete Delivery Entry")
def delete_delivery_dialog(delivery_id: int):
    st.warning(f"Delete Delivery #{delivery_id}?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM truck_item_deliveries WHERE id = %s;", (delivery_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_truck_deliveries_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM truck_item_deliveries;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_truck_deliveries, total_count=total_count, key="truck_deliveries_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Status", key="status_del_btn", use_container_width=True, disabled=(selected_row is None)):
                mark_delivered_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_del_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_delivery_dialog(int(selected_row[0]["id"]))
        with c4:
            if st.button("Assign", key="assign_del_btn", use_container_width=True):
                create_delivery_assignment_dialog()