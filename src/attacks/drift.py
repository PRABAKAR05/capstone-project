import numpy as np
from .base import BaseAttack

class TemporalDriftAttack(BaseAttack):
    def generate(self, clean_data, clean_mask, channel_indices, start_idx, end_idx, severity_params, rng, direction=None):
        attacked_data = clean_data.copy()
        attack_mask = np.zeros_like(clean_mask, dtype=bool)
        
        meta = {"max_deltas": {}}
        
        duration = end_idx - start_idx
        if duration <= 0:
            return attacked_data, attack_mask, meta
            
        # Create a smooth drift curve from 0 to 1
        drift_curve = np.linspace(0, 1, duration)
        
        for c in channel_indices:
            std_dev = severity_params[c]["std"]
            scale = severity_params[c]["scale"]
            max_magnitude = std_dev * scale
            
            if direction is None or direction == "bidirectional":
                dir_sign = rng.choice([-1.0, 1.0])
            elif direction == "positive":
                dir_sign = 1.0
            elif direction == "negative":
                dir_sign = -1.0
                
            max_delta = dir_sign * max_magnitude
            
            delta_t = drift_curve * max_delta
            
            attacked_data[start_idx:end_idx, c] += delta_t
            
            if max_delta != 0.0:
                attack_mask[start_idx:end_idx, c] = True
                
            meta["max_deltas"][c] = float(max_delta)
            
        return attacked_data, attack_mask, meta
