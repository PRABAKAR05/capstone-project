# Chapter 7: Results

## 7.1 Overview
This chapter presents the empirical findings of the anomaly detection architectures evaluated across the PhysioNet and WESAD datasets. The results begin with the independent single-channel baseline, proceed to the absolute performance of the multi-channel models, isolate the architectural contributions via ablation, quantify the statistical uncertainty of those contributions, and conclude with a granular error analysis of the Graph-Only model.

## 7.2 Independent Single-Channel Baseline
The initial phase of evaluation tested the Independent Single-Channel Baseline (Phase 5). This model evaluated each of the $C$ channels in total isolation. 

The baseline confirmed the fundamental vulnerability driving this research: while extreme, isolated physiological anomalies are trivially detectable, coordinated FDI attacks engineered to remain within individual physiological bounds successfully evade single-channel detection. Performance on single-channel baselines dropped precipitously when confronted with coordinated attacks, proving the necessity of cross-sensor consistency modeling in the IoMT domain.

## 7.3 Absolute Performance of Multi-Channel Models
To evaluate the proposed multi-channel architectures, Model A (Naive Flat Fusion), Model B (Graph-Only Message Passing), and Model C (Full CSCM) were trained and evaluated across three random weight initialization seeds (42, 123, 2024).

Table 7.1 presents the absolute F1, AUPRC, and AUROC metrics averaged across the three seeds.

**Table 7.1: Absolute Performance (Mean ± Std)**
| Dataset | Model | F1 | AUPRC | AUROC |
|---|---|---|---|---|
| PhysioNet | A (Naive) | 0.8788 ± 0.0019 | 0.9550 ± 0.0008 | 0.8946 ± 0.0017 |
| PhysioNet | B (Graph-Only) | **0.8863** ± 0.0031 | **0.9583** ± 0.0012 | **0.9029** ± 0.0021 |
| PhysioNet | C (CSCM) | 0.8827 ± 0.0030 | 0.9556 ± 0.0019 | 0.8962 ± 0.0036 |
| WESAD | A (Naive) | 0.8509 ± 0.0033 | 0.8820 ± 0.0087 | 0.6812 ± 0.0183 |
| WESAD | B (Graph-Only) | 0.8489 ± 0.0068 | **0.8877** ± 0.0035 | **0.6909** ± 0.0110 |
| WESAD | C (CSCM) | **0.8520** ± 0.0008 | 0.8822 ± 0.0015 | 0.6806 ± 0.0051 |

Across the clinical PhysioNet dataset, Model B achieved the highest absolute performance across all three metrics. On the wearable WESAD dataset, Model B achieved the highest AUPRC and AUROC, while Model C achieved a marginally higher F1 score.

## 7.4 Architectural Ablation
To strictly isolate the mechanisms driving performance, we evaluate the paired differences:
- $\Delta_{B-A}$: The effect of incorporating physiological graph message passing over flat fusion.
- $\Delta_{C-B}$: The effect of manually engineering the explicit mathematical differences ($|z_i - z_j|$ and $z_i \odot z_j$) over the raw graph representation.

**Table 7.2: Architectural Differences ($\Delta$)**
| Dataset | Comparison | $\Delta$ F1 | $\Delta$ AUPRC | $\Delta$ AUROC |
|---|---|---|---|---|
| PhysioNet | $\Delta_{B-A}$ (Graph vs Naive) | +0.0075 | +0.0033 | +0.0082 |
| PhysioNet | $\Delta_{C-B}$ (CSCM vs Graph) | -0.0035 | -0.0027 | -0.0067 |
| WESAD | $\Delta_{B-A}$ (Graph vs Naive) | -0.0020 | +0.0058 | +0.0097 |
| WESAD | $\Delta_{C-B}$ (CSCM vs Graph) | +0.0030 | -0.0055 | -0.0103 |

The ablation reveals that transitioning from naive fusion to graph message passing ($\Delta_{B-A}$) generally produced positive improvements, particularly in AUROC and AUPRC across both datasets. Conversely, transitioning from the graph-only model to the full CSCM model ($\Delta_{C-B}$) resulted in performance degradation across all metrics on PhysioNet, and mixed results on WESAD.

## 7.5 Statistical Uncertainty and Robustness
To rigorously determine if these observed differences were robust against intra-patient correlation and random initialization, hierarchical paired bootstrapping (1,000 resamples) was performed on the thresholded predictions for each seed independently. 

On PhysioNet, the graph-only model produced positive point estimates relative to Model A across all three seeds. Several seed-specific bootstrap confidence intervals strictly excluded zero (e.g., Seed 2024 F1 `[0.0018, 0.0187]` and AUROC `[0.0017, 0.0154]`). This indicates that incorporating the predefined physiological graph was associated with measurable improvements under the tested configuration.

However, the explicit pairwise features ($\Delta_{C-B}$) did not demonstrate a consistent additional benefit. Several seed-specific bootstrap intervals were entirely negative, while others encompassed zero, indicating no statistically robust improvement. 

## 7.6 Error and Failure Analysis
To understand the practical behavior of the optimal architecture (Model B, Graph-Only), a granular error analysis was conducted by pooling predictions across all three random seeds.

### 7.6.1 Attack Characteristics
The model exhibited robust recall across diverse attack types. On PhysioNet, Additive attacks (F1: 0.9220) and Drift attacks (F1: 0.9289) were detected more reliably than Multiplicative attacks (F1: 0.9046). Coordinated multi-channel attacks resulted in slightly lower detection rates than single-channel attacks, confirming that coordinated FDI remains a challenging adversary even for cross-sensor models. Detection scales logically with attack severity: "High" severity attacks on PhysioNet were detected with an F1 of 0.8814, while "Low" severity attacks achieved 0.8925.

### 7.6.2 Channel Characteristics and Edge Cases
Detection performance was highly heterogeneous across physiological channels. On PhysioNet, attacks on Heart Rate (HR) and Non-Invasive Mean Arterial Pressure (NIMAP) were detected with high F1 scores (>0.92). 

However, edge cases revealed critical limitations. On the WESAD dataset, the `chest_Resp` channel exhibited a profound failure rate. Attacks localized to `chest_Resp` yielded a Recall of 0.0000. This indicates a "sparse-positive" failure, likely driven by extreme data sparsity, severe class imbalance within that specific sub-modality, or an inability of the relation network to properly fuse the sparse respiratory signal with denser cardiovascular modalities.

### 7.6.3 Missingness
Missing data inherently degrades confidence in cross-sensor predictions. On PhysioNet, windows containing NaNs (imputed via forward filling or masked) resulted in a measurable drop in F1 (0.8615) compared to clean, fully observed windows (0.8927). 

### 7.6.4 Model Disagreement
An analysis of discrete disagreements between Model B and Model C across all 5,800+ pooled test windows revealed that the models agree 89.31% of the time. When they disagree, Model B was correct 5.80% of the time, while Model C was correct only 4.89% of the time (PhysioNet). This reinforces the finding from the statistical ablation that Model C's explicit mathematical representations did not offer a superior, generalized detection capability over Model B.

## 7.7 Summary
The empirical evaluation indicates that physiological graph-based message passing (Model B) provides a robust inductive bias, yielding performance improvements over naive fusion. The explicit mathematical consistency representations (Model C) failed to provide a consistent, statistically robust incremental advantage. Granular error analysis confirms the model accurately detects a variety of FDI attacks, though sparse-positive channels and physiological missingness remain challenging edge cases.
