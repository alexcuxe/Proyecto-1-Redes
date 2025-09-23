# Factors are placeholders for MVP. Replace with real tables for NTN/SKF later.

P_EXPONENT_BY_TYPE = {
    "deep_groove_ball": 3.0,
    "roller": 10.0 / 3.0
}

RELIABILITY_A1 = {
    90: 1.00,
    95: 0.62,  # demo values; replace with standard tables
    99: 0.21,
}

def temperature_factor(temperature_C: float, lubrication: str) -> float:
    """Simple heuristic: <=70C:1.0, 70..90C:0.9, >90C:0.8"""
    if temperature_C <= 70:
        return 1.0
    if temperature_C <= 90:
        return 0.9
    return 0.8

def lubrication_factor(lubrication: str) -> float:
    """Demo: grease/oil -> 1.0"""
    return 1.0
