from dataclasses import dataclass

@dataclass
class Bearing:
    model: str
    type: str      # e.g., "deep_groove_ball"
    C_N: float     # Dynamic load rating [N]
    d_mm: float | None = None
    D_mm: float | None = None
    B_mm: float | None = None
