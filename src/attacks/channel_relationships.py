"""
src/attacks/channel_relationships.py

Documents relationships for coordinated attacks, including the attack policy
and any per-relationship parameters read from configs/attacks.yaml.

Each relationship dict contains:
  channels        - list of channel names to attack together
  rationale       - scientific rationale (not a model performance claim)
  policy          - "opposite_direction" | "magnitude_asymmetry"
  policy_params   - dict of policy-specific parameters (may be empty)
"""


def get_physionet_relationships():
    return {
        "Sys_Dia_MAP_Inconsistency": {
            "channels": ["NISysABP", "NIDiasABP"],
            "rationale": (
                "Perturb Sys and Dia in opposite directions, violating the "
                "expected relationship with the observed MAP channel without "
                "modifying MAP itself."
            ),
            "policy":        "opposite_direction",
            "policy_params": {},
        },
        "HR_Temp_Systemic": {
            "channels": ["HR", "Temp"],
            "rationale": "Perturb HR and Temp to break their natural systemic correlation.",
            "policy":        "opposite_direction",
            "policy_params": {},
        },
    }


def get_wesad_relationships():
    return {
        "ECG_BVP_Timing": {
            "channels": ["chest_ECG", "wrist_BVP"],
            "rationale": (
                "Perturb ECG and BVP (e.g. drift) to desynchronize their "
                "expected pulse transit time relationship."
            ),
            "policy":        "opposite_direction",
            "policy_params": {},
        },
        "EDA_EDA_Systemic": {
            "channels": ["chest_EDA", "wrist_EDA"],
            "rationale": (
                "Perturb EDA at both sites to produce a cross-sensor consistency "
                "change in the expected tight systemic sympathetic response "
                "correlation, while keeping both channels within the physiological "
                "positivity constraint [0, 50]."
            ),
            # magnitude_asymmetry policy:
            #   chest_EDA receives a large positive shift (scale * sigma)
            #   wrist_EDA  receives a tiny positive shift (0.05 * scale * sigma)
            # The large magnitude difference breaks the r~0.97 tight correlation
            # without pushing either channel negative.
            "policy": "magnitude_asymmetry",
            "policy_params": {
                "direction":       "positive",
                "channel_0_scale": 1.0,
                "channel_1_scale": 0.05,
            },
        },
        "ACC_ACC_Motion": {
            "channels": ["chest_ACC_0", "wrist_ACC_0", "chest_ECG"],
            "rationale": "Break motion correlation and its expected effect on heart rate.",
            "policy":        "opposite_direction",
            "policy_params": {},
        },
    }
