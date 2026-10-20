import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    raise ValueError("DATABASE_URL not found")

conn = psycopg2.connect(db_url)
conn.autocommit = False
cur = conn.cursor()

try:
    print("Initiating surgical rollback for Phase 14 synthetic records...")
    cur.execute("BEGIN;")

    # In reverse dependency order:
    tables_to_clean = [
        "clinical_conflict_sources",
        "clinical_conflicts",
        "medication_adherence_logs",
        "prescription_items",
        "prescriptions",
        "insurance_claims",
        "patient_insurance_policies",
        "care_tasks",
        "extracted_entities",
        "clinical_documents",
        "appointments",
        "patient_accounts",
        "patients",
        "doctors",
        "profiles",
        "departments",
        "hospitals"
    ]

    deleted_counts = {}
    for tbl in tables_to_clean:
        # Delete only records created with Phase 14 synthetic deterministic UUIDs or SYN- tags
        query = f"""
            DELETE FROM public."{tbl}"
            WHERE id::text LIKE '11111111-00%'
               OR (CASE WHEN EXISTS (
                      SELECT 1 FROM information_schema.columns 
                      WHERE table_schema = 'public' AND table_name = '{tbl}' AND column_name = 'hospital_id'
                  ) THEN hospital_id::text LIKE '11111111-00%' ELSE FALSE END);
        """
        cur.execute(query)
        deleted_counts[tbl] = cur.rowcount
        if cur.rowcount > 0:
            print(f"Removed {cur.rowcount:3} synthetic records from {tbl}")

    cur.execute("COMMIT;")
    print("Surgical rollback committed successfully. Pre-existing rows remain untouched.")

except Exception as e:
    cur.execute("ROLLBACK;")
    print(f"Rollback failed: {e}")
    raise
finally:
    conn.close()
