import pandas as pd
import streamlit as st
from db import fetch_all, fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

EMPLOYEE_ROLES = ["DRIVER", "ASSISTANT"]
EMPLOYEE_STATUSES = ["Available", "On Leave", "Suspended", "Terminated"]

def fetch_employees(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT e.id, e.employee_name, s.store_name, e.employee_role, e.contact_phone, e.employee_status, e.points
        FROM employees AS e
        JOIN stores AS s ON e.store_id = s.id
        ORDER BY e.id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Add Employee")
def create_employee_dialog():
    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    if not stores:
        st.error("Please add stores before adding employees.")
        return
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("create_employee_form"):
        name = st.text_input("Employee Name")
        store_id = st.selectbox("Assigned Store", options=list(store_map.keys()), format_func=lambda x: store_map[x])
        role = st.selectbox("Role", EMPLOYEE_ROLES)
        phone = st.text_input("Contact Phone")
        status = st.selectbox("Status", EMPLOYEE_STATUSES, index=0)

        if st.form_submit_button("Save Employee"):
            if not name.strip() or not phone.strip():
                st.error("Name and valid phone number are required.")
                return
            execute_query(
                "INSERT INTO employees (employee_name, store_id, employee_role, contact_phone, employee_status) VALUES (%s, %s, %s, %s, %s);",
                (name.strip(), int(store_id), role, phone.strip(), status)
            )
            st.success("Employee created!")
            st.rerun()

@st.dialog("Edit Employee")
def edit_employee_dialog(emp_id: int):
    emp = fetch_one("SELECT * FROM employees WHERE id = %s;", (emp_id,))
    if not emp:
        st.error("Employee not found.")
        return

    stores = fetch_all("SELECT id, store_name FROM stores ORDER BY store_name ASC;")
    store_map = {str(s.id): s.store_name for s in stores}

    with st.form("edit_employee_form"):
        name = st.text_input("Employee Name", value=emp.employee_name)
        store_id = st.selectbox("Assigned Store", options=list(store_map.keys()), format_func=lambda x: store_map[x], index=list(store_map.keys()).index(str(emp.store_id)) if str(emp.store_id) in store_map else 0)
        role = st.selectbox("Role", EMPLOYEE_ROLES, index=EMPLOYEE_ROLES.index(emp.employee_role) if emp.employee_role in EMPLOYEE_ROLES else 0)
        phone = st.text_input("Contact Phone", value=emp.contact_phone)
        status = st.selectbox("Status", EMPLOYEE_STATUSES, index=EMPLOYEE_STATUSES.index(emp.employee_status) if emp.employee_status in EMPLOYEE_STATUSES else 0)
        points = st.number_input("Points", min_value=0, value=int(emp.points), step=1)

        if st.form_submit_button("Update Employee"):
            execute_query(
                """
                UPDATE employees 
                SET employee_name = %s, store_id = %s, employee_role = %s, contact_phone = %s, employee_status = %s, points = %s
                WHERE id = %s;
                """,
                (name.strip(), int(store_id), role, phone.strip(), status, points, emp_id)
            )
            st.success("Employee updated!")
            st.rerun()

@st.dialog("Delete Employee")
def delete_employee_dialog(emp_id: int, emp_name: str):
    st.warning(f"Are you sure you want to delete employee **{emp_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM employees WHERE id = %s;", (emp_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_employees_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM employees;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_employees, total_count=total_count, key="employees_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_emp_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_employee_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_emp_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_employee_dialog(int(selected_row[0]["id"]), str(selected_row[0]["employee_name"]))
        with c4:
            if st.button("Create", key="create_emp_btn", use_container_width=True):
                create_employee_dialog()
