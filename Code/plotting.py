"""Plot and axis helper utilities used by GUI graph rendering/export.

Keeps graph scaling and bounds logic separate from UI code.
"""

import numpy as np


def resolve_axis_limits(
    x_values,
    y_values,
    x_user_min=None,
    x_user_max=None,
    y_user_min=None,
    y_user_max=None,
    y_pad=1.0,
):
    x_values = np.asarray(x_values, dtype=np.float64)
    y_values = np.asarray(y_values, dtype=np.float64)
    x_valid = x_values[np.isfinite(x_values)]
    y_valid = y_values[np.isfinite(y_values)]
    if x_valid.size == 0 or y_valid.size == 0:
        return None

    x_auto_min = float(np.min(x_valid))
    x_auto_max = float(np.max(x_valid))
    y_auto_min = float(np.min(y_valid))
    y_auto_max = float(np.max(y_valid))

    if x_auto_max <= x_auto_min:
        x_auto_max = x_auto_min + 1.0
    if y_auto_max <= y_auto_min:
        y_auto_min -= float(y_pad)
        y_auto_max += float(y_pad)

    x_min = x_user_min if x_user_min is not None else x_auto_min
    x_max = x_user_max if x_user_max is not None else x_auto_max
    y_min = y_user_min if y_user_min is not None else y_auto_min
    y_max = y_user_max if y_user_max is not None else y_auto_max

    if x_max <= x_min:
        x_min, x_max = x_auto_min, x_auto_max
    if y_max <= y_min:
        y_min, y_max = y_auto_min, y_auto_max
    return x_min, x_max, y_min, y_max
