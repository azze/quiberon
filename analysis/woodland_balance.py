"""Seeded, side-swapped woodland and treeline comparisons without commanders."""
import argparse
import json
import math
from pathlib import Path
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.regiment import Regiment
from simulation.orders import Order,OrderKind as O
from simulation.terrain import TerrainMap,Forest

MODES=('treeline','woodland-ranged','woodland-melee','open-ranged','open-melee','woodland-skirmish')


def create(mode,seed=17,swapped=False,density=1.):
    if mode not in MODES:raise ValueError('Unknown woodland comparison.')
    melee=mode.endswith('melee')
    distance=20.5 if melee else 125 if mode in ('treeline','open-ranged') else 40
    left=Vec(400,300);right=Vec(400+distance,300)
    key='infantry' if mode=='treeline' else 'haudenosaunee_skirmishers'
    terrain=TerrainMap()
    if mode=='treeline':terrain=TerrainMap(forests=(Forest(300,300,120,180,density),))
    elif mode.startswith('woodland'):terrain=TerrainMap(forests=(Forest(500,300,350,250,density),))
    if swapped:
        left,right=Vec(1000-left.x,left.y),Vec(1000-right.x,right.y)
        terrain=TerrainMap(forests=tuple(Forest(1000-f.x,f.y,f.radius_x,f.radius_y,f.density) for f in terrain.forests))
    specialist=Regiment(1 if swapped else 0,'treeline defender' if mode=='treeline' else 'woodland specialist',int(swapped),left,
                        math.pi if swapped else 0,archetype_id=key)
    line=Regiment(0 if swapped else 1,'standard infantry',int(not swapped),right,0 if swapped else math.pi)
    if mode=='woodland-skirmish':
        specialist.order=Order(O.SKIRMISH,target_id=line.id)
        line.order=Order(O.ADVANCE,specialist.pos,target_id=specialist.id)
    battle=Battle([specialist,line],seed=seed,terrain=terrain,generate_commanders=False)
    return battle,specialist,line


def run(mode,seed=17,swapped=False,duration=450.,density=1.):
    battle,specialist,line=create(mode,seed,swapped,density)
    for _ in range(math.ceil(duration/battle.rules.dt)):
        battle.step()
        if battle.result:break
    winner='specialist' if battle.result==f'army_{specialist.army}' else 'line' if battle.result==f'army_{line.army}' else battle.result or 'timeout'
    return dict(mode=mode,seed=seed,swapped=swapped,density=density,winner=winner,duration=battle.time,
                specialist_remaining=specialist.strength,line_remaining=line.strength,
                specialist_morale=specialist.morale,line_morale=line.morale,
                specialist_volleys=specialist.analysis['volleys'],line_volleys=line.analysis['volleys'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=MODES,action='append');p.add_argument('--runs',type=int,default=10)
    p.add_argument('--seed',type=int,default=17);p.add_argument('--duration',type=float,default=450.)
    p.add_argument('--density',type=float,default=1.)
    p.add_argument('--output',type=Path,default=Path('benchmark-results/woodland-balance.json'))
    a=p.parse_args()
    if a.runs<1 or not math.isfinite(a.duration) or a.duration<=0:p.error('Positive runs and finite duration required.')
    if not math.isfinite(a.density) or not 0<=a.density<=1:p.error('Density must be between zero and one.')
    rows=[]
    for mode in a.mode or MODES:
        for seed in range(a.seed,a.seed+a.runs):
            for swapped in (False,True):rows.append(run(mode,seed,swapped,a.duration,a.density))
        group=[r for r in rows if r['mode']==mode]
        print(mode,{key:sum(r['winner']==key for r in group) for key in ('specialist','line','draw','timeout')},flush=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(battles=rows),indent=2)+'\n')


if __name__=='__main__':main()
