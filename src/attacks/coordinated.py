import numpy as np
from .base import BaseAttack
from .additive import AdditiveShiftAttack
from .multiplicative import MultiplicativeBiasAttack
from .drift import TemporalDriftAttack


class CoordinatedAttack(BaseAttack):
    """
    Coordinated multi-channel FDI attack.

    Supports two policies (set via `policy` parameter in generate()):

    1. opposite_direction (default)
       - Channel 0: base_direction (+1 or -1, randomly chosen)
       - Channel 1: opposite direction
       - Additional channels: random direction
       - Intended for channels without physiological floor constraints.

    2. magnitude_asymmetry
       - Both channels shift in the SAME configured direction.
       - Channel 0 is shifted by channel_0_scale * severity * sigma.
       - Channel 1 is shifted by channel_1_scale * severity * sigma.
       - The asymmetry (large vs tiny shift) breaks the expected tight
         systemic correlation while keeping both channels above their
         physiological floor (e.g. EDA >= 0).
       - Parameters: direction, channel_0_scale, channel_1_scale
         read from policy_params dict.

    Both policies:
    - Use the same configurable severity system (scale * sigma).
    - Are deterministic given the same rng seed.
    - Apply to the exact configured attack interval.
    - Respect the NaN policy enforced by the generator.
    """

    def __init__(self):
        self.strategies = [
            AdditiveShiftAttack(),
            MultiplicativeBiasAttack(),
            TemporalDriftAttack(),
        ]

    def generate(
        self,
        clean_data,
        clean_mask,
        channel_indices,
        start_idx,
        end_idx,
        severity_params,
        rng,
        direction=None,
        policy: str = "opposite_direction",
        policy_params: dict | None = None,
    ):
        """
        Args:
            policy: "opposite_direction" (default) or "magnitude_asymmetry".
            policy_params: dict of parameters for the chosen policy.
              For magnitude_asymmetry:
                direction        ("positive" | "negative")
                channel_0_scale  float multiplier on severity for channel 0
                channel_1_scale  float multiplier on severity for channel 1
        """
        attacked_data = clean_data.copy()
        attack_mask   = np.zeros_like(clean_mask, dtype=bool)
        meta          = {"coordinated": {}, "policy": policy}

        policy_params = policy_params or {}

        # ── Pick a base strategy (same type applied to all channels) ──
        strategy = rng.choice(self.strategies)
        meta["coordinated_strategy"] = strategy.__class__.__name__

        if policy == "magnitude_asymmetry":
            directions, scale_overrides = self._magnitude_asymmetry_plan(
                channel_indices, policy_params, rng
            )
        else:
            directions    = self._opposite_direction_plan(channel_indices, rng)
            scale_overrides = {ci: 1.0 for ci in channel_indices}

        for i, ci in enumerate(channel_indices):
            # Build per-channel severity params with scale override applied
            override   = scale_overrides.get(ci, 1.0)
            ch_sev     = {
                ci: {
                    "std":   severity_params[ci]["std"],
                    "scale": severity_params[ci]["scale"] * override,
                }
            }

            tmp_data, tmp_mask, ch_meta = strategy.generate(
                attacked_data, clean_mask, [ci],
                start_idx, end_idx, ch_sev, rng,
                direction=directions[i],
            )
            attacked_data  = tmp_data
            attack_mask   |= tmp_mask
            meta["coordinated"][ci] = {
                "direction":     directions[i],
                "scale_override": override,
                "meta":          ch_meta,
            }

        return attacked_data, attack_mask, meta

    # ── Direction planners ─────────────────────────────────────────────

    def _opposite_direction_plan(self, channel_indices, rng):
        directions = []
        if len(channel_indices) >= 2:
            base_dir = rng.choice([-1.0, 1.0])
            directions.append("positive" if base_dir > 0 else "negative")
            directions.append("negative" if base_dir > 0 else "positive")
            for _ in range(2, len(channel_indices)):
                d = rng.choice([-1.0, 1.0])
                directions.append("positive" if d > 0 else "negative")
        else:
            for _ in channel_indices:
                d = rng.choice([-1.0, 1.0])
                directions.append("positive" if d > 0 else "negative")
        return directions

    def _magnitude_asymmetry_plan(self, channel_indices, policy_params, rng):
        """
        Both channels go in the same direction.
        Channel 0 gets a large perturbation; channel 1 gets a tiny one.
        The difference in magnitude breaks the tight systemic correlation
        without pushing either channel negative.
        """
        direction      = policy_params.get("direction", "positive")
        ch0_scale      = float(policy_params.get("channel_0_scale", 1.0))
        ch1_scale      = float(policy_params.get("channel_1_scale", 0.05))

        directions     = [direction] * len(channel_indices)
        scale_overrides = {}

        for k, ci in enumerate(channel_indices):
            if k == 0:
                scale_overrides[ci] = ch0_scale
            elif k == 1:
                scale_overrides[ci] = ch1_scale
            else:
                # Additional channels: same direction, medium scale
                scale_overrides[ci] = (ch0_scale + ch1_scale) / 2.0

        return directions, scale_overrides
