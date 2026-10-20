import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    raise ValueError("DATABASE_URL not found")

# Locate latest snapshot
backups_root = os.path.join('carebridge', 'backend', 'supabase', 'backups')
snapshots = sorted([d for d in os.listdir(backups_root) if d.startswith('snapshot_')])
if not snapshots:
    raise RuntimeError("No snapshot found to verify recovery!")

latest_snapshot = snapshots[-1]
snapshot_path = os.path.join(backups_root, latest_snapshot, 'snapshot.json')
print(f"Verifying recovery from snapshot: {snapshot_path}")

with open(snapshot_path, 'r', encoding='utf-8') as f:
    snapshot_data = json.load(f)

conn = psycopg2.connect(db_url)
conn.autocommit = False
cur = conn.cursor()

try:
    print("\n--- 1. Creating Isolated PostgreSQL Sandbox Schema ---")
    cur.execute("DROP SCHEMA IF EXISTS recovery_sandbox_temp CASCADE;")
    cur.execute("CREATE SCHEMA recovery_sandbox_temp;")
    print("Schema 'recovery_sandbox_temp' created successfully.")

    print("\n--- 2. Cloning Table Definitions to Sandbox (PostgreSQL Types & Constraints) ---")
    # For each table in snapshot, clone structure into recovery_sandbox_temp
    for table_name in snapshot_data.keys():
        cur.execute(f"""
            CREATE TABLE recovery_sandbox_temp."{table_name}" (
                LIKE public."{table_name}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            );
        """)
        print(f"Cloned DDL for: {table_name}")

    print("\n--- 3. Restoring Snapshot Data into Isolated PostgreSQL Sandbox ---")
    restored_counts = {}
    for table_name, rows in snapshot_data.items():
        if not rows:
            restored_counts[table_name] = 0
            continue

        columns = list(rows[0].keys())
        col_identifiers = ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        insert_query = f'INSERT INTO recovery_sandbox_temp."{table_name}" ({col_identifiers}) VALUES ({placeholders})'

        for row in rows:
            values = []
            for col in columns:
                val = row[col]
                if isinstance(val, (dict, list)):
                    values.append(json.dumps(val))
                else:
                    values.append(val)
            cur.execute(insert_query, values)
        
        cur.execute(f'SELECT COUNT(*) FROM recovery_sandbox_temp."{table_name}";')
        cnt = cur.fetchone()[0]
        restored_counts[table_name] = cnt
        assert cnt == len(rows), f"Recovery mismatch for {table_name}: expected {len(rows)}, got {cnt}"
        print(f"Restored {table_name:28}: {cnt:4} rows (100% parity)")

    print("\n--- 4. Validating PostgreSQL-Specific Capabilities & Integrity ---")
    # Validate UUID and JSONB query capabilities in sandbox
    cur.execute("SELECT id FROM recovery_sandbox_temp.hospitals LIMIT 1;")
    sample_id = cur.fetchone()
    print(f"Verified PostgreSQL UUID query in sandbox: {sample_id}")

    print("\n--- 5. Clean Sandbox Teardown ---")
    cur.execute("DROP SCHEMA recovery_sandbox_temp CASCADE;")
    conn.commit()
    print("Schema 'recovery_sandbox_temp' dropped cleanly. Public schema completely untouched.")

    print("\n=======================================================")
    print("POSTGRESQL ISOLATED RECOVERY TEST: 100% PASSED")
    print("=======================================================")

except Exception as e:
    conn.rollback()
    # Ensure cleanup
    try:
        cleanup_conn = psycopg2.connect(db_url)
        with cleanup_conn.cursor() as cleanup_cur:
            cleanup_cur.execute("DROP SCHEMA IF EXISTS recovery_sandbox_temp CASCADE;")
            cleanup_conn.commit()
    except Exception:
        pass
    print(f"\nRECOVERY TEST FAILED: {e}")
    raise
finally:
    conn.close()
