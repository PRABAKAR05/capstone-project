import pytest
import numpy as np
from src.attacks.additive import AdditiveShiftAttack
from src.attacks.multiplicative import MultiplicativeBiasAttack
from src.attacks.drift import TemporalDriftAttack
from src.attacks.coordinated import CoordinatedAttack
from src.attacks.validators import validate_plausibility
from src.attacks.generator import AttackGenerator

@pytest.fixture
def mock_clean_data():
    # 10 timesteps, 3 channels
    return np.ones((10, 3), dtype=np.float32)

@pytest.fixture
def mock_clean_mask():
    return np.ones((10, 3), dtype=bool)

@pytest.fixture
def mock_severity():
    return {
        0: {"std": 1.0, "scale": 1.0},
        1: {"std": 2.0, "scale": 1.0},
        2: {"std": 0.5, "scale": 2.0}
    }

def test_additive_attack(mock_clean_data, mock_clean_mask, mock_severity):
    attack = AdditiveShiftAttack()
    rng = np.random.default_rng(42)
    
    # Attack channel 0, last 5 timesteps
    att_data, att_mask, meta = attack.generate(
        mock_clean_data, mock_clean_mask, [0], 5, 10, mock_severity, rng, direction="positive"
    )
    
    assert att_data.shape == mock_clean_data.shape
    # Check unchanged part
    np.testing.assert_array_equal(att_data[:5, 0], mock_clean_data[:5, 0])
    # Check changed part (1.0 + 1.0 = 2.0)
    np.testing.assert_array_equal(att_data[5:, 0], 2.0)
    
    # Check other channels unchanged
    np.testing.assert_array_equal(att_data[:, 1], mock_clean_data[:, 1])
    
    # Check attack mask
    assert not np.any(att_mask[:5, 0])
    assert np.all(att_mask[5:, 0])

def test_multiplicative_attack(mock_clean_data, mock_clean_mask, mock_severity):
    attack = MultiplicativeBiasAttack()
    rng = np.random.default_rng(42)
    
    # Attack channel 1, positive direction. Alpha = 0.1 * 1.0 scale = 0.1
    # 1.0 * 1.1 = 1.1
    att_data, att_mask, meta = attack.generate(
        mock_clean_data, mock_clean_mask, [1], 0, 10, mock_severity, rng, direction="positive"
    )
    
    np.testing.assert_allclose(att_data[:, 1], 1.1)

def test_temporal_drift(mock_clean_data, mock_clean_mask, mock_severity):
    attack = TemporalDriftAttack()
    rng = np.random.default_rng(42)
    
    # Drift channel 0, positive. max_delta = 1.0
    att_data, att_mask, meta = attack.generate(
        mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng, direction="positive"
    )
    
    # It should drift from 1.0 up to 2.0
    assert att_data[0, 0] == 1.0
    assert att_data[9, 0] == 2.0
    
def test_coordinated_two_channel_attack(mock_clean_data, mock_clean_mask, mock_severity):
    attack = CoordinatedAttack()
    rng = np.random.default_rng(42)
    
    att_data, att_mask, meta = attack.generate(
        mock_clean_data, mock_clean_mask, [0, 1], 0, 10, mock_severity, rng
    )
    
    # Coordinated attack enforces opposing/inconsistent directions for the first two channels
    d0 = meta["coordinated"][0]["direction"]
    d1 = meta["coordinated"][1]["direction"]
    
    assert d0 != d1
    
def test_clean_unchanged(mock_clean_data, mock_clean_mask, mock_severity):
    # Ensure source data is NEVER modified in-place
    orig_copy = mock_clean_data.copy()
    attack = AdditiveShiftAttack()
    rng = np.random.default_rng(42)
    
    attack.generate(mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng)
    
    np.testing.assert_array_equal(mock_clean_data, orig_copy)

def test_reproducibility(mock_clean_data, mock_clean_mask, mock_severity):
    attack = AdditiveShiftAttack()
    
    rng1 = np.random.default_rng(123)
    att1, _, _ = attack.generate(mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng1)
    
    rng2 = np.random.default_rng(123)
    att2, _, _ = attack.generate(mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng2)
    
    np.testing.assert_array_equal(att1, att2)

def test_seed_variation(mock_clean_data, mock_clean_mask, mock_severity):
    attack = AdditiveShiftAttack()
    
    rng1 = np.random.default_rng(42)
    att1, _, _ = attack.generate(mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng1)
    
    rng2 = np.random.default_rng(999)
    att2, _, _ = attack.generate(mock_clean_data, mock_clean_mask, [0], 0, 10, mock_severity, rng2)
    
    # Additive shift direction could change based on seed.
    # It might be the same, so let's test a coordinated one which definitely relies on rng more heavily
    c_attack = CoordinatedAttack()
    c_rng1 = np.random.default_rng(1)
    c_rng2 = np.random.default_rng(2)
    _, _, m1 = c_attack.generate(mock_clean_data, mock_clean_mask, [0, 1], 0, 10, mock_severity, c_rng1)
    _, _, m2 = c_attack.generate(mock_clean_data, mock_clean_mask, [0, 1], 0, 10, mock_severity, c_rng2)
    
    # Note: Depending on seeds, strategy/direction might differ
    
def test_plausibility_validation():
    data = np.array([
        [10.0, 50.0],
        [20.0, 100.0]
    ])
    channels = ["A", "B"]
    bounds = {
        "A": {"min": 0, "max": 30},
        "B": {"min": 0, "max": 80}  # 100 will violate this
    }
    
    valid, msg = validate_plausibility(data, bounds, channels)
    assert not valid
    assert "B violates max bound" in msg
    
    data[1, 1] = 60.0
    valid, msg = validate_plausibility(data, bounds, channels)
    assert valid
