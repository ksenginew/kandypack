import streamlit as st
import pandas as pd
from typing import Optional
from db import fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable


@st.cache_data(ttl=300)
def fetch_truck_schedules() -> pd.DataFrame:
    user = st.session_state.get("user")
    user_role = user.role if user else None
    if user_role not in ("store_manager", "admin"):
        st.error("You do not have permission to view truck schedules.")
        return pd.DataFrame()  # Return an empty DataFrame for unauthorized users
    query = """
        SELECT t.id, t.route_id, t.license_plate, t.route_name, t.start_timestamp, t.end_timestamp
        FROM view_truck_schedules_overview t
    """
    if user_role == "store_manager":
        query += "WHERE t.route_id IN (SELECT route_id FROM store_managers_routes WHERE user_id = %s) "
        params = (str(user.id),)
    else:
        params = None
    query += "ORDER BY start_timestamp DESC;"
    return fetch_data(query, params)


@st.cache_data(ttl=300)
def fetch_assigned_orders_count(schedule_id: int) -> int:
    query = "SELECT COUNT(*) FROM view_schedule_assigned_orders WHERE truck_schedule_id = %s;"
    res = fetch_one(query, (schedule_id,))
    return res[0] if res else 0


def fetch_assigned_orders(schedule_id: int, limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT 
            order_id,
            delivery_address,
            contact_phone,
            delivery_date,
            prefered_delivery_slot,
            total_items,
            item_statuses
        FROM view_schedule_assigned_orders
        WHERE truck_schedule_id = %s
        ORDER BY delivery_date ASC, order_id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (schedule_id, limit, offset))


@st.dialog("Assign Orders to Truck Schedule")
def assign_orders_dialog(schedule_id: int, route_id: int):
    st.markdown(f"### Assign Orders to Schedule #{schedule_id}")

    unassigned_query = """
        SELECT id, delivery_address, contact_phone, delivery_date, item_count
        FROM view_unassigned_orders_by_route
        WHERE route_id = %s
        ORDER BY delivery_date ASC;
    """
    unassigned_df = fetch_data(unassigned_query, (route_id,))

    if unassigned_df.empty:
        st.info("No unassigned orders found for this route.")
        if st.button("Close"):
            st.rerun()
        return

    order_options = {
        f"Order #{row['id']} - {row['delivery_address']} ({row['item_count']} items)": int(
            row["id"]
        )
        for _, row in unassigned_df.iterrows()
    }

    selected_labels = st.multiselect(
        "Select Orders to Assign", options=list(order_options.keys())
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Assign Selected",
            type="primary",
            use_container_width=True,
            disabled=not selected_labels,
        ):
            selected_ids = [order_options[lbl] for lbl in selected_labels]
            execute_query(
                "CALL sp_assign_orders_to_schedule(%s, %s);",
                (schedule_id, selected_ids),
            )
            st.success(f"Successfully assigned {len(selected_ids)} order(s).")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


@st.dialog("Unassign Order")
def unassign_order_dialog(schedule_id: int, order_id: int):
    st.warning(
        f"Are you sure you want to unassign Order #{order_id} from Schedule #{schedule_id}?"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Unassign", type="primary", use_container_width=True):
            execute_query(
                "CALL sp_unassign_order_from_schedule(%s, %s);", (schedule_id, order_id)
            )
            st.success(f"Order #{order_id} removed from schedule.")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


@st.dialog("Change Order Status")
def change_order_status_dialog(order_id: int):
    st.markdown(f"### Update Status for Order #{order_id}")

    new_status = st.selectbox(
        "Select New Status", options=["DELIVERED", "DELIVERY_FAILED", "CANCELLED"]
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply Status", type="primary", use_container_width=True):
            execute_query(
                "CALL sp_update_order_item_status(%s, %s);", (order_id, new_status)
            )
            st.success("Order item statuses updated successfully.")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


def render_truck_deliveries_interface():
    st.subheader("Truck Schedule Orders Management")

    schedules_df = fetch_truck_schedules()
    if schedules_df.empty:
        st.info("No truck schedules found.")
        return

    schedule_options = {
        f"Schedule #{row['id']} | Truck: {row['license_plate']} | Route: {row['route_name']} | "
        f"{row['start_timestamp'].strftime('%Y-%m-%d %H:%M')}": (
            int(row["id"]),
            int(row["route_id"]),
        )
        for _, row in schedules_df.iterrows()
    }

    selected_label = st.selectbox(
        "Select Truck Schedule", options=list(schedule_options.keys())
    )
    selected_schedule_id, route_id = schedule_options[selected_label]

    total_count = fetch_assigned_orders_count(selected_schedule_id)

    toolbar_container = st.container()
    table_container = st.container()

    with table_container:
        selected_data = render_datatable(
            data=lambda limit, offset: fetch_assigned_orders(
                selected_schedule_id, limit, offset
            ),
            total_count=total_count,
            key=f"orders_table_schedule_{selected_schedule_id}",
        )

    selected_order_id = None
    if selected_data is not None and len(selected_data) > 0:
        selected_order_id = int(selected_data[0]["order_id"])

    with toolbar_container:
        col_assign, col_unassign, col_status, _ = st.columns([1.5, 1.5, 1.5, 5.5])

        with col_assign:
            if st.button("Assign Orders", key="btn_assign", use_container_width=True):
                assign_orders_dialog(selected_schedule_id, route_id)

        with col_unassign:
            if st.button(
                "Unassign Order",
                key="btn_unassign",
                use_container_width=True,
                disabled=(selected_order_id is None),
            ):
                unassign_order_dialog(selected_schedule_id, selected_order_id)

        with col_status:
            if st.button(
                "Change Status",
                key="btn_status",
                use_container_width=True,
                disabled=(selected_order_id is None),
            ):
                change_order_status_dialog(selected_order_id)
