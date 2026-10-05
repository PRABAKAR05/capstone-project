import numpy as np
from .base import BaseAttack

class MultiplicativeBiasAttack(BaseAttack):
    def generate(self, clean_data, clean_mask, channel_indices, start_idx, end_idx, severity_params, rng, direction=None):
        attacked_data = clean_data.copy()
        attack_mask = np.zeros_like(clean_mask, dtype=bool)
        
        meta = {"alphas": {}}
        
        for c in channel_indices:
            # We scale the multiplicative alpha based on the scale parameter
            # A scale of 1.0 might mean 10% bias, so alpha = 0.1 * scale
            scale = severity_params[c]["scale"]
            magnitude = 0.1 * scale  # 10% per scale unit
            
            if direction is None or direction == "bidirectional":
                dir_sign = rng.choice([-1.0, 1.0])
            elif direction == "positive":
                dir_sign = 1.0
            elif direction == "negative":
                dir_sign = -1.0
                
            alpha = dir_sign * magnitude
            
            attacked_data[start_idx:end_idx, c] = attacked_data[start_idx:end_idx, c] * (1.0 + alpha)
            
            if alpha != 0.0:
                attack_mask[start_idx:end_idx, c] = True
                
            meta["alphas"][c] = float(alpha)
            
        return attacked_data, attack_mask, meta
