"""Numerical helpers for graph formatting and polynomial best-fit computation."""

import numpy as np


def format_graph_value(value):
    value = float(value)
    if abs(value) < 1e-15:
        return "0"
    return f"{value:.6g}"


def build_fit_equation(coeffs):
    degree = len(coeffs) - 1
    terms = []
    for i, coeff in enumerate(coeffs):
        power = degree - i
        if abs(coeff) < 1e-10:
            continue
        coeff_txt = f"{abs(coeff):.4g}"
        if power == 0:
            term = coeff_txt
        elif power == 1:
            term = f"{coeff_txt}x"
        else:
            term = f"{coeff_txt}x^{power}"
        if not terms:
            terms.append(f"-{term}" if coeff < 0 else term)
        else:
            sign = " - " if coeff < 0 else " + "
            terms.append(f"{sign}{term}")
    eq = "".join(terms) if terms else "0"
    return f"y = {eq}"


def compute_best_fit(mean, valid, requested_degree):
    mean = np.asarray(mean, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    x_valid = np.where(valid)[0].astype(np.float64)
    y_valid = mean[valid].astype(np.float64)
    if x_valid.size < 2:
        return None

    requested_degree = int(requested_degree)
    degree = max(1, min(6, requested_degree))
    degree = min(degree, int(x_valid.size - 1))

    coeffs = np.polyfit(x_valid, y_valid, degree)
    poly = np.poly1d(coeffs)
    x_full = np.arange(mean.size, dtype=np.float64)
    y_fit_full = poly(x_full)
    y_pred = poly(x_valid)

    ss_res = float(np.sum((y_valid - y_pred) ** 2))
    ss_tot = float(np.sum((y_valid - np.mean(y_valid)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
    equation = f"Best fit (degree {degree}): {build_fit_equation(coeffs)}   R^2={r2:.4f}"
    return {
        "degree": degree,
        "equation": equation,
        "y_fit": y_fit_full,
    }
