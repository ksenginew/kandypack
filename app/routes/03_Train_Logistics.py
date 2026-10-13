import streamlit as st
from interfaces.train_schedules import (
    render_in_transit_train_schedules_interface,
    render_train_schedules_interface,
)
from interfaces.train_allocations import render_train_allocations_interface

st.title("Bulk Railway Transport")

tab_schedules, tab_in_transit, tab_allocations = st.tabs([
    "Train Schedules",
    "In Transit",
    "Manifest Allocations",
])

with tab_schedules:
    @st.fragment
    def train_schedules_body():
        render_train_schedules_interface()
    train_schedules_body()

with tab_in_transit:
    @st.fragment
    def in_transit_train_schedules_body():
        render_in_transit_train_schedules_interface()
    in_transit_train_schedules_body()

with tab_allocations:
    @st.fragment
    def train_allocations_body():
        render_train_allocations_interface()
    train_allocations_body()