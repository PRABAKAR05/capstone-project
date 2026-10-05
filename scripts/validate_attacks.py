import h5py
import numpy as np

def validate_samples(h5_path: str):
    print(f"Validating {h5_path}")
    with h5py.File(h5_path, "r") as f:
        grp = f["samples"]
        num_samples = grp["clean_data"].shape[0]
        
        for i in range(num_samples):
            clean = grp["clean_data"][i]
            att = grp["attacked_data"][i]
            c_mask = grp["clean_mask"][i]
            a_mask = grp["attack_mask"][i]
            
            # 1. Shapes
            assert clean.shape == att.shape == c_mask.shape == a_mask.shape
            
            # 2. No NaN/Inf where observed/imputed (clean_mask == True)
            # Actually, our clean_mask means observed. But imputed values are also non-NaN.
            # So we should check where clean_data is not NaN
            valid_idx = ~np.isnan(clean)
            assert not np.isnan(att[valid_idx]).any()
            assert not np.isinf(att[valid_idx]).any()
            
            # 4. Attack Mask semantics (Rule 21)
            # Find elements that changed
            diff = np.abs(clean - att) > 1e-6
            
            # If changed, attack_mask must be True
            if np.any(diff):
                assert np.all(a_mask[diff] == True)
            
            # If not changed, attack_mask should be False (unless exact 0 delta was rolled, but we mark only if delta != 0)
            # Actually, there can be edge cases where a drift attack has 0.0 at t=0, so delta is 0, but it is part of the attack interval.
            # But our rule says "mark mask where we actually changed something".
            
            # Ensure no modification outside attack mask
            # i.e., where attack_mask is False, clean must equal att
            np.testing.assert_array_almost_equal(clean[~a_mask], att[~a_mask])

    print("All validations passed.")

if __name__ == "__main__":
    validate_samples("data/generated_attacks/physionet/samples.h5")
    validate_samples("data/generated_attacks/wesad/samples.h5")
