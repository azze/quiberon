"""Routing disorder and directional woodland combat rather than blanket armour."""
import math
from dataclasses import replace
import pytest
from simulation import combat,morale,ai,commander_ai
from simulation.archetypes import ARCHETYPES
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec
from simulation.regiment import Regiment,MoraleState as S
from simulation.formations import Formation as F
from simulation.orders import Order,OrderKind as O
from simulation.terrain import TerrainMap,Forest,Visibility
from simulation.commanders import Commander,Personality as P,Specialization as T
from analysis.woodland_balance import create,run
from analysis.performance import fingerprint


@pytest.mark.parametrize('speed',[0.,2.5])
def test_routing_loses_cohesion_instead_of_recovering_even_while_stopped(speed):
    u=Regiment(0,'fugitive',0,Vec(400,300),state=S.ROUTING,cohesion=80,speed=speed)
    for _ in range(100):morale.recover_cohesion(u,Rules(),.1)
    assert u.cohesion==pytest.approx(70.)
    u.cohesion=.02;morale.recover_cohesion(u,Rules(),.1);assert u.cohesion==0
    u.state=S.RALLYING;morale.recover_cohesion(u,Rules(),1.);assert u.cohesion>0


def test_routing_cohesion_is_tunable_and_frame_grouping_independent():
    def make():
        u=Regiment(0,'fugitive',0,Vec(400,300),facing=math.pi,state=S.ROUTING,cohesion=80)
        return Battle([u],seed=17,sandbox=True,rules=replace(Rules(),routing_cohesion_loss=2.),generate_commanders=False)
    a,b=make(),make()
    for _ in range(100):a.step()
    for _ in range(25):
        for _ in range(4):b.step()
    assert a.units[0].cohesion==pytest.approx(60.)
    assert fingerprint(a)==fingerprint(b)


def test_treeline_protects_incoming_fire_more_than_it_disrupts_outgoing_fire():
    b,defender,attacker=create('treeline')
    outward=combat.forest_fire_factors(b,defender,attacker,b.visibility(defender,attacker))
    inward=combat.forest_fire_factors(b,attacker,defender,b.visibility(attacker,defender))
    assert outward[2]>0 and inward[2]==0
    assert outward[1]==1 and inward[1]<1
    assert outward[0]*outward[1]>inward[0]*inward[1]
    # Cover behind/off the actual sight line is not a free defence bonus.
    assert combat.forest_fire_factors(b,attacker,defender,Visibility())[1]==1


def test_thin_vegetation_is_less_protective_and_does_not_override_hidden_targets():
    b,a,target=create('woodland-ranged')
    thin=combat.forest_fire_factors(b,a,target,Visibility(True,.95,2.,'forest'))[1]
    deep=combat.forest_fire_factors(b,a,target,Visibility(True,.5,40.,'forest'))[1]
    assert 0<deep<thin<1
    target.pos=Vec(600,300)
    assert not b.visibility(a,target).visible
    combat.fire(b,a,target);assert a.analysis['volleys']==0


def test_woodland_skill_bonuses_are_bounded_situational_and_fade_at_edges():
    b,u,line=create('woodland-melee')
    dense=combat.forest_melee_factors(b,u)
    assert dense[1]==pytest.approx(4.5) and dense[2]==pytest.approx(2.4)
    b.terrain=TerrainMap()
    bare=combat.forest_melee_factors(b,u)
    assert bare==(1.,1.,1.2)
    b.terrain=TerrainMap(forests=(Forest(500,300,350,250,.1),))
    edge=combat.forest_melee_factors(b,u)
    assert bare[1]<edge[1]<dense[1] and bare[2]<edge[2]<dense[2]
    assert 0<b.rules.terrain.woodland_skill(.1)<b.rules.terrain.woodland_skill(.45)==1
    assert all(a.forest_accuracy==a.forest_melee_damage==a.forest_melee_shock==1 for a in ARCHETYPES.values() if a.id!=u.archetype.id)


def test_forest_melee_disrupts_dense_formations_more_than_loose_formations():
    b,_,_=create('woodland-melee')
    unit=Regiment(2,'rifles',0,Vec(400,300),archetype_id='revolutionary_rifles')
    penalties=[]
    for formation in (F.LINE,F.COLUMN,F.SKIRMISH):
        unit.formation=formation;penalties.append(combat.forest_melee_factors(b,unit)[0])
    assert 0<penalties[0]<penalties[1]<penalties[2]<1


def test_skirmishers_accept_favourable_forest_fights_but_withdraw_when_depleted_or_exposed():
    b,u,enemy=create('woodland-skirmish')
    ai.destination(b,u);assert not u.skirmish_retreat and u.forest_cover>0
    u.strength=60;u.skirmish_until=0
    ai.destination(b,u);assert u.skirmish_retreat
    field,light,target=create('open-ranged');target.pos=light.pos+Vec(40,0)
    light.order=Order(O.SKIRMISH,target_id=target.id)
    ai.destination(field,light);assert light.skirmish_retreat


def test_cautious_officer_accounts_for_woodland_matchup_instead_of_headcount_only():
    b,u,enemy=create('woodland-ranged')
    u.commander=Commander('test','Test officer','Generic',P.CAUTIOUS,T.PATHFINDER)
    b.ai_armies={u.army}
    assert not commander_ai.plan(b,u,[enemy],enemy)
    b.terrain=TerrainMap()
    assert commander_ai.plan(b,u,[enemy],enemy)


@pytest.mark.parametrize('mode',['treeline','woodland-ranged','woodland-melee','woodland-skirmish'])
def test_seeded_woodland_and_treeline_matchups_favour_the_intended_regiment(mode):
    rows=[run(mode,seed,swapped) for seed in (17,18) for swapped in (False,True)]
    assert sum(r['winner']=='specialist' for r in rows)>=3
    assert not any(r['winner']=='line' for r in rows)


@pytest.mark.parametrize('mode',['open-ranged','open-melee'])
def test_woodland_specialists_keep_open_ground_counters(mode):
    assert run(mode,17)['winner']=='line'


def test_complete_woodland_battle_replays_are_identical():
    a,*_=create('woodland-skirmish',17);b,*_=create('woodland-skirmish',17)
    for _ in range(600):a.step()
    for _ in range(150):
        for _ in range(4):b.step()
    assert fingerprint(a)==fingerprint(b)
