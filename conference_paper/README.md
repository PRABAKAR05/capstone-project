# Conference Paper — CSCM / IoMT FDI Benchmark

**Title:** *Do Explicit Cross-Sensor Consistency Features Help? A Leakage-Controlled Benchmark for Coordinated Multi-Channel False Data Injection Detection in IoMT*

## Files

| File | Purpose |
|---|---|
| `paper.tex` | Camera-ready style draft for IEEEtran (`\documentclass[conference]{IEEEtran}`), two-column, 8 tables, 4 figures, 18 references. |
| `paper.docx` | Word version (single column, Times New Roman, ~10 pages / ~4,550 words) for editing and review. |
| `paper.pdf` | PDF rendered from the Word version, for quick reading. |
| `figs/` | Figures reused from the project (`docs/reports/figures/`). |

Rebuild both from one source: `python C:\Users\PRABAKAR\AppData\Local\Temp\opencode\build_paper.py`

## What the paper argues

1. **Graph structure is the useful inductive bias.** Graph-only message passing over a physiology-informed channel graph is the best model on the clinical dataset (F1 0.8863 ± 0.0031, AUPRC 0.9583, AUROC 0.9029) and is significantly better than naive fusion at seed 2024 (ΔF1 CI [0.0018, 0.0187], McNemar p = 0.0003).
2. **Hand-engineered cross-sensor consistency features do not help.** CSCM (explicit `|z_i − z_j|` and `z_i ⊙ z_j`) is consistently worse than graph-only on PhysioNet and is significantly worse at seed 42 (CI [−0.0180, −0.0005], p = 0.0198).
3. **On clean wearable data nothing separates.** WESAD models are statistically indistinguishable and AUROC ≈ 0.68 (near chance).
4. **Failure modes matter.** Sparse-positive channels can be missed entirely (`chest_Resp` recall 0.0000), missingness degrades detection (F1 0.8615 vs 0.8927), and coordinated attacks remain harder than single-channel attacks.

Framing: a **leakage-controlled benchmark with a largely null result**, not a state-of-the-art claim.

## Evidence provenance

Every number is taken from the repository's own artefacts:

- `docs/reports/phase7_results/aggregated_metrics.csv`, `all_seeds.csv`
- `docs/reports/phase8_results/statistical_tests.csv`
- `docs/reports/ERROR_ANALYSIS.md`
- `docs/thesis/Chapter_4..9, 11`

## Before you submit (TODO)

- [ ] Fill author block placeholders (`[Student Name]`, `[Registration Number]`).
- [ ] Compile the LaTeX locally (`pdflatex paper.tex` twice) and check the IEEEtran reference list renders as expected.
- [ ] **Expand Related Work** and add external FDI/anomaly baselines — this is the biggest reviewer objection.
- [ ] Consider adding seeds (5–10) and a pre-registered power analysis.
- [ ] Add a cross-dataset / generalization experiment, or state clearly that it was not done.
- [ ] Replace the forward-fill missingness strategy or discuss it more deeply.
- [ ] Confirm the target venue's page limit (typically 6–8 pages) and trim if needed.
- [ ] Confirm the venue's anonymity policy before circulating this version.
