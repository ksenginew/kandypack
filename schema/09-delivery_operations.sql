-- Scheduling starts road delivery; operations records its outcome.
-- OUT_FOR_DELIVERY remains available for previously assigned received items.
CREATE OR REPLACE PROCEDURE sp_set_scheduled_order_status(
    p_schedule_id BIGINT,
    p_order_id BIGINT,
    p_status VARCHAR,
    p_actor_id UUID
)
LANGUAGE plpgsql AS $$
DECLARE
    v_status enum_item_lifecycle_status;
    v_allowed enum_item_lifecycle_status[];
BEGIN
    IF p_status IS NULL OR p_status NOT IN
       ('OUT_FOR_DELIVERY', 'DELIVERED', 'DELIVERY_FAILED', 'CANCELLED') THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'Select a valid delivery status.';
    END IF;
    v_status := p_status::enum_item_lifecycle_status;

    -- Use the roster lock order before locking the schedule and order items.
    UPDATE road_delivery_validation_guard SET version = NOT version WHERE singleton;
    PERFORM 1 FROM truck_schedules WHERE id = p_schedule_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'The selected truck schedule no longer exists.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM users u
        JOIN truck_schedules s ON s.id = p_schedule_id
        JOIN routes r ON r.id = s.route_id
        JOIN stores store ON store.id = r.store_id
        WHERE u.id = p_actor_id
          AND (u.role = 'admin' OR (u.role = 'store_manager' AND store.manager_id = u.id))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'You do not have permission to update this delivery.';
    END IF;

    PERFORM 1 FROM orders WHERE id = p_order_id FOR UPDATE;
    PERFORM 1 FROM order_items WHERE order_id = p_order_id ORDER BY id FOR UPDATE;
    -- Lock assignment rows so a concurrent unassignment cannot race dispatch.
    PERFORM 1 FROM truck_item_deliveries d
    JOIN order_items i ON i.id = d.order_item_id
    WHERE d.truck_schedule_id = p_schedule_id AND i.order_id = p_order_id
    ORDER BY d.id FOR UPDATE OF d;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'This order is not assigned to the selected truck schedule.';
    END IF;

    v_allowed := CASE p_status
        WHEN 'OUT_FOR_DELIVERY' THEN ARRAY['STORE_RECEIVED']::enum_item_lifecycle_status[]
        WHEN 'CANCELLED' THEN ARRAY['STORE_RECEIVED', 'OUT_FOR_DELIVERY', 'DELIVERY_FAILED']::enum_item_lifecycle_status[]
        ELSE ARRAY['OUT_FOR_DELIVERY']::enum_item_lifecycle_status[]
    END;
    IF EXISTS (
        SELECT 1 FROM truck_item_deliveries d JOIN order_items i ON i.id = d.order_item_id
        WHERE d.truck_schedule_id = p_schedule_id AND i.order_id = p_order_id
          AND i.item_lifecycle_status <> v_status
          AND NOT (i.item_lifecycle_status = ANY(v_allowed))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'Dispatch received items before recording delivery results. Completed or cancelled items cannot be dispatched again.';
    END IF;

    -- Update only items on this trip and preserve timestamps on repeated calls.
    WITH changed AS (
        UPDATE order_items i SET item_lifecycle_status = v_status
        FROM truck_item_deliveries d
        WHERE d.order_item_id = i.id AND d.truck_schedule_id = p_schedule_id
          AND i.order_id = p_order_id AND i.item_lifecycle_status <> v_status
        RETURNING i.id
    )
    UPDATE truck_item_deliveries d
    SET delivered_at = CASE WHEN v_status = 'DELIVERED' THEN CURRENT_TIMESTAMP ELSE NULL END
    FROM changed WHERE d.order_item_id = changed.id;
END;
$$;
