"""Four independent demonstrations; existing controls can override every order."""
import math
from simulation.battle import Battle
from simulation.regiment import Regiment
from simulation.geometry import Vec
from simulation.formations import Formation
from simulation.orders import Order, OrderKind


def create(seed=1, **kwargs):
    units = []
    def add(name, position, goal=None, facing=0., formation=Formation.LINE):
        unit = Regiment(len(units), name, 0, Vec(*position), facing, formation=formation)
        if goal: unit.order = Order(OrderKind.MOVE, Vec(*goal))
        units.append(unit)
    add('Crossing line east', (90,100), (390,100))
    add('Crossing line west', (390,100), (90,100), math.pi)
    add('Column east', (90,235), (390,235), formation=Formation.COLUMN)
    add('Column west', (390,235), (90,235), math.pi, Formation.COLUMN)
    add('Short detour', (560,100), (930,100))
    add('Stationary screen', (730,100))
    add('Congested passage', (560,410), (930,410))
    for x in (680,710,740,770):
        add(f'Crowded screen {x}', (x,410))
    # Adjacent screens block detour candidates, forcing the soft fallback.
    add('Crowd upper', (720,330))
    add('Crowd lower', (720,490))
    add('Congested follower', (490,410), (920,410), formation=Formation.COLUMN)
    add('Congested return', (940,410), (520,410), math.pi)
    battle = Battle(units, seed, sandbox=True)
    battle.log('demo', 'Top left: crossing lines; middle left: columns; top right: detour; bottom right: congestion. F3 shows penalties.')
    return battle
