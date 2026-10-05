import numpy as np
from .additive import AdditiveShiftAttack
from .multiplicative import MultiplicativeBiasAttack
from .drift import TemporalDriftAttack
from .coordinated import CoordinatedAttack
from .validators import validate_plausibility


class AttackGenerator:
    """
    Orchestrates FDI attack generation over pre-processed windows.

    Mask semantics (PhysioNet-specific, verified from HDF5 inspection):
      clean_mask[t,c] == True  -> valid original OR forward-filled imputed value
      clean_mask[t,c] == False -> forward-filled imputed numeric value
      NaN in data at any position -> imputation could not fill; NEVER attacked

    Rejection categories (tracked separately per sample in metadata):
      A. nan_inherited   - NaN in clean source; NOT a failed attack;
                           those positions are excluded from perturbation.
      B. bound_violation - attack pushed a non-NaN value outside configured
                           min/max bounds.
    """

    def __init__(
        self,
        config: dict,
        dataset_name: str,
        norm_stats: dict,
        bounds: dict,
        all_channels: list[str],
    ):
        self.config       = config
        self.dataset_name = dataset_name
        self.norm_stats   = norm_stats
        self.bounds       = bounds
        self.all_channels = all_channels

        self.attacks = {
            "additive":      AdditiveShiftAttack(),
            "multiplicative": MultiplicativeBiasAttack(),
            "drift":         TemporalDriftAttack(),
            "coordinated_2": CoordinatedAttack(),
            "coordinated_3": CoordinatedAttack(),
        }

    def generate_attack(
        self,
        clean_data: np.ndarray,
        clean_mask: np.ndarray,
        attack_family: str,
        severity_level: str,
        target_channels: list[str],
        seed: int,
        policy: str = "opposite_direction",
        policy_params: dict | None = None,
    ) -> dict:
        """
        Generate one attacked window.

        Args:
            clean_data:      (T, C) float32 source window.
            clean_mask:      (T, C) bool mask from Phase 3.
            attack_family:   "clean" | "additive" | "multiplicative" |
                             "drift" | "coordinated_2" | "coordinated_3"
            severity_level:  "low" | "medium" | "high"
            target_channels: list of channel names to attack.
            seed:            integer seed for deterministic reproducibility.
            policy:          CoordinatedAttack policy ("opposite_direction" |
                             "magnitude_asymmetry"). Ignored for non-coordinated
                             families.
            policy_params:   Policy-specific parameters dict.

        Returns:
            dict with keys:
              attacked_data, attack_mask, attack_label, metadata
        """
        rng = np.random.default_rng(seed)

        # ── Clean baseline ────────────────────────────────────────────
        if attack_family == "clean":
            return {
                "attacked_data": clean_data.copy(),
                "attack_mask":   np.zeros_like(clean_mask, dtype=bool),
                "attack_label":  0,
                "metadata": {
                    "attack_family":    "clean",
                    "severity":         "none",
                    "attack_start":     0,
                    "attack_end":       0,
                    "seed":             seed,
                    "attacked_channels": [],
                    "policy":           "none",
                    "is_plausible":     True,
                    "rejection_reason": None,
                    "nan_positions":    0,
                    "boundary_deltas":  {},
                },
            }

        channel_indices = [self.all_channels.index(c) for c in target_channels]

        # ── Severity params per channel ───────────────────────────────
        scale = self.config["severity"][severity_level]["scale"]
        severity_params = {}
        for c in target_channels:
            std = (
                self.norm_stats
                    .get("statistics", {})
                    .get(c, {})
                    .get("zscore", {})
                    .get("std", 1.0)
            )
            severity_params[self.all_channels.index(c)] = {"std": std, "scale": scale}

        # ── Attack interval ───────────────────────────────────────────
        frac      = self.config["duration"]["fraction"]
        total_len = clean_data.shape[0]
        duration  = int(total_len * frac)
        start_idx = total_len - duration
        end_idx   = total_len

        # ── Count NaN positions in the attack interval ────────────────
        nan_positions = 0
        for ci in channel_indices:
            nan_positions += int(np.isnan(clean_data[start_idx:end_idx, ci]).sum())

        # ── Generate attack ───────────────────────────────────────────
        strategy = self.attacks[attack_family]

        if attack_family in ("coordinated_2", "coordinated_3"):
            attacked_data, attack_mask, meta = strategy.generate(
                clean_data, clean_mask, channel_indices,
                start_idx, end_idx, severity_params, rng,
                policy=policy,
                policy_params=policy_params or {},
            )
        else:
            attacked_data, attack_mask, meta = strategy.generate(
                clean_data, clean_mask, channel_indices,
                start_idx, end_idx, severity_params, rng,
            )

        # ── NaN policy: never modify a NaN source position ────────────
        for ci in channel_indices:
            nan_at = np.isnan(clean_data[:, ci])
            if nan_at.any():
                attacked_data[nan_at, ci] = clean_data[nan_at, ci]
                attack_mask[nan_at, ci]   = False

        # ── Plausibility: non-NaN positions only, and ONLY for targeted channels
        target_data = attacked_data[:, channel_indices]
        is_plausible, bound_reason = validate_plausibility(
            target_data, self.bounds, target_channels, valid_only=True
        )

        # ── Boundary discontinuity (one value per target channel) ─────
        boundary_deltas = {}
        if start_idx > 0:
            for ci in channel_indices:
                ch     = self.all_channels[ci]
                before = clean_data[start_idx - 1, ci]
                after  = attacked_data[start_idx, ci]
                if not (np.isnan(before) or np.isnan(after)):
                    boundary_deltas[ch] = float(abs(float(after) - float(before)))

        # ── Rejection category ────────────────────────────────────────
        rejection_reason = None
        if nan_positions > 0 and not is_plausible:
            rejection_reason = f"bound_violation+nan_inherited: {bound_reason}"
        elif not is_plausible:
            rejection_reason = f"bound_violation: {bound_reason}"
        elif nan_positions > 0:
            rejection_reason = (
                f"nan_inherited ({nan_positions} positions; "
                f"attack applied to non-NaN positions)"
            )

        return {
            "attacked_data": attacked_data,
            "attack_mask":   attack_mask,
            "attack_label":  1,
            "metadata": {
                "attack_family":     attack_family,
                "severity":          severity_level,
                "attack_start":      start_idx,
                "attack_end":        end_idx,
                "seed":             seed,
                "attacked_channels": target_channels,
                "policy":            policy,
                "strategy_meta":     meta,
                "is_plausible":      is_plausible,
                "rejection_reason":  rejection_reason,
                "nan_positions":     nan_positions,
                "boundary_deltas":   boundary_deltas,
            },
        }
