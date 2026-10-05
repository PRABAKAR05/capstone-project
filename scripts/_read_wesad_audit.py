import json

with open('results/dataset_audit/wesad_audit.json', encoding='utf-8') as f:
    d = json.load(f)

summary = d['summary']
subjects = d['subjects']

print('=' * 75)
print('WESAD FULL AUDIT RESULTS')
print('=' * 75)
print(f'  Subjects loaded: {summary["subjects_loaded_successfully"]} / {summary["subjects_expected"]}')
print(f'  Subjects failed: {summary["subjects_failed"]}')
print(f'  Chest mods: {summary["chest_modalities_found"]}')
print(f'  Wrist mods: {summary["wrist_modalities_found"]}')
print()

print(f'{"Subj":<6} {"MB":>7} {"Dur(s)":>9} {"L0":>8} {"L1(base)":>9} {"L2(stress)":>11} {"L3(amuse)":>10} {"L4(medit)":>10}')
print('-' * 75)
for sid in sorted(subjects.keys()):
    s = subjects[sid]
    v = s.get('validation') or {}
    linfo = v.get('labels') or {}
    dur = linfo.get('duration_seconds', 'N/A')
    counts = linfo.get('label_counts', {})
    sz = s.get('pkl_size_mb', 'N/A')
    print(f'{sid:<6} {str(sz):>7} {str(dur):>9} {counts.get(0,0):>8} {counts.get(1,0):>9} {counts.get(2,0):>11} {counts.get(3,0):>10} {counts.get(4,0):>10}')

print()
print('CHEST SIGNAL SHAPES AND QUALITY (S2 representative):')
s2v = subjects.get('S2', {}).get('validation') or {}
for mod in sorted((s2v.get('chest') or {}).keys()):
    st = s2v['chest'][mod]
    print(f'  chest/{mod:<6}: shape={str(st.get("shape")):<18} nan={st.get("nan_count")}, inf={st.get("inf_count")}, finite={st.get("finite_fraction")}')

print()
print('WRIST SIGNAL SHAPES AND QUALITY (S2 representative):')
for mod in sorted((s2v.get('wrist') or {}).keys()):
    st = s2v['wrist'][mod]
    print(f'  wrist/{mod:<6}: shape={str(st.get("shape")):<18} nan={st.get("nan_count")}, inf={st.get("inf_count")}, finite={st.get("finite_fraction")}')

print()
print('NaN/Inf check across ALL subjects:')
total_nan = 0
total_inf = 0
for sid, s in subjects.items():
    v = s.get('validation') or {}
    for device in ('chest', 'wrist'):
        for mod, stats in (v.get(device) or {}).items():
            if isinstance(stats, dict):
                total_nan += stats.get('nan_count', 0) or 0
                total_inf += stats.get('inf_count', 0) or 0
print(f'  Total NaN across all subjects/modalities: {total_nan}')
print(f'  Total Inf across all subjects/modalities: {total_inf}')
