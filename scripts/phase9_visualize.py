import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Matplotlib global settings for an academic, restrained look
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 12,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--'
})

# Semantic Palette
COLOR_A = '#7f8c8d' # Neutral Gray (Model A)
COLOR_B = '#d35400' # Distinct Orange (Model B - Graph)
COLOR_C = '#2980b9' # Distinct Blue (Model C - CSCM)

def plot_absolute_metrics():
    """Generates grouped bar charts for F1, AUPRC, AUROC across datasets."""
    datasets = ['PhysioNet', 'WESAD']
    metrics = ['F1', 'AUPRC', 'AUROC']
    
    # Data manually aggregated from Phase 7 (Mean across 3 seeds)
    data = {
        'PhysioNet': {
            'A': [0.8788, 0.9550, 0.8946],
            'B': [0.8863, 0.9583, 0.9029],
            'C': [0.8827, 0.9556, 0.8962]
        },
        'WESAD': {
            'A': [0.8509, 0.8820, 0.6812],
            'B': [0.8489, 0.8877, 0.6909],
            'C': [0.8520, 0.8822, 0.6806]
        }
    }
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    x = np.arange(len(metrics))
    width = 0.25
    
    for idx, ds in enumerate(datasets):
        ax = axes[idx]
        vals = data[ds]
        
        ax.bar(x - width, vals['A'], width, label='Model A (Naive)', color=COLOR_A, edgecolor='black', linewidth=0.5)
        ax.bar(x, vals['B'], width, label='Model B (Graph-Only)', color=COLOR_B, edgecolor='black', linewidth=0.5)
        ax.bar(x + width, vals['C'], width, label='Model C (CSCM)', color=COLOR_C, edgecolor='black', linewidth=0.5)
        
        ax.set_ylabel('Score')
        ax.set_title(f'{ds} Absolute Performance (Avg 3 Seeds)')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.set_ylim(0.5, 1.0)
        
        if idx == 0:
            ax.legend(loc='lower right')
            
        # Add values on top of bars
        for i, metric_idx in enumerate(x):
            ax.text(metric_idx - width, vals['A'][i] + 0.005, f"{vals['A'][i]:.4f}", ha='center', va='bottom', fontsize=9, rotation=90)
            ax.text(metric_idx, vals['B'][i] + 0.005, f"{vals['B'][i]:.4f}", ha='center', va='bottom', fontsize=9, rotation=90)
            ax.text(metric_idx + width, vals['C'][i] + 0.005, f"{vals['C'][i]:.4f}", ha='center', va='bottom', fontsize=9, rotation=90)

    plt.tight_layout()
    os.makedirs('reports/figures', exist_ok=True)
    plt.savefig('reports/figures/absolute_performance_bars.png', dpi=300)
    plt.close()

def plot_effect_size_cis():
    """Generates the horizontal error bar plot for Delta distributions."""
    
    # Data manually aggregated from Phase 8 (Seed 2024 as representative, or pooled)
    # The user specifically highlighted Seed 2024 for PhysioNet as strongly significant
    # We will plot the 95% CIs for Seed 2024 for both datasets.
    
    # Format: (Point Estimate, CI_Lower, CI_Upper)
    data = {
        'PhysioNet (Seed 2024)': {
            'B - A': {
                'F1': (0.0102, 0.0018, 0.0187),
                'AUPRC': (0.0044, -0.0008, 0.0105),
                'AUROC': (0.0083, 0.0017, 0.0154)
            },
            'C - B': {
                'F1': (-0.0034, -0.0130, 0.0060),
                'AUPRC': (-0.0049, -0.0098, -0.0004),
                'AUROC': (-0.0093, -0.0184, 0.0003)
            }
        },
        'WESAD (Seed 123)': {  # Seed 123 for WESAD showed some variance
            'B - A': {
                'F1': (-0.0059, -0.0118, -0.0029),
                'AUPRC': (0.0151, -0.0033, 0.0243),
                'AUROC': (0.0318, -0.0038, 0.0428)
            },
            'C - B': {
                'F1': (0.0105, -0.0005, 0.0290),
                'AUPRC': (-0.0081, -0.0212, 0.0029),
                'AUROC': (-0.0112, -0.0342, 0.0093)
            }
        }
    }
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    
    metrics = ['AUROC', 'AUPRC', 'F1'] # Y-axis order
    y_pos = np.arange(len(metrics)) * 2
    
    for idx, (ds_name, ds_data) in enumerate(data.items()):
        ax = axes[idx]
        ax.axvline(x=0, color='black', linestyle='--', linewidth=1.5, zorder=1)
        
        for m_idx, metric in enumerate(metrics):
            # B - A
            pe_BA, ci_l_BA, ci_u_BA = ds_data['B - A'][metric]
            err_BA = [[pe_BA - ci_l_BA], [ci_u_BA - pe_BA]]
            ax.errorbar(pe_BA, y_pos[m_idx] + 0.3, xerr=err_BA, fmt='o', color=COLOR_B, 
                        ecolor=COLOR_B, elinewidth=2, capsize=5, markersize=8, zorder=3,
                        label=r'$\Delta_{B-A}$ (Graph vs Naive)' if (idx==0 and m_idx==0) else "")
            ax.text(pe_BA, y_pos[m_idx] + 0.45, f"{pe_BA:+.4f}", ha='center', va='bottom', color=COLOR_B, fontsize=10)
            
            # C - B
            pe_CB, ci_l_CB, ci_u_CB = ds_data['C - B'][metric]
            err_CB = [[pe_CB - ci_l_CB], [ci_u_CB - pe_CB]]
            ax.errorbar(pe_CB, y_pos[m_idx] - 0.3, xerr=err_CB, fmt='s', color=COLOR_C, 
                        ecolor=COLOR_C, elinewidth=2, capsize=5, markersize=8, zorder=3,
                        label=r'$\Delta_{C-B}$ (CSCM vs Graph)' if (idx==0 and m_idx==0) else "")
            ax.text(pe_CB, y_pos[m_idx] - 0.45, f"{pe_CB:+.4f}", ha='center', va='top', color=COLOR_C, fontsize=10)
            
        ax.set_yticks(y_pos)
        ax.set_yticklabels(metrics)
        ax.set_title(f'{ds_name} Effect Sizes & 95% CIs')
        ax.set_xlabel('$\Delta$ Metric')
        
        # Determine x limits dynamically with some padding
        all_vals = []
        for m in metrics:
            all_vals.extend([ds_data['B - A'][m][1], ds_data['B - A'][m][2], ds_data['C - B'][m][1], ds_data['C - B'][m][2]])
        ax.set_xlim(min(all_vals) - 0.005, max(all_vals) + 0.005)
        
        if idx == 0:
            ax.legend(loc='lower left')
            
    plt.tight_layout()
    plt.savefig('reports/figures/effect_size_cis.png', dpi=300)
    plt.close()

if __name__ == "__main__":
    print("Generating Thesis Visualizations...")
    plot_absolute_metrics()
    plot_effect_size_cis()
    print("Done. Saved to reports/figures/")
