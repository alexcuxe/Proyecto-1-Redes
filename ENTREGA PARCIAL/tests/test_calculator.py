import math
from models.calculator import equivalent_dynamic_load, life_L10, life_hours, apply_adjustments

def test_equivalent_dynamic_load():
    assert equivalent_dynamic_load(1000, 500, "deep_groove_ball") == 1500

def test_life_chain():
    P = equivalent_dynamic_load(1000, 500, "deep_groove_ball")
    L10 = life_L10(20000, P, "deep_groove_ball")
    L10h = life_hours(L10, 1500)
    assert L10 > 0 and L10h > 0

def test_adjustments():
    base = 10000.0
    adj = apply_adjustments(base, 90, 25, "grease")
    assert math.isclose(adj, base, rel_tol=1e-6)
