import streamlit as st
from interfaces.routes import render_routes_interface
from interfaces.trucks import render_trucks_interface

st.title("Fleet & Corridor Management")

tab_routes, tab_trucks = st.tabs(["Delivery Routes", "Truck Fleet"])

with tab_routes:
    @st.fragment
    def routes_body():
        render_routes_interface()
    routes_body()

with tab_trucks:
    @st.fragment
    def trucks_body():
        render_trucks_interface()
    trucks_body()