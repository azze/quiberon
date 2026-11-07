import math
from simulation.battle import Battle
from simulation.regiment import Regiment, INFANTRY, CAVALRY, ARTILLERY
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind

ARMY_NAMES = {0: 'Continental Expedition', 1: 'Albion Restoration'}


def create(seed=1, spectator=False):
    units = []
    for army in range(2):
        x, facing = (270, 0.) if army == 0 else (730, math.pi)
        for i in range(4):
            units.append(Regiment(army * 6 + i, f'{"Continental" if army == 0 else "Albion"} Foot {i + 1}', army,
                                  Vec(x - (25 if i == 3 and army == 0 else -25 if i == 3 else 0), 170 + i * 85), facing,
                                  order=Order(OrderKind.ADVANCE, Vec(500, 170 + i * 85))))
        units.append(Regiment(army * 6 + 4, f'{"Republican" if army == 0 else "Royal"} Horse', army, Vec(x - 40 if army == 0 else x + 40, 75 if army == 0 else 525), facing, CAVALRY,
                              order=Order(OrderKind.ATTACK, target_id=(1-army)*6)))
        units.append(Regiment(army * 6 + 5, f'{"Continental" if army == 0 else "Albion"} Battery', army,
                              Vec(x - 90 if army == 0 else x + 90, 120), facing, ARTILLERY))
    if not spectator:
        for unit in units:
            if unit.army==0:unit.order=Order(OrderKind.HOLD)
    return Battle(units, seed, ai_armies={0, 1} if spectator else {1})
