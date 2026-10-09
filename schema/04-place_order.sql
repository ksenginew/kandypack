CREATE OR REPLACE PROCEDURE place_order(
    IN  p_customer_id           BIGINT,
    IN  p_route_id              BIGINT,
    IN  p_delivery_address      TEXT,
    IN  p_contact_phone         VARCHAR(50),
    IN  p_preferred_slot        VARCHAR(100),
    IN  p_delivery_date         TIMESTAMPTZ,
    IN  p_items                  JSONB,
    IN  p_created_by             UUID DEFAULT NULL,
    INOUT p_order_id             BIGINT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO orders (
        customer_id,
        route_id,
        delivery_address,
        contact_phone,
        order_date,
        delivery_date,
        prefered_delivery_slot,
        created_by,
        updated_by
    )
    VALUES (
        p_customer_id,
        p_route_id,
        p_delivery_address,
        p_contact_phone,
        CURRENT_TIMESTAMP,
        p_delivery_date,
        p_preferred_slot,
        p_created_by,
        p_created_by
    )
    RETURNING id INTO p_order_id;

    INSERT INTO view_order_items_grouped (
        order_id,
        product_id,
        quantity
    )
    SELECT
        p_order_id,
        (item->>'product_id')::BIGINT,
        (item->>'quantity')::INT
    FROM jsonb_array_elements(p_items) AS item;

    RAISE NOTICE 'Order % successfully placed.', p_order_id;
END;
$$;