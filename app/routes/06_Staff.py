import streamlit as st
from interfaces.employees import render_employees_interface

st.title("Staff & Personnel Operations")

@st.fragment
def employees_body():
    render_employees_interface()

employees_body()