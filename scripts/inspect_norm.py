import json

with open('data/processed/normalization/physionet_normalization.json') as f:
    pn = json.load(f)

print("PhysioNet norm top-level keys:", list(pn.keys()))
if 'statistics' in pn:
    for ch, s in pn['statistics'].items():
        print(f"  {ch}: {s}")
else:
    print(pn)

with open('data/processed/normalization/wesad_normalization.json') as f:
    wn = json.load(f)

print("WESAD norm top-level keys:", list(wn.keys()))
if 'statistics' in wn:
    for ch in list(wn['statistics'].keys()):
        print(f"  {ch}: {wn['statistics'][ch]}")
