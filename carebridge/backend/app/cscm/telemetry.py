"""CSCM Telemetry Service & FDIA Attack Simulator.

Provides multi-channel IoMT telemetry streams drawn from preserved clinical validation sets
and simulates coordinated False Data Injection Attacks (drift, scaling) for demonstration.
"""

import sys
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import h5py
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.graph import PhysiologicalGraph
SAMPLES_PATH = PROJECT_ROOT / "data" / "generated_attacks" / "physionet" / "samples.h5"

CHANNELS = PhysiologicalGraph.PHYSIONET_CHANNELS


class TelemetryService:
    """Manages synthetic patient telemetry feeds and FDIA attack scenarios."""

    def __init__(self):
        self._samples_cache: Optional[np.ndarray] = None
        self._load_preserved_samples()

    def _load_preserved_samples(self):
        if SAMPLES_PATH.exists():
            with h5py.File(str(SAMPLES_PATH), "r") as hf:
                if "samples" in hf and "clean_data" in hf["samples"]:
                    self._samples_cache = hf["samples"]["clean_data"][:]
        if self._samples_cache is None:
            # Fallback synthetic clean sample generator
            self._samples_cache = np.zeros((10, 4, 5), dtype=np.float32)
            for i in range(10):
                self._samples_cache[i, :, 0] = np.random.uniform(70, 95, size=4)  # HR
                self._samples_cache[i, :, 1] = np.random.uniform(110, 130, size=4)  # NISysABP
                self._samples_cache[i, :, 2] = np.random.uniform(70, 85, size=4)  # NIDiasABP
                self._samples_cache[i, :, 3] = (self._samples_cache[i, :, 1] + 2 * self._samples_cache[i, :, 2]) / 3.0  # NIMAP
                self._samples_cache[i, :, 4] = np.random.uniform(36.5, 37.3, size=4)  # Temp

    def get_baseline_window_for_patient(self, patient_id: UUID) -> np.ndarray:
        """Deterministically retrieves a clean physiological telemetry window (4, 5) for a patient."""
        idx = int(patient_id.int % len(self._samples_cache))
        # Return a copy so caller modifications don't mutate cache
        window = self._samples_cache[idx].copy()

        # Handle any residual NaNs by filling with realistic defaults
        defaults = [82.0, 120.0, 78.0, 92.0, 36.8]
        for c_idx in range(len(CHANNELS)):
            mask = np.isnan(window[:, c_idx])
            window[mask, c_idx] = defaults[c_idx]

        return window

    def apply_fdia_attack(
        self,
        base_window: np.ndarray,
        attack_type: str = "coordinated_scaling",
        target_channels: Optional[List[str]] = None,
        intensity: float = 1.4,
    ) -> Tuple[np.ndarray, List[str]]:
        """Injects False Data Injection Attack perturbations onto specific sensor channels.

        Returns:
            (perturbed_window, attacked_channels)
        """
        perturbed = base_window.copy()
        T, C = perturbed.shape

        if target_channels is None:
            # Default to correlated blood pressure edge pair: NISysABP and NIMAP
            target_channels = ["NISysABP", "NIMAP"]

        valid_targets = [ch for ch in target_channels if ch in CHANNELS]
        if not valid_targets:
            valid_targets = ["NISysABP", "NIMAP"]

        if attack_type == "coordinated_scaling":
            if len(valid_targets) >= 2:
                c1 = CHANNELS.index(valid_targets[0])
                c2 = CHANNELS.index(valid_targets[1])
                # Multiplicative discordance violating MAP = (Sys + 2*Dias)/3 constraint
                perturbed[:, c1] = perturbed[:, c1] * float(intensity)
                perturbed[:, c2] = perturbed[:, c2] * max(0.65, 1.0 / float(intensity))
            else:
                for ch in valid_targets:
                    c_idx = CHANNELS.index(ch)
                    perturbed[:, c_idx] = perturbed[:, c_idx] * float(intensity)

        elif attack_type == "coordinated_drift":
            drift_step = (intensity - 1.0) * 20.0 if intensity > 1.0 else 18.0
            drift_vectors = np.linspace(5.0, 5.0 + drift_step, num=T)
            for ch in valid_targets:
                c_idx = CHANNELS.index(ch)
                perturbed[:, c_idx] = perturbed[:, c_idx] + drift_vectors

        elif attack_type == "single_channel_drift":
            ch = valid_targets[0]
            c_idx = CHANNELS.index(ch)
            drift_vectors = np.linspace(5.0, 35.0, num=T)
            perturbed[:, c_idx] = perturbed[:, c_idx] + drift_vectors

        else:
            # Fallback coordinated attack
            for ch in valid_targets:
                c_idx = CHANNELS.index(ch)
                perturbed[:, c_idx] = perturbed[:, c_idx] * float(intensity)

        return perturbed, valid_targets

    def format_telemetry_readings(
        self,
        window: np.ndarray,
        base_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Converts (T, C) matrix into formatted time series objects."""
        if base_time is None:
            base_time = datetime.now(timezone.utc) - timedelta(minutes=window.shape[0] * 30)

        readings: List[Dict[str, Any]] = []
        for t in range(window.shape[0]):
            time_pt = base_time + timedelta(minutes=t * 30)
            values = {}
            for c_idx, ch_name in enumerate(CHANNELS):
                val = float(window[t, c_idx])
                values[ch_name] = round(val, 2)
            readings.append({
                "timestamp": time_pt.isoformat(),
                "values": values,
            })
        return readings


# Global telemetry service instance
telemetry_service = TelemetryService()
