# Chapter 5: Proposed Methodology

## 5.1 Overview
This chapter details the data preprocessing pipeline, windowing strategy, and the architectural progression of the anomaly detection models evaluated in this research. The evaluation spans from an independent single-channel baseline to a naive multi-channel framework, and ultimately to the proposed Cross-Sensor Consistency Modeling (CSCM) architectures, explicitly ablating the contribution of graph-based message passing against mathematically engineered pairwise features.

## 5.2 Data Preprocessing
To transform the asynchronous, highly variable physiological recordings into a structured format suitable for deep learning, a rigorous preprocessing pipeline was applied.

### 5.2.1 Temporal Alignment
Raw physiological sensors often sample at varying frequencies and possess distinct timestamp paradigms. All channels within a given patient record were temporally aligned to a shared, global time axis, ensuring that index $t$ consistently represented the exact same chronological moment across all sensors.

### 5.2.2 Resampling
To standardize the temporal resolution, aligned records were resampled. High-frequency signals (e.g., WESAD ECG at 700 Hz) were downsampled, and asynchronous sparse signals (e.g., PhysioNet clinical observations) were binned into uniform discrete steps.

### 5.2.3 Missing-Value Handling
In clinical datasets like PhysioNet, sensors are frequently disconnected or fail to report values, resulting in missing data (NaNs). Missing values within short gaps were imputed using forward-filling to simulate the persistence of physiological states, while extensive blocks of missingness were flagged via binary observation masks.

### 5.2.4 Train-Only Normalization
To prevent data leakage, $z$-score normalization parameters (mean and standard deviation) were computed strictly on the designated training splits. These frozen parameters were subsequently applied to the validation and test splits. Normalization was performed independently for each physiological channel.

## 5.3 Window Construction
Following preprocessing and normalization, the continuous multi-variate time-series were segmented into fixed-length rolling windows. A window length of $T = 120$ steps was selected (equivalent to 30 seconds for WESAD), providing the models with sufficient temporal context to capture both rapid dynamic changes (e.g., heart rate variability) and slower cyclic patterns (e.g., respiration). The resulting input tensor to the deep learning models was $\mathbf{X} \in \mathbb{R}^{B \times T \times C}$, where $B$ is the batch size, $T$ is the window length, and $C$ is the number of channels.

## 5.4 Attack Label Construction
As defined by the threat model, False Data Injection attacks were executed across the continuous signals prior to windowing. The synthetic generation pipeline produced an `attack_mask` of shape $T \times C$ for each window, where $1$ indicates the presence of a malicious injection at a specific time step and channel. The global window label was derived using the Boolean condition: `window_attack = attack_mask.any()`. This strict definition requires the model to correctly classify any window containing even a partial attack fraction as an anomaly.

## 5.5 Independent Single-Channel Baseline
Before proposing multi-channel architectures, an independent single-channel baseline (frozen as the Phase 5 Baseline) was established. This model processed each of the $C$ channels in isolation. The primary objective was to demonstrate the fundamental limitation of traditional IoMT security: while isolated anomalies are trivially detectable, coordinated attacks engineered to remain within individual physiological bounds successfully evade independent channel monitoring.

## 5.6 Multi-Channel Detection Framework
To address the limitations of independent detection, three multi-channel architectures were constructed and evaluated. All three architectures shared the exact same temporal encoder (a 1D Convolutional Neural Network followed by a Bidirectional GRU) to extract a dense temporal representation $z_i \in \mathbb{R}^{256}$ for each channel $i$.

### 5.6.1 Model A: Naive Multi-Channel Model
Model A represents the standard approach to multi-variate time-series classification. The temporal embeddings for all $C$ channels were flattened into a single vector $\mathbf{z}_{flat} = [z_1, z_2, ..., z_C]$. This vector was passed through a flat Multi-Layer Perceptron (MLP) fusion block to produce the final classification probability. While Model A receives all channels simultaneously, it lacks a structural inductive bias to explicitly compute relationships between specific pairs of sensors.

