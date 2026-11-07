from dataclasses import dataclass
from enum import Enum
from .geometry import Vec

class OrderKind(str, Enum):
    HOLD = 'hold'
    MOVE = 'move'
    ADVANCE = 'advance'
    ATTACK = 'attack'
    CHARGE = 'charge'
    DEFEND = 'defend'
    RESERVE = 'reserve'
    WITHDRAW = 'withdraw'
    SKIRMISH = 'skirmish'

@dataclass(frozen=True)
class Order:
    kind: OrderKind = OrderKind.HOLD
    destination: Vec | None = None
    target_id: int | None = None
    facing: float | None = None  # Optional arrival heading in radians for move/advance.

@dataclass(frozen=True)
class Command:
    regiment_id: int
    order: Order | None = None
    formation: 'Formation | None' = None

from .formations import Formation
