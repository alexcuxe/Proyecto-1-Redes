# Core formulas (MVP). Conservative and documented. Easy to swap later.
from .constants import P_EXPONENT_BY_TYPE, RELIABILITY_A1, temperature_factor, lubrication_factor

def equivalent_dynamic_load(Fr_N: float, Fa_N: float, bearing_type: str) -> float:
    """MVP: P = Fr + Fa (conservative). Later: P = X*Fr + Y*Fa based on family/regime."""
    Fr = max(0.0, float(Fr_N or 0.0))
    Fa = max(0.0, float(Fa_N or 0.0))
    return Fr + Fa

def life_L10(C_N: float, P_N: float, bearing_type: str) -> float:
    """L10 [million rev]: (C/P)^p; ball bearings p=3 by default."""
    if P_N <= 0:
        return float('inf')
    p = P_EXPONENT_BY_TYPE.get(bearing_type, 3.0)
    return (C_N / P_N) ** p

def life_hours(L10_mrev: float, rpm: float) -> float:
    """L10h [hours] = (1e6 * L10) / (60 * rpm)"""
    rpm = max(1.0, float(rpm or 1.0))
    return (1e6 * L10_mrev) / (60.0 * rpm)

def apply_adjustments(L10h: float, reliability_percent: int | None, temperature_C: float | None, lubrication: str | None) -> float:
    """Lna_h = a1 * a3 * a_lub * L10h (all demo factors)."""
    a1 = RELIABILITY_A1.get(int(reliability_percent or 90), 1.0)
    a3 = temperature_factor(temperature_C or 25.0, lubrication or "grease")
    a_lub = lubrication_factor(lubrication or "grease")
    return L10h * a1 * a3 * a_lub
