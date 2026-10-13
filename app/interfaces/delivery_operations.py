import streamlit as st
from psycopg import Error

from db import execute_query, fetch_data

DELIVERY_STATUSES = ["DELIVERED", "DELIVERY_FAILED", "CANCELLED", "OUT_FOR_DELIVERY"]
NOTICE_KEY = "delivery_operations_notice"


def operator():
    user = st.session_state.get("user")
    return user if getattr(user, "role", None) in ("admin", "store_manager") else None


def fetch_delivery_schedules():
    user = operator()
    if user is None:
        return None
    return fetch_data(
        """SELECT s.id, t.license_plate, r.route_name,
                  s.start_timestamp AT TIME ZONE 'Asia/Colombo' AS start_local
           FROM truck_schedules s JOIN trucks t ON t.id = s.truck_id
           JOIN routes r ON r.id = s.route_id JOIN stores store ON store.id = r.store_id
           WHERE (%s = 'admin' OR store.manager_id = %s)
             AND EXISTS (SELECT 1 FROM truck_item_deliveries d WHERE d.truck_schedule_id = s.id)
           ORDER BY s.start_timestamp DESC, s.id DESC""",
        (user.role, str(user.id)),
    )


def fetch_delivery_orders(schedule_id):
    user = operator()
    if user is None:
        return None
    return fetch_data(
        """SELECT v.order_id, v.delivery_address, v.contact_phone,
                  v.delivery_date AT TIME ZONE 'Asia/Colombo' AS delivery_date,
                  v.total_items, v.item_statuses
           FROM view_schedule_assigned_orders v
           JOIN truck_schedules s ON s.id = v.truck_schedule_id
           JOIN routes r ON r.id = s.route_id JOIN stores store ON store.id = r.store_id
           WHERE v.truck_schedule_id = %s AND (%s = 'admin' OR store.manager_id = %s)
           ORDER BY v.delivery_date, v.order_id""",
        (schedule_id, user.role, str(user.id)),
    )


def apply_delivery_status(schedule_id, order_id, status):
    user = operator()
    if user is None:
        st.error("You do not have permission to update deliveries.")
        return
    try:
        execute_query("CALL sp_set_scheduled_order_status(%s, %s, %s, %s)",
                      (schedule_id, order_id, status, str(user.id)))
    except Error as error:
        st.error(error.diag.message_primary or "The delivery status could not be updated.")
        return
    st.session_state[NOTICE_KEY] = f"Order #{order_id}: {status.replace('_', ' ').title()}."
    st.rerun()


@st.dialog("Change Order Status")
def change_order_status_dialog(schedule_id, order_id):
    st.write(f"Update Order #{order_id} on Schedule #{schedule_id}.")
    status = st.selectbox("New status", DELIVERY_STATUSES,
                          format_func=lambda value: value.replace("_", " ").title())
    if st.button("Apply Status", type="primary"):
        apply_delivery_status(schedule_id, order_id, status)


def render_delivery_operations():
    if operator() is None:
        st.error("You do not have permission to manage deliveries.")
        return
    notice = st.session_state.pop(NOTICE_KEY, None)
    if notice:
        st.success(notice)
    st.caption("Creating a truck schedule marks its assigned items Out for delivery. "
               "Record the delivery result here. All times shown are Sri Lanka time.")
    if st.button("Refresh", key="delivery_operations_refresh"):
        st.rerun()
    schedules = fetch_delivery_schedules()
    if schedules.empty:
        st.info("No truck schedules with assigned orders found. Schedule received orders in Last-Mile Dispatch first.")
        return
    labels = {int(row.id): f"Schedule #{row.id} | {row.license_plate} | {row.route_name} | "
              f"{row.start_local:%Y-%m-%d %H:%M}" for row in schedules.itertuples()}
    schedule_id = st.selectbox("Truck schedule", list(labels), format_func=labels.get,
                               key="delivery_operations_schedule")
    orders = fetch_delivery_orders(schedule_id)
    if orders.empty:
        st.info("No assigned orders found for this schedule.")
        return
    st.dataframe(orders.rename(columns={"order_id": "Order", "delivery_address": "Delivery address",
                 "contact_phone": "Contact phone", "delivery_date": "Delivery date",
                 "total_items": "Items", "item_statuses": "Item statuses"}),
                 hide_index=True, width="stretch")
    order_labels = {int(row.order_id): f"Order #{row.order_id} | {row.delivery_address} | {row.item_statuses}"
                    for row in orders.itertuples()}
    order_id = st.selectbox("Order to update", list(order_labels), format_func=order_labels.get,
                            key=f"delivery_operations_order_{schedule_id}")
    status = st.selectbox("New status", DELIVERY_STATUSES,
                          format_func=lambda value: value.replace("_", " ").title(),
                          key="delivery_operations_status")
    if st.button("Apply Status", type="primary", key="delivery_operations_apply"):
        apply_delivery_status(schedule_id, order_id, status)
