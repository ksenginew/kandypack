import streamlit as st
from interfaces.truck_schedules import render_truck_schedules_interface
from interfaces.truck_item_deliveries import render_truck_deliveries_interface

st.title("Truck Scheduling & Delivery Manifest")

tab_schedules, tab_deliveries = st.tabs(["Truck Schedules", "Delivery Drop-offs"])

with tab_schedules:
    @st.fragment
    def schedules_body():
        render_truck_schedules_interface()
    schedules_body()

with tab_deliveries:
    @st.fragment
    def deliveries_body():
        render_truck_deliveries_interface()
    deliveries_body()