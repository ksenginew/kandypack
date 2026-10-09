-- Last-mile schedule validation and an optional procedure wrapper.
-- Apply this file to an existing database without rerunning 00-schema.sql.
-- Intervals are [start, end); only a zero gap makes deliveries consecutive.
-- Working weeks run Monday 00:00 to Monday 00:00 in Asia/Colombo.
BEGIN;

-- Serialize roster writes before validation. Updating this singleton also
-- causes stale REPEATABLE READ / SERIALIZABLE writers to fail and retry,
-- rather than validating aggregate hours against an outdated snapshot.
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

-- NOT VALID keeps legacy seed records intact, while enforcing the check on
-- every new or updated row. Legacy data can be audited and validated later.
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

    -- Test all three positions: inserting a trip between two existing trips
    -- must not turn an assistant's roster into a chain of three deliveries.
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

    -- Compute unrounded elapsed time in each week, including overnight and
    -- cross-week trips. Do not charge an entire trip to its departure week.
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

-- A route-limit reduction or employee-role change must not invalidate a
-- roster indirectly. These triggers supplement the other modules' triggers.
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

COMMIT;
