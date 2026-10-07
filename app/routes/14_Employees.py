import math
import re
import pandas as pd
import streamlit as st
from ui.datatable import render_datatable
from db import fetch_all, fetch_data, execute_query, fetch_one

EMPLOYEE_ROLES = ["DRIVER", "ASSISTANT"]
EMPLOYEE_STATUSES = ["Available", "On Leave", "Suspended", "Terminated"]
PHONE_REGEX = r"^[0-9\+\-\s\(\)\.]{7,20}$"


def fetch_employees(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT 
            e.id, 
            e.employee_name, 
            s.store_name, 
            e.employee_role, 
            e.contact_phone, 
            e.employee_status, 
            e.points
        FROM employees AS e
        INNER JOIN stores AS s ON e.store_id = s.id
        ORDER BY e.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))


@st.dialog("Create Employee")
def create_employee_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    if not stores:
        st.error("Please create at least one store before adding employees.")
        return

    store_options = {str(s.id): s.store_name for s in stores}

    with st.form("create_employee_form"):
        name = st.text_input("Full Name")
        selected_store = st.selectbox("Store", options=list(store_options.keys()), format_func=lambda x: store_options[x])
        role = st.selectbox("Role", options=EMPLOYEE_ROLES, index=0)
        phone = st.text_input("Contact Phone", placeholder="+1-555-0199")
        status = st.selectbox("Status", options=EMPLOYEE_STATUSES, index=0)
        points = st.number_input("Initial Points", min_value=0, value=0, step=1)

        if st.form_submit_button("Save Employee"):
            if not name.strip():
                st.error("Employee name is required.")
                return
            if not re.match(PHONE_REGEX, phone.strip()):
                st.error("Invalid phone format (7-20 characters: digits, +, -, spaces, parentheses).")
                return

            execute_query(
                """
                INSERT INTO employees (store_id, employee_name, employee_role, contact_phone, employee_status, points)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (int(selected_store), name.strip(), role, phone.strip(), status, int(points)),
            )
            st.success("Employee created successfully!")
            st.rerun()


@st.dialog("Edit Employee")
def edit_employee_dialog(emp_id: int):
    employee = fetch_one("SELECT * FROM employees WHERE id = %s", (emp_id,))
    if not employee:
        st.error("Employee not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC")
    store_options = {str(s.id): s.store_name for s in stores}
    current_store_id = str(employee.store_id)

    with st.form("edit_employee_form"):
        new_name = st.text_input("Full Name", value=employee.employee_name)
        selected_store = st.selectbox(
            "Store",
            options=list(store_options.keys()),
            format_func=lambda x: store_options[x],
            index=list(store_options.keys()).index(current_store_id) if current_store_id in store_options else 0,
        )
        new_role = st.selectbox(
            "Role",
            options=EMPLOYEE_ROLES,
            index=EMPLOYEE_ROLES.index(employee.employee_role) if employee.employee_role in EMPLOYEE_ROLES else 0,
        )
        new_phone = st.text_input("Contact Phone", value=employee.contact_phone)
        new_status = st.selectbox(
            "Status",
            options=EMPLOYEE_STATUSES,
            index=EMPLOYEE_STATUSES.index(employee.employee_status) if employee.employee_status in EMPLOYEE_STATUSES else 0,
        )
        new_points = st.number_input("Points", min_value=0, value=int(employee.points), step=1)

        if st.form_submit_button("Save Changes"):
            if not new_name.strip():
                st.error("Employee name cannot be blank.")
                return
            if not re.match(PHONE_REGEX, new_phone.strip()):
                st.error("Invalid phone format.")
                return

            execute_query(
                """
                UPDATE employees 
                SET store_id = %s, employee_name = %s, employee_role = %s, contact_phone = %s, employee_status = %s, points = %s 
                WHERE id = %s
                """,
                (int(selected_store), new_name.strip(), new_role, new_phone.strip(), new_status, int(new_points), emp_id),
            )
            st.success("Employee record updated!")
            st.rerun()


@st.dialog("Confirm Deletion")
def delete_employee_dialog(emp_id: int, emp_name: str):
    st.warning(f"Are you sure you want to delete employee **{emp_name}** (ID: {emp_id})?")
    st.caption("Warning: Cannot be deleted if tied to active truck schedules (foreign key constraint).")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM employees WHERE id = %s", (emp_id,))
            st.rerun()
    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


st.set_page_config(page_title="Employee Management", layout="wide")
st.title("Employee Management")


@st.fragment
def page_body():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM employees")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(
            data=fetch_employees,
            total_count=total_count,
            key="employees_table",
        )

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", use_container_width=True, disabled=(selected_row is None)):
                edit_employee_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", use_container_width=True, disabled=(selected_row is None)):
                delete_employee_dialog(int(selected_row[0]["id"]), str(selected_row[0]["employee_name"]))
        with c4:
            if st.button("Create", use_container_width=True):
                create_employee_dialog()


page_body()