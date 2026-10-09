from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from db import fetch_all
import reports

st.set_page_config(
    page_title="Management Reports",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Management Reports Hub")
st.caption("Generate rail and road logistics reports on demand.")

# Dropdown to select one of the 6 reports
report_options = [
    "1. Quarterly Sales Report (Value & Volume)",
    "2. Most Ordered Items in a Given Quarter",
    "3. City-Wise and Route-Wise Sales Breakdown",
    "4. Driver and Assistant Working Hours",
    "5. Truck Usage Analysis per Month",
    "6. Customer Order History with Delivery Details",
]

selected_report = st.selectbox(
    "Select Report Type",
    options=report_options,
    index=0
)

st.divider()

def render_download_button(df: pd.DataFrame, filename: str):
    """Utility helper to export report data to CSV."""
    if not df.empty:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Report as CSV",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )


# ==============================================================================
# REPORT 1: Quarterly Sales Report
# ==============================================================================
if selected_report.startswith("1."):
    st.subheader("Quarterly Sales Report (Value & Volume)")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        year_input = st.selectbox("Year", options=[2024, 2025, 2026, 2027], index=2, key="r1_year")
    with col2:
        quarter_input = st.selectbox("Quarter", options=["All Quarters", "Q1", "Q2", "Q3", "Q4"], index=0, key="r1_quarter")
    with col3:
        st.write("")
        st.write("")
        btn_r1 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r1 or "r1_df" in st.session_state:
        if btn_r1:
            q_num = None if quarter_input == "All Quarters" else int(quarter_input[1])
            df = reports.get_quarterly_sales_report(
                year=year_input if quarter_input != "All Quarters" else None,
                quarter=q_num
            )
            if quarter_input == "All Quarters" and not df.empty:
                df = df[df["report_year"] == year_input]
            st.session_state["r1_df"] = df

        df = st.session_state.get("r1_df", pd.DataFrame())

        if df.empty:
            st.warning("No sales records found for the selected period.")
        else:
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Items Sold", f"{int(df['total_items_sold'].sum()):,}")
            kpi2.metric("Total Revenue", f"LKR {float(df['total_sales_value'].sum()):,.2f}")
            kpi3.metric("Total Volume Units", f"{float(df['total_volume_space_units'].sum()):,.2f}")

            st.dataframe(df, use_container_width=True)
            render_download_button(df, f"quarterly_sales_{year_input}.csv")


# ==============================================================================
# REPORT 2: Most Ordered Items in a Given Quarter
# ==============================================================================
elif selected_report.startswith("2."):
    st.subheader("Most Ordered Items in a Given Quarter")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        year_input = st.selectbox("Year", options=[2024, 2025, 2026], index=2, key="r2_year")
    with col2:
        quarter_input = st.selectbox("Quarter", options=[1, 2, 3, 4], index=0, key="r2_quarter")
    with col3:
        top_n = st.number_input("Top N Items", min_value=1, max_value=50, value=10, step=1, key="r2_limit")
    with col4:
        st.write("")
        st.write("")
        btn_r2 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r2 or "r2_df" in st.session_state:
        if btn_r2:
            st.session_state["r2_df"] = reports.get_most_ordered_items_report(year_input, quarter_input, top_n)

        df = st.session_state.get("r2_df", pd.DataFrame())

        if df.empty:
            st.warning(f"No order records found for Q{quarter_input} {year_input}.")
        else:
            st.dataframe(df, use_container_width=True)

            if "product_name" in df.columns and "total_quantity_ordered" in df.columns:
                st.bar_chart(df.set_index("product_name")["total_quantity_ordered"])

            render_download_button(df, f"top_items_Q{quarter_input}_{year_input}.csv")


# ==============================================================================
# REPORT 3: City-Wise and Route-Wise Sales Breakdown
# ==============================================================================
elif selected_report.startswith("3."):
    st.subheader("City-Wise and Route-Wise Sales Breakdown")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=90), key="r3_start")
    with col2:
        end_date = st.date_input("End Date", value=date.today(), key="r3_end")
    with col3:
        st.write("")
        st.write("")
        btn_r3 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r3 or "r3_df" in st.session_state:
        if btn_r3:
            st.session_state["r3_df"] = reports.get_city_route_sales_report(start_date, end_date)

        df = st.session_state.get("r3_df", pd.DataFrame())

        if df.empty:
            st.warning("No sales records found for this period.")
        else:
            total_rev = df["total_sales_revenue"].sum() if "total_sales_revenue" in df.columns else 0
            total_orders = df["total_orders"].sum() if "total_orders" in df.columns else 0

            kpi1, kpi2 = st.columns(2)
            kpi1.metric("Total Revenue Across Routes", f"LKR {float(total_rev):,.2f}")
            kpi2.metric("Total Route Orders", f"{int(total_orders):,}")

            st.dataframe(df, use_container_width=True)
            render_download_button(df, f"city_route_sales_{start_date}_{end_date}.csv")


