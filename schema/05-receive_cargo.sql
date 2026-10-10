
CREATE INDEX IF NOT EXISTS idx_order_status ON "order"(status);
CREATE INDEX IF NOT EXISTS idx_ta_train_trip ON train_allocation(train_trip_id)

CREATE OR REPLACE PROCEDURE receive_cargo_at_store(
    p_train_trip_id INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- update
    UPDATE "order"
    SET status = 'At Store'
    WHERE id IN (
        SELECT order_id
        FROM train_allocation
        WHERE train_trip_id = p_train_trip_id
    )
    AND status IN ('Scheduled', 'In Rail Transit');

END;
$$;

