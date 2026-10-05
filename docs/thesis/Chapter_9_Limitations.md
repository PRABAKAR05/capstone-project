# Chapter 9: Limitations

## 9.1 Parameter Capacity Confound
The most critical limitation of this research concerns the strict architectural ablation performed between Model B (Graph-Only) and Model C (Full CSCM). 

To cleanly ablate the *features*, the underlying temporal embeddings ($z$) and the network depths were held entirely constant. Consequently, because Model B utilizes the edge representation $r_{ij} = [z_i, z_j]$ and Model C utilizes $r_{ij} = [z_i, z_j, |z_i-z_j|, z_i \odot z_j]$, the dimension of the input to the relation MLP differs substantially (512 vs. 1024). This structural difference results in a total parameter count of approximately 381,000 for Model B and 448,000 for Model C.

Because Model C has roughly 17% more parameters, the observed degradation in Model C's performance ($\Delta_{C-B}$) cannot be exclusively attributed to the explicit consistency features themselves. The degradation may indeed stem from the manually engineered differences introducing noise or conflicting gradients into the relation network, but it could equally be driven by the expanded capacity altering optimization dynamics, leading to mild overfitting on the training set. Therefore, the conclusion that explicit pairwise consistency is unnecessary remains strictly conditional on the specific parameterizations tested in this experiment.

## 9.2 Reliance on Synthetic FDI Attacks
This study utilized a mathematically rigorous, dynamically constrained synthetic generation pipeline to create False Data Injection attacks. While the generation process strictly bounded attacks to ensure single-channel plausibility (thus ensuring they evade trivial threshold alarms), they remain synthetic artifacts. 

A sophisticated, real-world adversary might not employ simple additive, multiplicative, or drift equations. Instead, an attacker might utilize advanced generative models (e.g., Generative Adversarial Networks or Normalizing Flows) to synthesize highly complex, organic-looking coordinated signals that perfectly mimic deep biological correlations while systematically drifting the clinical interpretation. The detection models evaluated herein have not been tested against such advanced generative adversaries.

## 9.3 Temporal Granularity
The detection framework operates on a rolling window paradigm ($T = 120$ steps). The model generates a single global binary label $\hat{y}$ indicating whether the entire 30-second temporal window is compromised. 

While this window-level classification is appropriate for triggering broad clinical alarms or network-level security alerts, it does not provide exact point-level localization of the attack within the window, nor does it explicitly identify which specific subset of channels $\mathcal{S}$ is compromised. Future clinical deployment would require granular explainability mechanisms to localize the anomaly both temporally and dimensionally to assist clinicians in isolating the compromised sensors.
