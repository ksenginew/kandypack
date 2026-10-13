"""Delivery lifecycle and dashboard checks in a disposable PostgreSQL database.

Run: docker compose exec -T server python tests/test_delivery_operations.py
"""
import os
from datetime import date, time
from pathlib import Path
import secrets
import sys
import tomllib
from types import SimpleNamespace
import unittest

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parents[1]


class DeliveryOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.getenv("DATABASE_URL") or tomllib.loads(
            (ROOT / ".streamlit/secrets.toml").read_text())["DATABASE_URL"]
        options = conninfo_to_dict(url)
        options["dbname"] = "postgres"
        cls.admin_conn = psycopg.connect(make_conninfo(**options), autocommit=True)
        cls.database_name = "delivery_operations_test_" + secrets.token_hex(8)
        cls.admin_conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database_name)))
        cls.addClassCleanup(cls.remove_database)
        options["dbname"] = cls.database_name
        cls.test_url = make_conninfo(**options)
        with psycopg.connect(cls.test_url, autocommit=True) as conn:
            for filename in ("00-schema.sql", "03-complete_delivery.sql", "06-schedule_delivery.sql",
                             "09-delivery_operations.sql", "09-delivery_operations.sql"):
                conn.execute((ROOT / "schema" / filename).read_text(encoding="utf-8"))
            cls.actors = {}
            for name, role in (("admin", "admin"), ("manager", "store_manager"),
                               ("other_manager", "store_manager"), ("user", "user"), ("other_user", "user")):
                cls.actors[name] = conn.execute(
                    "INSERT INTO users (name, email, role, password_hash) VALUES (%s, %s, %s, 'unused') RETURNING id",
                    (name, f"{name}@example.com", role)).fetchone()[0]
            conn.execute("INSERT INTO stores (store_name, address, manager_id) VALUES ('Own store', 'Kandy', %s), ('Other store', 'Colombo', %s)",
                         (cls.actors["manager"], cls.actors["other_manager"]))
            conn.execute("INSERT INTO routes (store_id, route_name, service_area, max_delivery_time_hrs) VALUES (1, 'Own route', 'Kandy', 12), (2, 'Other route', 'Colombo', 12)")
            conn.execute("INSERT INTO trucks (store_id, license_plate, capacity) VALUES (1, 'OWN-1', 100), (1, 'OWN-2', 100), (2, 'OTHER-1', 100)")
            conn.execute("""INSERT INTO employees (store_id, employee_name, employee_role, contact_phone)
                            VALUES (1, 'Driver 1', 'DRIVER', '0771234567'), (1, 'Driver 2', 'DRIVER', '0771234567'),
                                   (1, 'Assistant 1', 'ASSISTANT', '0771234567'), (1, 'Assistant 2', 'ASSISTANT', '0771234567'),
                                   (2, 'Other driver', 'DRIVER', '0771234567'), (2, 'Other assistant', 'ASSISTANT', '0771234567')""")
            conn.execute("INSERT INTO products (product_name, unit_price, space_consumption_unit) VALUES ('Product', 10, 1)")

    @classmethod
    def remove_database(cls):
        cls.admin_conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.database_name)))
        cls.admin_conn.close()

    def setUp(self):
        self.conn = psycopg.connect(self.test_url)

    def tearDown(self):
        self.conn.close()
        with psycopg.connect(self.test_url) as conn:
            conn.execute("DELETE FROM truck_schedules")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM customers")

    def order(self, user="user", route=1, status="STORE_RECEIVED"):
        customer = self.conn.execute("INSERT INTO customers (customer_name, address, contact_phone, user_id) VALUES (%s, 'Address', '0771234567', %s) RETURNING id",
                                     (user, self.actors[user])).fetchone()[0]
        order = self.conn.execute("""INSERT INTO orders (customer_id, route_id, delivery_address, contact_phone, order_date, delivery_date)
                                     VALUES (%s, %s, 'Address', '0771234567', '2026-09-20', '2026-10-05') RETURNING id""",
                                  (customer, route)).fetchone()[0]
        self.conn.execute("INSERT INTO order_items (order_id, product_id, unit_price, item_lifecycle_status) SELECT %s, 1, 10, %s FROM generate_series(1, 2)",
                          (order, status))
        return order

    def schedule(self, orders, route=1, truck=1, driver=1, assistant=3):
        return self.conn.execute("""SELECT create_received_order_delivery(%s, %s, %s, %s,
                                   '2026-10-05 08:00+05:30', '2026-10-05 10:00+05:30', %s, %s)""",
                                 (truck, route, driver, assistant, orders, self.actors["admin"])).fetchone()[0]

    def status(self, schedule, order, status, actor="admin"):
        self.conn.execute("CALL sp_set_scheduled_order_status(%s, %s, %s, %s)",
                          (schedule, order, status, self.actors.get(actor)))

    def rejected(self, operation, text):
        with self.assertRaises(psycopg.errors.CheckViolation) as caught:
            with self.conn.transaction():
                operation()
        self.assertIn(text, str(caught.exception))

    def test_scheduling_dispatches_items_and_delivery_repeat_preserves_timestamps(self):
        own, other, unassigned = self.order(), self.order("other_user"), self.order()
        schedule = self.schedule([own, other])
        self.status(schedule, own, "OUT_FOR_DELIVERY", "manager")
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (own,)).fetchall(), [("OUT_FOR_DELIVERY",)])
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (other,)).fetchall(), [("OUT_FOR_DELIVERY",)])
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (unassigned,)).fetchall(), [("STORE_RECEIVED",)])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_item_deliveries WHERE delivered_at IS NOT NULL").fetchone()[0], 0)
        self.status(schedule, own, "DELIVERED")
        timestamps = self.conn.execute("SELECT delivered_at FROM truck_item_deliveries WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s) ORDER BY id", (own,)).fetchall()
        self.assertTrue(all(row[0] is not None for row in timestamps))
        self.conn.commit()
        self.status(schedule, own, "DELIVERED")
        self.assertEqual(self.conn.execute("SELECT delivered_at FROM truck_item_deliveries WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s) ORDER BY id", (own,)).fetchall(), timestamps)
        self.rejected(lambda: self.status(schedule, own, "OUT_FOR_DELIVERY"), "cannot be dispatched again")

    def test_unassigned_unreceived_and_invalid_transitions_rejected(self):
        own, unassigned = self.order(), self.order()
        schedule = self.schedule([own])
        self.rejected(lambda: self.status(schedule, unassigned, "OUT_FOR_DELIVERY"), "not assigned")
        # Legacy assignments can still be received until explicitly dispatched.
        self.conn.execute("UPDATE order_items SET item_lifecycle_status = 'STORE_RECEIVED' WHERE order_id = %s", (own,))
        for value in ("DELIVERED", "DELIVERY_FAILED"):
            self.rejected(lambda: self.status(schedule, own, value), "Dispatch received items")
        for value in ("PLACED", "NOT_A_STATUS", None):
            self.rejected(lambda: self.status(schedule, own, value), "valid delivery status")
        self.conn.execute("UPDATE order_items SET item_lifecycle_status = 'IN_TRANSIT' WHERE order_id = %s", (own,))
        self.rejected(lambda: self.status(schedule, own, "OUT_FOR_DELIVERY"), "Dispatch received items")

    def test_failed_delivery_and_cancellation(self):
        own = self.order()
        schedule = self.schedule([own])
        self.status(schedule, own, "OUT_FOR_DELIVERY")
        self.status(schedule, own, "DELIVERY_FAILED")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_item_deliveries WHERE delivered_at IS NOT NULL").fetchone()[0], 0)
        self.status(schedule, own, "CANCELLED")
        self.rejected(lambda: self.status(schedule, own, "OUT_FOR_DELIVERY"), "cannot be dispatched again")

    def test_failed_booking_leaves_items_received_and_unassigned(self):
        booked, pending = self.order(), self.order()
        self.schedule([booked])
        self.rejected(lambda: self.schedule([pending]), "overlapping")
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (pending,)).fetchall(), [("STORE_RECEIVED",)])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_schedules").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_item_deliveries").fetchone()[0], 2)

    def test_rolled_back_schedule_rolls_back_item_statuses(self):
        own = self.order()
        with self.conn.transaction(force_rollback=True):
            self.schedule([own])
            self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (own,)).fetchall(), [("OUT_FOR_DELIVERY",)])
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (own,)).fetchall(), [("STORE_RECEIVED",)])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_schedules").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_item_deliveries").fetchone()[0], 0)

    def test_role_and_store_permissions(self):
        own = self.order()
        schedule = self.schedule([own])
        for actor in ("other_manager", "user", "other_user", "missing"):
            self.rejected(lambda: self.status(schedule, own, "OUT_FOR_DELIVERY", actor), "permission")
        self.status(schedule, own, "OUT_FOR_DELIVERY", "manager")
        self.status(schedule, own, "DELIVERED", "admin")

    def test_only_selected_schedule_items_change(self):
        own = self.order()
        first = self.schedule([own])
        second = self.conn.execute("""INSERT INTO truck_schedules (truck_id, route_id, driver_id, assistant_id, start_timestamp, end_timestamp)
                                      VALUES (2, 1, 2, 4, '2026-10-05 08:00+05:30', '2026-10-05 10:00+05:30') RETURNING id""").fetchone()[0]
        self.conn.execute("UPDATE truck_item_deliveries SET truck_schedule_id = %s WHERE id = (SELECT max(id) FROM truck_item_deliveries)", (second,))
        self.status(first, own, "DELIVERED")
        self.assertEqual(self.conn.execute("SELECT d.truck_schedule_id, i.item_lifecycle_status FROM truck_item_deliveries d JOIN order_items i ON i.id = d.order_item_id ORDER BY d.id").fetchall(),
                         [(first, "DELIVERED"), (second, "OUT_FOR_DELIVERY")])

    def app(self, filename, actor):
        from streamlit.testing.v1 import AppTest
        sys.path.insert(0, str(ROOT / "app"))
        app = AppTest.from_file(str(ROOT / "app" / filename), default_timeout=15)
        app.secrets["DATABASE_URL"] = self.test_url
        role = "store_manager" if actor.endswith("manager") else "user" if actor.endswith("user") else "admin"
        app.session_state["user"] = SimpleNamespace(id=self.actors[actor], role=role)
        return app.run()

    def test_ui_delivery_updates_order_and_user_dashboard(self):
        own, other = self.order(), self.order("other_user")
        schedule = self.schedule([own, other])
        self.conn.commit()
        app = self.app("routes/11_Delivery_Operations.py", "manager")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        app.selectbox(key=f"delivery_operations_order_{schedule}").set_value(own)
        app.selectbox(key="delivery_operations_status").set_value("OUT_FOR_DELIVERY")
        app.button(key="delivery_operations_apply").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(any("Out For Delivery" in message.value for message in app.success))
        dashboard = self.app("routes/00_Dashboard.py", "user")
        self.assertFalse(dashboard.exception, [e.message for e in dashboard.exception])
        self.assertEqual(list(dashboard.dataframe[0].value.Order), [own])
        self.assertEqual(list(dashboard.dataframe[1].value.Status), ["OUT_FOR_DELIVERY"])
        self.assertEqual(next(metric.value for metric in dashboard.metric if metric.label == "Orders out for delivery"), "1")
        self.assertFalse(any(button.key == "delivery_operations_apply" for button in dashboard.button))
        app.selectbox(key="delivery_operations_status").set_value("DELIVERED")
        app.button(key="delivery_operations_apply").click().run()
        dashboard.button(key="my_orders_refresh").click().run()
        self.assertEqual(list(dashboard.dataframe[1].value.Status), ["DELIVERED"])
        self.assertEqual(next(metric.value for metric in dashboard.metric if metric.label == "Delivered orders"), "1")

    def test_ui_create_schedule_updates_user_dashboard_immediately(self):
        from streamlit.testing.v1 import AppTest
        own, unassigned = self.order(), self.order("other_user")
        self.conn.commit()
        sys.path.insert(0, str(ROOT / "app"))
        # Exercise the same form/save path without browser dialog fragments.
        app = AppTest.from_string(
            "from interfaces.truck_schedules import schedule_form, save_schedule\n"
            "values = schedule_form()\n"
            "if values is not None: save_schedule(values)\n", default_timeout=15)
        app.secrets["DATABASE_URL"] = self.test_url
        app.session_state["user"] = SimpleNamespace(id=self.actors["manager"], role="store_manager")
        app.run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        app.multiselect(key="schedule_create_orders_1").set_value([own])
        app.date_input(key="schedule_create_start_date").set_value(date(2026, 10, 5))
        app.date_input(key="schedule_create_end_date").set_value(date(2026, 10, 5))
        app.time_input(key="schedule_create_start_time").set_value(time(8))
        app.time_input(key="schedule_create_end_time").set_value(time(10))
        next(button for button in app.button if button.label == "Create Schedule").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.error, [e.value for e in app.error])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM truck_schedules").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT DISTINCT item_lifecycle_status FROM order_items WHERE order_id = %s", (unassigned,)).fetchall(), [("STORE_RECEIVED",)])
        dashboard = self.app("routes/00_Dashboard.py", "user")
        self.assertFalse(dashboard.exception, [e.message for e in dashboard.exception])
        self.assertEqual(list(dashboard.dataframe[1].value.Status), ["OUT_FOR_DELIVERY"])
        self.assertEqual(next(metric.value for metric in dashboard.metric if metric.label == "Orders out for delivery"), "1")

    def test_ui_store_scope_cannot_leak_schedules_between_sessions(self):
        own, other = self.order(), self.order("other_user", route=2)
        own_schedule = self.schedule([own])
        other_schedule = self.schedule([other], route=2, truck=3, driver=5, assistant=6)
        self.conn.commit()
        app = self.app("routes/11_Delivery_Operations.py", "manager")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(all(f"Schedule #{own_schedule}" in option for option in app.selectbox(key="delivery_operations_schedule").options))
        app = self.app("routes/11_Delivery_Operations.py", "other_manager")
        self.assertTrue(all(f"Schedule #{other_schedule}" in option for option in app.selectbox(key="delivery_operations_schedule").options))
        app = self.app("routes/11_Delivery_Operations.py", "user")
        self.assertFalse(app.selectbox)
        self.assertTrue(any("permission" in error.value for error in app.error))

    def test_user_order_details_are_scoped_and_mixed_statuses_visible(self):
        own, other = self.order(), self.order("other_user")
        schedule = self.schedule([own])
        self.status(schedule, own, "OUT_FOR_DELIVERY")
        self.conn.execute("UPDATE order_items SET item_lifecycle_status = 'STORE_RECEIVED' WHERE id = (SELECT max(id) FROM order_items WHERE order_id = %s)", (own,))
        self.conn.commit()
        app = self.app("routes/00_Dashboard.py", "user")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(list(app.dataframe[0].value.Order), [own])
        self.assertEqual(set(app.dataframe[1].value.Status), {"STORE_RECEIVED", "OUT_FOR_DELIVERY"})
        app.selectbox(key="my_orders_status").set_value("OUT_FOR_DELIVERY").run()
        self.assertEqual(list(app.dataframe[0].value.Order), [own])
        from interfaces.my_orders import fetch_my_order_items
        self.assertTrue(fetch_my_order_items(self.actors["user"], other).empty)

    def test_empty_user_dashboard(self):
        app = self.app("routes/00_Dashboard.py", "user")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(any("No orders" in info.value for info in app.info))


if __name__ == "__main__":
    unittest.main(verbosity=2)
