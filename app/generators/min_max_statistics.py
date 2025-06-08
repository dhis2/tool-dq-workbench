# minmax/statistics.py

import numpy as np
from scipy.stats import median_abs_deviation, boxcox
from scipy.special import inv_boxcox
import math

def check_no_variance(values):
    if not values:
        return True
    variance = np.var(values)
    median = np.median(values)
    return (100 * variance / median) < 2 if median else True

def past_values_max_bounds(values, threshold):
    max_val = max(values) if values else 0
    val_max = max(max_val * threshold, 10)
    val_min = max(max_val * (1 - threshold), 0)
    return val_max, val_min

def values_z_score(values, threshold):
    mean = np.mean(values)
    std = np.std(values)
    val_max = mean + threshold * std
    val_min = max(mean - threshold * std, 0)
    return val_max, val_min

def values_mad(values, threshold):
    median = np.median(values)
    mad = median_abs_deviation(values)
    val_max = median + threshold * mad
    val_min = max(median - threshold * mad, 0)
    return val_max, val_min

def values_boxcox(values, threshold):
    try:
        transformed, lmbda = boxcox(values)
    except (ValueError, TypeError):
        return np.nan, np.nan, "BOXCOX failed"

    mean = np.mean(transformed)
    std = np.std(transformed)

    upper = mean + threshold * std
    lower = mean - threshold * std

    val_max = inv_boxcox(upper, lmbda)
    val_min = inv_boxcox(lower, lmbda)

    # sanity fallback
    if not math.isfinite(val_min) or val_max == val_min:
        return np.nan, np.nan, "BOXCOX failed (invalid bounds)"

    if len([v for v in values if v > val_max]) > (len(values) / 2):
        return np.nan, np.nan, "BOXCOX rejected (too many above max)"
    if len([v for v in values if v < val_min]) > (len(values) / 2):
        return np.nan, np.nan, "BOXCOX rejected (too many below min)"

    return val_max, val_min, f"BOXCOX (λ={lmbda:.3f})"


# grouping.py

def select_method_for_median(groups, median_val):
    """
    Given a list of groups and a median, return the method and threshold
    for the first group whose limitMedian exceeds the median.
    """
    if not groups:
        raise ValueError("No groups defined for method selection.")

    sorted_groups = sorted(groups, key=lambda g: g["limitMedian"])
    for group in sorted_groups:
        if median_val < group["limitMedian"]:
            return group["method"], group["threshold"]

    raise ValueError(f"No method group found for median: {median_val}")


def compute_statistical_bounds(values, method, threshold):
    if not values or len(set(values)) == 1 or check_no_variance(values):
        val_max, val_min = past_values_max_bounds(values, 1.5)
        return val_min, val_max, "PREV_MAX - No variance"

    method_map = {
        "PREV_MAX": past_values_max_bounds,
        "ZSCORE": values_z_score,
        "MAD": values_mad,
        "BOXCOX": values_boxcox
    }

    func = method_map.get(method)
    if not func:
        raise ValueError(f"Unknown method: {method}")

    result = func(values, threshold)

    if method == "BOXCOX":
        val_max, val_min, comment = result
    else:
        val_max, val_min = result
        comment = method

    return val_min, val_max, comment

