
CREATE INDEX IF NOT EXISTS idx_oi_lifecycle ON order_items(item_lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_ta_train_id ON train_allocations(train_id);

CREATE OR REPLACE PROCEDURE receive_cargo_at_store(
    p_train_id BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Update all order items allocated to this train schedule to 'STORE_RECEIVED'
    UPDATE order_items
    SET item_lifecycle_status = 'STORE_RECEIVED'
    WHERE id IN (
        SELECT order_item_id
        FROM train_allocations
        WHERE train_id = p_train_id
    )
    AND item_lifecycle_status IN ('SCHEDULED', 'IN_TRANSIT');

END;
$$;
