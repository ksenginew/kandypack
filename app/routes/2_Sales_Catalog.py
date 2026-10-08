import streamlit as st
from interfaces.customers import render_customers_interface
from interfaces.products import render_products_interface

st.title("Customer Accounts & Product Catalog")

tab_customers, tab_products = st.tabs(["Customers", "Product Inventory"])

with tab_customers:
    @st.fragment
    def customers_body():
        render_customers_interface()
    customers_body()

with tab_products:
    @st.fragment
    def products_body():
        render_products_interface()
    products_body()