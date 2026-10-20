import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name;
""")
tables = [r[0] for r in cur.fetchall()]

schema_info = {}
for t in tables:
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{t}'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    
    cur.execute(f"""
        SELECT kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = '{t}';
    """)
    fks = cur.fetchall()
    
    schema_info[t] = {
        'columns': {c[0]: {'type': c[1], 'nullable': c[2], 'default': c[3]} for c in cols},
        'fks': fks
    }

with open('carebridge/backend/supabase/schema_dump.json', 'w', encoding='utf-8') as f:
    json.dump(schema_info, f, indent=2)

print("Schema dump written to carebridge/backend/supabase/schema_dump.json")
conn.close()
