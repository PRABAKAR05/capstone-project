# Chapter 6: Experimental Setup

## 6.1 Overview
This chapter details the rigorous experimental framework established to evaluate the models described in Chapter 5. To ensure valid, reproducible results and prevent data leakage, strict controls were implemented regarding data splitting, normalization, and metric calculation. Furthermore, the statistical testing framework designed to robustly evaluate the differences between model architectures is defined.

## 6.2 Data Splits
A fundamental requirement for evaluating physiological anomaly detection models is patient isolation. If data from a single patient appears in both the training and testing sets, the model may memorize patient-specific physiological signatures rather than learning generalized anomaly detection.

To prevent this, data splitting was performed deterministically at the subject/record level rather than the window level:
- **PhysioNet/CinC 2012:** The dataset was partitioned based on unique `RecordID`s.
- **WESAD:** The dataset was partitioned based on unique `SubjectID`s (e.g., S2, S3, etc.).

For both datasets, the subjects were deterministically shuffled using a fixed random seed (frozen in Phase 4) and split into **Train (70%)**, **Validation (15%)**, and **Test (15%)** sets. All subsequent synthetic attack generation and model evaluations strictly adhered to these frozen splits.

## 6.3 Normalization Strategy
Standardization of physiological signals is critical for deep learning models to converge efficiently. However, normalizing across the entire dataset prior to splitting introduces data leakage, as the test set distribution informs the scaling parameters used during training.

To ensure strict evaluation integrity:
1. Mean and standard deviation parameters were calculated **exclusively on the training split** for each physiological channel independently.
2. These pre-computed, frozen scaling parameters were subsequently applied to standardize the validation and test splits.
3. Normalization was applied *before* synthetic attack injection to simulate realistic clinical sensor distributions.

## 6.4 Evaluation Metrics
Given the extreme class imbalance typical of anomaly and attack detection contexts (where normal physiological windows vastly outnumber attacked windows), standard accuracy is an insufficient metric. Models were evaluated using the following window-level metrics:

- **F1 Score:** The harmonic mean of precision and recall, providing a balanced measure of the model's ability to identify attacks without generating excessive false positives.
- **Area Under the Precision-Recall Curve (AUPRC):** A highly sensitive metric for imbalanced datasets that summarizes the trade-off between precision and recall across all classification thresholds.
- **Area Under the Receiver Operating Characteristic Curve (AUROC):** Summarizes the trade-off between the True Positive Rate and the False Positive Rate.

Model predictions were generated as continuous probabilities $\hat{y} \in [0, 1]$. To calculate the discrete F1 score, an optimal classification threshold was dynamically calibrated on the **Validation set** by maximizing the validation F1 score. This threshold was then frozen and applied to the Test set.

## 6.5 Multi-Seed Evaluation
Deep learning models, particularly those operating on complex spatiotemporal graphs, are susceptible to variance caused by random weight initialization. To ensure the observed performance differences were not artifacts of a "lucky" initialization, all models were trained and evaluated across three distinct random seeds: **42, 123, and 2024**. Results in the subsequent chapter report the performance across these seeds to evaluate the robustness of the architectures.

## 6.6 Statistical Analysis Framework
To rigorously determine if the performance differences between Model A (Naive), Model B (Graph-Only), and Model C (CSCM) were statistically meaningful, a robust testing framework was implemented (Phase 8). 

Evaluating sequential windows independently violates the assumption of Independent and Identically Distributed (I.I.D.) samples, as windows drawn from the same patient exhibit strong temporal correlation. 

### 6.6.1 Hierarchical Paired Bootstrapping
To correctly estimate uncertainty conditional on the test set, we employed **hierarchical paired bootstrapping**:
- Rather than resampling individual windows, we resampled at the patient level (`RecordID` for PhysioNet, `SubjectID` for WESAD) with replacement, perfectly preserving the intra-patient correlation structure.
- For 1,000 bootstrap iterations, we calculated the paired differences in metrics:
  - $\Delta_{B-A} = \text{Metric}(B) - \text{Metric}(A)$
  - $\Delta_{C-B} = \text{Metric}(C) - \text{Metric}(B)$
- We extracted the 95% Confidence Intervals (CIs) for these differences. A 95% CI that strictly excludes zero provides evidence of a measurable performance difference between the architectures.

### 6.6.2 McNemar's Test
As a supplementary analysis of error patterns, McNemar’s test with continuity correction was applied to the paired, thresholded binary predictions. This test evaluates whether the specific pattern of False Positives and False Negatives produced by two models diverged significantly (defined as $p < 0.05$).

## 6.7 Summary
This chapter outlined the strict experimental controls utilized in this research. By enforcing patient-isolated data splits, train-only normalization, validation-calibrated thresholds, and multi-seed hierarchical bootstrapping, the experimental setup guarantees that the architectural comparisons presented in the subsequent results chapter are robust, reproducible, and mathematically rigorous.
