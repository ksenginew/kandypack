BEGIN;

DROP TABLE IF EXISTS truck_item_deliveries CASCADE;
DROP TABLE IF EXISTS truck_schedules CASCADE;
DROP TABLE IF EXISTS train_allocations CASCADE;
DROP TABLE IF EXISTS train_schedules CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS trucks CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS users CASCADE;

DROP TYPE IF EXISTS enum_item_lifecycle_status CASCADE;
DROP TYPE IF EXISTS enum_vehicle_status CASCADE;
DROP TYPE IF EXISTS enum_employee_status CASCADE;
DROP TYPE IF EXISTS enum_employee_role CASCADE;
DROP TYPE IF EXISTS enum_user_role CASCADE;

DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;

-- Universal trigger function for auto-updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Enum type definitions
CREATE TYPE enum_user_role AS ENUM (
    'admin',
    'sales',
    'logistics',
    'store_manager',
    'user'
);

CREATE TYPE enum_employee_role AS ENUM (
    'DRIVER',
    'ASSISTANT'
);

CREATE TYPE enum_employee_status AS ENUM (
    'Available',
    'On Leave',
    'Suspended',
    'Terminated'
);

CREATE TYPE enum_vehicle_status AS ENUM (
    'Active',
    'Maintenance',
    'Decommissioned'
);

CREATE TYPE enum_item_lifecycle_status AS ENUM (
    'PLACED',
    'SCHEDULED',
    'IN_TRANSIT',
    'STORE_RECEIVED',
    'OUT_FOR_DELIVERY',
    'DELIVERED',
    'DELIVERY_FAILED',
    'CANCELLED'
);

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT uuidv7(),
    name           VARCHAR(255) NOT NULL,
    email          VARCHAR(255) NOT NULL UNIQUE CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    email_verified TIMESTAMPTZ,
    image          VARCHAR(512),
    role           enum_user_role NOT NULL DEFAULT 'user',
    password_hash  VARCHAR(255) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stores (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_name VARCHAR(255) NOT NULL UNIQUE,
    address    TEXT NOT NULL,
    manager_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE routes (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id              BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    route_name            VARCHAR(255) NOT NULL,
    service_area          VARCHAR(255) NOT NULL,
    max_delivery_time_hrs NUMERIC(5, 2) NOT NULL CHECK (max_delivery_time_hrs > 0),
    created_by            UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by            UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trucks (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id       BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    license_plate  VARCHAR(50) NOT NULL UNIQUE,
    capacity       NUMERIC(10, 2) NOT NULL CHECK (capacity > 0),
    vehicle_status enum_vehicle_status NOT NULL DEFAULT 'Active',
    route_id       BIGINT REFERENCES routes(id) ON DELETE SET NULL,
    created_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id        BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    employee_name   VARCHAR(255) NOT NULL,
    employee_role   enum_employee_role NOT NULL,
    contact_phone   VARCHAR(50) NOT NULL CHECK (contact_phone ~ '^[0-9\+\-\s\(\)\.]{7,20}$'),
    employee_status enum_employee_status NOT NULL DEFAULT 'Available',
    points          INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_name    VARCHAR(255) NOT NULL,
    address          TEXT NOT NULL,
    contact_phone    VARCHAR(50) NOT NULL CHECK (contact_phone ~ '^[0-9\+\-\s\(\)\.]{7,20}$'),
    user_id          UUID REFERENCES users(id) ON DELETE SET NULL,
    default_route_id BIGINT REFERENCES routes(id) ON DELETE SET NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name            VARCHAR(255) NOT NULL,
    unit_price              NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    space_consumption_unit  NUMERIC(10, 4) NOT NULL CHECK (space_consumption_unit > 0),
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by              UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by              UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id            BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    route_id               BIGINT NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    delivery_address       TEXT NOT NULL CHECK (trim(delivery_address) <> ''),
    contact_phone          VARCHAR(50) NOT NULL CHECK (contact_phone ~ '^[0-9\+\-\s\(\)\.]{7,20}$'),
    order_date             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_date          TIMESTAMPTZ NOT NULL,
    prefered_delivery_slot VARCHAR(100),
    created_by             UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by             UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_place_orders_7_days_advance CHECK (delivery_date >= order_date + INTERVAL '7 days')
);

CREATE TABLE order_items (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id              BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id            BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    unit_price            NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    item_lifecycle_status enum_item_lifecycle_status NOT NULL DEFAULT 'PLACED',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE train_schedules (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    destination_store_id BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    departure_timestamp  TIMESTAMPTZ NOT NULL,
    max_capacity         NUMERIC(10, 2) NOT NULL CHECK (max_capacity > 0),
    created_by           UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by           UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE train_allocations (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_item_id BIGINT NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE CASCADE,
    train_id      BIGINT NOT NULL REFERENCES train_schedules(id) ON DELETE CASCADE,
    created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE truck_schedules (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_id        BIGINT NOT NULL REFERENCES trucks(id) ON DELETE CASCADE,
    route_id        BIGINT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    driver_id       BIGINT NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
    assistant_id    BIGINT REFERENCES employees(id) ON DELETE SET NULL,
    start_timestamp TIMESTAMPTZ NOT NULL,
    end_timestamp   TIMESTAMPTZ NOT NULL,
    duration_hours  NUMERIC(8, 2) GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (end_timestamp - start_timestamp)) / 3600.0) STORED,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_truck_schedules_time_window CHECK (end_timestamp > start_timestamp)
);

CREATE TABLE truck_item_deliveries (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_schedule_id BIGINT NOT NULL REFERENCES truck_schedules(id) ON DELETE CASCADE,
    order_item_id     BIGINT NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE CASCADE,
    delivered_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX idx_stores_manager_id ON stores(manager_id);

CREATE INDEX idx_routes_store_id ON routes(store_id);

CREATE INDEX idx_trucks_store_id ON trucks(store_id);
CREATE INDEX idx_trucks_route_id ON trucks(route_id);

CREATE INDEX idx_employees_store_id ON employees(store_id);

CREATE INDEX idx_customers_user_id ON customers(user_id);
CREATE INDEX idx_customers_default_route_id ON customers(default_route_id);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_route_id ON orders(route_id);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_order_items_lifecycle ON order_items(item_lifecycle_status);

CREATE INDEX idx_train_schedules_dest_store ON train_schedules(destination_store_id);

CREATE INDEX idx_train_allocations_train_id ON train_allocations(train_id);

CREATE INDEX idx_truck_schedules_truck_id ON truck_schedules(truck_id);
CREATE INDEX idx_truck_schedules_route_id ON truck_schedules(route_id);
CREATE INDEX idx_truck_schedules_driver_id ON truck_schedules(driver_id);
CREATE INDEX idx_truck_schedules_assistant_id ON truck_schedules(assistant_id);

CREATE INDEX idx_truck_deliveries_schedule ON truck_item_deliveries(truck_schedule_id);

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_stores_updated_at BEFORE UPDATE ON stores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_routes_updated_at BEFORE UPDATE ON routes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_trucks_updated_at BEFORE UPDATE ON trucks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_employees_updated_at BEFORE UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_order_items_updated_at BEFORE UPDATE ON order_items FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_train_schedules_updated_at BEFORE UPDATE ON train_schedules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_train_allocations_updated_at BEFORE UPDATE ON train_allocations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_truck_schedules_updated_at BEFORE UPDATE ON truck_schedules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_truck_item_deliveries_updated_at BEFORE UPDATE ON truck_item_deliveries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
