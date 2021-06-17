"""Tests for the grid specification."""
import pytest
from ssim import grid


@pytest.fixture
def storage_spec_dict():
    return {
        "name": "S1",
        "bus": "632",
        "phases": 3,
        "kwrated": 100,
        "kwhrated": 1000,
        "%stored": 50,
        "controller": "cycle",
        "controller_params": {
            "p_droop": 5000,
            "q_droop": -500
        },
        "inverter_efficiency": {"x": [1, 3, 5, 5.5],
                                "y": [0.8, 0.9, 10.1, 11.3]}
    }


def test_storage_spec_efficiency_curves(storage_spec_dict):
    spec = grid.StorageSpecification.from_dict(storage_spec_dict)
    assert spec.inverter_efficiency == ((1, 0.8), (3, 0.9),
                                        (5, 10.1), (5.5, 11.3))
    del storage_spec_dict["inverter_efficiency"]
    spec = grid.StorageSpecification.from_dict(storage_spec_dict)
    assert spec.inverter_efficiency is None
