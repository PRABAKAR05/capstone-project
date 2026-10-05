import os
import subprocess

def run_all():
    datasets = ["physionet", "wesad"]
    models = ["naive", "cscm"]
    seeds = [42, 123, 2024]
    
    python_exe = "C:\\Users\\PRABAKAR\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    for ds in datasets:
        for md in models:
            for sd in seeds:
                cmd = [python_exe, "scripts/phase6_train.py", "--dataset", ds, "--model", md, "--seed", str(sd)]
                print(f"Running: {' '.join(cmd)}")
                subprocess.run(cmd, env=env, check=True)
                
    print("All Phase 6 training completed.")

if __name__ == "__main__":
    run_all()
