from datetime import datetime, timedelta, timezone
import json
import random
import uuid
from argon2 import PasswordHasher

ph = PasswordHasher()
password_hash = ph.hash("password")

random.seed(42)
OUTPUT_FILE = "schema/01-seed.sql"
BASE_TIME = datetime(2026, 10, 9, 8, 0, 0, tzinfo=timezone.utc)


FIRST_NAMES = [
    "Kavindu", "Nuwan", "Chathura", "Dinesh", "Saman", "Kasun", "Ruwan", "Dilshan",
    "Pradeep", "Nadeesha", "Sanduni", "Tharushi", "Malsha", "Ishara", "Suresh",
    "Mahesh", "Nalaka", "Chaminda", "Supun", "Roshan", "Anura", "Janaka", "Priyantha",
    "Ashan", "Duminda", "Buddhika", "Harsha", "Manjula", "Sunil", "Bandula"
]

LAST_NAMES = [
    "Perera", "Fernando", "Silva", "Jayasinghe", "Bandara", "Dissanayake", "Herath",
    "Gunasekara", "Amarasinghe", "Karunaratne", "Senanayake", "Ranasinghe", "Liyanage",
    "Wickramasinghe", "Ekanayake", "Rajapaksha", "Mendis", "Alwis", "Weerasinghe"
]

CITIES = [
    ("Colombo Central Store", "No. 45, Galle Road, Colombo 03", "Colombo"),
    ("Kandy Regional Hub", "No. 12, Peradeniya Road, Kandy", "Kandy"),
    ("Galle Coastal Hub", "No. 88, Matara Road, Galle", "Galle"),
    ("Gampaha Distribution Hub", "No. 102, Kandy Road, Yakkala", "Gampaha"),
    ("Kurunegala Transit Hub", "No. 15, Dambulla Road, Kurunegala", "Kurunegala"),
    ("Negombo Logistics Hub", "No. 73, Main Street, Negombo", "Negombo"),
    ("Ratnapura Depot", "No. 22, Colombo Road, Ratnapura", "Ratnapura"),
    ("Anuradhapura Center", "No. 31, Maithripala Senanayake Mawatha, Anuradhapura", "Anuradhapura"),
    ("Matara Station Store", "No. 54, Station Road, Matara", "Matara"),
    ("Badulla Mountain Depot", "No. 67, Lower Street, Badulla", "Badulla")
]

PRODUCT_CATALOG = [
    ("Organic Green Tea (500g)", 850.00, 0.0025, {"category": "Beverages", "weight_kg": 0.5}),
    ("Ceylon Black Tea Export Pack (1kg)", 1600.00, 0.0040, {"category": "Beverages", "weight_kg": 1.0}),
    ("Pure Coconut Oil (1L)", 1150.00, 0.0018, {"category": "Groceries", "liquid": True}),
    ("Red Raw Rice (5kg)", 1100.00, 0.0080, {"category": "Grains", "weight_kg": 5.0}),
    ("White Basmati Rice (5kg)", 2400.00, 0.0080, {"category": "Grains", "weight_kg": 5.0}),
    ("Whole White Pepper (200g)", 620.00, 0.0010, {"category": "Spices", "grade": "Premium"}),
    ("Organic Cinnamon Sticks (250g)", 980.00, 0.0015, {"category": "Spices", "origin": "Matara"}),
    ("Roasted Coffee Beans (500g)", 2100.00, 0.0028, {"category": "Beverages", "roast": "Medium-Dark"}),
    ("Dehydrated Mango Slices (200g)", 750.00, 0.0012, {"category": "Snacks", "organic": True}),
    ("Organic Virgin Coconut Oil (500ml)", 890.00, 0.0012, {"category": "Health & Beauty"}),
    ("Kithul Treacle Glass Bottle (750ml)", 1450.00, 0.0020, {"category": "Sweeteners"}),
    ("Kithul Jaggery Slab (500g)", 950.00, 0.0015, {"category": "Sweeteners"}),
    ("Natural Cashew Nuts (500g)", 2850.00, 0.0022, {"category": "Snacks", "salted": False}),
    ("Chili Powder Pack (500g)", 420.00, 0.0015, {"category": "Spices"}),
    ("Turmeric Powder Export Grade (250g)", 580.00, 0.0010, {"category": "Spices"}),
    ("Cardamom Pods A-Grade (100g)", 1950.00, 0.0008, {"category": "Spices"}),
    ("Dry Red Lentils (1kg)", 340.00, 0.0020, {"category": "Pulses"}),
    ("Chickpeas Raw (1kg)", 480.00, 0.0022, {"category": "Pulses"}),
    ("Coconut Milk Canned (400ml)", 390.00, 0.0011, {"category": "Canned Goods"}),
    ("Sardines in Tomato Sauce (425g)", 520.00, 0.0012, {"category": "Canned Goods"}),
]

