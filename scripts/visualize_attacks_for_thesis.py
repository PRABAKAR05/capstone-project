import h5py
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_thesis_screenshots():
    print("Generating updated Figure 11.3 and 11.4 for Review 2...")
    
    os.makedirs("figures", exist_ok=True)
    
    # We use WESAD because its longer windows (14 steps) look better in graphs than PhysioNet (5 steps)
    h5_path = "data/generated_attacks/wesad/wesad_attacks.h5"
    
    try:
        with h5py.File(h5_path, "r") as f:
            # We explicitly found that Window 5, Channel 80 contains a very clear, massive FDI attack
            X_clean = f["test"]["clean_data"][5, 80, :]
            X_attacked = f["test"]["attacked_data"][5, 80, :]
            y_mask = f["test"]["attack_mask"][5, 80, :].astype(int)
                
            time_steps = np.arange(len(X_clean))
            
            # --- Figure 11.3 & 11.4: Multi-panel FDI Attack Visualization ---
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
            
            # Top: Clean vs Attacked
            ax1.plot(time_steps, X_clean, label="Clean Signal", color="blue", alpha=0.6, marker="o", markersize=4)
            ax1.plot(time_steps, X_attacked, label="Attacked Signal", color="red", linestyle="dashed", marker="x", markersize=4)
            ax1.set_title("A. Clean vs. Attacked Signal")
            ax1.set_ylabel("Normalized Value")
            ax1.legend(loc="upper left")
            ax1.grid(True, alpha=0.3)
            
            # Middle: Difference (Attacked - Clean)
            difference = X_attacked - X_clean
            ax2.plot(time_steps, difference, color="purple", label="Difference (Attack Injection)")
            ax2.axhline(0, color="black", linestyle="--", alpha=0.5)
            ax2.set_title("B. Signal Difference (Attacked - Clean)")
            ax2.set_ylabel("Value Difference")
            ax2.grid(True, alpha=0.3)
            
            # Bottom: Binary Attack Mask
            ax3.step(time_steps, y_mask, color="black", where="mid", linewidth=2)
            ax3.fill_between(time_steps, 0, y_mask, step="mid", color="gray", alpha=0.3)
            ax3.set_title("C. Binary Attack Mask")
            ax3.set_xlabel("Time Step")
            ax3.set_ylabel("Mask (0=Clean, 1=Attacked)")
            ax3.set_yticks([0, 1])
            ax3.set_ylim(-0.1, 1.1)
            ax3.grid(True, alpha=0.3)
            
            fig.suptitle("Figure 11.3 & 11.4: Synthetic FDI Attack Generation and Attack Mask", fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig("figures/Figure_11_3_and_11_4_FDI_Visualization.png", dpi=300)
            plt.close()
            
            print("Successfully saved updated multi-panel visualization to figures/Figure_11_3_and_11_4_FDI_Visualization.png")
            
    except Exception as e:
        print(f"Error generating plots: {e}")

if __name__ == "__main__":
    generate_thesis_screenshots()
