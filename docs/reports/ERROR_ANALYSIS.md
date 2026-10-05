# Error and Failure Analysis

This document provides a deep dive into the specific detection behaviors, edge cases, and failure modes of the Graph-Only model (Model B) and compares disagreements with the Full CSCM model (Model C). Predictions are pooled across all 3 random seeds (42, 123, 2024).

## PHYSIONET Error Analysis

### A. Attack Characteristics (Model B / Graph-Only)
| Subgroup | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| clean | 1626 | 1104.0 | 0.9266 | 0.8337 | 0.8777 | 204 | 81 |
| single_channel | 1623 | 1320.0 | 0.9068 | 0.9293 | 0.9179 | 91 | 123 |
| coordinated_2 | 1626 | 1170.0 | 0.8974 | 0.8656 | 0.8812 | 163 | 120 |
| coordinated_3 | 1626 | 1059.0 | 0.9046 | 0.8259 | 0.8635 | 202 | 101 |
| additive | 516 | 435.0 | 0.9103 | 0.9340 | 0.9220 | 28 | 39 |
| multiplicative | 585 | 480.0 | 0.8792 | 0.9316 | 0.9046 | 31 | 58 |
| drift | 522 | 405.0 | 0.9358 | 0.9221 | 0.9289 | 32 | 26 |
| Severity: low | 1641 | 1203.0 | 0.9002 | 0.8848 | 0.8925 | 141 | 120 |
| Severity: medium | 1575 | 1146.0 | 0.9084 | 0.8792 | 0.8936 | 143 | 105 |
| Severity: high | 1659 | 1200.0 | 0.9008 | 0.8627 | 0.8814 | 172 | 119 |

### B. Channel Breakdown (Model B / Graph-Only)
*(Note: Evaluated on Single-Channel attacks to isolate channel discriminability)*

| Channel | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| HR | 366 | 309.0 | 0.9061 | 0.9655 | 0.9349 | 10 | 29 |
| NIDiasABP | 327 | 264.0 | 0.8902 | 0.9289 | 0.9091 | 18 | 29 |
| NIMAP | 336 | 267.0 | 0.9326 | 0.9121 | 0.9222 | 24 | 18 |
| Temp | 279 | 216.0 | 0.9074 | 0.8950 | 0.9011 | 23 | 20 |
| NISysABP | 315 | 264.0 | 0.8977 | 0.9368 | 0.9168 | 16 | 27 |

### C. Impact of Missingness (Model B / Graph-Only)
| NaN Count in Window | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| Clean/Fully Observed | 5076 | 3705.0 | 0.9120 | 0.8743 | 0.8927 | 486 | 326 |
| Contains NaNs | 1425 | 948.0 | 0.8956 | 0.8299 | 0.8615 | 174 | 99 |

### D. Model Disagreement (Graph-Only vs CSCM)
Breakdown of predictions where Models B and C disagree across the pooled seeds.

| Disagreement Type | Count | % of Total |
|---|---|---|
| Both Models Correct | 5039 | 77.51% |
| Both Models Wrong | 767 | 11.80% |
| **Model B Correct, C Wrong** | **377** | **5.80%** |
| **Model C Correct, B Wrong** | **318** | **4.89%** |

## WESAD Error Analysis

### A. Attack Characteristics (Model B / Graph-Only)
| Subgroup | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| clean | 432 | 291.0 | 0.9863 | 0.6753 | 0.8017 | 138 | 4 |
| single_channel | 429 | 333.0 | 0.9850 | 0.7847 | 0.8735 | 90 | 5 |
| coordinated_2 | 429 | 357.0 | 0.9832 | 0.8298 | 0.9000 | 72 | 6 |
| coordinated_3 | 429 | 297.0 | 0.9798 | 0.6978 | 0.8151 | 126 | 6 |
| additive | 162 | 126.0 | 0.9841 | 0.7799 | 0.8702 | 35 | 2 |
| multiplicative | 150 | 117.0 | 0.9829 | 0.7877 | 0.8745 | 31 | 2 |
| drift | 117 | 90.0 | 0.9889 | 0.7876 | 0.8768 | 24 | 1 |
| Severity: low | 435 | 327.0 | 0.9786 | 0.7565 | 0.8533 | 103 | 7 |
| Severity: medium | 396 | 312.0 | 0.9744 | 0.7917 | 0.8736 | 80 | 8 |
| Severity: high | 456 | 348.0 | 0.9943 | 0.7672 | 0.8661 | 105 | 2 |

### B. Channel Breakdown (Model B / Graph-Only)
*(Note: Evaluated on Single-Channel attacks to isolate channel discriminability)*

| Channel | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| wrist_ACC_1 | 48 | 42.0 | 1.0000 | 0.8750 | 0.9333 | 6 | 0 |
| wrist_TEMP | 21 | 15.0 | 1.0000 | 0.7500 | 0.8571 | 5 | 0 |
| chest_EMG | 27 | 18.0 | 1.0000 | 0.6667 | 0.8000 | 9 | 0 |
| wrist_ACC_0 | 21 | 18.0 | 1.0000 | 0.9000 | 0.9474 | 2 | 0 |
| chest_ACC_1 | 33 | 24.0 | 1.0000 | 0.7500 | 0.8571 | 8 | 0 |
| wrist_BVP | 36 | 27.0 | 0.9630 | 0.7647 | 0.8525 | 8 | 1 |
| chest_EDA | 42 | 33.0 | 0.9394 | 0.7750 | 0.8493 | 9 | 2 |
| chest_ACC_2 | 33 | 24.0 | 0.9583 | 0.7419 | 0.8364 | 8 | 1 |
| wrist_ACC_2 | 24 | 12.0 | 1.0000 | 0.5000 | 0.6667 | 12 | 0 |
| chest_ECG | 30 | 24.0 | 1.0000 | 0.8000 | 0.8889 | 6 | 0 |
| chest_Temp | 21 | 18.0 | 1.0000 | 0.9000 | 0.9474 | 2 | 0 |
| wrist_EDA | 48 | 39.0 | 1.0000 | 0.8125 | 0.8966 | 9 | 0 |
| chest_Resp | 18 | 18.0 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| chest_ACC_0 | 27 | 21.0 | 0.9524 | 0.7692 | 0.8511 | 6 | 1 |

### C. Impact of Missingness (Model B / Graph-Only)
| NaN Count in Window | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |
|---|---|---|---|---|---|---|---|
| Clean/Fully Observed | 1719 | 1278.0 | 0.9836 | 0.7469 | 0.8490 | 426 | 21 |

### D. Model Disagreement (Graph-Only vs CSCM)
Breakdown of predictions where Models B and C disagree across the pooled seeds.

| Disagreement Type | Count | % of Total |
|---|---|---|
| Both Models Correct | 1255 | 73.01% |
| Both Models Wrong | 426 | 24.78% |
| **Model B Correct, C Wrong** | **17** | **0.99%** |
| **Model C Correct, B Wrong** | **21** | **1.22%** |

