from datetime import date, datetime
from typing import Optional, Union
import pandas as pd
from db import fetch_data


def get_quarterly_sales_report(
    year: Optional[int] = None, quarter: Optional[int] = None
) -> pd.DataFrame:
    """Report 1: Quarterly sales report (value and volume).

    If year and quarter are provided, returns data filtered for that specific quarter.
    Otherwise, returns the complete quarterly sales breakdown.
    """
    if year is not None and quarter is not None:
        query = "SELECT * FROM view_quarterly_sales_report v WHERE v.report_year = %s AND v.report_quarter = %s;"
        return fetch_data(query, (year, quarter))

    query = "SELECT * FROM view_quarterly_sales_report;"
    return fetch_data(query)


def get_most_ordered_items_report(
    year: int, quarter: int, limit: int = 10
) -> pd.DataFrame:
    """Report 2: Most ordered items in a given quarter ranked by sales and quantity."""
    query = "SELECT * FROM get_most_ordered_items_by_quarter(%s, %s, %s);"
    return fetch_data(query, (year, quarter, limit))


def get_city_route_sales_report(
    start_date: Union[date, datetime, str],
    end_date: Union[date, datetime, str],
) -> pd.DataFrame:
    """Report 3: City-wise and route-wise sales breakdown.

    If start_date and end_date are provided, filters orders within that range.
    Otherwise, returns the overall historical breakdown.
    """
    query = "SELECT * FROM get_city_route_sales(%s, %s);"
    return fetch_data(query, (start_date, end_date))


def get_employee_working_hours_report(
    start_date: Union[date, datetime, str],
    end_date: Union[date, datetime, str],
) -> pd.DataFrame:
    """Report 4: Driver and assistant working hours report with threshold compliance."""
    query = "SELECT * FROM get_employee_working_hours_report(%s, %s);"
    return fetch_data(query, (start_date, end_date))


def get_monthly_truck_usage_report(year: int, month: int) -> pd.DataFrame:
    """Report 5: Truck usage analysis per month (trip count, operating hours, items delivered)."""
    query = "SELECT * FROM get_monthly_truck_usage(%s, %s);"
    return fetch_data(query, (year, month))


def get_customer_order_history_report(
    customer_id: Optional[int] = None,
) -> pd.DataFrame:
    """Report 6: Customer order history with full rail and road delivery details."""
    if customer_id is not None:
        query = """
            SELECT *
            FROM view_customer_order_delivery_details
            WHERE customer_id = %s
            ORDER BY order_date DESC, order_item_id ASC;
        """
        return fetch_data(query, (customer_id,))

    query = "SELECT * FROM view_customer_order_delivery_details;"
    return fetch_data(query)
