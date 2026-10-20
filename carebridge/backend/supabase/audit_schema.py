import os
from urllib.parse import urlparse
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print("ERROR: DATABASE_URL not found in carebridge/backend/.env")
    exit(1)

parsed = urlparse(db_url)
print(f"Target DB Host: {parsed.hostname}")
print(f"Target DB Port: {parsed.port}")
print(f"Target DB Database: {parsed.path.lstrip('/')}")
print(f"Target DB User: {parsed.username}")

conn = psycopg2.connect(db_url)
cur = conn.cursor()

query = """
    SELECT t.table_name, c.relrowsecurity, c.relforcerowsecurity
    FROM information_schema.tables t
    JOIN pg_class c ON c.relname = t.table_name
    JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
    WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
    ORDER BY t.table_name;
"""

cur.execute(query)
tables = cur.fetchall()
print(f"\n=======================================================")
print(f"DYNAMIC SCHEMA INVENTORY: {len(tables)} BASE TABLES FOUND")
print(f"=======================================================")

inventory = []
for t, rls, force_rls in tables:
    cur.execute(f'SELECT COUNT(*) FROM public."{t}"')
    cnt = cur.fetchone()[0]
    print(f"Table: {t:28} | RLS: {str(rls):5} | Baseline Rows: {cnt:4}")
    inventory.append((t, rls, cnt))

conn.close()
print("\nDynamic schema audit completed successfully.")
