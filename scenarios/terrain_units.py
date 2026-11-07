"""Focused bayonet and woodland demonstrations using ordinary battle controls."""
import math
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.regiment import Regiment,MoraleState
from simulation.orders import Order,OrderKind as O
from simulation.terrain import TerrainMap,Forest


def create(seed=17,mode='woodland'):
    if mode=='bayonets':
        units=[Regiment(0,'Bayonet line',0,Vec(250,200),order=Order(O.CHARGE,target_id=2)),
               Regiment(1,'Royal assault',0,Vec(250,400),archetype_id='royal_grenadiers',order=Order(O.CHARGE,target_id=3)),
               Regiment(2,'Steady defenders',1,Vec(330,200),math.pi),
               Regiment(3,'Wavering defenders',1,Vec(330,400),math.pi,morale=35,state=MoraleState.WAVERING,cohesion=50)]
        return Battle(units,seed=seed)
    wood=Regiment(0,'Woodland harriers',0,Vec(300,300),archetype_id='haudenosaunee_skirmishers',order=Order(O.SKIRMISH,target_id=1))
    line=Regiment(1,'Conventional line',1,Vec(480,300),math.pi,order=Order(O.ADVANCE,Vec(300,300),target_id=0))
    return Battle([wood,line,Regiment(2,'Blue reserve',0,Vec(100,100)),Regiment(3,'Red reserve',1,Vec(900,100))],
                  seed=seed,terrain=TerrainMap(forests=(Forest(500,300,360,200,1),)))
