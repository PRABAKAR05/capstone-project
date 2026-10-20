import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT id, gender, blood_group FROM public.patients;")
for r in cur.fetchall():
    print(r)

cur.execute("""
    SELECT conname, pg_get_constraintdef(oid) 
    FROM pg_constraint 
    WHERE conrelid = 'public.patients'::regclass;
""")
print("\nPatients constraints:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
