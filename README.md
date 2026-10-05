# CSCM-IoMT

**Coordinated Multi-Channel False Data Injection Attack Detection  
Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT**

---

## Research Question

> "Can physiology-aware cross-sensor consistency modeling improve detection of
> coordinated multi-channel FDI attacks in IoMT physiological time-series data
> compared with a single-channel detection baseline?"

This is a hypothesis under investigation — results are not predetermined.

---

## Datasets

Two datasets are used. **Raw dataset files must never be modified.**

| Dataset | Source | Local Location |
|---------|--------|---------------|
| PhysioNet/CinC Challenge 2012 | https://physionet.org/content/challenge-2012/1.0.0/ | `predicting-mortality-of-icu-patients-.../` |
| WESAD — Wearable Stress and Affect Detection | https://ub-madoc.bib.uni-mannheim.de/45817/ | `WESAD/WESAD/` |

### PhysioNet Format
Long-format CSV: `Time,Parameter,Value`  
Irregular ICU time-series. 48-hour records. `-1` = missing sentinel.

### WESAD Format
Subject `.pkl` files containing synchronized multi-modal physiological signals.  
15 subjects: S2–S17 (S1, S12 absent — sensor malfunction per documentation).  
Chest (RespiBAN, 700 Hz): ACC, ECG, EDA, EMG, RESP, Temp  
Wrist (E4): ACC (32 Hz), BVP (64 Hz), EDA (4 Hz), TEMP (4 Hz)

---

## Installation

```bash
pip install -r requirements.txt
```

> PyTorch and torch-geometric are **model-phase dependencies** (Phase 10+).
> They are not required for Phase 1 (environment) or Phase 2 (dataset audit).

---

## Dataset Configuration

Edit `configs/paths.yaml` if the datasets are in non-default locations:

```yaml
datasets:
  physionet:
    set_a: "predicting-mortality-of-icu-patients-.../set-a"
  wesad:
    root: "WESAD/WESAD"
```

Set `CSCM_PROJECT_ROOT` environment variable to the project directory if running scripts from elsewhere.

---

## Phase 1: Environment Setup

```bash
python scripts/environment_info.py
```

Outputs: `results/dataset_audit/environment.json` and `environment.md`

---

## Phase 2: Dataset Audit

### Quick sample test (2 records / 2 subjects)
```bash
python scripts/audit_datasets.py --sample 2
```

### Full audit (all records + all subjects — may take 30–60 min for WESAD)
```bash
python scripts/audit_datasets.py
```

### Dataset-specific
```bash
python scripts/audit_datasets.py --physionet-only
python scripts/audit_datasets.py --wesad-only
```

### Outputs
```
results/dataset_audit/
    environment.json
    environment.md
    physionet_audit.json
    physionet_audit.md
    wesad_audit.json
    wesad_audit.md
    combined_audit.md          ← PRIMARY DELIVERABLE
```

---

## Unit Tests

```bash
pytest tests/ -v
```

Run specific test files:
```bash
pytest tests/test_physionet_loader.py -v
pytest tests/test_wesad_loader.py -v
pytest tests/test_config.py -v
```

---

## Project Structure

```
capstone_PRABAKAR/
├── configs/
│   ├── paths.yaml          ← Dataset path configuration
│   ├── physionet.yaml      ← PhysioNet parameters
│   └── wesad.yaml          ← WESAD device/subject config
│
├── src/
│   ├── data/
│   │   ├── physionet_loader.py   ← PhysioNet record parser
│   │   └── wesad_loader.py       ← WESAD pkl loader
│   └── utils/
│       ├── config.py             ← Path resolution
│       ├── logging.py            ← Logging factory
│       └── reproducibility.py   ← Seed management
│
├── scripts/
│   ├── environment_info.py  ← Phase 1
│   └── audit_datasets.py    ← Phase 2
│
├── tests/
│   ├── test_physionet_loader.py
│   ├── test_wesad_loader.py
│   └── test_config.py
│
├── results/dataset_audit/   ← Audit outputs (generated)
├── requirements.txt
└── pyproject.toml
```

---

## Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Environment setup | ✅ Complete |
| 2 | Dataset audit | ✅ Complete |
| 3 | Preprocessing design | ⏳ Pending audit review |
| 4 | Attack generation | ⏳ Pending |
| 5 | Baseline model | ⏳ Pending |
| 6 | CSCM + GAT | ⏳ Pending |
| 7–10 | Evaluation, ablation, experiments | ⏳ Pending |

---

## Reproducibility

All experiments use seed 42 by default. Configure in `configs/experiments.yaml` (Phase 3+).

```python
from src.utils.reproducibility import set_all_seeds
set_all_seeds(42)
```

---

## Limitations

- FDI attacks are **synthetic** — this is a controlled threat model study.
- WESAD has 15 subjects — leave-subject-out evaluation recommended.
- PhysioNet uses irregular sampling — temporal alignment requires explicit decisions.
- Cross-dataset generalization may not be valid given different modalities.

---

## Citation

PhysioNet: Silva, I., Moody, G., et al. "Predicting In-Hospital Mortality of ICU Patients." CinC 2012.  
WESAD: Schmidt, P., et al. "Introducing WESAD, a Multimodal Dataset for Wearable Stress and Affect Detection." ICMI 2018.
