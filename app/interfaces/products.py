import pandas as pd
import streamlit as st
from db import fetch_data, fetch_one, execute_query
from ui.datatable import render_datatable

def fetch_products(limit: int, offset: int) -> pd.DataFrame:
    query = """
        SELECT id, product_name, unit_price, space_consumption_unit, created_at
        FROM products
        ORDER BY id ASC
        LIMIT %s OFFSET %s;
    """
    return fetch_data(query, (limit, offset))

@st.dialog("Create Product")
def create_product_dialog():
    with st.form("create_product_form"):
        name = st.text_input("Product Name")
        unit_price = st.number_input("Unit Price ($)", min_value=0.0, value=10.0, step=0.5)
        space = st.number_input("Space Unit Consumption (m³)", min_value=0.0001, value=0.05, step=0.01, format="%.4f")

        if st.form_submit_button("Save Product"):
            if not name.strip():
                st.error("Product name is required.")
                return
            execute_query(
                "INSERT INTO products (product_name, unit_price, space_consumption_unit) VALUES (%s, %s, %s);",
                (name.strip(), float(unit_price), float(space))
            )
            st.success("Product created!")
            st.rerun()

@st.dialog("Edit Product")
def edit_product_dialog(prod_id: int):
    prod = fetch_one("SELECT * FROM products WHERE id = %s;", (prod_id,))
    if not prod:
        st.error("Product not found.")
        return

    with st.form("edit_product_form"):
        name = st.text_input("Product Name", value=prod.product_name)
        unit_price = st.number_input("Unit Price ($)", min_value=0.0, value=float(prod.unit_price), step=0.5)
        space = st.number_input("Space Unit Consumption (m³)", min_value=0.0001, value=float(prod.space_consumption_unit), step=0.01, format="%.4f")

        if st.form_submit_button("Update Product"):
            execute_query(
                "UPDATE products SET product_name = %s, unit_price = %s, space_consumption_unit = %s WHERE id = %s;",
                (name.strip(), float(unit_price), float(space), prod_id)
            )
            st.success("Product updated!")
            st.rerun()

@st.dialog("Delete Product")
def delete_product_dialog(prod_id: int, prod_name: str):
    st.warning(f"Are you sure you want to delete **{prod_name}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, Delete", type="primary", use_container_width=True):
            execute_query("DELETE FROM products WHERE id = %s;", (prod_id,))
            st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

def render_products_interface():
    toolbar_container = st.container()
    table_container = st.container()

    count_row = fetch_one("SELECT COUNT(*) FROM products;")
    total_count = count_row[0] if count_row else 0

    with table_container:
        selected_row = render_datatable(data=fetch_products, total_count=total_count, key="products_datatable")

    with toolbar_container:
        c1, c2, c3, c4 = st.columns([1, 1, 6, 1])
        with c1:
            if st.button("Edit", key="edit_prod_btn", use_container_width=True, disabled=(selected_row is None)):
                edit_product_dialog(int(selected_row[0]["id"]))
        with c2:
            if st.button("Delete", key="delete_prod_btn", use_container_width=True, disabled=(selected_row is None)):
                delete_product_dialog(int(selected_row[0]["id"]), str(selected_row[0]["product_name"]))
        with c4:
            if st.button("Create", key="create_prod_btn", use_container_width=True):
                create_product_dialog()