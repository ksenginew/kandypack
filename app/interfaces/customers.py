import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_customers(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT c.id, c.customer_name, c.address, c.contact_phone, r.route_name, u.email AS user_account
        FROM customers AS c
        LEFT JOIN routes AS r ON c.default_route_id = r.id
        LEFT JOIN users AS u ON c.user_id = u.id
        ORDER BY c.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Customer")
def create_customer_dialog():
    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC;")
    users = fetch_all("SELECT id, email FROM users ORDER BY email ASC;")
    route_map = {str(r.id): r.route_name for r in routes}
    user_map = {str(u.id): u.email for u in users}

    with st.form("create_customer_form"):
        name = st.text_input("Customer Name")
        address = st.text_area("Address")
        phone = st.text_input("Contact Phone")
        route_id = st.selectbox("Default Route", options=["None"] + list(route_map.keys()), format_func=lambda x: route_map.get(x, "None"))
        user_id = st.selectbox("Linked User Account", options=["None"] + list(user_map.keys()), format_func=lambda x: user_map.get(x, "None"))

        if st.form_submit_button("Save Customer"):
            if not name.strip() or not phone.strip():
                st.error("Name and contact phone are required.")
                return
            r_val = None if route_id == "None" else int(route_id)
            u_val = None if user_id == "None" else user_id
            execute_query(
                "INSERT INTO customers (customer_name, address, contact_phone, default_route_id, user_id) VALUES (%s, %s, %s, %s, %s);",
                (name.strip(), address.strip(), phone.strip(), r_val, u_val)
            )
            st.success("Customer added!")
            st.rerun()

@st.dialog("Edit Customer")
def edit_customer_dialog(cust_id: int):
    customer = fetch_one("SELECT * FROM customers WHERE id = %s;", (cust_id,))
    if not customer:
        st.error("Customer not found.")
        return

    routes = fetch_all("SELECT id, route_name FROM routes ORDER BY route_name ASC;")
    users = fetch_all("SELECT id, email FROM users ORDER BY email ASC;")
    route_map = {str(r.id): r.route_name for r in routes}
    user_map = {str(u.id): u.email for u in users}

    cur_route = str(customer.default_route_id) if customer.default_route_id else "None"
    cur_user = str(customer.user_id) if customer.user_id else "None"

    with st.form("edit_customer_form"):
        name = st.text_input("Customer Name", value=customer.customer_name)
        address = st.text_area("Address", value=customer.address)
        phone = st.text_input("Contact Phone", value=customer.contact_phone)
        route_opts = ["None"] + list(route_map.keys())
        user_opts = ["None"] + list(user_map.keys())
        route_id = st.selectbox("Default Route", options=route_opts, format_func=lambda x: route_map.get(x, "None"), index=route_opts.index(cur_route) if cur_route in route_opts else 0)
        user_id = st.selectbox("Linked User Account", options=user_opts, format_func=lambda x: user_map.get(x, "None"), index=user_opts.index(cur_user) if cur_user in user_opts else 0)

        if st.form_submit_button("Update Customer"):
            r_val = None if route_id == "None" else int(route_id)
            u_val = None if user_id == "None" else user_id
            execute_query(
                "UPDATE customers SET customer_name = %s, address = %s, contact_phone = %s, default_route_id = %s, user_id = %s WHERE id = %s;",
                (name.strip(), address.strip(), phone.strip(), r_val, u_val, cust_id)
            )
            st.success("Customer updated!")
            st.rerun()

@st.dialog("Delete Customer")
def delete_customer_dialog(cust_id: int, cust_name: str):
    st.warning(f"Are you sure you want to delete customer **{cust_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM customers WHERE id = %s;", (cust_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_customers_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM customers;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_customers, total_count=total_count, key="customers_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_cust_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_customer_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_cust_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_customer_dialog(int(selected_row[0]["id"]), str(selected_row[0]["customer_name"]))
        with c4:
            if st.button("Create", key="create_cust_btn", use_container_width=True):
                create_customer_dialog()