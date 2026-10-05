import json

# PhysioNet
with open('results/dataset_audit/physionet_audit.json', encoding='utf-8') as f:
    pn = json.load(f)

params = pn['parameters']
summary = pn['summary']
records = pn['records']

print('=' * 75)
print('PHYSIONET FULL AUDIT RESULTS')
print('=' * 75)
print(f'  Records parsed:       {len(records)}')
print(f'  Records failed:       {summary["records_failed"]}')
print(f'  Unique parameters:    {summary["unique_parameters"]}')
print(f'  Physiological params: {len(summary["physiological_params"])}')
print()

# Observation stats
obs_counts = [r["raw_observations"] for r in records.values()]
durations = [r["duration_hours"] for r in records.values() if r.get("duration_hours") is not None]
durations_sorted = sorted(durations)
obs_sorted = sorted(obs_counts)
print(f'  Observations/record:  min={min(obs_counts)}, median={obs_sorted[len(obs_sorted)//2]}, max={max(obs_counts)}')
print(f'  Duration (hours):     min={min(durations):.1f}, median={durations_sorted[len(durations_sorted)//2]:.1f}, max={max(durations):.1f}')
print()
print(f'{"Parameter":<14} {"Category":<15} {"Coverage%":>10} {"TotalObs":>10} {"Median/R":>9} {"Sentinels":>10} {"HighCov":>8}')
print('-' * 75)
for p, s in sorted(params.items(), key=lambda x: -x[1]['coverage_percent']):
    flag = 'YES' if s['high_coverage'] else ''
    print(f'{p:<14} {s["category"]:<15} {s["coverage_percent"]:>10.1f} {s["total_observations"]:>10} {str(s["median_obs_per_record"]):>9} {s["sentinel_count"]:>10} {flag:>8}')

print()
print('HIGH-COVERAGE PHYSIOLOGICAL (>=70%):')
for p in sorted(summary.get('high_coverage_params', [])):
    if params[p]['category'] == 'physiological':
        print(f'  {p}: {params[p]["coverage_percent"]:.1f}%')
