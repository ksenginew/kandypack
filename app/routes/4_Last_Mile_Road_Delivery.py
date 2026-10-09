"""Database-backed CRUD for last-mile delivery schedules and crew rosters."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from psycopg import Error

from db import fetch_all, fetch_data, fetch_one, get_connection
from ui.datatable import render_datatable

LOCAL_TIME = ZoneInfo("Asia/Colombo")
NOTICE_KEY = "road_delivery_notice"


def show_database_error(error):
    if getattr(error, "sqlstate", None) in ("40001", "40P01"):
        st.error("Another roster change happened at the same time. Please try again.")
    elif getattr(error.diag, "constraint_name", None) == "chk_road_delivery_crew":
        st.error("Select a separate driver and driver assistant for this schedule.")
    elif getattr(error.diag, "constraint_name", None) == "chk_truck_schedules_time_window":
        st.error("Delivery end must be after delivery start.")
    else:
        st.error(error.diag.message_primary or "The schedule could not be saved.")


def fetch_schedules(limit, offset):
    return fetch_data(
        """
        SELECT s.id, t.license_plate AS truck, r.route_name AS route,
               d.employee_name AS driver, a.employee_name AS assistant,
               s.start_timestamp AT TIME ZONE 'Asia/Colombo' AS start_local,
               s.end_timestamp AT TIME ZONE 'Asia/Colombo' AS end_local,
               s.duration_hours, r.max_delivery_time_hrs AS route_max_hours,
               (SELECT count(*) FROM truck_item_deliveries i
                WHERE i.truck_schedule_id = s.id) AS assigned_items
        FROM truck_schedules s
        JOIN trucks t ON t.id = s.truck_id
        JOIN routes r ON r.id = s.route_id
        JOIN employees d ON d.id = s.driver_id
        LEFT JOIN employees a ON a.id = s.assistant_id
        ORDER BY s.start_timestamp DESC, s.id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )


def schedule_form(schedule=None):
    routes = fetch_all("SELECT id, route_name, max_delivery_time_hrs FROM routes ORDER BY route_name, id")
    trucks = fetch_all("SELECT id, license_plate, vehicle_status FROM trucks ORDER BY license_plate, id")
    crew = fetch_all("SELECT id, employee_name, employee_role FROM employees ORDER BY employee_name, id")
    drivers = [e for e in crew if e.employee_role == "DRIVER"]
    assistants = [e for e in crew if e.employee_role == "ASSISTANT"]
    if not all((routes, trucks, drivers, assistants)):
        st.info("Add a route, truck, driver, and assistant before scheduling a delivery.")
        return None

    route_labels = {r.id: f"{r.route_name} (maximum {r.max_delivery_time_hrs} hours)" for r in routes}
    truck_labels = {t.id: f"{t.license_plate} ({t.vehicle_status})" for t in trucks}
    driver_labels = {e.id: e.employee_name for e in drivers}
    assistant_labels = {e.id: e.employee_name for e in assistants}
    now = datetime.now(LOCAL_TIME).replace(second=0, microsecond=0)
    start = schedule.start_timestamp.astimezone(LOCAL_TIME) if schedule else now
    end = schedule.end_timestamp.astimezone(LOCAL_TIME) if schedule else now + timedelta(hours=1)
    prefix = f"schedule_edit_{schedule.id}" if schedule else "schedule_create"

    def selection(label, labels, current_id, key):
        options = list(labels)
        return st.selectbox(label, options, index=options.index(current_id) if current_id in options else 0,
                            format_func=labels.get, key=key)

    with st.form(f"{prefix}_form"):
        route_id = selection("Route", route_labels, schedule.route_id if schedule else None, f"{prefix}_route")
        truck_id = selection("Truck", truck_labels, schedule.truck_id if schedule else None, f"{prefix}_truck")
        col1, col2 = st.columns(2)
        with col1:
            driver_id = selection("Driver", driver_labels, schedule.driver_id if schedule else None,
                                  f"{prefix}_driver")
        with col2:
            assistant_id = selection("Driver Assistant", assistant_labels,
                                     schedule.assistant_id if schedule else None, f"{prefix}_assistant")
        st.caption("Dates and times are in Sri Lanka time (Asia/Colombo).")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", start.date(), key=f"{prefix}_start_date")
            start_time = st.time_input("Start Time", start.time().replace(tzinfo=None), step=60,
                                       key=f"{prefix}_start_time")
        with col2:
            end_date = st.date_input("End Date", end.date(), key=f"{prefix}_end_date")
            end_time = st.time_input("End Time", end.time().replace(tzinfo=None), step=60,
                                     key=f"{prefix}_end_time")
        submitted = st.form_submit_button("Save Changes" if schedule else "Create Schedule", type="primary")
    if not submitted:
        return None
    start_at = datetime.combine(start_date, start_time, tzinfo=LOCAL_TIME)
    end_at = datetime.combine(end_date, end_time, tzinfo=LOCAL_TIME)
    if end_at <= start_at:
        st.error("Delivery end must be after delivery start.")
        return None
    return truck_id, route_id, driver_id, assistant_id, start_at, end_at