TIME_SLOTS = [
    "Morning (08:00 - 11:00)",
    "Midday (11:00 - 14:00)",
    "Afternoon (14:00 - 17:00)",
    "Evening (17:00 - 20:00)"
]

def sql_val(val):
    """Formats Python values into standard PostgreSQL literal expressions."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S%z')}'"
    if isinstance(val, dict):
        escaped = json.dumps(val).replace("'", "''")
        return f"'{escaped}'::jsonb"
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"

def generate_phone(idx):
    """Generates phone numbers complying with ^[0-9\\+\\-\\s\\(\\)\\.]{7,20}$."""
    return f"+94 77 {1000000 + (idx % 9000000):07d}"

def write_bulk_insert(f, table_name, columns, rows_data, chunk_size=200, overriding_system=True):
    """Writes batched INSERT statements with OVERRIDING SYSTEM VALUE."""
    col_list = ", ".join(columns)
    override_clause = " OVERRIDING SYSTEM VALUE" if overriding_system else ""
    
    for i in range(0, len(rows_data), chunk_size):
        chunk = rows_data[i:i + chunk_size]
        f.write(f"INSERT INTO {table_name} ({col_list}){override_clause} VALUES\n")
        val_lines = []
        for row in chunk:
            formatted_vals = ", ".join(sql_val(v) for v in row)
            val_lines.append(f"  ({formatted_vals})")
        f.write(",\n".join(val_lines))
        f.write(";\n\n")


def main():
    print(f"Generating deterministic seed dataset into '{OUTPUT_FILE}'...")

    total_rows = 0
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n\n")

        
        
        
        
        users = [
            (
                uuid.UUID(int=1), "System Administrator", "admin@supplychain.internal",
                BASE_TIME - timedelta(days=90), None, "admin",
                password_hash,
                BASE_TIME - timedelta(days=90), BASE_TIME - timedelta(days=90)
            ),
            (
                uuid.UUID(int=2), "Head of Logistics", "logistics.director@supplychain.internal",
                BASE_TIME - timedelta(days=85), None, "logistics",
                password_hash,
                BASE_TIME - timedelta(days=85), BASE_TIME - timedelta(days=85)
            ),
            (
                uuid.UUID(int=3), "Commercial Sales Lead", "sales.lead@supplychain.internal",
                BASE_TIME - timedelta(days=80), None, "sales",
                password_hash,
                BASE_TIME - timedelta(days=80), BASE_TIME - timedelta(days=80)
            )
        ]

        
        for i in range(10):
            uid = uuid.UUID(int=10 + i)
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[i % len(LAST_NAMES)]
            users.append((
                uid, f"{first} {last} (Manager)", f"manager.{CITIES[i][2].lower()}@supplychain.internal",
                BASE_TIME - timedelta(days=70 - i), None, "store_manager",
                password_hash,
                BASE_TIME - timedelta(days=70 - i), BASE_TIME - timedelta(days=70 - i)
            ))

        
        for i in range(47):
            uid = uuid.UUID(int=100 + i)
            first = FIRST_NAMES[(i + 5) % len(FIRST_NAMES)]
            last = LAST_NAMES[(i + 3) % len(LAST_NAMES)]
            users.append((
                uid, f"{first} {last}", f"user.{first.lower()}.{last.lower()}{i+1}@gmail.com",
                BASE_TIME - timedelta(days=60 - (i % 30)), None, "user",
                password_hash,
                BASE_TIME - timedelta(days=60 - (i % 30)), BASE_TIME - timedelta(days=60 - (i % 30))
            ))

        write_bulk_insert(
            f, "users",
            ["id", "name", "email", "email_verified", "image", "role", "password_hash", "created_at", "updated_at"],
            users, overriding_system=False
        )
        total_rows += len(users)

        admin_uid = users[0][0]

        
        
        
        stores = []
        for i, (name, addr, _) in enumerate(CITIES, start=1):
            mgr_uid = uuid.UUID(int=10 + (i - 1))
            stores.append((
                i, name, addr, mgr_uid, admin_uid, admin_uid,
                BASE_TIME - timedelta(days=65), BASE_TIME - timedelta(days=65)
            ))

        write_bulk_insert(
            f, "stores",
            ["id", "store_name", "address", "manager_id", "created_by", "updated_by", "created_at", "updated_at"],
            stores
        )
        total_rows += len(stores)

        
        
        
        routes = []
        route_id = 1
        sectors = ["North Sector", "Central & Commercial", "South Suburbs"]
        for store in stores:
            s_id = store[0]
            city_name = CITIES[s_id - 1][2]
            for sec_idx, sec in enumerate(sectors, start=1):
                max_hours = round(random.uniform(2.5, 6.0), 2)
                routes.append((
                    route_id, s_id, f"RT-{city_name.upper()[:3]}-{sec_idx:02d}",
                    f"{city_name} {sec}", max_hours, admin_uid, admin_uid,
                    BASE_TIME - timedelta(days=60), BASE_TIME - timedelta(days=60)
                ))
                route_id += 1

        write_bulk_insert(
            f, "routes",
            ["id", "store_id", "route_name", "service_area", "max_delivery_time_hrs", "created_by", "updated_by", "created_at", "updated_at"],
            routes
        )
        total_rows += len(routes)

        
        
        
        trucks = []
        truck_id = 1
        for s_idx in range(1, 11):
            for t_seq in range(1, 4):
                assigned_route_id = ((s_idx - 1) * 3) + t_seq
                plate_province = ["WP", "CP", "SP", "NWP", "SGP"][s_idx % 5]
                plate = f"{plate_province} CAR-{1000 + truck_id}"
                capacity = random.choice([1500.00, 2500.00, 3500.00, 5000.00])
                v_status = "Maintenance" if truck_id == 7 else "Active"

                trucks.append((
                    truck_id, s_idx, plate, capacity, v_status, assigned_route_id,
                    admin_uid, admin_uid, BASE_TIME - timedelta(days=55), BASE_TIME - timedelta(days=55)
                ))
                truck_id += 1

        write_bulk_insert(
            f, "trucks",
            ["id", "store_id", "license_plate", "capacity", "vehicle_status", "route_id", "created_by", "updated_by", "created_at", "updated_at"],
            trucks
        )
        total_rows += len(trucks)

        
        
        
        employees = []
        emp_id = 1
        store_drivers = {s_idx: [] for s_idx in range(1, 11)}
        store_assistants = {s_idx: [] for s_idx in range(1, 11)}

        for s_idx in range(1, 11):
            
            for d_seq in range(3):
                emp_name = f"{FIRST_NAMES[(emp_id * 2) % len(FIRST_NAMES)]} {LAST_NAMES[(emp_id * 3) % len(LAST_NAMES)]}"
                phone = generate_phone(emp_id)
                status = "On Leave" if emp_id == 12 else "Available"
                pts = random.randint(50, 450)
                employees.append((
                    emp_id, s_idx, emp_name, "DRIVER", phone, status, pts,
                    admin_uid, admin_uid, BASE_TIME - timedelta(days=50), BASE_TIME - timedelta(days=50)
                ))
                store_drivers[s_idx].append(emp_id)
                emp_id += 1

            
            for a_seq in range(3):
                emp_name = f"{FIRST_NAMES[(emp_id * 5) % len(FIRST_NAMES)]} {LAST_NAMES[(emp_id * 7) % len(LAST_NAMES)]}"
                phone = generate_phone(emp_id)
                status = "Available"
                pts = random.randint(20, 250)
                employees.append((
                    emp_id, s_idx, emp_name, "ASSISTANT", phone, status, pts,
                    admin_uid, admin_uid, BASE_TIME - timedelta(days=50), BASE_TIME - timedelta(days=50)
                ))
                store_assistants[s_idx].append(emp_id)
                emp_id += 1

        write_bulk_insert(
            f, "employees",
            ["id", "store_id", "employee_name", "employee_role", "contact_phone", "employee_status", "points", "created_by", "updated_by", "created_at", "updated_at"],
            employees
        )
        total_rows += len(employees)

        
        
        
        customers = []
        for c_id in range(1, 201):
            first = FIRST_NAMES[(c_id * 3) % len(FIRST_NAMES)]
            last = LAST_NAMES[(c_id * 5) % len(LAST_NAMES)]
            c_name = f"{first} {last}"
            c_route = ((c_id - 1) % len(routes)) + 1
            matched_user_id = users[13 + (c_id % 47)][0] if c_id % 3 == 0 else None
            meta = {
                "preferred_channel": random.choice(["SMS", "Call", "WhatsApp"]),
                "tier": random.choice(["Standard", "Silver", "Gold", "VIP"]),
                "credit_limit": random.choice([25000, 50000, 100000])
            }
            c_addr = f"No. {random.randint(1, 250)}, {first} Road, Route #{c_route} Region"
            c_phone = generate_phone(5000 + c_id)

            customers.append((
                c_id, c_name, c_addr, c_phone, matched_user_id, c_route,
                meta, admin_uid, admin_uid, BASE_TIME - timedelta(days=45), BASE_TIME - timedelta(days=45)
            ))

        write_bulk_insert(
            f, "customers",
            ["id", "customer_name", "address", "contact_phone", "user_id", "default_route_id", "metadata", "created_by", "updated_by", "created_at", "updated_at"],
            customers
        )
        total_rows += len(customers)

        
        
        
        products = []
        for p_id, item in enumerate(PRODUCT_CATALOG, start=1):
            p_name, unit_price, space_unit, p_meta = item
            products.append((
                p_id, p_name, unit_price, space_unit, p_meta,
                admin_uid, admin_uid, BASE_TIME - timedelta(days=50), BASE_TIME - timedelta(days=50)
            ))

        write_bulk_insert(
            f, "products",
            ["id", "product_name", "unit_price", "space_consumption_unit", "metadata", "created_by", "updated_by", "created_at", "updated_at"],
            products
        )
        total_rows += len(products)

        
        
        
        orders = []
        order_items = []
        item_id = 1

        for o_id in range(1, 601):
            cust = customers[(o_id - 1) % len(customers)]
            c_id = cust[0]
            route_id = cust[5]
            delivery_addr = cust[2]
            contact_phone = cust[3]

            days_offset = (o_id // 15)  
            order_dt = BASE_TIME - timedelta(days=40) + timedelta(days=days_offset, hours=random.randint(0, 12))
            delivery_dt = order_dt + timedelta(days=random.randint(7, 9), hours=random.randint(2, 6))
            slot = random.choice(TIME_SLOTS)

            orders.append((
                o_id, c_id, route_id, delivery_addr, contact_phone,
                order_dt, delivery_dt, slot, admin_uid, admin_uid,
                order_dt, order_dt
            ))

            
            num_items = 2 + (o_id % 3)
            
            if days_offset < 28:
                primary_status = "DELIVERED"
            elif days_offset < 34:
                primary_status = random.choice(["OUT_FOR_DELIVERY", "DELIVERED", "DELIVERY_FAILED"])
            elif days_offset < 38:
                primary_status = random.choice(["STORE_RECEIVED", "IN_TRANSIT"])
            else:
                primary_status = random.choice(["PLACED", "SCHEDULED"])

            for _ in range(num_items):
                p_choice = random.choice(products)
                p_id = p_choice[0]
                unit_price = p_choice[2]
                qty = random.randint(1, 8)
                
                
                item_status = primary_status
                if item_status == "PLACED" and random.random() < 0.05:
                    item_status = "CANCELLED"

                for _ in range(qty):
                    order_items.append((
                        item_id, o_id, p_id, unit_price,
                        item_status, order_dt, order_dt
                    ))
                    item_id += 1

        write_bulk_insert(
            f, "orders",
            ["id", "customer_id", "route_id", "delivery_address", "contact_phone", "order_date", "delivery_date", "prefered_delivery_slot", "created_by", "updated_by", "created_at", "updated_at"],
            orders
        )
        total_rows += len(orders)

        write_bulk_insert(
            f, "order_items",
            ["id", "order_id", "product_id", "unit_price", "item_lifecycle_status", "created_at", "updated_at"],
            order_items
        )
        total_rows += len(order_items)

        
        
        
        train_schedules = []
        for ts_id in range(1, 81):
            dest_store_id = ((ts_id - 1) % len(stores)) + 1
            day_step = ts_id // 2
            dep_time = BASE_TIME - timedelta(days=38) + timedelta(days=day_step, hours=random.choice([4, 16]))
            cap = random.choice([10000.00, 15000.00, 20000.00, 30000.00])
            train_schedules.append((
                ts_id, dest_store_id, dep_time, cap, admin_uid, admin_uid,
                dep_time - timedelta(days=1), dep_time - timedelta(days=1)
            ))

        write_bulk_insert(
            f, "train_schedules",
            ["id", "destination_store_id", "departure_timestamp", "max_capacity", "created_by", "updated_by", "created_at", "updated_at"],
            train_schedules
        )
        total_rows += len(train_schedules)

        
        
        
        
        train_eligible_items = [
            item for item in order_items 
            if item[5] in ("SCHEDULED", "IN_TRANSIT", "STORE_RECEIVED", "OUT_FOR_DELIVERY", "DELIVERED")
        ]
        
        train_allocations = []
        alloc_count = min(600, len(train_eligible_items))
        for alloc_id in range(1, alloc_count + 1):
            allocated_item = train_eligible_items[alloc_id - 1]
            chosen_train_id = ((alloc_id - 1) % len(train_schedules)) + 1
            train_dep = train_schedules[chosen_train_id - 1][2]

            train_allocations.append((
                alloc_id, allocated_item[0], chosen_train_id, admin_uid,
                train_dep - timedelta(hours=6), train_dep - timedelta(hours=6)
            ))

        write_bulk_insert(
            f, "train_allocations",
            ["id", "order_item_id", "train_id", "created_by", "created_at", "updated_at"],
            train_allocations
        )
        total_rows += len(train_allocations)

        
        
        
        truck_schedules = []
        for sch_id in range(1, 251):
            chosen_truck = trucks[(sch_id - 1) % len(trucks)]
            truck_pk = chosen_truck[0]
            store_pk = chosen_truck[1]
            route_pk = chosen_truck[5]

            driver_pk = random.choice(store_drivers[store_pk])
            assistant_pk = random.choice(store_assistants[store_pk])

            sched_day = sch_id // 6
            start_ts = BASE_TIME - timedelta(days=36) + timedelta(days=sched_day, hours=random.choice([7, 13]))
            duration = random.choice([2.5, 3.5, 4.0, 5.0])
            end_ts = start_ts + timedelta(hours=duration)

            
            truck_schedules.append((
                sch_id, truck_pk, route_pk, driver_pk, assistant_pk,
                start_ts, end_ts, admin_uid, admin_uid,
                start_ts - timedelta(hours=12), start_ts - timedelta(hours=12)
            ))

        write_bulk_insert(
            f, "truck_schedules",
            ["id", "truck_id", "route_id", "driver_id", "assistant_id", "start_timestamp", "end_timestamp", "created_by", "updated_by", "created_at", "updated_at"],
            truck_schedules
        )
        total_rows += len(truck_schedules)

        
        
        
        delivery_candidates = [
            item for item in order_items 
            if item[4] in ("OUT_FOR_DELIVERY", "DELIVERED", "DELIVERY_FAILED")
        ]
        
        truck_deliveries = []
        delivery_count = min(900, len(delivery_candidates))
        for deliv_id in range(1, delivery_count + 1):
            deliv_item = delivery_candidates[deliv_id - 1]
            sched = truck_schedules[(deliv_id - 1) % len(truck_schedules)]
            sched_id = sched[0]
            sched_start = sched[5]
            
            
            delivered_ts = None
            if deliv_item[5] == "DELIVERED":
                delivered_ts = sched_start + timedelta(hours=random.uniform(0.5, 2.2))
            
            truck_deliveries.append((
                deliv_id, sched_id, deliv_item[0], delivered_ts,
                sched_start, sched_start
            ))

        write_bulk_insert(
            f, "truck_item_deliveries",
            ["id", "truck_schedule_id", "order_item_id", "delivered_at", "created_at", "updated_at"],
            truck_deliveries
        )
        total_rows += len(truck_deliveries)

        
        
        
        f.write("-- ---------------------------------------------------------\n")
        f.write("-- Sync Identity Sequences with Max Generated Primary Keys\n")
        f.write("-- ---------------------------------------------------------\n")
        identity_tables = [
            "stores", "routes", "trucks", "employees", "customers",
            "products", "orders", "order_items", "train_schedules",
            "train_allocations", "truck_schedules", "truck_item_deliveries"
        ]
        for tbl in identity_tables:
            f.write(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 1));\n")

        f.write("\nCOMMIT;\n")

    print(f"Done. Successfully generated {total_rows} total seed rows in '{OUTPUT_FILE}'.")
if __name__ == "__main__":
    main()