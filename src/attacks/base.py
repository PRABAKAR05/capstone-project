from abc import ABC, abstractmethod
import numpy as np

class BaseAttack(ABC):
    """
    Abstract base class for all synthetic FDI attacks.
    """
    @abstractmethod
    def generate(
        self,
        clean_data: np.ndarray,
        clean_mask: np.ndarray,
        channel_indices: list[int],
        start_idx: int,
        end_idx: int,
        severity_params: dict,
        rng: np.random.Generator
    ) -> tuple[np.ndarray, np.ndarray, dict]:
        """
        Generate an attack on the provided clean data.
        
        Args:
            clean_data: The clean window of shape (T, C). DO NOT MODIFY IN PLACE.
            clean_mask: The boolean mask indicating authentic observations.
            channel_indices: Indices of channels to attack.
            start_idx: Attack start temporal index.
            end_idx: Attack end temporal index (exclusive).
            severity_params: Dictionary of per-channel severity standard deviations.
            rng: Configured random generator for reproducible stochastics.
            
        Returns:
            attacked_data: The perturbed array (T, C).
            attack_mask: Boolean array indicating exactly which (t, c) were modified.
            metadata: Dictionary of attack parameters (direction, magnitude, etc.).
        """
        pass
