import numpy as np
from .base import BaseAttack

class AdditiveShiftAttack(BaseAttack):
    def generate(self, clean_data, clean_mask, channel_indices, start_idx, end_idx, severity_params, rng, direction=None):
        attacked_data = clean_data.copy()
        attack_mask = np.zeros_like(clean_mask, dtype=bool)
        
        meta = {"deltas": {}}
        
        for c in channel_indices:
            # Determine perturbation delta based on standard deviation
            std_dev = severity_params[c]["std"]
            scale = severity_params[c]["scale"]
            magnitude = std_dev * scale
            
            if direction is None:
                dir_sign = rng.choice([-1.0, 1.0])
            elif direction == "positive":
                dir_sign = 1.0
            elif direction == "negative":
                dir_sign = -1.0
            elif direction == "bidirectional":
                dir_sign = rng.choice([-1.0, 1.0])
                
            delta = dir_sign * magnitude
            
            # Apply only to the attack interval
            attacked_data[start_idx:end_idx, c] += delta
            
            # Mark mask where we actually changed something (i.e. delta != 0)
            if delta != 0.0:
                attack_mask[start_idx:end_idx, c] = True
                
            meta["deltas"][c] = float(delta)
            
        return attacked_data, attack_mask, meta
