import numpy as np


def validate_plausibility(
    data: np.ndarray,
    bounds: dict,
    channels: list[str],
    valid_only: bool = False,
) -> tuple[bool, str]:
    """
    Validates that the tensor does not contain structural problems or
    values outside configured physical boundaries.

    Args:
        data:       shape (T, C) float array of (potentially attacked) values.
        bounds:     {channel_name: {"min": val, "max": val}}
        channels:   list of channel names corresponding to data columns.
        valid_only: if True, NaN positions are EXCLUDED from bounds checks.
                    This is the correct mode for attacked PhysioNet data where
                    NaN is inherited from the clean source (not attack-generated).

    Returns:
        is_plausible (bool), reason (str)

    Rejection categories intentionally NOT conflated here:
        NaN  – structural signal of missing source; checked separately in generator.
        Inf  – unconditional failure (always checked).
        Bounds – configurable physical limits; checked only on valid (non-NaN) positions
                 when valid_only=True.
    """
    if np.isinf(data).any():
        return False, "Contains Inf values"

    for i, ch in enumerate(channels):
        if ch not in bounds:
            continue
        col = data[:, i]
        if valid_only:
            col = col[~np.isnan(col)]
        if len(col) == 0:
            continue

        min_bound = bounds[ch].get("min", -np.inf)
        max_bound = bounds[ch].get("max",  np.inf)

        if np.any(col < min_bound):
            return False, f"Channel {ch} violates min bound {min_bound}"
        if np.any(col > max_bound):
            return False, f"Channel {ch} violates max bound {max_bound}"

    return True, "Valid"
