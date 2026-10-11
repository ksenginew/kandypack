import datetime
import calendar
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

today = datetime.date.today()
current_year = today.year
current_quarter = (today.month - 1) // 3 + 1

# Quarter month ranges
quarter_months = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12]
}[current_quarter]

start_month = quarter_months[0]
end_month = quarter_months[-1]
last_day_of_quarter = calendar.monthrange(current_year, end_month)[1]

quarter_start_ts = datetime.datetime(current_year, start_month, 1, 0, 0, 0)
quarter_end_ts = datetime.datetime(current_year, end_month, last_day_of_quarter, 23, 59, 59)

st.title("🚆 Kandypack Operations & Sales Overview")
st.caption(f"Current Quarter: Q{current_quarter} {current_year} | Period: {quarter_start_ts.strftime('%b %d, %Y')} – {quarter_end_ts.strftime('%b %d, %Y')}")

sales_kpi_query = """
    SELECT
        COUNT(DISTINCT o.id) AS total_orders,
        COUNT(oi.id) AS total_items_sold,
        COALESCE(SUM(oi.unit_price), 0.00) AS total_revenue,
        COALESCE(SUM(p.space_consumption_unit), 0.0000) AS total_volume_space
    FROM orders o
    JOIN order_items oi ON o.id = oi.order_id
    JOIN products p ON oi.product_id = p.id
    WHERE EXTRACT(YEAR FROM o.order_date) = %s
      AND EXTRACT(QUARTER FROM o.order_date) = %s
      AND oi.item_lifecycle_status != 'CANCELLED';
"""
df_sales_kpi = load_data(sales_kpi_query, (current_year, current_quarter))

if not df_sales_kpi.empty:
    kpi = df_sales_kpi.iloc[0]
    total_orders = int(kpi["total_orders"])
    total_rev = float(kpi["total_revenue"])
    total_items = int(kpi["total_items_sold"])
    total_vol = float(kpi["total_volume_space"])
    aov = (total_rev / total_orders) if total_orders > 0 else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Revenue", f"Rs. {total_rev:,.2f}")
    k2.metric("Orders Placed", f"{total_orders:,}")
    k3.metric("Units Sold", f"{total_items:,}")
    k4.metric("Avg Order Value (AOV)", f"Rs. {aov:,.2f}")
    k5.metric("Total Volume Space", f"{total_vol:,.2f} m³")
else:
    st.info("No sales data recorded for the current quarter.")

st.divider()

# ==============================================================================
# 2. MOST ORDERED ITEMS
# ==============================================================================
col_top_tbl, col_top_chart = st.columns([1, 1])

top_items_query = """
    SELECT * FROM get_most_ordered_items_by_quarter(%s, %s, %s);
"""
df_top_items = load_data(top_items_query, (current_year, current_quarter, 10))

