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

CREATE INDEX idx_order_items_grouping 
ON order_items (order_id, product_id, unit_price, item_lifecycle_status);

CREATE OR REPLACE FUNCTION trg_view_order_items_grouped_insert()
RETURNS TRIGGER AS $$
DECLARE
    v_first_id BIGINT;
BEGIN
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
    SELECT MIN(id) INTO v_first_id FROM inserted;

    NEW.id := v_first_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_view_order_items_grouped_io_insert
INSTEAD OF INSERT ON view_order_items_grouped
FOR EACH ROW
EXECUTE FUNCTION trg_view_order_items_grouped_insert();

CREATE OR REPLACE FUNCTION trg_view_order_items_grouped_update()
RETURNS TRIGGER AS $$
DECLARE
    v_diff INT;
    v_new_id BIGINT;
BEGIN
    IF NEW.quantity IS NULL OR NEW.quantity < 0 THEN
        RAISE EXCEPTION 'quantity cannot be negative';
    END IF;

    -- Case 1: Quantity decreased
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
            LIMIT v_diff
        );

        IF NEW.quantity > 0 THEN
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

    -- Case 2: Quantity increased
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

    -- Case 3: Quantity unchanged
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
    SELECT MIN(id) INTO v_new_id
    FROM order_items
    WHERE order_id = NEW.order_id
      AND product_id = NEW.product_id
      AND unit_price = NEW.unit_price
      AND item_lifecycle_status = NEW.item_lifecycle_status;

    NEW.id := v_new_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_view_order_items_grouped_io_update
INSTEAD OF UPDATE ON view_order_items_grouped
FOR EACH ROW
EXECUTE FUNCTION trg_view_order_items_grouped_update();

CREATE OR REPLACE FUNCTION trg_view_order_items_grouped_delete()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM order_items
    WHERE order_id = OLD.order_id
      AND product_id = OLD.product_id
      AND unit_price = OLD.unit_price
      AND item_lifecycle_status = OLD.item_lifecycle_status;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_view_order_items_grouped_io_delete
INSTEAD OF DELETE ON view_order_items_grouped
FOR EACH ROW
EXECUTE FUNCTION trg_view_order_items_grouped_delete();
