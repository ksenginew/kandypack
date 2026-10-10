from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from psycopg import Error

from db import fetch_all, fetch_data, fetch_one, get_connection
from ui.datatable import render_datatable

LOCAL_TIME = ZoneInfo("Asia/Colombo")
NOTICE_KEY = "road_delivery_notice"


def manager_id():
    user = st.session_state.get("user")
    return user.id if getattr(user, "role", None) == "store_manager" else None


def fetch_received_orders(route_id):
    return fetch_all(
        """SELECT o.id, c.customer_name, o.delivery_address,
                  o.order_date AT TIME ZONE 'Asia/Colombo' AS order_placed,
                  count(i.id) AS item_count, sum(i.quantity) AS total_quantity
           FROM orders o JOIN customers c ON c.id = o.customer_id
           JOIN order_items i ON i.order_id = o.id
           JOIN routes r ON r.id = o.route_id
           JOIN routes chosen ON chosen.id = %s
           JOIN stores store ON store.id = r.store_id
           WHERE (r.store_id, r.route_name, r.service_area, r.max_delivery_time_hrs) =
                 (chosen.store_id, chosen.route_name, chosen.service_area, chosen.max_delivery_time_hrs)
             AND (%s::uuid IS NULL OR store.manager_id = %s)
           GROUP BY o.id, c.customer_name
           HAVING bool_and(i.item_lifecycle_status = 'STORE_RECEIVED')
              AND NOT EXISTS (SELECT 1 FROM truck_item_deliveries d
                              JOIN order_items assigned ON assigned.id = d.order_item_id
                              WHERE assigned.order_id = o.id)
           ORDER BY o.order_date, o.id""",
        (route_id, manager_id(), manager_id()),
    )


def fetch_managed_schedule(schedule_id):
    return fetch_one(
        """SELECT schedule.* FROM truck_schedules schedule
           JOIN routes r ON r.id = schedule.route_id JOIN stores store ON store.id = r.store_id
           WHERE schedule.id = %s AND (%s::uuid IS NULL OR store.manager_id = %s)""",
        (schedule_id, manager_id(), manager_id()),
    )


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
               (SELECT count(DISTINCT i.order_id) FROM truck_item_deliveries d
                JOIN order_items i ON i.id = d.order_item_id
                WHERE d.truck_schedule_id = s.id) AS assigned_orders
        FROM truck_schedules s
        JOIN trucks t ON t.id = s.truck_id
        JOIN routes r ON r.id = s.route_id
        JOIN employees d ON d.id = s.driver_id
        LEFT JOIN employees a ON a.id = s.assistant_id
        JOIN stores store ON store.id = r.store_id
        WHERE (%s::uuid IS NULL OR store.manager_id = %s)
        ORDER BY s.start_timestamp DESC, s.id DESC
        LIMIT %s OFFSET %s
        """,
        (manager_id(), manager_id(), limit, offset),
    )


def unique_records(records, fields, current_id=None):
    """Collapse matching records while keeping an edited schedule's assigned ID."""
    unique = {}
    for record in records:
        identity = tuple(getattr(record, field) for field in fields)
        if identity not in unique or record.id == current_id:
            unique[identity] = record
    return list(unique.values())


def distinguish_labels(records, labels):
    """Keep different records with the same display text identifiable."""
    counts = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    return {
        record.id: (f"{labels[record.id]} ({record.store_name}, #{record.id})"
                    if counts[labels[record.id]] > 1 else labels[record.id])
        for record in records
    }


