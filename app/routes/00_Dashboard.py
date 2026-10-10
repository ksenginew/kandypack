import datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from db import safe_fetch_all

st.set_page_config(
    page_title="Kandypack Supply Chain Overview",
    page_icon="🚆",
    layout="wide",
)

def load_data(query: str, params: tuple = None) -> pd.DataFrame:
    rows, err = safe_fetch_all(query, params)
    if isinstance(rows, tuple) and rows[0] is None:
        st.error(f"Database error: {rows[1]}")
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([row._asdict() for row in rows])

# ---------------- Header & Year Filter ----------------
st.title("🚆 Kandypack Operations & Sales Overview")
st.caption("Live monitoring of overall pipeline, revenue, fleet status, and delivery lifecycles.")

current_year = datetime.date.today().year
col_filter, _ = st.columns([2, 6])
with col_filter:
    selected_year = st.selectbox(
        "Select Reporting Year",
        options=[current_year, current_year - 1, current_year - 2],
        index=0,
    )

# ---------------- KPI Metrics ----------------
kpi_query = """
    SELECT 
        (SELECT COUNT(*) FROM orders WHERE EXTRACT(YEAR FROM order_date) = %s) AS total_orders,
        (SELECT COALESCE(SUM(oi.total_price), 0) 
         FROM order_items oi 
         JOIN orders o ON oi.order_id = o.id 
         WHERE EXTRACT(YEAR FROM o.order_date) = %s) AS total_revenue,
        (SELECT COUNT(*) FROM trucks WHERE vehicle_status = 'Active') AS active_trucks,
        (SELECT COUNT(*) FROM employees WHERE employee_status = 'Available') AS available_crew,
        (SELECT COUNT(*) FROM order_items WHERE item_lifecycle_status = 'IN_TRANSIT') AS in_transit_items,
        (SELECT COUNT(*) FROM order_items WHERE item_lifecycle_status = 'DELIVERED') AS delivered_items;
"""
df_kpi = load_data(kpi_query, (selected_year, selected_year))

if not df_kpi.empty:
    kpi = df_kpi.iloc[0]
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Orders", f"{int(kpi['total_orders']):,}")
    m2.metric("Revenue (LKR)", f"Rs. {float(kpi['total_revenue']):,.2f}")
    m3.metric("Active Trucks", int(kpi["active_trucks"]))
    m4.metric("Available Crew", int(kpi["available_crew"]))
    m5.metric("In Transit Items", int(kpi["in_transit_items"]))
    m6.metric("Delivered Items", int(kpi["delivered_items"]))

st.markdown("---")

# ---------------- Visuals Row ----------------
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("📦 Order Item Lifecycle Breakdown")
    lifecycle_query = """
        SELECT 
            oi.item_lifecycle_status AS status, 
            COUNT(oi.id) AS count
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE EXTRACT(YEAR FROM o.order_date) = %s
        GROUP BY oi.item_lifecycle_status
        ORDER BY count DESC;
    """
    df_lifecycle = load_data(lifecycle_query, (selected_year,))

    if not df_lifecycle.empty:
        fig_donut = px.pie(
            df_lifecycle,
            names="status",
            values="count",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No order items recorded for this year.")

with right_col:
    st.subheader("🏬 Store Distribution Hubs")
    store_query = """
        SELECT 
            s.store_name,
            COUNT(DISTINCT r.id) AS assigned_routes,
            COUNT(DISTINCT t.id) AS allocated_trucks,
            COUNT(DISTINCT e.id) AS staff_count
        FROM stores s
        LEFT JOIN routes r ON s.id = r.store_id
        LEFT JOIN trucks t ON s.id = t.store_id
        LEFT JOIN employees e ON s.id = e.store_id
        GROUP BY s.id, s.store_name
        ORDER BY allocated_trucks DESC;
    """
    df_stores = load_data(store_query)

    if not df_stores.empty:
        fig_stores = px.bar(
            df_stores,
            x="store_name",
            y=["allocated_trucks", "assigned_routes", "staff_count"],
            barmode="group",
            labels={"value": "Count", "store_name": "Store Hub", "variable": "Asset Type"},
            color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c"],
        )
        st.plotly_chart(fig_stores, use_container_width=True)
    else:
        st.info("No hub data available.")

st.markdown("---")

# ---------------- Recent Orders Feed ----------------
st.subheader("🕒 Recent Orders Pipeline")
recent_query = """
    SELECT 
        o.id AS order_id,
        c.customer_name,
        r.route_name,
        s.store_name AS hub,
        o.order_date,
        COUNT(oi.id) AS item_count,
        COALESCE(SUM(oi.total_price), 0) AS total_value
    FROM orders o
    JOIN customers c ON o.customer_id = c.id
    JOIN routes r ON o.route_id = r.id
    JOIN stores s ON r.store_id = s.id
    LEFT JOIN order_items oi ON o.id = oi.order_id
    GROUP BY o.id, c.customer_name, r.route_name, s.store_name, o.order_date
    ORDER BY o.order_date DESC
    LIMIT 10;
"""
df_recent = load_data(recent_query)

if not df_recent.empty:
    st.dataframe(
        df_recent.style.format({"total_value": "Rs. {:,.2f}"}),
        use_container_width=True,
    )
else:
    st.info("No recent orders found.")
