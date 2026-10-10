BEGIN;

CREATE TABLE IF NOT EXISTS road_delivery_validation_guard (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO road_delivery_validation_guard (singleton) VALUES (TRUE)
ON CONFLICT (singleton) DO NOTHING;

CREATE OR REPLACE FUNCTION lock_road_delivery_validation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE road_delivery_validation_guard SET version = NOT version
    WHERE singleton = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Road delivery validation lock is missing.';
    END IF;
    RETURN NULL;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'truck_schedules'::regclass
          AND conname = 'chk_road_delivery_crew'
    ) THEN
        ALTER TABLE truck_schedules ADD CONSTRAINT chk_road_delivery_crew
        CHECK (assistant_id IS NOT NULL AND driver_id <> assistant_id) NOT VALID;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION validate_road_delivery_schedule(p_schedule_id BIGINT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v_schedule truck_schedules%ROWTYPE;
    v_max_hours NUMERIC;
    v_week_start TIMESTAMPTZ;
    v_employee_id BIGINT;
    v_limit NUMERIC;
    v_hours NUMERIC;
BEGIN
    SELECT * INTO v_schedule FROM truck_schedules WHERE id = p_schedule_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF v_schedule.assistant_id IS NULL
       OR v_schedule.driver_id = v_schedule.assistant_id THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'Each schedule requires a separate driver and driver assistant.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM employees WHERE id = v_schedule.driver_id
                   AND employee_role = 'DRIVER') THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'The selected driver must have the DRIVER role.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM employees WHERE id = v_schedule.assistant_id
                   AND employee_role = 'ASSISTANT') THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'The selected driver assistant must have the ASSISTANT role.';
    END IF;

    SELECT max_delivery_time_hrs INTO v_max_hours
    FROM routes WHERE id = v_schedule.route_id;
    IF EXISTS (
        SELECT 1 FROM truck_item_deliveries d
        JOIN order_items i ON i.id = d.order_item_id
        JOIN orders o ON o.id = i.order_id
        JOIN routes r ON r.id = o.route_id
        JOIN routes chosen ON chosen.id = v_schedule.route_id
        WHERE d.truck_schedule_id = p_schedule_id
          AND (r.store_id, r.route_name, r.service_area, r.max_delivery_time_hrs)
              IS DISTINCT FROM
              (chosen.store_id, chosen.route_name, chosen.service_area, chosen.max_delivery_time_hrs)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'The delivery route must match all assigned orders.';
    END IF;
    IF EXTRACT(EPOCH FROM (v_schedule.end_timestamp - v_schedule.start_timestamp))
       / 3600.0 > v_max_hours THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = format('Delivery duration exceeds the route maximum of %s hours.', v_max_hours);
    END IF;

    IF EXISTS (
        SELECT 1 FROM truck_schedules s
        WHERE s.id <> p_schedule_id
          AND s.start_timestamp < v_schedule.end_timestamp
          AND s.end_timestamp > v_schedule.start_timestamp
          AND (s.truck_id = v_schedule.truck_id
               OR s.driver_id IN (v_schedule.driver_id, v_schedule.assistant_id)
               OR s.assistant_id IN (v_schedule.driver_id, v_schedule.assistant_id))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'The truck, driver, or assistant already has an overlapping delivery.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM truck_schedules s
        WHERE s.id <> p_schedule_id AND s.driver_id = v_schedule.driver_id
          AND (s.end_timestamp = v_schedule.start_timestamp
               OR s.start_timestamp = v_schedule.end_timestamp)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'A driver cannot work two consecutive deliveries without a gap.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM truck_schedules a
        JOIN truck_schedules b ON b.assistant_id = a.assistant_id
                             AND b.start_timestamp = a.end_timestamp
        JOIN truck_schedules c ON c.assistant_id = b.assistant_id
                             AND c.start_timestamp = b.end_timestamp
        WHERE a.assistant_id = v_schedule.assistant_id
          AND p_schedule_id IN (a.id, b.id, c.id)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'An assistant cannot work more than two consecutive routes without a gap.';
    END IF;

    FOR v_week_start IN
        SELECT local_week AT TIME ZONE 'Asia/Colombo'
        FROM generate_series(
            date_trunc('week', v_schedule.start_timestamp AT TIME ZONE 'Asia/Colombo'),
            date_trunc('week', (v_schedule.end_timestamp - INTERVAL '1 microsecond')
                              AT TIME ZONE 'Asia/Colombo'),
            INTERVAL '1 week'
        ) AS local_week
    LOOP
        FOREACH v_employee_id IN ARRAY ARRAY[v_schedule.driver_id, v_schedule.assistant_id]
        LOOP
            v_limit := CASE WHEN v_employee_id = v_schedule.driver_id THEN 40 ELSE 60 END;
            SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (
                LEAST(s.end_timestamp, v_week_start + INTERVAL '168 hours')
                - GREATEST(s.start_timestamp, v_week_start)
            )) / 3600.0), 0) INTO v_hours
            FROM truck_schedules s
            WHERE (s.driver_id = v_employee_id OR s.assistant_id = v_employee_id)
              AND s.start_timestamp < v_week_start + INTERVAL '168 hours'
              AND s.end_timestamp > v_week_start;
            IF v_hours > v_limit THEN
                RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = format(
                    'Employee %s exceeds the %s-hour weekly limit for the week beginning %s (%s hours).',
                    v_employee_id, v_limit,
                    (v_week_start AT TIME ZONE 'Asia/Colombo')::DATE, round(v_hours, 4));
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_road_delivery_schedule()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    PERFORM validate_road_delivery_schedule(NEW.id);
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_road_delivery_reference_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_schedule_id BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'routes' THEN
        FOR v_schedule_id IN SELECT id FROM truck_schedules WHERE route_id = NEW.id LOOP
            PERFORM validate_road_delivery_schedule(v_schedule_id);
        END LOOP;
    ELSE
        FOR v_schedule_id IN SELECT id FROM truck_schedules
            WHERE driver_id = NEW.id OR assistant_id = NEW.id LOOP
            PERFORM validate_road_delivery_schedule(v_schedule_id);
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_road_delivery_lock ON truck_schedules;
CREATE TRIGGER trg_road_delivery_lock
BEFORE INSERT OR UPDATE OR DELETE ON truck_schedules
FOR EACH STATEMENT EXECUTE FUNCTION lock_road_delivery_validation();

