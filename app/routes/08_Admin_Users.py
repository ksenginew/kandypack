import streamlit as st
from interfaces.users import render_users_interface

st.title("User Access & RBAC Administration")

@st.fragment
def users_body():
    render_users_interface()

users_body()
