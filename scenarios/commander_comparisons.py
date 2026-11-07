"""Editable, seeded commander comparisons using ordinary battle recipes."""
from dataclasses import replace
from .battle_config import ArmyConfig,BattleConfig
from simulation.commanders import Personality as P,Specialization as S

COMMANDER_PRESETS=['Disciplined versus Reckless','Cavalry Personalities','Defensive Stand',
                   'Pathfinders in Woodland','Morale Support']


def create(name,seed=17):
    if name not in COMMANDER_PRESETS:raise ValueError('Unknown commander comparison.')
    army=ArmyConfig(4,0,0);red=army;terrain='Open Field'
    if name=='Cavalry Personalities':army=red=ArmyConfig(0,3,0)
    if name=='Defensive Stand':red=ArmyConfig(6,0,0)
    if name=='Pathfinders in Woodland':terrain='Wooded Battlefield'
    config=BattleConfig(name=name,seed=seed,blue=army,red=red,symmetric=army==red,
                        ai_armies=(0,1),terrain_preset=terrain).prepared()
    placements=[]
    for p in config.placements:
        personality=P.METHODICAL;specialty=S.PATHFINDER
        if name=='Disciplined versus Reckless':personality=P.METHODICAL if p.army==0 else P.AGGRESSIVE
        elif name=='Cavalry Personalities':
            index=sum(q.army==p.army and q.id<p.id for q in config.placements)
            personality=(P.AGGRESSIVE,P.CAUTIOUS,P.OPPORTUNISTIC)[index]
        elif name=='Defensive Stand':
            personality=P.STALWART if p.army==0 else P.AGGRESSIVE
            if p.army==0:specialty=S.DEFENSIVE
        elif name=='Pathfinders in Woodland':specialty=S.PATHFINDER if p.army==0 else S.FIREBRAND
        elif name=='Morale Support' and p.id==config.placements[0].id:specialty=S.INSPIRER
        placements.append(replace(p,commander=replace(p.commander,personality=personality,specialization=specialty)))
    return replace(config,placements=tuple(placements))
