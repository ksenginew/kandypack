CREATE OR REPLACE VIEW view_truck_schedules_overview AS
SELECT 
    ts.id,
    ts.route_id,
    t.license_plate,
    r.route_name,
    ts.start_timestamp,
    ts.end_timestamp
FROM truck_schedules ts
JOIN trucks t ON ts.truck_id = t.id
JOIN routes r ON ts.route_id = r.id;

CREATE OR REPLACE VIEW view_schedule_assigned_orders AS
SELECT 
    tid.truck_schedule_id,
    o.id AS order_id,
    o.delivery_address,
    o.contact_phone,
    o.delivery_date,
    o.prefered_delivery_slot,
    COUNT(oi.id) AS total_items,
    STRING_AGG(DISTINCT oi.item_lifecycle_status::text, ', ') AS item_statuses
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN truck_item_deliveries tid ON tid.order_item_id = oi.id
GROUP BY 
    tid.truck_schedule_id,
    o.id,
    o.delivery_address,
    o.contact_phone,
    o.delivery_date,
    o.prefered_delivery_slot;

CREATE OR REPLACE VIEW view_unassigned_orders_by_route AS
SELECT 
    o.id,
    o.route_id,
    o.delivery_address,
    o.contact_phone,
    o.delivery_date,
    COUNT(oi.id) AS item_count
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
LEFT JOIN truck_item_deliveries tid ON tid.order_item_id = oi.id
WHERE tid.id IS NULL
GROUP BY 
    o.id,
    o.route_id,
    o.delivery_address,
    o.contact_phone,
    o.delivery_date;

-- Assign orders and their items to a schedule
CREATE OR REPLACE PROCEDURE sp_assign_orders_to_schedule(
    p_schedule_id INT,
    p_order_ids INT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO truck_item_deliveries (truck_schedule_id, order_item_id)
    SELECT p_schedule_id, oi.id
    FROM order_items oi
    WHERE oi.order_id = ANY(p_order_ids)
    ON CONFLICT (order_item_id) DO NOTHING;
END;
$$;

-- Unassign an order and its items from a schedule
CREATE OR REPLACE PROCEDURE sp_unassign_order_from_schedule(
    p_schedule_id INT,
    p_order_id INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM truck_item_deliveries tid
    USING order_items oi
    WHERE tid.order_item_id = oi.id
      AND tid.truck_schedule_id = p_schedule_id
      AND oi.order_id = p_order_id;
END;
$$;

-- Update lifecycle status of an order
CREATE OR REPLACE PROCEDURE sp_update_order_item_status(
    p_order_id INT,
    p_status VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status enum_item_lifecycle_status;
BEGIN
    v_status := p_status::enum_item_lifecycle_status;

    -- Update order item status
    UPDATE order_items 
    SET item_lifecycle_status = v_status,
        updated_at = CURRENT_TIMESTAMP
    WHERE order_id = p_order_id;

    -- Synchronize delivery timestamps in truck_item_deliveries
    IF p_status = 'DELIVERED' THEN
        UPDATE truck_item_deliveries tid
        SET delivered_at = CURRENT_TIMESTAMP
        FROM order_items oi
        WHERE tid.order_item_id = oi.id 
          AND oi.order_id = p_order_id;
    ELSE
        UPDATE truck_item_deliveries tid
        SET delivered_at = NULL
        FROM order_items oi
        WHERE tid.order_item_id = oi.id 
          AND oi.order_id = p_order_id;
    END IF;
END;
$$;
