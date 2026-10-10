-- View for grouped order items
CREATE OR REPLACE VIEW view_order_items_grouped AS
SELECT
    MIN(id) AS id,
    order_id,
    product_id,
    unit_price,
    item_lifecycle_status,
    COUNT(*)::INT AS quantity
FROM
    order_items
GROUP BY
    order_id,
    product_id,
    unit_price,
    item_lifecycle_status;

CREATE OR REPLACE FUNCTION trg_view_order_items_grouped_io()
RETURNS TRIGGER AS $$
DECLARE
    v_diff INT;
    v_target_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.quantity IS NULL OR NEW.quantity <= 0 THEN
            RAISE EXCEPTION 'quantity must be greater than 0';
        END IF;

        WITH inserted AS (
            INSERT INTO order_items (
                order_id,
                product_id,
                unit_price,
                item_lifecycle_status
            )
            SELECT 
                NEW.order_id,
                NEW.product_id,
                NEW.unit_price,
                COALESCE(NEW.item_lifecycle_status, 'PLACED'::enum_item_lifecycle_status)
            FROM generate_series(1, NEW.quantity)
            RETURNING id
        )
        SELECT MIN(id) INTO v_target_id FROM inserted;

        NEW.id := v_target_id;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.quantity IS NULL OR NEW.quantity <= 0 THEN
            RAISE EXCEPTION 'quantity must be greater than 0';
        END IF;

        -- Case A: Quantity decreased
        IF NEW.quantity < OLD.quantity THEN
            v_diff := OLD.quantity - NEW.quantity;

            DELETE FROM order_items
            WHERE id IN (
                SELECT id 
                FROM order_items
                WHERE order_id = OLD.order_id
                  AND product_id = OLD.product_id
                  AND unit_price = OLD.unit_price
                  AND item_lifecycle_status = OLD.item_lifecycle_status
                ORDER BY id DESC  
                LIMIT v_diff
            );

            UPDATE order_items
            SET 
                order_id = NEW.order_id,
                product_id = NEW.product_id,
                unit_price = NEW.unit_price,
                item_lifecycle_status = NEW.item_lifecycle_status
            WHERE order_id = OLD.order_id
                AND product_id = OLD.product_id
                AND unit_price = OLD.unit_price
                AND item_lifecycle_status = OLD.item_lifecycle_status;

        -- Case B: Quantity increased
        ELSIF NEW.quantity > OLD.quantity THEN
            v_diff := NEW.quantity - OLD.quantity;

            UPDATE order_items
            SET 
                order_id = NEW.order_id,
                product_id = NEW.product_id,
                unit_price = NEW.unit_price,
                item_lifecycle_status = NEW.item_lifecycle_status
            WHERE order_id = OLD.order_id
              AND product_id = OLD.product_id
              AND unit_price = OLD.unit_price
              AND item_lifecycle_status = OLD.item_lifecycle_status;

            INSERT INTO order_items (
                order_id,
                product_id,
                unit_price,
                item_lifecycle_status
            )
            SELECT 
                NEW.order_id,
                NEW.product_id,
                NEW.unit_price,
                NEW.item_lifecycle_status
            FROM generate_series(1, v_diff);

        -- Case C: Quantity unchanged
        ELSE
            UPDATE order_items
            SET 
                order_id = NEW.order_id,
                product_id = NEW.product_id,
                unit_price = NEW.unit_price,
                item_lifecycle_status = NEW.item_lifecycle_status
            WHERE order_id = OLD.order_id
              AND product_id = OLD.product_id
              AND unit_price = OLD.unit_price
              AND item_lifecycle_status = OLD.item_lifecycle_status;
        END IF;

        -- Set the returned row's ID
        SELECT MIN(id) INTO v_target_id
        FROM order_items
        WHERE order_id = NEW.order_id
            AND product_id = NEW.product_id
            AND unit_price = NEW.unit_price
            AND item_lifecycle_status = NEW.item_lifecycle_status;

        NEW.id := v_target_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        DELETE FROM order_items
        WHERE order_id = OLD.order_id
          AND product_id = OLD.product_id
          AND unit_price = OLD.unit_price
          AND item_lifecycle_status = OLD.item_lifecycle_status;

        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_view_order_items_grouped_io
INSTEAD OF INSERT OR UPDATE OR DELETE ON view_order_items_grouped
FOR EACH ROW
EXECUTE FUNCTION trg_view_order_items_grouped_io();

-- Procedure to place an order
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