def schedule_form(schedule=None):
    routes = fetch_all("""SELECT r.id, r.store_id, r.route_name, r.service_area,
                                r.max_delivery_time_hrs, s.store_name
                         FROM routes r JOIN stores s ON s.id = r.store_id
                         WHERE (%s::uuid IS NULL OR s.manager_id = %s)
                         ORDER BY r.route_name, r.id""", (manager_id(), manager_id()))
    routes = unique_records(
        routes, ("store_id", "route_name", "service_area", "max_delivery_time_hrs"),
        schedule.route_id if schedule else None,
    )
    if not routes:
        st.info("No delivery routes are available for your store. Add a route before scheduling a delivery.")
        return None
    prefix = f"schedule_edit_{schedule.id}" if schedule else "schedule_create"

    def selection(label, labels, current_id, key):
        options = list(labels)
        return st.selectbox(label, options, index=options.index(current_id) if current_id in options else 0,
                            format_func=labels.get, key=key)

    route_labels = distinguish_labels(
        routes, {r.id: f"{r.route_name} (maximum {r.max_delivery_time_hrs} hours)" for r in routes},
    )
    # Outside the form: changing route immediately reloads orders and store resources.
    route_id = selection("Route", route_labels, schedule.route_id if schedule else None, f"{prefix}_route")
    store = next(r for r in routes if r.id == route_id)
    st.caption(f"Delivery store: {store.store_name}")
    trucks = fetch_all("""SELECT id, license_plate, vehicle_status FROM trucks
                          WHERE store_id = %s ORDER BY license_plate, id""", (store.store_id,))
    crew = fetch_all("""SELECT e.id, e.store_id, e.employee_name, e.employee_role,
                              e.contact_phone, e.employee_status, s.store_name
                       FROM employees e JOIN stores s ON s.id = e.store_id
                       WHERE e.store_id = %s ORDER BY e.employee_name, e.id""", (store.store_id,))
    crew_fields = ("store_id", "employee_name", "employee_role", "contact_phone", "employee_status")
    drivers = unique_records(
        [e for e in crew if e.employee_role == "DRIVER"], crew_fields,
        schedule.driver_id if schedule else None,
    )
    assistants = unique_records(
        [e for e in crew if e.employee_role == "ASSISTANT"], crew_fields,
        schedule.assistant_id if schedule else None,
    )
    if not all((routes, trucks, drivers, assistants)):
        st.info("Add a route, truck, driver, and assistant before scheduling a delivery.")
        return None

    truck_labels = {t.id: f"{t.license_plate} ({t.vehicle_status})" for t in trucks}
    driver_labels = distinguish_labels(drivers, {e.id: e.employee_name for e in drivers})
    assistant_labels = distinguish_labels(assistants, {e.id: e.employee_name for e in assistants})
    now = datetime.now(LOCAL_TIME).replace(second=0, microsecond=0)
    start = schedule.start_timestamp.astimezone(LOCAL_TIME) if schedule else now
    end = schedule.end_timestamp.astimezone(LOCAL_TIME) if schedule else now + timedelta(hours=1)
    order_ids = []
    if schedule is None:
        orders = fetch_received_orders(route_id)
        order_labels = {
            o.id: f"Order #{o.id}: {o.customer_name} | {o.delivery_address} | "
                  f"{o.item_count} items, {o.total_quantity} units | Placed {o.order_placed:%Y-%m-%d}"
            for o in orders
        }
    else:
        assigned = fetch_data(
            """SELECT DISTINCT o.id AS order_id, c.customer_name, o.delivery_address,
                              o.order_date AT TIME ZONE 'Asia/Colombo' AS order_placed
               FROM truck_item_deliveries d JOIN order_items i ON i.id = d.order_item_id
               JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id
               WHERE d.truck_schedule_id = %s ORDER BY o.id""", (schedule.id,),
        )
        if not assigned.empty:
            st.write("Assigned orders")
            st.dataframe(assigned, hide_index=True, width="stretch")

    with st.form(f"{prefix}_form"):
        if schedule is None:
            order_ids = st.multiselect(
                "Received Orders", list(order_labels), format_func=order_labels.get,
                key=f"{prefix}_orders_{route_id}", disabled=not orders,
                placeholder="Select received orders" if orders else "No received orders ready for delivery",
            )
            if not orders:
                st.info("No complete, unassigned orders have been received for this route.")
            st.caption("An order is ready when all its items are received at this store. "
                       "All items in each selected order will be assigned to this delivery.")
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
        submitted = st.form_submit_button("Save Changes" if schedule else "Create Schedule", type="primary",
                                          disabled=schedule is None and not orders)
    if not submitted:
        return None
    start_at = datetime.combine(start_date, start_time, tzinfo=LOCAL_TIME)
    end_at = datetime.combine(end_date, end_time, tzinfo=LOCAL_TIME)
    if end_at <= start_at:
        st.error("Delivery end must be after delivery start.")
        return None
    if schedule is None and not order_ids:
        st.error("Select at least one received order for this delivery.")
        return None
    return (truck_id, route_id, driver_id, assistant_id, start_at, end_at), order_ids


def save_schedule(values, schedule_id=None):
    schedule_values, order_ids = values
    actor_id = getattr(st.session_state.get("user"), "id", None)
    try:
        with get_connection() as conn:
            if schedule_id is None:
                row = conn.execute(
                    "SELECT create_received_order_delivery(%s, %s, %s, %s, %s, %s, %s, %s)",
                    (*schedule_values, order_ids, actor_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """UPDATE truck_schedules SET truck_id = %s, route_id = %s,
                       driver_id = %s, assistant_id = %s, start_timestamp = %s,
                       end_timestamp = %s, updated_by = %s WHERE id = %s
                       AND (%s::uuid IS NULL OR EXISTS (
                           SELECT 1 FROM routes r JOIN stores store ON store.id = r.store_id
                           WHERE r.id = truck_schedules.route_id AND store.manager_id = %s))
                       AND (%s::uuid IS NULL OR EXISTS (
                           SELECT 1 FROM routes r JOIN stores store ON store.id = r.store_id
                           WHERE r.id = %s AND store.manager_id = %s)) RETURNING id""",
                    (*schedule_values, actor_id, schedule_id, manager_id(), manager_id(),
                     manager_id(), schedule_values[1], manager_id()),
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
    schedule = fetch_managed_schedule(schedule_id)
    if schedule is None:
        st.error("This schedule was removed. Refresh the list.")
        return
    values = schedule_form(schedule)
    if values is not None:
        save_schedule(values, schedule_id)


@st.dialog("Delete Delivery Schedule")
def delete_schedule_dialog(schedule_id):
    if fetch_managed_schedule(schedule_id) is None:
        st.error("This schedule is unavailable for your store.")
        return
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
                       AND (%s::uuid IS NULL OR EXISTS (
                           SELECT 1 FROM routes r JOIN stores store ON store.id = r.store_id
                           WHERE r.id = s.route_id AND store.manager_id = %s))
                       RETURNING s.id""", (schedule_id, manager_id(), manager_id()),
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
st.caption("Select received orders and assign a truck and crew for delivery. All times shown are Sri Lanka time.")
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
    total = fetch_one("""SELECT count(*) FROM truck_schedules s JOIN routes r ON r.id = s.route_id
                         JOIN stores store ON store.id = r.store_id
                         WHERE (%s::uuid IS NULL OR store.manager_id = %s)""",
                      (manager_id(), manager_id()))[0]
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
