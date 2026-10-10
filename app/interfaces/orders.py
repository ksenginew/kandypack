import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_orders(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT 
            o.id,
            c.customer_name,
            r.route_name,
            o.delivery_address,
            o.contact_phone,
            o.order_date,
            o.delivery_date,
            o.prefered_delivery_slot,
            COUNT(oi.id) AS total_items,
            COALESCE(SUM(oi.unit_price), 0.00) AS order_total
        FROM orders AS o
        INNER JOIN customers AS c ON o.customer_id = c.id
        INNER JOIN routes AS r ON o.route_id = r.id
        LEFT JOIN order_items AS oi ON o.id = oi.order_id
        GROUP BY o.id, c.customer_name, r.route_name
        ORDER BY o.id DESC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Order")
def create_order_dialog():
    customers = fetch_all("SELECT id, customer_name, address, contact_phone, default_route_id FROM customers ORDER BY customer_name ASC")
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC")

    if not customers or not routes:
        st.error("Customers and routes must exist before placing an order.")
        return

    cust_map = {str(c.id): c for c in customers}
    cust_options = {str(c.id): c.customer_name for c in customers}
    route_options = {str(r.id): r.route_name for r in routes}

    with st.form("create_order_form"):
        selected_cust_id = st.selectbox("Customer", options=list(cust_options.keys()), format_func=lambda x: cust_options[x])
        selected_cust = cust_map.get(selected_cust_id)
        default_route = (
            str(selected_cust.default_route_id)
            if selected_cust and selected_cust.default_route_id
            else list(route_options.keys())[0]
        )

        selected_route_id = st.selectbox(
            "Delivery Route",
            options=list(route_options.keys()),
            format_func=lambda x: route_options[x],
            index=list(route_options.keys()).index(default_route) if default_route in route_options else 0,
        )

        delivery_address = st.text_area("Delivery Address", value=selected_cust.address if selected_cust else "")
        contact_phone = st.text_input("Contact Phone", value=selected_cust.contact_phone if selected_cust else "")

        c1, c2 = st.columns(2)
        with c1:
            delivery_date = st.date_input("Delivery Date", min_value=datetime.date.today())
        with c2:
            time_slot = st.selectbox("Preferred Slot", ["Morning (08:00 - 11:00)", "Midday (11:00 - 14:00)", "Afternoon (14:00 - 17:00)","Evening (17:00 - 20:00)"])

        if st.form_submit_button("Place Order"):
            if not delivery_address.strip() or not contact_phone.strip():
                st.error("Address and contact phone are required.")
                return
            delivery_timestamp = datetime.datetime.combine(delivery_date, datetime.time(12, 0))
            order_row = fetch_one(
                """
                INSERT INTO orders (customer_id, route_id, delivery_address, contact_phone, delivery_date, prefered_delivery_slot)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (int(selected_cust_id), int(selected_route_id), delivery_address.strip(), contact_phone.strip(), delivery_timestamp, time_slot),
            )
            if order_row:
                st.session_state["selected_order_id"] = order_row.id
                st.success(f"Order #{order_row.id} created!")
                st.rerun()

@st.dialog("Edit Order")
def edit_order_dialog(order_id: int):
    order = fetch_one("SELECT * FROM orders WHERE id = %s;", (order_id,))
    if not order:
        st.error("Order not found.")
        return

    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC")
    route_options = {str(r.id): r.route_name for r in routes}

    with st.form("edit_order_form"):
        selected_route_id = st.selectbox(
            "Route",
            options=list(route_options.keys()),
            format_func=lambda x: route_options[x],
            index=list(route_options.keys()).index(str(order.route_id)) if str(order.route_id) in route_options else 0,
        )
        address = st.text_area("Delivery Address", value=order.delivery_address)
        phone = st.text_input("Contact Phone", value=order.contact_phone)
        delivery_date = st.date_input("Delivery Date", value=order.delivery_date.date() if order.delivery_date else datetime.date.today())
        slot = st.text_input("Preferred Slot", value=order.prefered_delivery_slot or "")

        if st.form_submit_button("Save Changes"):
            delivery_timestamp = datetime.datetime.combine(delivery_date, datetime.time(12, 0))
            execute_query(
                """
                UPDATE orders 
                SET route_id = %s, delivery_address = %s, contact_phone = %s, delivery_date = %s, prefered_delivery_slot = %s
                WHERE id = %s;
                """,
                (int(selected_route_id), address.strip(), phone.strip(), delivery_timestamp, slot.strip(), order_id),
            )
            st.success("Order updated!")
            st.rerun()

@st.dialog("Delete Order")
def delete_order_dialog(order_id: int):
    st.warning(f"Are you sure you want to delete **Order #{order_id}** and its items?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM orders WHERE id = %s;", (order_id,))
            if st.session_state.get("selected_order_id") == order_id:
                st.session_state["selected_order_id"] = None
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_orders_interface(on_select_order=None):
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM orders;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_orders, total_count=total_count, key="orders_datatable")

    with toolbar_container:
        c1, c2, c3, c4, c5 = st.columns([2,2,2,4,2])
        with c1:
            if st.button("View", key="view_order_items_btn", use_container_width=True, disabled=(selected_row is None)):
                oid = int(selected_row[0]["id"])
                st.session_state["selected_order_id"] = oid
                if on_select_order:
                    on_select_order(oid)
                st.rerun()
        with c2:
            if st.button("Edit", key="edit_order_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_order_dialog(int(selected_row[0]["id"]))
        with c3:
            if st.button("Delete", key="delete_order_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_order_dialog(int(selected_row[0]["id"]))
        with c5:
            if st.button("Create", key="create_order_btn", use_container_width=True):
                create_order_dialog()