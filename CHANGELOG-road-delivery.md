# Last-mile road delivery changes — 2026-10-09

## Scope

- Implemented `schema/06-schedule_delivery.sql` and `app/routes/4_Last_Mile_Road_Delivery.py`.
- Preserved the existing schema, seeds, other modules, and prior `app/main.py` change.
- Added this changelog to `.gitignore` as requested.
- Added `tests/test_road_delivery.py` for database and UI integration checks.

## Database

- Added table triggers and a crew check to enforce validation for direct schedule INSERT/UPDATE as well as `CALL schedule_delivery(...)`.
- Required a separate DRIVER and ASSISTANT; rejected route-duration overruns and overlapping truck/crew assignments across routes.
- Per your clarification, consecutive trips have exactly no gap: drivers cannot take two; assistants cannot take three, including a trip inserted between existing bookings.
- Enforced exact elapsed weekly hours (40 driver / 60 assistant), splitting trips at Monday midnight in Asia/Colombo rather than using rounded duration or departure week alone.
- Serialized roster changes with a guard row; concurrent writers cannot bypass overlap or aggregate checks. Stale repeatable-read/serializable writers must retry.
- Protected referenced rosters when route maximum duration or employee roles are edited directly.
- Installed only this module's triggers, functions, procedure, and check; did not recreate tables or rewrite existing seed records. The crew check is NOT VALID for legacy rows but applies to all new/updated rows.

## UI

- Replaced mock truck/employee choices and hard-coded hours with database records and a paginated schedule list.
- Added create/edit dialogs with route, truck, crew, and Colombo start/end timestamps; writes use parameterized CRUD statements and database validation.
- Added confirmed deletion; schedules containing delivery items are retained to preserve other modules' delivery history.
- Displayed validation failures without crashing the page and retained successful CRUD notices across reruns.

## Applying to an existing database

Run from Git Bash:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d kandypack < schema/06-schedule_delivery.sql
```

Do not rerun `00-schema.sql` or remove the database volume: those actions replace existing data.

## Verification

- All 33 integration checks passed: direct INSERT/UPDATE, multirow statements, required crew and roles, exact route limits, overlap, consecutive-trip boundaries, weekly caps, cross-week splitting, reference edits, procedure calls, and concurrent writes at READ COMMITTED / REPEATABLE READ / SERIALIZABLE.
- Streamlit form checks passed for create/read/edit/delete, database validation feedback, and refusal to delete a schedule with linked delivery items. AppTest renders dialog bodies inline because it does not simulate browser dialog-fragment submissions.
- Verified installation can be repeated and preserves legacy rows. Each completed test run removes its uniquely named test database.
- Corrected test isolation to pass an explicit Streamlit secret: loading TOML secrets can replace the DATABASE_URL environment variable. Removed the single unlinked booking created by the initial UI test using its exact ID, creation timestamp, and assignment details; no other records were removed.
- Installed `06-schedule_delivery.sql` in the local application database and confirmed the last-mile page loads without errors.
- Python syntax, Git whitespace checks, and changelog ignore rule verified.

Run the tests in the existing app container:

```bash
docker compose exec -T server python tests/test_road_delivery.py
```

Existing seed records are retained, not retroactively certified as compliant. New/edited schedules are validated; correcting an older noncompliant schedule requires making it satisfy the rules.
