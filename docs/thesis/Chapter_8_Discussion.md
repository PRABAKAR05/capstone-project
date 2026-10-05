# Chapter 8: Discussion

## 8.1 Graph-Based Interaction Modeling
The central finding of this research is that structuring multi-channel physiological data as a graph and allowing the network to explicitly compute pairwise interactions yields measurable improvements over naive flat fusion. 

In Model A (Naive Multi-Channel), the network receives the entire concatenated vector of channel representations $\mathbf{z}_{flat}$. The dense layers must implicitly learn which channel combinations are biologically meaningful. By contrast, Model B (Graph-Only) enforces a structural inductive bias. The network is forced to evaluate specific, biologically justified pairs (e.g., Heart Rate and Respiration) via the relation MLP before globally aggregating the interactions. 

The positive $\Delta_{B-A}$ effect sizes, combined with the rigorous exclusion of zero in several seed-specific 95% Confidence Intervals, provide strong evidence that this graph-based structural constraint improves the model's ability to detect sophisticated, coordinated anomalies that evade single-channel detection.

## 8.2 Explicit Consistency Representation
While the original hypothesis posited that manually engineering explicit mathematical consistency metrics—such as the absolute difference $|z_i - z_j|$ and element-wise product $z_i \odot z_j$—would accelerate the relation network's ability to identify decoupled signals, the empirical evidence did not support a consistent benefit.

The degradation observed in Model C across multiple metrics and seeds suggests that the relation MLP in Model B, operating strictly on the raw concatenated representations $[z_i, z_j]$, is already sufficiently powerful to approximate the necessary non-linear distance boundaries. Handcrafting the arithmetic representations may be redundant.

## 8.3 Dataset Differences
The performance profiles diverged significantly between the PhysioNet/CinC 2012 clinical dataset and the WESAD wearable dataset. 
- **PhysioNet:** The graph-only model yielded consistent, broad improvements across all metrics. The clinical nature of the data—highly asynchronous, noisy, and drawn from critically ill patients—likely meant that enforcing biological structural priors (the graph) was essential for extracting signal from the noise.
- **WESAD:** The baseline models already achieved high performance, likely due to the high-frequency, continuous, and synchronized nature of the wearable sensors in a controlled laboratory environment. The graph structure improved AUROC and AUPRC, but F1 margins were extraordinarily tight. In environments where signals are already highly synchronized and clean, naive flat fusion performs adequately, diminishing the relative advantage of explicit graph modeling.

## 8.4 Failure Cases
The error analysis highlighted specific boundary conditions where the detection models failed.
The most severe failure mode occurred on the `chest_Resp` channel within the WESAD dataset, which exhibited a 0.0000 recall rate during isolated attacks. This indicates an extreme "sparse-positive" failure. When an attack is injected into a channel that is inherently sparse, highly irregular, or possesses a distinctly separate morphological profile from dense cardiovascular signals (like ECG), the relation network may learn to completely discount its embedding. 

Furthermore, the introduction of NaNs (missing values) predictably degraded detection capabilities. While the forward-filling mechanism preserved the data shape, prolonged periods of signal loss essentially blinded the relation network to cross-sensor interactions, forcing it to rely on stale or zero-padded vectors, reducing F1 performance.
