import streamlit as st
from interfaces.stores import render_stores_interface

st.title("Store Hubs & Branches")

@st.fragment
def stores_body():
    render_stores_interface()

stores_body()