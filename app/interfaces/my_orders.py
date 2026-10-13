import streamlit as st
from psycopg import Error

from db import fetch_data


def fetch_my_orders(user_id):
    return fetch_data(
        """SELECT o.id AS order_id,
                  o.order_date AT TIME ZONE 'Asia/Colombo' AS order_date,
                  o.delivery_date AT TIME ZONE 'Asia/Colombo' AS delivery_date,
                  o.delivery_address, count(i.id) AS items,
                  count(i.id) FILTER (WHERE i.item_lifecycle_status = 'OUT_FOR_DELIVERY') AS out_for_delivery_items,
                  COALESCE(bool_and(i.item_lifecycle_status = 'DELIVERED'), FALSE) AS all_delivered,
                  COALESCE(string_agg(DISTINCT i.item_lifecycle_status::text, ', '
                           ORDER BY i.item_lifecycle_status::text), 'No items') AS item_statuses
           FROM orders o JOIN customers c ON c.id = o.customer_id
           LEFT JOIN order_items i ON i.order_id = o.id
           WHERE c.user_id = %s
           GROUP BY o.id ORDER BY o.order_date DESC, o.id DESC""",
        (str(user_id),),
    )


def fetch_my_order_items(user_id, order_id):
    return fetch_data(
        """SELECT p.product_name, i.item_lifecycle_status::text AS status,
                  count(i.id) AS quantity, i.unit_price,
                  t.license_plate AS truck,
                  s.start_timestamp AT TIME ZONE 'Asia/Colombo' AS scheduled_start,
                  max(d.delivered_at) AT TIME ZONE 'Asia/Colombo' AS delivered_at
           FROM orders o JOIN customers c ON c.id = o.customer_id
           JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id
           LEFT JOIN truck_item_deliveries d ON d.order_item_id = i.id
           LEFT JOIN truck_schedules s ON s.id = d.truck_schedule_id
           LEFT JOIN trucks t ON t.id = s.truck_id
           WHERE c.user_id = %s AND o.id = %s
           GROUP BY p.id, i.item_lifecycle_status, i.unit_price, t.license_plate, s.start_timestamp
           ORDER BY p.product_name, i.item_lifecycle_status""",
        (str(user_id), order_id),
    )


def render_my_orders_dashboard():
    user = st.session_state.get("user")
    if getattr(user, "role", None) != "user":
        st.error("Sign in as a user to view your orders.")
        return
    st.title("My Orders & Deliveries")
    st.caption("Track your orders and each item's delivery status. All times shown are Sri Lanka time.")
    if st.button("Refresh", key="my_orders_refresh"):
        st.rerun()
    try:
        orders = fetch_my_orders(user.id)
        if orders.empty:
            st.info("No orders are linked to your account yet.")
            return
        total, dispatched, delivered = st.columns(3)
        total.metric("My orders", len(orders))
        dispatched.metric("Orders out for delivery", int((orders.out_for_delivery_items > 0).sum()))
        delivered.metric("Delivered orders", int(orders.all_delivered.sum()))
        statuses = sorted({status for values in orders.item_statuses for status in values.split(", ")})
        status_filter = st.selectbox("Filter by item status", ["All"] + statuses,
                                     format_func=lambda value: value.replace("_", " ").title(),
                                     key="my_orders_status")
        visible = orders if status_filter == "All" else orders[
            orders.item_statuses.apply(lambda values: status_filter in values.split(", "))]
        st.dataframe(visible[["order_id", "order_date", "delivery_date", "delivery_address", "items", "item_statuses"]]
                     .rename(columns={"order_id": "Order", "order_date": "Placed",
                         "delivery_date": "Delivery date", "delivery_address": "Delivery address",
                         "items": "Items", "item_statuses": "Item statuses"}), hide_index=True, width="stretch")
        if visible.empty:
            st.info("No orders match this status.")
            return
        ids = [int(value) for value in visible.order_id]
        order_id = st.selectbox("View order items", ids, format_func=lambda value: f"Order #{value}",
                                key=f"my_orders_detail_{status_filter}")
        items = fetch_my_order_items(user.id, order_id)
        st.subheader(f"Order #{order_id} items")
        if items.empty:
            st.info("This order has no items yet.")
        else:
            st.dataframe(items.rename(columns={"product_name": "Product", "status": "Status",
                         "quantity": "Quantity", "unit_price": "Unit price (LKR)",
                         "truck": "Truck", "scheduled_start": "Scheduled departure", "delivered_at": "Delivered at"}),
                         hide_index=True, width="stretch")
    except Error:
        st.error("Your delivery information could not be loaded. Please refresh and try again.")