### 5.6.2 Model B: Graph-Only Ablation
Model B introduced physiological graph message passing. Rather than flattening the embeddings, Model B constructed pairwise edges between channels. The edge representation was defined strictly as the concatenation of the two node embeddings: $r_{ij} = [z_i, z_j]$. This concatenated representation was passed through a relation MLP (`512 -> 128 -> 64`) to generate a message $m_{ij}$.

### 5.6.3 Model C: CSCM
Model C (the full Cross-Sensor Consistency Model) extended Model B by introducing explicitly engineered mathematical consistency features. The edge representation was augmented with the absolute difference and the element-wise product of the node embeddings: $r_{ij} = [z_i, z_j, |z_i - z_j|, z_i \odot z_j]$. This expanded representation was passed through a wider relation MLP (`1024 -> 128 -> 64`) to generate the message $m_{ij}$.

## 5.7 Physiology-Informed Channel Graph
Both Model B and Model C rely on a pre-defined adjacency matrix defining the physiological graph. Edges were constructed based on known biological covariances. For example, the cardiopulmonary coupling between Heart Rate and Respiration Rate was formalized as a bidirectional edge, instructing the network to explicitly evaluate the consistency between these two specific sensors.

## 5.8 Cross-Sensor Representation
The critical divergence in this methodology lies in the cross-sensor representation (Section 5.6.2 vs 5.6.3). The theoretical hypothesis underlying Model C was that manually computing $|z_i - z_j|$ would provide the relation MLP with a direct "distance" metric, accelerating the detection of decoupled signals during a coordinated attack. Model B acts as the strict ablation, forcing the relation MLP to infer any necessary distance or covariance directly from the raw concatenated vectors.

## 5.9 Graph Message Passing
For both Model B and Model C, once the pairwise messages $m_{ij}$ were computed by the relation MLP, they were aggregated at the destination node $j$. The aggregation function employed was a permutation-invariant summation over all incoming edges defined by the physiological graph.

## 5.10 Classification Layer
Following message passing (in Models B and C) or flat fusion (in Model A), the global graph representation was subjected to a pooling operation, yielding a single vector per window. A final linear classification layer equipped with a Sigmoid activation function output the probability $\hat{y} \in [0, 1]$ that the window contained an FDI attack.

## 5.11 Training Procedure
The models were trained using Binary Cross-Entropy (BCE) loss. Due to the class imbalance inherent in anomaly detection, the loss was dynamically weighted based on the ratio of clean to attacked windows in the training set. Optimization was performed using Adam, with early stopping triggered by stagnation in the validation AUROC. Thresholds for discrete binary predictions were calibrated strictly on the validation set by maximizing the F1 score prior to any test-set exposure.

## 5.12 Model Comparison and Ablation Design
The architecture progression from Model A to Model B to Model C isolates specific structural mechanisms. The comparison of $\Delta_{B-A}$ measures the utility of physiological graph message passing over naive flat fusion. The comparison of $\Delta_{C-B}$ measures the incremental utility of explicit mathematical consistency representations. 

**Important Limitation:** To preserve the strict feature ablation (the presence vs. absence of $|z_i - z_j|$ and $z_i \odot z_j$), the models were not artificially parameter-matched. Consequently, the relation MLP in Model B (~381K total parameters) is smaller than that of Model C (~448K total parameters). This parameter-capacity confound must be acknowledged when interpreting the B-vs-C ablation results.

## 5.13 Summary
This chapter detailed the complete pipeline from raw physiological recordings to architectural evaluation. By freezing preprocessing, windowing, and independent baselines, a rigorously controlled environment was established to evaluate the naive multi-channel framework against two advanced graph-based architectures. The deliberate ablation design between Model B (Graph-Only) and Model C (CSCM) allows for a focused investigation into how deep learning models best process cross-sensor physiological consistency.