with col_top_tbl:
    if not df_top_items.empty:
        st.markdown("**Top 10 Items Ordered in Current Quarter**")
        st.dataframe(
            df_top_items[[
                "sales_rank", "product_name", "total_quantity_ordered", "total_revenue", "total_space_occupied"
            ]].rename(columns={
                "sales_rank": "Rank",
                "product_name": "Product Name",
                "total_quantity_ordered": "Qty Sold",
                "total_revenue": "Revenue (LKR)",
                "total_space_occupied": "Space Units"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No items ordered in this quarter.")

with col_top_chart:
    if not df_top_items.empty:
        st.markdown(f"**Top Items by Quantity Ordered (Q{current_quarter})**")
        fig_top = px.bar(
            df_top_items,
            x="total_quantity_ordered",
            y="product_name",
            orientation="h",
            color="total_revenue",
            color_continuous_scale="Viridis",
            labels={
                "total_quantity_ordered": "Quantity Ordered",
                "product_name": "Product",
                "total_revenue": "Revenue (Rs.)"
            },
        )
        fig_top.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)

st.divider()

city_route_query = """
    SELECT * FROM get_city_route_sales(%s, %s);
"""
df_city_route = load_data(city_route_query, (quarter_start_ts, quarter_end_ts))

if not df_city_route.empty:
    cr1, cr2 = st.columns([1, 1])

    with cr1:
        # Aggregate by City Hub
        df_city_agg = df_city_route.groupby("city_hub", as_index=False).agg({
            "total_sales_revenue": "sum",
            "total_orders": "sum",
            "total_units_sold": "sum"
        }).sort_values(by="total_sales_revenue", ascending=False)

        fig_city = px.pie(
            df_city_agg,
            names="city_hub",
            values="total_sales_revenue",
            hole=0.4,
            title="Revenue Share by City Hub"
        )
        st.plotly_chart(fig_city, use_container_width=True)

    with cr2:
        fig_route = px.bar(
            df_city_route.sort_values(by="total_sales_revenue", ascending=False).head(10),
            x="route_name",
            y="total_sales_revenue",
            color="city_hub",
            labels={"total_sales_revenue": "Revenue (LKR)", "route_name": "Route"},
            title="Top 10 Routes by Revenue"
        )
        st.plotly_chart(fig_route, use_container_width=True)

    with st.expander("🔍 View Complete Route Sales Breakdown Data"):
        st.dataframe(
            df_city_route.rename(columns={
                "city_hub": "City Hub",
                "route_name": "Route Name",
                "service_area": "Service Area",
                "total_orders": "Orders",
                "total_units_sold": "Units Sold",
                "total_sales_revenue": "Revenue (LKR)"
            }),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No city or route sales recorded in this quarter.")

st.divider()

st.markdown("**Driver & Assistant Working Hours**")

emp_hours_query = """
    SELECT * FROM get_employee_working_hours_report(%s, %s);
"""
df_emp_hours = load_data(emp_hours_query, (quarter_start_ts, quarter_end_ts))

if not df_emp_hours.empty:
    # Role Filter
    selected_role = st.radio(
        "Filter by Employee Role:",
        options=["All", "DRIVER", "ASSISTANT"],
        horizontal=True
    )
    df_filtered_emp = df_emp_hours if selected_role == "All" else df_emp_hours[df_emp_hours["employee_role"] == selected_role]

    eh1, eh2 = st.columns([1, 1])

    with eh1:
        fig_emp = px.bar(
            df_filtered_emp.head(15),
            x="employee_name",
            y="total_hours_worked",
            color="employee_role",
            labels={"total_hours_worked": "Total Hours Worked", "employee_name": "Employee"},
            title="Top Active Crew Members (Hours Worked in Quarter)"
        )
        st.plotly_chart(fig_emp, use_container_width=True)

    with eh2:
        st.markdown("**Crew Schedule & Threshold Status**")
        st.dataframe(
            df_filtered_emp[[
                "employee_name", "employee_role", "store_name", "total_trips_assigned", "total_hours_worked", "limit_exceeded"
            ]].rename(columns={
                "employee_name": "Name",
                "employee_role": "Role",
                "store_name": "Hub",
                "total_trips_assigned": "Trips",
                "total_hours_worked": "Total Hours",
                "limit_exceeded": "Threshold Exceeded"
            }),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No employee schedule data found for this quarter.")

st.divider()

st.markdown(f"**Truck Usage Analysis (Per Month in Q{current_quarter})**")

truck_month = st.selectbox(
    "Select Month in Current Quarter",
    options=quarter_months,
    format_func=lambda m: f"{calendar.month_name[m]} {current_year}",
    index=quarter_months.index(today.month) if today.month in quarter_months else 0
)

truck_usage_query = """
    SELECT * FROM get_monthly_truck_usage(%s, %s);
"""
df_truck_usage = load_data(truck_usage_query, (current_year, truck_month))

if not df_truck_usage.empty:
    tu1, tu2 = st.columns([1, 1])

    with tu1:
        fig_truck_trips = px.bar(
            df_truck_usage.head(10),
            x="license_plate",
            y="total_trips",
            color="operating_store",
            labels={"total_trips": "Completed Trips", "license_plate": "Truck"},
            title=f"Total Trips Completed ({calendar.month_name[truck_month]})"
        )
        st.plotly_chart(fig_truck_trips, use_container_width=True)

    with tu2:
        fig_truck_hours = px.bar(
            df_truck_usage.head(10),
            x="license_plate",
            y="total_operating_hours",
            color="operating_store",
            labels={"total_operating_hours": "Operating Hours", "license_plate": "Truck"},
            title=f"Operating Hours ({calendar.month_name[truck_month]})"
        )
        st.plotly_chart(fig_truck_hours, use_container_width=True)

    with st.expander(f"📋 Detailed Truck Operations Table ({calendar.month_name[truck_month]})"):
        st.dataframe(
            df_truck_usage[[
                "license_plate", "operating_store", "vehicle_capacity", "vehicle_status",
                "total_trips", "total_operating_hours", "total_items_delivered", "avg_trip_duration_hrs"
            ]].rename(columns={
                "license_plate": "License Plate",
                "operating_store": "Hub",
                "vehicle_capacity": "Capacity",
                "vehicle_status": "Status",
                "total_trips": "Trips",
                "total_operating_hours": "Operating Hrs",
                "total_items_delivered": "Delivered Items",
                "avg_trip_duration_hrs": "Avg Duration (hrs)"
            }),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info(f"No truck operations recorded for {calendar.month_name[truck_month]} {current_year}.")

st.divider()

st.markdown("**Customer Order History & Delivery Details**")

# Fetch customers who made orders in the current quarter
quarter_customers_query = """
    SELECT DISTINCT c.id, c.customer_name 
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    WHERE EXTRACT(YEAR FROM o.order_date) = %s
      AND EXTRACT(QUARTER FROM o.order_date) = %s
    ORDER BY c.customer_name ASC;
"""
df_customers = load_data(quarter_customers_query, (current_year, current_quarter))

if not df_customers.empty:
    customer_dict = dict(zip(df_customers["customer_name"], df_customers["id"]))
    selected_customer_name = st.selectbox(
        "Select Customer to View Delivery Journey:",
        options=list(customer_dict.keys())
    )
    selected_customer_id = customer_dict[selected_customer_name]

    order_history_query = """
        SELECT * FROM get_customer_order_history(%s)
        WHERE EXTRACT(YEAR FROM order_date) = %s
          AND EXTRACT(QUARTER FROM order_date) = %s;
    """
    df_history = load_data(order_history_query, (selected_customer_id, current_year, current_quarter))

    if not df_history.empty:
        st.dataframe(
            df_history.rename(columns={
                "order_id": "Order ID",
                "order_date": "Order Date",
                "scheduled_delivery_date": "Est. Delivery",
                "route_name": "Route",
                "destination_city_hub": "City Hub",
                "product_name": "Product",
                "unit_price": "Unit Price (LKR)",
                "lifecycle_status": "Status",
                "train_trip_id": "Train Trip #",
                "truck_plate": "Truck",
                "driver_name": "Driver",
                "assistant_name": "Assistant",
                "actual_delivered_at": "Actual Delivery Date"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No orders found for this customer within the current quarter.")
else:
    st.info("No active customers with orders in the current quarter.")
