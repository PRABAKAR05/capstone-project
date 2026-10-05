# Chapter 4: Dataset and Problem Formulation

## 4.1 Overview
The evaluation of multi-channel physiological anomaly detection models requires robust, highly granular time-series data. This chapter outlines the datasets utilized in this research, formulates the core problem of detecting False Data Injection (FDI) attacks in the Internet of Medical Things (IoMT), and describes the synthetic attack generation pipeline developed to benchmark the proposed architectures.

## 4.2 Dataset Description
To ensure the proposed architectures generalize across different physiological contexts and sampling environments, two distinct public datasets were utilized: the PhysioNet/Computing in Cardiology (CinC) Challenge 2012 dataset and the WESAD (Wearable Stress and Affect Detection) dataset.

### 4.2.1 PhysioNet/CinC Challenge 2012
The PhysioNet/CinC Challenge 2012 dataset consists of multi-parameter physiological records collected from Intensive Care Unit (ICU) patients. It provides highly irregular, sparse, and asynchronous multivariate time-series data representative of clinical-grade IoMT environments. For this research, data from the continuous monitoring subset was utilized, prioritizing patients with concurrent records across multiple core physiological parameters. 

### 4.2.2 WESAD
The WESAD dataset provides multimodal sensor data collected via wearable devices (e.g., the RespiBAN chest sensor) during controlled laboratory studies. Unlike the clinical ICU setting of PhysioNet, WESAD represents edge-based, continuous, high-frequency wearable monitoring. It is critical to note that while WESAD originally contains labels for baseline, stress, and amusement states, these labels were discarded for this research. The objective of this study is entirely divorced from stress detection; instead, the continuous physiological recordings serve solely as a healthy, real-world substrate upon which synthetic FDI attacks are mathematically injected.

## 4.3 Physiological Channels
The selection of channels for both datasets was driven by the necessity of underlying physiological correlation. Cross-sensor consistency modeling relies on the premise that parameters governed by the same biological systems (e.g., the autonomic nervous system) will covary in predictable patterns.

### 4.3.1 PhysioNet Channels
For the PhysioNet dataset, four parameters were extracted based on their dense sampling availability and fundamental cardiovascular/respiratory coupling:
- Heart Rate (HR)
- Respiration Rate (Resp)
- Blood Oxygen Saturation (SpO2)
- Non-Invasive Blood Pressure - Mean (NIDiasABP/NISysABP aggregated to Mean or closely related parameters mapped to standard HR/Resp vectors).
*(Note: As per Phase 1-5 implementations, specific high-density features were retained).*

### 4.3.2 WESAD Channels
For the WESAD dataset, four channels from the RespiBAN chest-worn device were extracted:
- Electrocardiogram (chest_ECG)
- Electrodermal Activity (chest_EDA)
- Electromyogram (chest_EMG)
- Respiration (chest_Resp)

## 4.4 Problem Formulation
Consider an IoMT network monitoring a patient via $C$ heterogeneous sensors. At discrete time step $t$, the system receives an observation vector $\mathbf{x}_t \in \mathbb{R}^C$. Over a temporal window of length $T$, the system processes the matrix $\mathbf{X} \in \mathbb{R}^{T \times C}$. 

Under normal physiological conditions, $\mathbf{X}$ is governed by a joint distribution $P(\mathbf{X})$. In the presence of an FDI attack, an adversary injects a malicious perturbation $\mathbf{\delta} \in \mathbb{R}^{T \times C}$ into a subset of channels $\mathcal{S} \subseteq \{1, 2, ..., C\}$. The received signal becomes $\mathbf{\tilde{X}} = \mathbf{X} + \mathbf{\delta}$. 

The problem is formulated as a binary classification task: given a window $\mathbf{\tilde{X}}$, a detection model $F(\cdot)$ must output $\hat{y} \in \{0, 1\}$, where $1$ indicates the presence of an FDI attack on any channel within the window, and $0$ indicates an entirely benign, uncompromised window.

## 4.5 Coordinated Multi-Channel FDI Threat Model
Existing single-channel anomaly detection systems operate under the assumption that physiological anomalies manifest as severe, out-of-bound deviations on individual sensors. Our threat model assumes an adversary who aims to manipulate clinical decision-making or trigger false alarms without immediately triggering these boundary-based systems.

The adversary is assumed to have compromised one or more edge sensors or communication links, allowing them to manipulate the digital readout before it reaches the central aggregator. In a **coordinated attack**, the adversary simultaneously injects correlated perturbations across multiple sensors (e.g., synchronously raising HR and Resp) such that the marginal distribution of each individual channel remains biologically plausible, but the joint distribution across the physiological graph is violated.

## 4.6 Synthetic Attack Generation
To rigorously benchmark the detection systems, a deterministic, synthetic FDI generation pipeline was engineered (frozen in Phase 4 of the experimental methodology). The pipeline injects mathematically defined anomalies over the clean physiological substrate.

### 4.6.1 Attack Families
Attacks were drawn from three distinct mathematical families:
1. **Additive Attacks:** A constant or bounded uniform noise term is added to the signal, simulating sensor offset or calibration tampering.
2. **Multiplicative Attacks:** The signal is scaled by a dynamic coefficient, simulating gain errors or signal attenuation.
3. **Drift Attacks:** A linear or polynomial trend is accumulated over the window, simulating progressive sensor degradation or gradual physiological manipulation.

### 4.6.2 Attack Severity
Attacks were parameterized across three severity levels—Low, Medium, and High—controlling the magnitude of the perturbation $\delta$. Crucially, even "High" severity attacks were strictly capped to ensure they did not violate global physiological limits, forcing models to rely on contextual anomalies rather than trivial bounds checking.

### 4.6.3 Coordinated Attacks
Windows were partitioned into specific attack compositions:
- **Clean:** No injection.
- **Single-Channel:** Only one sensor is compromised.
- **Coordinated 2-Channel:** Two sensors are compromised simultaneously.
- **Coordinated 3-Channel:** Three sensors are compromised simultaneously.
In coordinated attacks, the directionality and severity of the perturbations were explicitly coupled to mimic physiological synchrony (e.g., both channels exhibiting an additive increase).

### 4.6.4 Plausibility Constraints
All generated attack profiles were dynamically clipped. If an additive injection pushed a patient's simulated Heart Rate above a hard physiological limit (e.g., 220 BPM), the injection was constrained. This ensured the dataset specifically targeted the vulnerability gap of single-channel, threshold-based monitoring systems.

## 4.7 Attack Validation
The output of the generation pipeline was a set of HDF5 artifacts containing the modified time-series matrices and dense binary masks denoting the exact coordinate $(t, c)$ of every injection. A window was assigned a positive global attack label (`window_attack = attack_mask.any()`) if any injection occurred within its temporal boundaries. The pipeline was validated to confirm that the ratio of clean to attacked windows matched the pre-defined experimental target configurations.

## 4.8 Summary
This chapter detailed the utilization of the PhysioNet/CinC 2012 and WESAD datasets to represent distinct clinical and wearable IoMT environments. The core problem was formulated as the detection of sophisticated, coordinated False Data Injection attacks. By utilizing a rigorous synthetic attack generation pipeline with strict physiological plausibility constraints, the datasets provide an empirically challenging benchmark for evaluating cross-sensor consistency modeling.
