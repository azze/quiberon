"""Scripted overlapping starts are intentionally separate from validated recipes."""
from simulation.battle import Battle
from simulation.regiment import Regiment, MoraleState
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind as O


def create(seed=1,mode='crowded-line',**kwargs):
    if mode=='pursuit':
        units=[Regiment(i,f'Uhlan pursuer {i+1}',0,Vec(200,300),archetype_id='commonwealth_uhlans',order=Order(O.ATTACK,target_id=2)) for i in range(2)]
        units+=[Regiment(2,'Fleeing cavalry',1,Vec(270,300),archetype_id='cavalry',state=MoraleState.ROUTING,morale=10),
                Regiment(3,'Enemy reserve',1,Vec(900,100),order=Order(O.RESERVE))]
    elif mode=='reinforcement':
        units=[Regiment(0,'Left front',0,Vec(430,260)),Regiment(1,'Right front',0,Vec(430,340)),
               Regiment(2,'Reinforcement',0,Vec(250,300),order=Order(O.MOVE,Vec(430,300))),
               Regiment(3,'Enemy line',1,Vec(550,300),3.141592653589793)]
    else:
        units=[Regiment(i,f'Competing line {i+1}',0,Vec(400,300)) for i in range(3)]
        units.append(Regiment(3,'Enemy line',1,Vec(530,300),3.141592653589793))
    battle=Battle(units,seed)
    battle.log('demo',f'{mode}: F3 shows settling, overlap and last volley frontage; ordinary controls remain available.')
    return battle
