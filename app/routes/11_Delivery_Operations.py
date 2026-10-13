import streamlit as st
from psycopg import Error
from interfaces.delivery_operations import render_delivery_operations

st.title("Delivery Operations")
try:
    render_delivery_operations()
except Error:
    st.error("Delivery information could not be loaded. Please refresh and try again.")
