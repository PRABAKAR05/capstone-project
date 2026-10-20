import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load backend environment variables
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment!")
    sys.exit(1)

def apply_sql_file(conn, filepath):
    print(f"Applying migration: {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"Successfully applied: {filepath}")

def main():
    print("Connecting to Supabase PostgreSQL...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    schema_file = os.path.join(os.path.dirname(__file__), "supabase", "migrations", "0001_phase2_schema.sql")
    seed_file = os.path.join(os.path.dirname(__file__), "supabase", "seed.sql")

    try:
        apply_sql_file(conn, schema_file)
        apply_sql_file(conn, seed_file)
        print("Phase 2 database migrations and seed data applied successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration error: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
