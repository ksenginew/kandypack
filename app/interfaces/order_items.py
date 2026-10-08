import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

LIFECYCLE_STATUS_OPTIONS = [
    "PLACED",
    "SCHEDULED",
    "IN_TRANSIT",
    "STORE_RECEIVED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "DELIVERY_FAILED",
    "CANCELLED",
]

def fetch_order_items(limit: int, offset: int) -> pd.DataFrame:
    order_id = st.session_state.get("selected_order_id")
    status_filter = st.session_state.get("tab_item_status_filter", "All")

    if not order_id:
        return pd.DataFrame(columns=["id", "product_name", "unit_price", "quantity", "item_lifecycle_status"])

    base_query = """
        SELECT 
            v.id,
            p.product_name,
            v.unit_price,
            v.quantity,
            v.item_lifecycle_status
        FROM view_order_items_grouped AS v
        INNER JOIN products AS p ON v.product_id = p.id
        WHERE v.order_id = %s
    """
    if status_filter != "All":
        base_query += " AND v.item_lifecycle_status = %s ORDER BY v.id ASC LIMIT %s OFFSET %s;"
        return fetch_data(base_query, (order_id, status_filter, limit, offset))
    base_query += " ORDER BY v.id ASC LIMIT %s OFFSET %s;"
    return fetch_data(base_query, (order_id, limit, offset))

@st.dialog("Add Items to Order")
def add_items_dialog(order_id: int):
    products = fetch_all("SELECT id, product_name, unit_price FROM products ORDER BY product_name ASC;")
    if not products:
        st.error("No products available.")
        return

    prod_map = {str(p.id): f"{p.product_name} (${float(p.unit_price):.2f})" for p in products}
    price_map = {str(p.id): float(p.unit_price) for p in products}

    with st.form("add_order_items_form"):
        prod_id = st.selectbox("Product", options=list(prod_map.keys()), format_func=lambda x: prod_map[x])
        quantity = st.number_input("Quantity", min_value=1, max_value=500, value=1, step=1)
        status = st.selectbox("Lifecycle Status", options=LIFECYCLE_STATUS_OPTIONS, index=0)

        if st.form_submit_button("Add Items"):
            unit_price = price_map.get(prod_id, 0.0)
            execute_query(
                """
                INSERT INTO view_order_items_grouped (order_id, product_id, unit_price, item_lifecycle_status, quantity)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (order_id, int(prod_id), unit_price, status, int(quantity)),
            )
            st.success(f"Added items to Order #{order_id}!")
            st.rerun()

@st.dialog("Edit Order Item Group")
def edit_item_dialog(group_id: int):
    item = fetch_one("SELECT * FROM view_order_items_grouped WHERE id = %s;", (group_id,))
    if not item:
        st.error("Item group not found.")
        return

    products = fetch_all("SELECT id, product_name FROM products ORDER BY product_name ASC;")
    prod_map = {str(p.id): p.product_name for p in products}

    with st.form("edit_order_item_form"):
        prod_id = st.selectbox(
            "Product",
            options=list(prod_map.keys()),
            format_func=lambda x: prod_map[x],
            index=list(prod_map.keys()).index(str(item.product_id)) if str(item.product_id) in prod_map else 0,
        )
        unit_price = st.number_input("Unit Price ($)", min_value=0.0, value=float(item.unit_price), step=0.5)
        quantity = st.number_input("Quantity", min_value=1, max_value=500, value=int(item.quantity), step=1)
        status = st.selectbox(
            "Lifecycle Status",
            options=LIFECYCLE_STATUS_OPTIONS,
            index=LIFECYCLE_STATUS_OPTIONS.index(item.item_lifecycle_status) if item.item_lifecycle_status in LIFECYCLE_STATUS_OPTIONS else 0,
        )

        if st.form_submit_button("Save Changes"):
            execute_query(
                """
                UPDATE view_order_items_grouped 
                SET product_id = %s, unit_price = %s, item_lifecycle_status = %s, quantity = %s 
                WHERE id = %s;
                """,
                (int(prod_id), float(unit_price), status, int(quantity), group_id),
            )
            st.success("Item updated!")
            st.rerun()

@st.dialog("Confirm Item Group Deletion")
def delete_item_dialog(group_id: int):
    st.warning("Delete this item group from the order?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM view_order_items_grouped WHERE id = %s;", (group_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_order_items_interface():
    current_order_id = st.session_state.get("selected_order_id")

    orders = fetch_all("SELECT id FROM orders ORDER BY id DESC;")
    order_ids = [o.id for o in orders] if orders else []

    c1, c2 = st.columns([1, 2])
    with c1:
        if order_ids:
            cur_idx = order_ids.index(current_order_id) if current_order_id in order_ids else 0
            selected_id = st.selectbox("Active Order ID", options=order_ids, index=cur_idx, format_func=lambda x: f"Order #{x}")
            if selected_id != current_order_id:
                st.session_state["selected_order_id"] = selected_id
                current_order_id = selected_id
        else:
            st.info("No orders exist.")
            return

    with c2:
        st.selectbox("Lifecycle Status Filter", options=["All"] + LIFECYCLE_STATUS_OPTIONS, key="tab_item_status_filter")

    if not current_order_id:
        st.info("Select an order to view items.")
        return

    order_meta = fetch_one(
        """
        SELECT o.id, c.customer_name, r.route_name, o.delivery_address, o.delivery_date
        FROM orders AS o
        JOIN customers AS c ON o.customer_id = c.id
        JOIN routes AS r ON o.route_id = r.id
        WHERE o.id = %s;
        """,
        (current_order_id,),
    )
    if order_meta:
        st.caption(f"**Customer:** {order_meta.customer_name} | **Route:** {order_meta.route_name} | **Delivery:** {order_meta.delivery_date.strftime('%Y-%m-%d') if order_meta.delivery_date else 'N/A'}")

    status_filter = st.session_state.get("tab_item_status_filter", "All")
    if status_filter != "All":
        count_row = fetch_one("SELECT COUNT(*) FROM view_order_items_grouped WHERE order_id = %s AND item_lifecycle_status = %s;", (current_order_id, status_filter))
    else:
        count_row = fetch_one("SELECT COUNT(*) FROM view_order_items_grouped WHERE order_id = %s;", (current_order_id,))
    total_count = count_row[0] if count_row else 0

    toolbar_container = st.container()
    table_container = st.container()

    with table_container:
        selected_row = render_datatable(data=fetch_order_items, total_count=total_count, key=f"items_tbl_{current_order_id}_{status_filter}")

    with toolbar_container:
        ic1, ic2, ic3, ic4 = st.columns([1, 1, 6, 1])
        with ic1:
            if st.button("Edit", key="edit_grouped_item_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_item_dialog(int(selected_row[0]["id"]))
        with ic2:
            if st.button("Delete", key="delete_grouped_item_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_item_dialog(int(selected_row[0]["id"]))
        with ic4:
            if st.button("Add Items", key="add_grouped_item_btn", use_container_width=True):
                add_items_dialog(current_order_id)