def save_schedule(values, schedule_id=None):
    actor_id = getattr(st.session_state.get("user"), "id", None)
    try:
        with get_connection() as conn:
            if schedule_id is None:
                row = conn.execute(
                    """INSERT INTO truck_schedules
                       (truck_id, route_id, driver_id, assistant_id,
                        start_timestamp, end_timestamp, created_by, updated_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (*values, actor_id, actor_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """UPDATE truck_schedules SET truck_id = %s, route_id = %s,
                       driver_id = %s, assistant_id = %s, start_timestamp = %s,
                       end_timestamp = %s, updated_by = %s WHERE id = %s RETURNING id""",
                    (*values, actor_id, schedule_id),
                ).fetchone()
        if row is None:
            st.error("This schedule was removed. Refresh the list and try again.")
            return
    except Error as error:
        show_database_error(error)
        return
    st.session_state[NOTICE_KEY] = "Schedule updated." if schedule_id else "Schedule created."
    st.rerun()


@st.dialog("Create Delivery Schedule", width="large")
def create_schedule_dialog():
    values = schedule_form()
    if values is not None:
        save_schedule(values)


@st.dialog("Edit Delivery Schedule", width="large")
def edit_schedule_dialog(schedule_id):
    schedule = fetch_one("SELECT * FROM truck_schedules WHERE id = %s", (schedule_id,))
    if schedule is None:
        st.error("This schedule was removed. Refresh the list.")
        return
    values = schedule_form(schedule)
    if values is not None:
        save_schedule(values, schedule_id)


@st.dialog("Delete Delivery Schedule")
def delete_schedule_dialog(schedule_id):
    st.warning(f"Delete schedule #{schedule_id}?")
    st.caption("Schedules with assigned delivery items are kept to preserve delivery history.")
    if st.button("Confirm Delete", type="primary"):
        try:
            with get_connection() as conn:
                # Lock first so a concurrent delivery-item assignment cannot
                # race the history check and be removed by ON DELETE CASCADE.
                conn.execute("SELECT id FROM truck_schedules WHERE id = %s FOR UPDATE",
                             (schedule_id,)).fetchone()
                row = conn.execute(
                    """DELETE FROM truck_schedules s WHERE s.id = %s
                       AND NOT EXISTS (SELECT 1 FROM truck_item_deliveries i
                                       WHERE i.truck_schedule_id = s.id)
                       RETURNING s.id""", (schedule_id,),
                ).fetchone()
            if row is None:
                st.error("This schedule has assigned delivery items or was already removed.")
                return
        except Error as error:
            show_database_error(error)
            return
        st.session_state[NOTICE_KEY] = "Schedule deleted."
        st.rerun()


st.set_page_config(page_title="Last-Mile Road Delivery", layout="wide")
st.title("4. Last-Mile Road Delivery & Rostering")
st.caption("Create, view, edit, and delete delivery schedules. All times shown are Sri Lanka time.")
notice = st.session_state.pop(NOTICE_KEY, None)
if notice:
    st.success(notice)
with st.expander("Scheduling rules"):
    st.write("Each trip needs one driver and one assistant and must fit within its route's maximum delivery time.")
    st.write("A truck or crew member cannot have overlapping deliveries. Drivers need a gap between trips; "
             "assistants may work at most two trips with no gap.")
    st.write("Working weeks begin on Monday: drivers may work up to 40 hours and assistants up to 60 hours. "
             "Trips crossing a week boundary count toward each week separately.")

try:
    toolbar = st.container()
    total = fetch_one("SELECT count(*) FROM truck_schedules")[0]
    selected = render_datatable(fetch_schedules, total, key="road_delivery_schedules")
    with toolbar:
        create_col, edit_col, delete_col, _ = st.columns([1, 1, 1, 5])
        with create_col:
            if st.button("Create", key="road_delivery_create", width="stretch"):
                create_schedule_dialog()
        with edit_col:
            if st.button("Edit", key="road_delivery_edit", width="stretch", disabled=selected is None):
                edit_schedule_dialog(int(selected[0]["id"]))
        with delete_col:
            if st.button("Delete", key="road_delivery_delete", width="stretch", disabled=selected is None):
                delete_schedule_dialog(int(selected[0]["id"]))
except Error as error:
    show_database_error(error)
