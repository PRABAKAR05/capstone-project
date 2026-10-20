import os
import json
import datetime
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    raise ValueError("DATABASE_URL not found")

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = os.path.join('carebridge', 'backend', 'supabase', 'backups', f'snapshot_{timestamp}')
os.makedirs(backup_dir, exist_ok=True)

conn = psycopg2.connect(db_url)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Query base tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name;
""")
tables = [r['table_name'] for r in cur.fetchall()]

snapshot_data = {}
total_rows = 0

for table in tables:
    cur.execute(f'SELECT * FROM public."{table}";')
    rows = cur.fetchall()
    # Serialize datetimes and UUIDs
    clean_rows = []
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
                clean_row[k] = v.isoformat()
            elif hasattr(v, '__str__') and not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                clean_row[k] = str(v)
            else:
                clean_row[k] = v
        clean_rows.append(clean_row)
    snapshot_data[table] = clean_rows
    total_rows += len(clean_rows)
    print(f"Backed up table {table:28}: {len(clean_rows):4} rows")

snapshot_file = os.path.join(backup_dir, 'snapshot.json')
with open(snapshot_file, 'w', encoding='utf-8') as f:
    json.dump(snapshot_data, f, indent=2, default=str)

# Also write summary manifest
manifest = {
    "timestamp": timestamp,
    "database_host": urlparse(db_url).hostname,
    "table_count": len(tables),
    "total_rows": total_rows,
    "tables": {t: len(snapshot_data[t]) for t in tables}
}
with open(os.path.join(backup_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)

conn.close()
print(f"\nSnapshot successfully created at: {backup_dir}")
print(f"Total tables: {len(tables)}, Total rows backed up: {total_rows}")
