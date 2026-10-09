import streamlit as st
from interfaces.orders import render_orders_interface
from interfaces.order_items import render_order_items_interface

st.title("Sales Orders & Item Lifecycle")
tabs = ["Customer Orders", "Order Items Manifest"]
tab_orders, tab_items = st.tabs(tabs, key="sales_orders_tabs", default=tabs[0], on_change="rerun")

with tab_orders:    
    @st.fragment
    def orders_body():
        def on_select_order(order_id):
            st.session_state.tab_item_status_filter = "All"
            st.session_state.sales_orders_tabs = tabs[1]
        render_orders_interface(on_select_order)
    orders_body()

with tab_items:
    @st.fragment
    def items_body():
        render_order_items_interface()
    items_body()
