import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("""
    SELECT tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    WHERE tc.table_schema = 'public' 
      AND tc.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
    ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position;
""")
for r in cur.fetchall():
    print(f"{r[0]:28} | {r[1]:35} | {r[2]:12} | {r[3]}")
conn.close()
