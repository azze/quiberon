"""Shared command-button layout/eligibility for drawing and input hit tests."""
from dataclasses import dataclass
import pygame
from simulation.formations import Formation as F
from simulation.orders import OrderKind as O
from simulation.regiment import UnitType as T

FORMATIONS=((F.LINE,'Line'),(F.COLUMN,'Column'),(F.SKIRMISH,'Loose'))
ORDERS=((O.HOLD,'Hold'),(O.MOVE,'Move'),(O.ADVANCE,'Advance'),(O.ATTACK,'Attack'),
        (O.CHARGE,'Charge'),(O.SKIRMISH,'Skirmish'),(O.DEFEND,'Defend'),
        (O.RESERVE,'Reserve'),(O.WITHDRAW,'Withdraw'))


@dataclass(frozen=True)
class Button:
    key: str
    label: str
    rect: pygame.Rect
    enabled: bool
    active: bool


def can_order(unit,kind):
    if unit is None or not unit.effective or unit.army!=0:return False
    if kind==O.CHARGE:return unit.stats.kind!=T.ARTILLERY
    if kind==O.SKIRMISH:return unit.stats.kind==T.INFANTRY
    return True


def buttons(width,height,battle,controls):
    unit=battle.unit(controls.selected)
    ready=unit is not None and unit.effective and unit.army==0 and battle.result is None
    rows=[]
    for i,(formation,label) in enumerate(FORMATIONS):
        enabled=ready and unit.stats.kind==T.INFANTRY and formation in unit.archetype.formations and not unit.transition_left
        rows.append(Button('formation:'+formation.value,label,pygame.Rect(96+i*92,height-144,86,26),
                           bool(enabled),bool(unit and (unit.next_formation or unit.formation)==formation)))
    start=80;gap=4;available=max(9,width-start-14-gap*(len(ORDERS)-1))
    for i,(kind,label) in enumerate(ORDERS):
        left=start+i*available//len(ORDERS)+i*gap
        right=start+(i+1)*available//len(ORDERS)+i*gap
        active=controls.pending_order==kind or (controls.pending_order is None and unit and unit.order.kind==kind)
        rows.append(Button('order:'+kind.value,label,pygame.Rect(left,height-112,right-left,26),
                           bool(ready and can_order(unit,kind)),bool(active)))
    return rows
