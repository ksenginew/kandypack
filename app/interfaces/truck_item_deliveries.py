import datetime
import pandas as pd
import streamlit as st
from db import fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable
from interfaces.truck_schedules import manager_id

def fetch_truck_deliveries(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT tid.id, tid.truck_schedule_id, t.license_plate, tid.order_item_id,
               p.product_name, tid.delivered_at, tid.created_at
        FROM truck_item_deliveries AS tid
        JOIN truck_schedules AS ts ON tid.truck_schedule_id = ts.id
        JOIN trucks AS t ON ts.truck_id = t.id
        JOIN order_items AS oi ON tid.order_item_id = oi.id
        JOIN products AS p ON oi.product_id = p.id
        JOIN routes AS r ON r.id = ts.route_id
        JOIN stores AS store ON store.id = r.store_id
        WHERE (%s::uuid IS NULL OR store.manager_id = %s)
        ORDER BY tid.id DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (manager_id(), manager_id(), limit, offset))

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
    st.caption("Assign complete received orders from the Truck Schedules tab.")
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("""SELECT count(*) FROM truck_item_deliveries d
        JOIN truck_schedules ts ON ts.id = d.truck_schedule_id
        JOIN routes r ON r.id = ts.route_id JOIN stores store ON store.id = r.store_id
        WHERE (%s::uuid IS NULL OR store.manager_id = %s)""", (manager_id(), manager_id()))
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_truck_deliveries, total_count=total_count, key="truck_deliveries_datatable")

    with toolbar_container:
        c1, c2, _ = st.columns([1, 1, 7])
        with c1:
            if st.button("Status", key="status_del_btn", use_container_width=True, disabled=(selected_row is None)):
                mark_delivered_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_del_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_delivery_dialog(int(selected_row[0]["id"]))
