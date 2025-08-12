# minmax/statistics.py

import numpy as np
from scipy.stats import median_abs_deviation, boxcox
from scipy.special import inv_boxcox
import math
from app.minmax.min_max_method import MinMaxMethod

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

def values_iqr(values, threshold):
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    val_min = max(q1 - threshold * iqr, 0)
    val_max = q3 + threshold * iqr
    return val_max, val_min

def values_boxcox(values, threshold):
    values = np.asarray(values, dtype=float)

    # Basic sanity: finite & strictly positive
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        return np.nan, np.nan, "BOXCOX failed (nonpositive or nonfinite values)"

    try:
        transformed, lmbda = boxcox(values)
    except Exception as e:
        return np.nan, np.nan, f"BOXCOX failed ({type(e).__name__})"

    mean = float(np.mean(transformed))
    std = float(np.std(transformed))
    if not np.isfinite(std) or std == 0.0:
        return np.nan, np.nan, "BOXCOX failed (zero/NaN std)"

    upper = mean + threshold * std
    lower = mean - threshold * std

    # Respect inverse domain: λ*y + 1 > 0
    eps = 1e-9
    if lmbda > 0:
        lower_safe = max(lower, -1.0 / lmbda + eps)  # push lower up if needed
        upper_safe = upper
    elif lmbda < 0:
        upper_safe = min(upper, -1.0 / lmbda - eps)  # pull upper down if needed
        lower_safe = lower
    else:
        # λ == 0 uses log transform; no domain boundary on y
        upper_safe, lower_safe = upper, lower

    try:
        val_max = float(inv_boxcox(upper_safe, lmbda))
        val_min = float(inv_boxcox(lower_safe, lmbda))
    except Exception as e:
        return np.nan, np.nan, f"BOXCOX failed (inverse error: {type(e).__name__})"

    # sanity fallback
    if (not math.isfinite(val_min) or not math.isfinite(val_max)
        or val_max <= 0 or val_min <= 0 or val_max == val_min):
        return np.nan, np.nan, "BOXCOX failed (invalid bounds)"

    if sum(v > val_max for v in values) > (len(values) / 2):
        return np.nan, np.nan, "BOXCOX rejected (too many above max)"
    if sum(v < val_min for v in values) > (len(values) / 2):
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

def _coerce_method(method):
    if isinstance(method, MinMaxMethod):
        return method
    s = str(method).upper()
    # try by name
    try:
        return MinMaxMethod[s]
    except KeyError:
        # try by value (your enum values == names anyway)
        for m in MinMaxMethod:
            if m.value == s:
                return m
        raise ValueError(f"Unknown method: {method}")

def compute_statistical_bounds(values, method, threshold):
    if not values or len(set(values)) == 1 or check_no_variance(values):
        val_max, val_min = past_values_max_bounds(values, 1.5)
        return val_min, val_max, "PREV_MAX - No variance"

    method = _coerce_method(method)

    method_map = {
        MinMaxMethod.PREV_MAX: past_values_max_bounds,
        MinMaxMethod.ZSCORE: values_z_score,
        MinMaxMethod.MAD: values_mad,
        MinMaxMethod.IQR: values_iqr,
        MinMaxMethod.BOXCOX: values_boxcox
    }

    func = method_map[method]
    res  = func(values, threshold)

    # Normalize results
    if isinstance(res, tuple) and len(res) == 3:
        val_min, val_max, comment = res
    else:
        val_min, val_max = res
        comment = method.value  # or MinMaxMethod.label_map()[method.value]

    return val_min, val_max, comment


