# bearing_utils.py
# basic mechanical formulas for bearing life (demo)

import math

def adjusted_P(Fr, Fa):
    # Simple equivalent dynamic load (demo)
    # NOTE: You should replace with ISO/Shigley factors later
    Fr = max(float(Fr or 0), 0.0)
    Fa = max(float(Fa or 0), 0.0)
    return Fr + 1.5 * Fa

def calc_l10h(C, P, rpm):
    # L10h = (C/P)^3 * 1e6 / (60*rpm)
    # Guard clauses for robustness
    rpm = max(float(rpm or 1), 1.0)
    P = max(float(P or 1e-6), 1e-6)
    C = max(float(C or 1e-6), 1e-6)
    L10 = (C / P) ** 3
    return (L10 * (1_000_000.0 / (60.0 * rpm)))

def round2(x): 
    try: 
        return round(float(x), 2)
    except: 
        return 0.0
