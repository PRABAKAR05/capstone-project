import subprocess
import sys

python = sys.executable

# Correct model names as per phase6_evaluate.py argparser:
# naive = Model A (Baseline)
# ablation = Model B (Graph-Only)
# cscm = Model C (CSCM)

runs = [
    ("physionet", "naive",   42),
    ("physionet", "naive",   123),
    ("physionet", "naive",   2024),
    ("wesad",     "naive",   42),
    ("wesad",     "naive",   123),
    ("wesad",     "naive",   2024),
    ("physionet", "ablation",42),
    ("physionet", "ablation",123),
    ("physionet", "ablation",2024),
    ("wesad",     "ablation",42),
    ("wesad",     "ablation",123),
    ("wesad",     "ablation",2024),
    ("physionet", "cscm",    42),
    ("physionet", "cscm",    123),
    ("physionet", "cscm",    2024),
    ("wesad",     "cscm",    42),
    ("wesad",     "cscm",    123),
    ("wesad",     "cscm",    2024),
]

import os
env = os.environ.copy()
env["PYTHONPATH"] = "."

for dataset, model, seed in runs:
    result = subprocess.run(
        [python, "scripts/phase6_evaluate.py",
         "--dataset", dataset, "--model", model, "--seed", str(seed)],
        capture_output=True, text=True, env=env
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"ERROR [{dataset}|{model}|seed {seed}]: {result.stderr.strip()}")
