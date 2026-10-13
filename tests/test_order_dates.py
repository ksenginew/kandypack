"""Order date validation and form checks in a disposable database.

Run: docker compose exec -T server python tests/test_order_dates.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import secrets
import sys
import tomllib
import unittest
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TIME = ZoneInfo("Asia/Colombo")


class OrderDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.getenv("DATABASE_URL") or tomllib.loads(
            (ROOT / ".streamlit/secrets.toml").read_text())["DATABASE_URL"]
        options = conninfo_to_dict(url)
        options["dbname"] = "postgres"
        cls.admin = psycopg.connect(make_conninfo(**options), autocommit=True)
        cls.database_name = "order_dates_test_" + secrets.token_hex(8)
        cls.admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database_name)))
        cls.addClassCleanup(cls.remove_database)
        options["dbname"] = cls.database_name
        cls.test_url = make_conninfo(**options)
        with psycopg.connect(cls.test_url) as conn:
            conn.execute((ROOT / "schema/00-schema.sql").read_text(encoding="utf-8"))
            conn.execute("INSERT INTO stores (store_name, address) VALUES ('Test store', 'Kandy')")
            conn.execute("INSERT INTO routes (store_id, route_name, service_area, max_delivery_time_hrs) VALUES (1, 'Test route', 'Kandy', 12)")
            conn.execute("INSERT INTO customers (customer_name, address, contact_phone, default_route_id) VALUES ('Test customer', 'Test address', '+94 77 1234567', 1)")
        sys.path.insert(0, str(ROOT / "app"))
        # Initialize the app DB module with isolated Streamlit secrets before
        # importing its helpers from the test thread.
        app = cls.form_app("from interfaces.orders import earliest_delivery_date\n")
        assert not app.exception, [e.message for e in app.exception]
        from db import pool
        cls.addClassCleanup(pool.close)

    @classmethod
    def remove_database(cls):
        cls.admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.database_name)))
        cls.admin.close()

    @classmethod
    def form_app(cls, script):
        app = AppTest.from_string(script, default_timeout=10)
        app.secrets["DATABASE_URL"] = cls.test_url
        return app.run()

    def tearDown(self):
        with psycopg.connect(self.test_url) as conn:
            conn.execute("DELETE FROM orders")

    def test_minimum_date_respects_full_seven_days_and_sri_lanka_time(self):
        from interfaces.orders import earliest_delivery_date
        cases = (
            (datetime(2026, 10, 13, 11, 59, tzinfo=LOCAL_TIME), "2026-10-20"),
            (datetime(2026, 10, 13, 12, 0, tzinfo=LOCAL_TIME), "2026-10-20"),
            (datetime(2026, 10, 13, 12, 0, 1, tzinfo=LOCAL_TIME), "2026-10-21"),
            # 23:00 UTC is already the following calendar day in Sri Lanka.
            (datetime(2026, 10, 13, 23, 0, tzinfo=timezone.utc), "2026-10-21"),
        )
        for placed, expected in cases:
            with self.subTest(placed=placed):
                self.assertEqual(earliest_delivery_date(placed).isoformat(), expected)

    def test_create_order_default_date_saves_without_constraint_error(self):
        app = self.form_app("from interfaces.orders import create_order_dialog\ncreate_order_dialog.__wrapped__()\n")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        date_input = app.date_input(key="create_order_delivery_date")
        from interfaces.orders import earliest_delivery_date
        self.assertEqual(date_input.value, earliest_delivery_date(datetime.now(LOCAL_TIME)))
        next(button for button in app.button if button.label == "Place Order").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.error, [e.value for e in app.error])
        with psycopg.connect(self.test_url) as conn:
            rows = conn.execute("SELECT order_date, delivery_date FROM orders").fetchall()
        self.assertEqual(len(rows), 1)
        placed, delivery = rows[0]
        self.assertGreaterEqual(delivery, placed + timedelta(days=7))
        self.assertEqual(delivery.astimezone(LOCAL_TIME).hour, 12)

    def test_date_picker_prevents_too_early_submission(self):
        app = self.form_app("from interfaces.orders import create_order_dialog\ncreate_order_dialog.__wrapped__()\n")
        app.date_input(key="create_order_delivery_date").set_value(datetime.now(LOCAL_TIME).date())
        next(button for button in app.button if button.label == "Place Order").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        # Streamlit clamps values below min_value before invoking our handler.
        self.assertGreaterEqual(app.date_input(key="create_order_delivery_date").value,
                                datetime.now(LOCAL_TIME).date() + timedelta(days=7))
        with psycopg.connect(self.test_url) as conn:
            placed, delivery = conn.execute("SELECT order_date, delivery_date FROM orders").fetchone()
        self.assertGreaterEqual(delivery, placed + timedelta(days=7))

    def test_validation_rejects_insufficient_full_days_with_clear_message(self):
        app = self.form_app(
            "from datetime import datetime\n"
            "from zoneinfo import ZoneInfo\n"
            "from interfaces.orders import validate_delivery_date\n"
            "zone = ZoneInfo('Asia/Colombo')\n"
            "validate_delivery_date(datetime(2026, 10, 20, 12, tzinfo=zone), "
            "datetime(2026, 10, 13, 12, 0, 1, tzinfo=zone))\n")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(any("at least 7 days" in e.value and "21 Oct 2026" in e.value for e in app.error))

    def test_database_constraint_failure_shows_message_without_traceback(self):
        # Invalid phone input exercises a real database check violation.
        app = self.form_app("from interfaces.orders import create_order_dialog\ncreate_order_dialog.__wrapped__()\n")
        next(field for field in app.text_input if field.label == "Contact Phone").set_value("bad")
        next(button for button in app.button if button.label == "Place Order").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertTrue(any("could not be saved" in e.value for e in app.error))
        with psycopg.connect(self.test_url) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 0)

    def existing_order(self):
        with psycopg.connect(self.test_url) as conn:
            return conn.execute("""INSERT INTO orders (customer_id, route_id, delivery_address, contact_phone, order_date, delivery_date)
                                   VALUES (1, 1, 'Original address', '+94 77 1234567', '2026-09-01 12:00+00', '2026-09-08 12:00+00')
                                   RETURNING id, delivery_date""").fetchone()

    def test_edit_historical_order_preserves_timestamp_when_address_changes(self):
        order_id, original_timestamp = self.existing_order()
        app = self.form_app(f"from interfaces.orders import edit_order_dialog\nedit_order_dialog.__wrapped__({order_id})\n")
        self.assertFalse(app.exception, [e.message for e in app.exception])
        app.text_area[0].set_value("New address")
        next(button for button in app.button if button.label == "Save Changes").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.error, [e.value for e in app.error])
        with psycopg.connect(self.test_url) as conn:
            address, delivery = conn.execute("SELECT delivery_address, delivery_date FROM orders WHERE id = %s", (order_id,)).fetchone()
        self.assertEqual(address, "New address")
        self.assertEqual(delivery, original_timestamp)

    def test_edit_date_cannot_violate_original_order_advance_notice(self):
        order_id, original_timestamp = self.existing_order()
        app = self.form_app(f"from interfaces.orders import edit_order_dialog\nedit_order_dialog.__wrapped__({order_id})\n")
        app.date_input(key=f"edit_order_delivery_date_{order_id}").set_value(original_timestamp.date() - timedelta(days=1))
        next(button for button in app.button if button.label == "Save Changes").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(app.date_input(key=f"edit_order_delivery_date_{order_id}").value,
                         original_timestamp.astimezone(LOCAL_TIME).date())
        with psycopg.connect(self.test_url) as conn:
            delivery = conn.execute("SELECT delivery_date FROM orders WHERE id = %s", (order_id,)).fetchone()[0]
        self.assertEqual(delivery, original_timestamp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
