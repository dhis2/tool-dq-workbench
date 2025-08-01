# tests/test_statistics.py

import pandas as pd
import numpy as np
import pytest
from app.minmax.min_max_statistics import (
    check_no_variance,
    past_values_max_bounds,
    values_z_score,
    values_mad,
    values_boxcox,
    compute_statistical_bounds,
select_method_for_median
)

@pytest.fixture
def simple_data():
    return  [10, 15, 20, 25, 30]

def test_check_no_variance_low():
    d = [100, 100, 100, 100]
    assert check_no_variance(d)

def test_check_no_variance_high():
    df =  [10, 20, 30]
    assert not check_no_variance(df)

def test_past_values_max_bounds(simple_data):
    val_max, val_min = past_values_max_bounds(simple_data, 1.25)
    assert val_max >= 10  # Should always be at least 10
    assert val_max > val_min
    assert isinstance(val_max, float)

def test_values_z_score(simple_data):
    val_max, val_min = values_z_score(simple_data, 1.0)
    assert val_max > val_min

def test_values_mad(simple_data):
    val_max, val_min = values_mad(simple_data, 1.0)
    assert val_max > val_min

def test_values_boxcox(simple_data):
    # All values must be > 0
    val_max, val_min = values_boxcox(simple_data, 2.0)
    assert np.isfinite(val_max)
    assert np.isfinite(val_min)

def test_values_boxcox_with_zero():
    df = pd.DataFrame({"value": [0, 5, 10]})
    val_max, val_min = values_boxcox(df, 2.0)
    assert np.isnan(val_max) and np.isnan(val_min)

def test_select_method_for_median():
    groups = [
        {"limitMedian": 10, "method": "A", "threshold": 1},
        {"limitMedian": 50, "method": "B", "threshold": 2},
    ]
    method, threshold = select_method_for_median(groups, 9)
    assert method == "A"
    method, threshold = select_method_for_median(groups, 49)
    assert method == "B"

def test_compute_statistical_bounds(simple_data):
    val_min, val_max, method = compute_statistical_bounds(simple_data, "ZSCORE", 1.0)
    assert method == "ZSCORE"
    assert val_max > val_min
