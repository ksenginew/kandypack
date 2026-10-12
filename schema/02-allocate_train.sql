DROP VIEW IF EXISTS view_train_schedules;

DROP TRIGGER IF EXISTS trg_allocate_after_order ON orders;
DROP TRIGGER IF EXISTS trg_allocate_after_train_schedule ON train_schedules;
DROP TRIGGER IF EXISTS trg_allocate_after_order_items ON order_items;
DROP TRIGGER IF EXISTS trg_allocate_after_order_items_update ON order_items;
DROP TRIGGER IF EXISTS trg_reset_order_items_before_train_delete ON train_schedules;
DROP TRIGGER IF EXISTS trg_allocate_after_train_delete ON train_schedules;

UPDATE train_schedules AS ts
SET remaining_capacity = ts.max_capacity - COALESCE(allocated.used_capacity, 0)
FROM (
	SELECT ts.id, COALESCE(SUM(p.space_consumption_unit), 0) AS used_capacity
	FROM train_schedules AS ts
	LEFT JOIN train_allocations AS ta ON ta.train_id = ts.id
	LEFT JOIN order_items AS oi ON oi.id = ta.order_item_id
	LEFT JOIN products AS p ON p.id = oi.product_id
	GROUP BY ts.id
) AS allocated
WHERE ts.id = allocated.id
;

CREATE VIEW view_train_schedules AS
WITH filter_parameters AS (
	SELECT TIMESTAMPTZ '2026-10-11 14:30:00-05:00' AS "FILTER_TIMESTAMP"
)
SELECT ts.id,
	   s.store_name AS destination_store,
	   ts.departure_timestamp,
	   ts.max_capacity,
	   ts.remaining_capacity,
	   COUNT(ta.id) AS allocated_items
FROM train_schedules AS ts
JOIN stores AS s ON ts.destination_store_id = s.id
LEFT JOIN train_allocations AS ta ON ts.id = ta.train_id
CROSS JOIN filter_parameters
WHERE ts.departure_timestamp > filter_parameters."FILTER_TIMESTAMP"
GROUP BY ts.id, s.store_name
ORDER BY ts.departure_timestamp ASC;

CREATE OR REPLACE PROCEDURE allocate_order_items_to_trains()
LANGUAGE plpgsql
AS $$
DECLARE
	v_schedule RECORD;
	v_item RECORD;
BEGIN
	PERFORM pg_advisory_xact_lock(hashtext('allocate_order_items_to_trains'));

	FOR v_schedule IN
		SELECT id, destination_store_id, remaining_capacity
		FROM train_schedules
		WHERE departure_timestamp > TIMESTAMPTZ '2026-10-11 14:30:00-05:00'
		ORDER BY departure_timestamp ASC, id ASC
	LOOP
		FOR v_item IN
			SELECT oi.id, p.space_consumption_unit
			FROM order_items AS oi
			JOIN orders AS o ON o.id = oi.order_id
			JOIN routes AS r ON r.id = o.route_id
			JOIN products AS p ON p.id = oi.product_id
			WHERE oi.item_lifecycle_status = 'PLACED'
			  AND r.store_id = v_schedule.destination_store_id
			  AND NOT EXISTS (
				  SELECT 1
				  FROM train_allocations AS ta
				  WHERE ta.order_item_id = oi.id
			  )
			ORDER BY o.order_date ASC, o.id ASC, oi.id ASC
		LOOP
			IF EXISTS (
				SELECT 1
				FROM train_allocations
				WHERE order_item_id = v_item.id
			) THEN
				CONTINUE;
			END IF;

			IF v_item.space_consumption_unit > v_schedule.remaining_capacity THEN
				CONTINUE;
			END IF;

			INSERT INTO train_allocations (order_item_id, train_id)
			VALUES (v_item.id, v_schedule.id);

			UPDATE train_schedules
			SET remaining_capacity = remaining_capacity - v_item.space_consumption_unit
			WHERE id = v_schedule.id;

			UPDATE order_items
			SET item_lifecycle_status = 'SCHEDULED'
			WHERE id = v_item.id;

			v_schedule.remaining_capacity := v_schedule.remaining_capacity - v_item.space_consumption_unit;
		END LOOP;
	END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION trigger_allocate_order_items_to_trains()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
	IF pg_trigger_depth() > 1 THEN
		RETURN NEW;
	END IF;

	CALL allocate_order_items_to_trains();
	RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION trigger_allocate_after_order_items()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
	IF EXISTS (
		SELECT 1
		FROM new_order_items
		WHERE item_lifecycle_status = 'PLACED'
	) THEN
		CALL allocate_order_items_to_trains();
	END IF;

	RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION reset_order_items_before_train_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
	UPDATE order_items AS oi
	SET item_lifecycle_status = 'PLACED'
	FROM train_allocations AS ta
	WHERE ta.train_id = OLD.id
	  AND ta.order_item_id = oi.id;

	RETURN OLD;
END;
$$;

CREATE TRIGGER trg_reset_order_items_before_train_delete
BEFORE DELETE ON train_schedules
FOR EACH ROW
EXECUTE FUNCTION reset_order_items_before_train_delete();

CREATE OR REPLACE FUNCTION trigger_allocate_after_train_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
	CALL allocate_order_items_to_trains();
	RETURN OLD;
END;
$$;

CREATE TRIGGER trg_allocate_after_train_delete
AFTER DELETE ON train_schedules
FOR EACH ROW
EXECUTE FUNCTION trigger_allocate_after_train_delete();

CREATE TRIGGER trg_allocate_after_train_schedule
AFTER INSERT OR UPDATE ON train_schedules
FOR EACH STATEMENT
EXECUTE FUNCTION trigger_allocate_order_items_to_trains();

CREATE TRIGGER trg_allocate_after_order_items
AFTER INSERT ON order_items
REFERENCING NEW TABLE AS new_order_items
FOR EACH STATEMENT
EXECUTE FUNCTION trigger_allocate_after_order_items();

CREATE TRIGGER trg_allocate_after_order_items_update
AFTER UPDATE ON order_items
REFERENCING NEW TABLE AS new_order_items
FOR EACH STATEMENT
EXECUTE FUNCTION trigger_allocate_after_order_items();
