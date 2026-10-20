import os
import re
import json

EXCLUDE_DIRS = {'.git', 'node_modules', '.next', '__pycache__', 'backups', '.system_generated', '.pytest_cache'}

def scan_text(patterns, root_dirs):
    results = {p: [] for p in patterns}
    for rdir in root_dirs:
        for root, dirs, files in os.walk(rdir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if file.endswith(('.png', '.jpg', '.ico', '.pdf', '.docx', '.h5', '.pt', '.npy', '.parquet', '.zip', '.tar', '.gz')):
                    continue
                fpath = os.path.join(root, file)
                relpath = os.path.relpath(fpath, '.')
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines):
                        for p in patterns:
                            if re.search(r'\b' + re.escape(p) + r'\b', line, re.IGNORECASE):
                                results[p].append({
                                    'file': relpath.replace('\\', '/'),
                                    'line_num': idx + 1,
                                    'line': line.strip()[:140]
                                })
                except Exception as e:
                    pass
    return results

patterns = ['receptionist', 'caregiver', 'lab_tech', 'lab_technician', 'account_link_status']
scan_dirs = ['carebridge', 'docs']

res = scan_text(patterns, scan_dirs)

summary = {}
for p, hits in res.items():
    file_map = {}
    for h in hits:
        file_map.setdefault(h['file'], []).append(h)
    summary[p] = {
        'total_hits': len(hits),
        'distinct_files_count': len(file_map),
        'files': {f: len(l) for f, l in sorted(file_map.items())}
    }

with open('carebridge/backend/supabase/audit_roles_report.json', 'w', encoding='utf-8') as f:
    json.dump({'summary': summary, 'details': res}, f, indent=2)

print("AUDIT SUCCESSFUL! Summary saved to carebridge/backend/supabase/audit_roles_report.json")
for p, data in summary.items():
    print(f"Pattern '{p}': {data['total_hits']} hits across {data['distinct_files_count']} files")
