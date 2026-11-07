"""Repeatable cavalry engagements for interactive and headless experiments."""
import math
from dataclasses import replace
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind as O
from simulation.regiment import Regiment, MoraleState as S
from simulation.terrain import TerrainMap, Forest

MATCHUPS=('standard-routing','standard-wavering','steady-front','steady-flank',
          'uhlans-routing','forest-front','open-front','double-pursuit')


def create(name,seed=1,swapped=False):
    if name not in MATCHUPS: raise ValueError(f'Unknown cavalry matchup: {name}')
    cavalry='commonwealth_uhlans' if name in ('uhlans-routing','double-pursuit') else 'cavalry'
    count=2 if name=='double-pursuit' else 1
    target=Regiment(count,'Infantry',1,Vec(350,300),math.pi)
    if name.endswith('routing') or name=='double-pursuit':
        target.state=S.ROUTING; target.morale=10; target.facing=0
    elif name=='standard-wavering':
        target.state=S.WAVERING; target.morale=35; target.cohesion=55
    start=Vec(350,150) if name=='steady-flank' else Vec(200,300)
    horses=[Regiment(i,f'Cavalry {i+1}',0,start,math.pi/2 if name=='steady-flank' else 0,
                     archetype_id=cavalry,order=Order(O.ATTACK,target_id=target.id)) for i in range(count)]
    units=[*horses,target,Regiment(count+1,'Red reserve',1,Vec(900,100)),
           Regiment(count+2,'Blue reserve',0,Vec(100,100))]
    terrain=TerrainMap(forests=(Forest(350,300,240,140,.9),)) if name=='forest-front' else TerrainMap()
    if swapped:
        units=[replace(u,army=1-u.army,pos=Vec(1000-u.pos.x,600-u.pos.y),facing=u.facing+math.pi) for u in units]
        terrain=replace(terrain,forests=tuple(replace(f,x=1000-f.x,y=600-f.y) for f in terrain.forests),
                        hills=tuple(replace(h,x=1000-h.x,y=600-h.y) for h in terrain.hills))
    return Battle(units,seed=seed,terrain=terrain)

