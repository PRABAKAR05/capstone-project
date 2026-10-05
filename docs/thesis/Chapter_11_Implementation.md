# Chapter 11: Implementation

## 11.1 Project Plan
The development and execution of the CSCM-IoMT project were structured into a rigorous nine-phase implementation plan to systematically build and evaluate the detection architectures:

- **Phase 1 (Environment Setup):** Configuration of the deep learning environment and dataset acquisition.
- **Phase 2 (Dataset Audit):** Extensive parsing and temporal auditing of PhysioNet/CinC-2012 and WESAD records to ensure data integrity.
- **Phase 3 (Preprocessing):** Implementation of temporal alignment, resampling, missing-value imputation (forward fill), and train-only normalization.
- **Phase 4 (Synthetic FDI Generation):** Engineering a deterministic pipeline to inject additive, multiplicative, drift, and coordinated multi-channel FDI attacks under controlled severity and physiological plausibility constraints.
- **Phase 5 (Baseline Modeling):** Training independent single-channel detection models to establish a baseline for comparison against coordinated multi-channel attack detection.
- **Phase 6 (CSCM Architecture):** Implementation of the Cross-Sensor Consistency Modeling (CSCM) framework using temporal feature extraction, a physiology-informed channel graph, graph-based message passing, and explicit pairwise representation features.
- **Phase 7 (Architectural Ablation):** Controlled comparison of the naive multi-channel model, graph-only message passing model, and full CSCM model to determine whether explicit pairwise representation features provide additional benefit beyond graph-based interaction.
- **Phase 8 (Statistical Analysis):** Evaluation of model differences using hierarchical paired bootstrap resampling at the RecordID level for PhysioNet and SubjectID level for WESAD, together with supplementary McNemar analysis.
- **Phase 9 (Final Consolidation):** Granular error analysis and generation of final visualizations.

## 11.2 Sample Code
The following snippet demonstrates the architectural difference between Model B (Graph-Only) and Model C (CSCM). Model B uses the concatenated representations of connected channels, while CSCM additionally introduces explicit pairwise difference and element-wise interaction features.

```python
import torch
import torch.nn as nn

class RelationNetwork(nn.Module):
    def __init__(self, in_dim, out_dim, mode="graph_only"):
        super().__init__()
        self.mode = mode
        
        # Model B (Graph-Only) uses concatenated features: [z_i, z_j]
        if self.mode == "graph_only":
            mlp_in = in_dim * 2  
            self.mlp = nn.Sequential(
                nn.Linear(mlp_in, 128),
                nn.ReLU(),
                nn.Linear(128, out_dim)
            )
            
        # Model C (CSCM) adds explicit consistency: [z_i, z_j, |z_i-z_j|, z_i * z_j]
        elif self.mode == "cscm":
            mlp_in = in_dim * 4  
            self.mlp = nn.Sequential(
                nn.Linear(mlp_in, 128),
                nn.ReLU(),
                nn.Linear(128, out_dim)
            )

    def forward(self, z_i, z_j):
        if self.mode == "graph_only":
            # Feature representation for Model B
            r_ij = torch.cat([z_i, z_j], dim=-1)
            
        elif self.mode == "cscm":
            # Feature representation for Model C
            abs_diff = torch.abs(z_i - z_j)
            element_prod = z_i * z_j
            r_ij = torch.cat([z_i, z_j, abs_diff, element_prod], dim=-1)
            
        # Generate message m_ij
        m_ij = self.mlp(r_ij)
        return m_ij
```

## 11.3 Testing Strategies
To guarantee the reliability of the anomaly detection pipeline, comprehensive testing strategies were integrated throughout the project lifecycle:

1. **Unit Testing:** Automated unit tests utilizing the `pytest` framework were implemented to validate data loaders and configuration parsing.
2. **Dataset Integrity Testing:** Pre-computation audits ensured records were properly loaded and isolated correctly by unique patient/subject identifiers.
3. **Attack Validation:** The attack generation pipeline dynamically validated that all synthetic FDI manipulations strictly adhered to defined global physiological plausibility constraints.
4. **Reproducibility:** Random operations were controlled using fixed random seeds. Final experiments were repeated using seeds 42, 123, and 2024 to test robustness against initialization variance.
5. **Train/Validation/Test Leakage Checks:** Normalization parameters (mean/std) were computed exclusively on the designated training split before being strictly applied to the validation and test splits.
6. **Threshold Calibration:** Classification thresholds for discrete binary predictions were dynamically optimized strictly on the isolated validation splits to prevent test-set leakage.
7. **Statistical Validation:** Model differences were rigorously evaluated via hierarchical paired bootstrapping at the RecordID level for PhysioNet and SubjectID level for WESAD to ensure differences were statistically meaningful and accounted for intra-patient correlation.

## 11.4 Sample Screenshots

*(Note: The following images reflect the implemented state of the project components and analysis).*

- **[Figure 11.1: Dataset Audit Output]**
  *Description: Terminal output displaying PhysioNet records, WESAD subjects, channel availability, and missingness statistics.*
- **[Figure 11.2: Preprocessing and HDF5 Output]**
  *Description: Overview of the window shape, aligned records, and the resulting HDF5 dataset structure.*
- **[Figure 11.3: FDI Attack Generation]**
  *Description: Visualization comparing a clean physiological signal against its corresponding attacked signal under coordinated multi-channel manipulation.*
- **[Figure 11.4: Attack Mask Visualization]**
  *Description: Graph illustrating the clean signal, attacked signal, and the corresponding binary attack mask.*
- **[Figure 11.5: Model Architecture Progression]**
  *Description: Architectural diagram detailing the flow from input, temporal encoder, graph construction, relation network variants (Graph-only vs CSCM), to the final classifier.*
- **[Figure 11.6: Final A/B/C Results Comparison]**
  *Description: Master results table and corresponding bar charts showing the absolute F1, AUPRC, and AUROC across Models A, B, and C.*
- **[Figure 11.7: Error Analysis and Effect-Size]**
  *Description: Visualization of the effect-size ($\Delta_{B-A}$ and $\Delta_{C-B}$) with 95% Confidence Intervals, paired with a breakdown of detection performance across sparse-positive channels and coordinated attack types.*
