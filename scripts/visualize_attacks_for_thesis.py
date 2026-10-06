import h5py
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_thesis_screenshots():
    print("Generating Figure 11.3 and 11.4 for the thesis...")
    
    os.makedirs("figures", exist_ok=True)
    
    # 1. Load an attacked sample from the final dataset
    h5_path = "data/generated_attacks/physionet/physionet_attacks.h5"
    
    try:
        with h5py.File(h5_path, "r") as f:
            # Load first window from test set
            X_clean = f["test"]["clean_data"][0]      # shape: [C, 2, T]
            X_attacked = f["test"]["attacked_data"][0] # shape: [C, 2, T]
            y_mask = f["test"]["attack_mask"][0]       # shape: [C, T]
            
            # Select the first channel (e.g. HR)
            channel_1_clean = X_clean[0, :]
            channel_1_attacked = X_attacked[0, :]
            channel_1_mask = y_mask[0, :]
            
            time_steps = np.arange(len(channel_1_clean))
            
            # --- Figure 11.3: Clean vs Attacked ---
            plt.figure(figsize=(10, 4))
            plt.plot(time_steps, channel_1_clean, label="Clean Signal", color="blue", alpha=0.6)
            plt.plot(time_steps, channel_1_attacked, label="Attacked Signal", color="red", linestyle="dashed")
            plt.title("Figure 11.3: FDI Attack Generation")
            plt.xlabel("Time Step")
            plt.ylabel("Normalized Value")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig("figures/Figure_11_3_Attack_Generation.png")
            plt.close()
            
            # --- Figure 11.4: Attack Mask Visualization ---
            fig, ax1 = plt.subplots(figsize=(10, 4))
            
            ax1.plot(time_steps, channel_1_clean, label="Clean Signal", color="gray", alpha=0.5)
            ax1.plot(time_steps, channel_1_attacked, label="Attacked Signal", color="red")
            ax1.set_xlabel("Time Step")
            ax1.set_ylabel("Signal Value", color="red")
            ax1.tick_params(axis="y", labelcolor="red")
            
            ax2 = ax1.twinx()
            ax2.fill_between(time_steps, 0, channel_1_mask, color="black", alpha=0.2, label="Binary Attack Mask")
            ax2.set_ylabel("Mask (0=Clean, 1=Attacked)", color="black")
            ax2.tick_params(axis="y", labelcolor="black")
            
            plt.title("Figure 11.4: Attack Mask Visualization")
            fig.tight_layout()
            plt.savefig("figures/Figure_11_4_Attack_Mask.png")
            plt.close()
            
            print("Successfully saved Figure 11.3 and 11.4 to the 'figures/' folder!")
            print("You can open them directly in VS Code to see them.")
            
    except Exception as e:
        print(f"Error generating plots: {e}")

if __name__ == "__main__":
    generate_thesis_screenshots()