# ==============================================================================
# REPORT 4: Driver and Assistant Working Hours Report
# ==============================================================================
elif selected_report.startswith("4."):
    st.subheader("Driver & Assistant Working Hours & Limit Compliance")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        # Default to previous 7 days (weekly check)
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=7), key="r4_start")
    with col2:
        end_date = st.date_input("End Date", value=date.today(), key="r4_end")
    with col3:
        st.write("")
        st.write("")
        btn_r4 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r4 or "r4_df" in st.session_state:
        if btn_r4:
            st.session_state["r4_df"] = reports.get_employee_working_hours_report(start_date, end_date)

        df = st.session_state.get("r4_df", pd.DataFrame())

        if df.empty:
            st.warning("No logged truck schedules found in this time range.")
        else:
            violations = df[df["limit_exceeded"] == True] if "limit_exceeded" in df.columns else pd.DataFrame()
            if not violations.empty:
                st.error(f"⚠️ Limit Exceeded: {len(violations)} employee(s) crossed maximum working hours for this period! (Driver limit: 40 hrs, Assistant limit: 60 hrs)")

            def highlight_violations(row):
                return ["background-color: #ffd6d6; color: #900;" if row.get("limit_exceeded") else "" for _ in row]

            st.dataframe(df.style.apply(highlight_violations, axis=1), use_container_width=True)
            render_download_button(df, f"employee_working_hours_{start_date}_{end_date}.csv")


# ==============================================================================
# REPORT 5: Truck Usage Analysis per Month
# ==============================================================================
elif selected_report.startswith("5."):
    st.subheader("Truck Usage Analysis per Month")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        year_input = st.selectbox("Year", options=[2024, 2025, 2026], index=2, key="r5_year")
    with col2:
        month_input = st.selectbox(
            "Month",
            options=list(range(1, 13)),
            format_func=lambda m: datetime(2000, m, 1).strftime("%B"),
            index=date.today().month - 1,
            key="r5_month"
        )
    with col3:
        st.write("")
        st.write("")
        btn_r5 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r5 or "r5_df" in st.session_state:
        if btn_r5:
            st.session_state["r5_df"] = reports.get_monthly_truck_usage_report(year_input, month_input)

        df = st.session_state.get("r5_df", pd.DataFrame())

        if df.empty:
            st.warning("No truck activity recorded for the selected month.")
        else:
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Dispatched Trips", f"{int(df['total_trips'].sum()):,}")
            kpi2.metric("Total Operational Hours", f"{float(df['total_operating_hours'].sum()):,.2f} hrs")
            kpi3.metric("Total Units Delivered", f"{int(df['total_items_delivered'].sum()):,}")

            st.dataframe(df, use_container_width=True)
            render_download_button(df, f"truck_usage_{year_input}_{month_input}.csv")


# ==============================================================================
# REPORT 6: Customer Order History with Delivery Details
# ==============================================================================
elif selected_report.startswith("6."):
    st.subheader("Customer Order History with Rail & Road Details")

    # Fetch customer list dynamically for filtering
    customers_data = fetch_all("SELECT id, customer_name FROM customers ORDER BY customer_name ASC;")
    customer_options = {"All Customers": None}
    if customers_data:
        for c in customers_data:
            customer_options[f"{c.customer_name} (ID: {c.id})"] = c.id

    col1, col2 = st.columns([2, 1])
    with col1:
        chosen_customer = st.selectbox("Customer Filter", options=list(customer_options.keys()), key="r6_cust")
    with col2:
        st.write("")
        st.write("")
        btn_r6 = st.button("Generate Report", type="primary", use_container_width=True)

    if btn_r6 or "r6_df" in st.session_state:
        if btn_r6:
            cust_id = customer_options[chosen_customer]
            st.session_state["r6_df"] = reports.get_customer_order_history_report(cust_id)

        df = st.session_state.get("r6_df", pd.DataFrame())

        if df.empty:
            st.warning("No order history records found.")
        else:
            st.dataframe(df, use_container_width=True)
            render_download_button(df, "customer_order_history.csv")