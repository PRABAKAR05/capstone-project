import json

with open('carebridge/backend/supabase/schema_dump.json') as f:
    schema = json.load(f)

for table, data in sorted(schema.items()):
    cols = [f"{col}: {info['type']}" for col, info in data['columns'].items()]
    print(f"\nTABLE: {table}")
    for c in cols:
        print(f"  - {c}")
    if data['fks']:
        print("  FOREIGN KEYS:")
        for fk in data['fks']:
            print(f"    * {fk[0]} -> {fk[1]}({fk[2]})")
