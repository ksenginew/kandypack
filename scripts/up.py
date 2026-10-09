import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from psycopg import Connection, OperationalError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# Resolve schema folder relative to the current working directory
SCHEMA_DIR = Path.cwd() / "schema"


def run_migrations():
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not SCHEMA_DIR.is_dir():
        print(f"Error: Schema directory not found at {SCHEMA_DIR.resolve()}", file=sys.stderr)
        sys.exit(1)

    sql_files = sorted(SCHEMA_DIR.glob("*.sql"))

    if not sql_files:
        print(f"No SQL files found in {SCHEMA_DIR.resolve()}.")
        return

    print(f"Found {len(sql_files)} SQL file(s) in {SCHEMA_DIR.resolve()}.")

    try:
        with Connection.connect(DATABASE_URL) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    for sql_file in sql_files:
                        print(f"Applying: {sql_file.name}...")
                        cur.execute(sql_file.read_text(encoding="utf-8"))

            print("All schema files applied successfully!")

    except OperationalError as e:
        print(f"Database connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Migration failed and was rolled back: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()