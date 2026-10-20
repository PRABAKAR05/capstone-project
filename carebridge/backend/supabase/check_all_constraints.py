import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("""
    SELECT relname 
    FROM pg_class c 
    JOIN pg_namespace n ON n.oid = c.relnamespace 
    WHERE n.nspname = 'public' AND c.relkind = 'r'
    ORDER BY relname;
""")
tables = [r[0] for r in cur.fetchall()]

for t in tables:
    cur.execute(f"""
        SELECT conname, pg_get_constraintdef(oid) 
        FROM pg_constraint 
        WHERE conrelid = 'public."{t}"'::regclass;
    """)
    constraints = cur.fetchall()
    print(f"\nTABLE {t}:")
    for c in constraints:
        print(f"  [{c[0]}]: {c[1]}")

conn.close()
