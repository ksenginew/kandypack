CREATE OR REPLACE VIEW view_quarterly_sales_report AS
SELECT
    EXTRACT(YEAR FROM o.order_date)::INT AS report_year,
    EXTRACT(QUARTER FROM o.order_date)::INT AS report_quarter,
    COUNT(oi.id) AS total_items_sold,
    COALESCE(SUM(oi.unit_price), 0.00) AS total_sales_value,
    COALESCE(SUM(p.space_consumption_unit), 0.0000) AS total_volume_space_units
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE oi.item_lifecycle_status != 'CANCELLED'
GROUP BY 
    EXTRACT(YEAR FROM o.order_date),
    EXTRACT(QUARTER FROM o.order_date)
ORDER BY 
    report_year DESC, 
    report_quarter DESC;

CREATE OR REPLACE FUNCTION get_most_ordered_items_by_quarter(
    p_year INT,
    p_quarter INT,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    sales_rank BIGINT,
    product_id BIGINT,
    product_name VARCHAR(255),
    total_quantity_ordered BIGINT,
    total_revenue NUMERIC(14, 2),
    total_space_occupied NUMERIC(14, 4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DENSE_RANK() OVER (ORDER BY COUNT(oi.id) DESC) AS sales_rank,
        p.id AS product_id,
        p.product_name,
        COUNT(oi.id) AS total_quantity_ordered,
        COALESCE(SUM(oi.unit_price), 0.00) AS total_revenue,
        COALESCE(SUM(p.space_consumption_unit), 0.0000) AS total_space_occupied
    FROM orders o
    JOIN order_items oi ON o.id = oi.order_id
    JOIN products p ON oi.product_id = p.id
    WHERE EXTRACT(YEAR FROM o.order_date) = p_year
      AND EXTRACT(QUARTER FROM o.order_date) = p_quarter
      AND oi.item_lifecycle_status != 'CANCELLED'
    GROUP BY p.id, p.product_name
    ORDER BY sales_rank ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW view_city_route_sales_breakdown AS
SELECT
    s.id AS store_id,
    s.store_name AS city_hub,
    r.id AS route_id,
    r.route_name,
    r.service_area,
    COUNT(DISTINCT o.id) AS total_orders,
    COUNT(oi.id) AS total_units_sold,
    COALESCE(SUM(oi.unit_price), 0.00) AS total_sales_revenue
FROM stores s
JOIN routes r ON s.id = r.store_id
LEFT JOIN orders o ON r.id = o.route_id
LEFT JOIN order_items oi ON o.id = oi.order_id AND oi.item_lifecycle_status != 'CANCELLED'
GROUP BY s.id, s.store_name, r.id, r.route_name, r.service_area
ORDER BY s.store_name ASC, total_sales_revenue DESC;

CREATE OR REPLACE FUNCTION get_city_route_sales(
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
)
RETURNS TABLE (
    city_hub VARCHAR(255),
    route_name VARCHAR(255),
    service_area VARCHAR(255),
    total_orders BIGINT,
    total_units_sold BIGINT,
    total_sales_revenue NUMERIC(14, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.store_name AS city_hub,
        r.route_name,
        r.service_area,
        COUNT(DISTINCT o.id) AS total_orders,
        COUNT(oi.id) AS total_units_sold,
        COALESCE(SUM(oi.unit_price), 0.00) AS total_sales_revenue
    FROM stores s
    JOIN routes r ON s.id = r.store_id
    LEFT JOIN orders o ON r.id = o.route_id 
        AND o.order_date >= p_start_date 
        AND o.order_date <= p_end_date
    LEFT JOIN order_items oi ON o.id = oi.order_id 
        AND oi.item_lifecycle_status != 'CANCELLED'
    GROUP BY s.store_name, r.route_name, r.service_area
    ORDER BY s.store_name ASC, total_sales_revenue DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_employee_working_hours_report(
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
)
RETURNS TABLE (
    employee_id BIGINT,
    employee_name VARCHAR(255),
    employee_role enum_employee_role,
    store_name VARCHAR(255),
    total_trips_assigned BIGINT,
    total_hours_worked NUMERIC(10, 2),
    weekly_limit_hours INT,
    limit_exceeded BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH trip_allocations AS (
        -- Driver schedules
        SELECT
            ts.driver_id AS emp_id,
            ts.duration_hours
        FROM truck_schedules ts
        WHERE ts.start_timestamp >= p_start_date 
          AND ts.end_timestamp <= p_end_date

        UNION ALL

        -- Assistant schedules
        SELECT
            ts.assistant_id AS emp_id,
            ts.duration_hours
        FROM truck_schedules ts
        WHERE ts.assistant_id IS NOT NULL
          AND ts.start_timestamp >= p_start_date 
          AND ts.end_timestamp <= p_end_date
    )
    SELECT
        e.id AS employee_id,
        e.employee_name,
        e.employee_role,
        s.store_name,
        COUNT(ta.emp_id) AS total_trips_assigned,
        COALESCE(SUM(ta.duration_hours), 0.00)::NUMERIC(10, 2) AS total_hours_worked,
        CASE WHEN e.employee_role = 'DRIVER' THEN 40 ELSE 60 END AS weekly_limit_hours,
        CASE 
            WHEN e.employee_role = 'DRIVER' AND COALESCE(SUM(ta.duration_hours), 0.00) > 40 THEN TRUE
            WHEN e.employee_role = 'ASSISTANT' AND COALESCE(SUM(ta.duration_hours), 0.00) > 60 THEN TRUE
            ELSE FALSE
        END AS limit_exceeded
    FROM employees e
    JOIN stores s ON e.store_id = s.id
    LEFT JOIN trip_allocations ta ON e.id = ta.emp_id
    GROUP BY e.id, e.employee_name, e.employee_role, s.store_name
    ORDER BY total_hours_worked DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_monthly_truck_usage(
    p_year INT,
    p_month INT
)
RETURNS TABLE (
    truck_id BIGINT,
    license_plate VARCHAR(50),
    operating_store VARCHAR(255),
    vehicle_capacity NUMERIC(10, 2),
    vehicle_status enum_vehicle_status,
    total_trips BIGINT,
    total_operating_hours NUMERIC(10, 2),
    total_items_delivered BIGINT,
    avg_trip_duration_hrs NUMERIC(6, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id AS truck_id,
        t.license_plate,
        s.store_name AS operating_store,
        t.capacity AS vehicle_capacity,
        t.vehicle_status,
        COUNT(DISTINCT ts.id) AS total_trips,
        COALESCE(SUM(ts.duration_hours), 0.00)::NUMERIC(10, 2) AS total_operating_hours,
        COUNT(tid.id) AS total_items_delivered,
        CASE 
            WHEN COUNT(DISTINCT ts.id) > 0 
            THEN ROUND((COALESCE(SUM(ts.duration_hours), 0.00) / COUNT(DISTINCT ts.id)), 2)
            ELSE 0.00 
        END AS avg_trip_duration_hrs
    FROM trucks t
    JOIN stores s ON t.store_id = s.id
    LEFT JOIN truck_schedules ts ON t.id = ts.truck_id
        AND EXTRACT(YEAR FROM ts.start_timestamp) = p_year
        AND EXTRACT(MONTH FROM ts.start_timestamp) = p_month
    LEFT JOIN truck_item_deliveries tid ON ts.id = tid.truck_schedule_id
        AND tid.delivered_at IS NOT NULL
    GROUP BY t.id, t.license_plate, s.store_name, t.capacity, t.vehicle_status
    ORDER BY total_trips DESC, total_operating_hours DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW view_customer_order_delivery_details AS
SELECT
    c.id AS customer_id,
    c.customer_name,
    o.id AS order_id,
    o.order_date,
    o.delivery_date AS scheduled_delivery_date,
    r.route_name,
    s.store_name AS destination_city_hub,
    oi.id AS order_item_id,
    p.product_name,
    oi.unit_price,
    oi.item_lifecycle_status,
    -- Train leg details
    trs.id AS train_trip_id,
    trs.departure_timestamp AS train_departure_time,
    -- Road last-mile details
    ts.id AS truck_schedule_id,
    t.license_plate AS truck_plate,
    d.employee_name AS driver_name,
    a.employee_name AS assistant_name,
    tid.delivered_at AS actual_delivered_at
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN routes r ON o.route_id = r.id
JOIN stores s ON r.store_id = s.id
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
LEFT JOIN train_allocations tra ON oi.id = tra.order_item_id
LEFT JOIN train_schedules trs ON tra.train_id = trs.id
LEFT JOIN truck_item_deliveries tid ON oi.id = tid.order_item_id
LEFT JOIN truck_schedules ts ON tid.truck_schedule_id = ts.id
LEFT JOIN trucks t ON ts.truck_id = t.id
LEFT JOIN employees d ON ts.driver_id = d.id
LEFT JOIN employees a ON ts.assistant_id = a.id
ORDER BY o.order_date DESC, oi.id ASC;

CREATE OR REPLACE FUNCTION get_customer_order_history(p_customer_id BIGINT)
RETURNS TABLE (
    order_id BIGINT,
    order_date TIMESTAMPTZ,
    scheduled_delivery_date TIMESTAMPTZ,
    route_name VARCHAR(255),
    destination_city_hub VARCHAR(255),
    order_item_id BIGINT,
    product_name VARCHAR(255),
    unit_price NUMERIC(12, 2),
    lifecycle_status enum_item_lifecycle_status,
    train_trip_id BIGINT,
    truck_plate VARCHAR(50),
    driver_name VARCHAR(255),
    assistant_name VARCHAR(255),
    actual_delivered_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.order_id,
        v.order_date,
        v.scheduled_delivery_date,
        v.route_name,
        v.destination_city_hub,
        v.order_item_id,
        v.product_name,
        v.unit_price,
        v.item_lifecycle_status,
        v.train_trip_id,
        v.truck_plate,
        v.driver_name,
        v.assistant_name,
        v.actual_delivered_at
    FROM view_customer_order_delivery_details v
    WHERE v.customer_id = p_customer_id
    ORDER BY v.order_date DESC, v.order_item_id ASC;
END;
$$ LANGUAGE plpgsql;

