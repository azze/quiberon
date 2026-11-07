"""Immutable unit baselines, shared by archetypes and live regiments."""
from dataclasses import dataclass
from enum import Enum

class UnitType(str, Enum):
    INFANTRY = "infantry"
    CAVALRY = "cavalry"
    ARTILLERY = "artillery"

@dataclass(frozen=True)
class UnitStats:
    kind: UnitType = UnitType.INFANTRY
    strength: int = 240
    speed: float = 2.8
    turn_rate: float = .65
    range: float = 155.
    reload: float = 12.
    discipline: float = 1.

INFANTRY = UnitStats()
CAVALRY = UnitStats(UnitType.CAVALRY, 100, 7.5, 1.1, 0, 5)
ARTILLERY = UnitStats(UnitType.ARTILLERY, 48, 1.8, .4, 440, 19)