DROP TRIGGER IF EXISTS trg_road_delivery_validate ON truck_schedules;
CREATE TRIGGER trg_road_delivery_validate
AFTER INSERT OR UPDATE ON truck_schedules
FOR EACH ROW EXECUTE FUNCTION enforce_road_delivery_schedule();

DROP TRIGGER IF EXISTS trg_road_delivery_route_lock ON routes;
CREATE TRIGGER trg_road_delivery_route_lock
BEFORE UPDATE OF max_delivery_time_hrs ON routes
FOR EACH STATEMENT EXECUTE FUNCTION lock_road_delivery_validation();
DROP TRIGGER IF EXISTS trg_road_delivery_route_validate ON routes;
CREATE TRIGGER trg_road_delivery_route_validate
AFTER UPDATE OF max_delivery_time_hrs ON routes
FOR EACH ROW WHEN (OLD.max_delivery_time_hrs IS DISTINCT FROM NEW.max_delivery_time_hrs)
EXECUTE FUNCTION enforce_road_delivery_reference_change();

DROP TRIGGER IF EXISTS trg_road_delivery_employee_lock ON employees;
CREATE TRIGGER trg_road_delivery_employee_lock
BEFORE UPDATE OF employee_role ON employees
FOR EACH STATEMENT EXECUTE FUNCTION lock_road_delivery_validation();
DROP TRIGGER IF EXISTS trg_road_delivery_employee_validate ON employees;
CREATE TRIGGER trg_road_delivery_employee_validate
AFTER UPDATE OF employee_role ON employees
FOR EACH ROW WHEN (OLD.employee_role IS DISTINCT FROM NEW.employee_role)
EXECUTE FUNCTION enforce_road_delivery_reference_change();

