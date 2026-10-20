import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("""
    SELECT t.typname, e.enumlabel
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public'
    ORDER BY t.typname, e.enumsortorder;
""")
rows = cur.fetchall()
enums = {}
for typname, label in rows:
    enums.setdefault(typname, []).append(label)

with open('carebridge/backend/supabase/enums.json', 'w') as f:
    json.dump(enums, f, indent=2)

print("Enums written to carebridge/backend/supabase/enums.json:")
for k, v in enums.items():
    print(f"  {k}: {v}")

conn.close()
