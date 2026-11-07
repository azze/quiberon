from dataclasses import dataclass
from enum import Enum

class Formation(str, Enum):
    LINE = 'line'
    COLUMN = 'column'
    SKIRMISH = 'skirmish'

# Frontage, depth, movement multiplier, turn multiplier, firing multiplier.
PROFILES = {Formation.LINE: (64., 12., .75, .65, 1.),
            Formation.COLUMN: (22., 34., 1., 1., .32),
            Formation.SKIRMISH: (78., 28., .94, 1.15, .52)}


@dataclass(frozen=True)
class CongestionProfile:
    speed_reduction: float
    cohesion_loss: float  # points per second at full overlap, for a moving unit

CONGESTION_PROFILES = {
    Formation.LINE: CongestionProfile(.45, 2.4),
    Formation.COLUMN: CongestionProfile(.25, .9),
    Formation.SKIRMISH: CongestionProfile(.30, 1.1),
}