CREATE OR REPLACE PROCEDURE schedule_delivery(
    p_truck_id BIGINT, p_route_id BIGINT, p_driver_id BIGINT,
    p_assistant_id BIGINT, p_start_timestamp TIMESTAMPTZ,
    p_end_timestamp TIMESTAMPTZ, p_created_by UUID DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO truck_schedules (
        truck_id, route_id, driver_id, assistant_id,
        start_timestamp, end_timestamp, created_by, updated_by
    ) VALUES (
        p_truck_id, p_route_id, p_driver_id, p_assistant_id,
        p_start_timestamp, p_end_timestamp, p_created_by, p_created_by
    );
END;
$$;

-- Schedule complete received orders in one transaction. Duplicate route records
-- with identical store, name, service area and time limit represent one route.
CREATE OR REPLACE FUNCTION create_received_order_delivery(
    p_truck_id BIGINT, p_route_id BIGINT, p_driver_id BIGINT,
    p_assistant_id BIGINT, p_start_timestamp TIMESTAMPTZ,
    p_end_timestamp TIMESTAMPTZ, p_order_ids BIGINT[], p_actor_id UUID DEFAULT NULL
)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    v_route routes%ROWTYPE;
    v_order_id BIGINT;
    v_schedule_id BIGINT;
    v_count BIGINT;
    v_route_ids BIGINT[];
BEGIN
    IF COALESCE(cardinality(p_order_ids), 0) = 0 OR array_position(p_order_ids, NULL) IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'Select at least one received order for this delivery.';
    END IF;
    -- Use the roster's serialization order before locking orders or resources.
    UPDATE road_delivery_validation_guard SET version = NOT version WHERE singleton;
    SELECT * INTO v_route FROM routes WHERE id = p_route_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'The selected route no longer exists.';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE id = p_actor_id AND role = 'store_manager')
       AND NOT EXISTS (SELECT 1 FROM stores WHERE id = v_route.store_id AND manager_id = p_actor_id) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'Select a route belonging to your managed store.';
    END IF;
    PERFORM 1 FROM trucks WHERE id = p_truck_id AND store_id = v_route.store_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Select a truck from the delivery store.';
    END IF;
    PERFORM 1 FROM employees WHERE id = p_driver_id AND store_id = v_route.store_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Select a driver from the delivery store.';
    END IF;
    PERFORM 1 FROM employees WHERE id = p_assistant_id AND store_id = v_route.store_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Select an assistant from the delivery store.';
    END IF;
    SELECT array_agg(id) INTO v_route_ids FROM (
        SELECT id FROM routes
        WHERE (store_id, route_name, service_area, max_delivery_time_hrs) =
              (v_route.store_id, v_route.route_name, v_route.service_area, v_route.max_delivery_time_hrs)
        ORDER BY id FOR SHARE
    ) matching_routes;
    -- Lock parent orders as well as every item to prevent the selection changing
    -- while validating and assigning the complete order.
    PERFORM 1 FROM orders WHERE id = ANY(p_order_ids) ORDER BY id FOR UPDATE;
    SELECT count(*) INTO v_count FROM orders WHERE id = ANY(p_order_ids);
    IF v_count <> (SELECT count(DISTINCT id) FROM unnest(p_order_ids) id) THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'A selected order no longer exists.';
    END IF;
    PERFORM 1 FROM order_items WHERE order_id = ANY(p_order_ids) ORDER BY id FOR UPDATE;
    FOR v_order_id IN SELECT DISTINCT id FROM unnest(p_order_ids) id ORDER BY id LOOP
        IF NOT EXISTS (SELECT 1 FROM orders WHERE id = v_order_id AND route_id = ANY(v_route_ids)) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Selected orders must belong to this delivery route.';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM order_items WHERE order_id = v_order_id)
           OR EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = v_order_id
                      AND (i.item_lifecycle_status <> 'STORE_RECEIVED'
                           OR EXISTS (SELECT 1 FROM truck_item_deliveries d WHERE d.order_item_id = i.id))) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = format('Order #%s is no longer available. All items must be received and unassigned.', v_order_id);
        END IF;
    END LOOP;
    INSERT INTO truck_schedules
        (truck_id, route_id, driver_id, assistant_id, start_timestamp, end_timestamp, created_by, updated_by)
    VALUES (p_truck_id, p_route_id, p_driver_id, p_assistant_id, p_start_timestamp, p_end_timestamp, p_actor_id, p_actor_id)
    RETURNING id INTO v_schedule_id;
    INSERT INTO truck_item_deliveries (truck_schedule_id, order_item_id)
        SELECT v_schedule_id, id FROM order_items WHERE order_id = ANY(p_order_ids);
    -- The items remain STORE_RECEIVED while reserved for a future trip.
    -- Dispatch and delivery confirmation own the later lifecycle transitions.
    RETURN v_schedule_id;
END;
$$;

COMMIT;
