"""Focused balance checks: trajectory spread and casualty/shock multipliers."""
import math
from dataclasses import replace
import pytest
from simulation import combat,projectiles,infantry_charge
from simulation.archetypes import ARCHETYPES
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec
from simulation.regiment import Regiment,UnitType

INFANTRY_IDS=[a.id for a in ARCHETYPES.values() if a.stats.kind==UnitType.INFANTRY]


@pytest.mark.parametrize('key',INFANTRY_IDS)
def test_all_infantry_get_the_same_volley_bonus_without_changing_reload_or_range(key,monkeypatch):
    results=[]
    for multiplier in (1.,1.1):
        shooter=Regiment(0,'infantry',0,Vec(250,300),archetype_id=key)
        target=Regiment(1,'target',1,Vec(330,300),strength=10000)
        b=Battle([shooter,target],rules=replace(Rules(),infantry_volley_damage=multiplier),generate_commanders=False)
        monkeypatch.setattr(b.rng,'random',lambda:0.) # fixed volley hits; no accuracy/seed noise
        combat.fire(b,shooter,target)
        results.append((10000-target.strength,shooter.reload_left,shooter.stats.range))
    assert results[1][0]==math.ceil(results[0][0]*1.1-1e-9)
    assert results[1][1:]==results[0][1:]
    assert Rules().infantry_volley_damage==1.1


def test_small_damage_bonuses_survive_rounding_and_do_not_create_damage_from_zero():
    b=Battle([],seed=17)
    samples=[combat.scale_casualties(b,1,1.2) for _ in range(10000)]
    assert 1.18<sum(samples)/len(samples)<1.22
    state=b.rng.getstate()
    assert combat.scale_casualties(b,0,1.2)==0
    assert combat.scale_casualties(b,5,1)==5
    assert combat.scale_casualties(b,10,1.2)==12
    assert b.rng.getstate()==state


def test_infantry_buff_does_not_change_artillery_salvos():
    shots=[]
    for factor in (1.,1.1):
        gun=Regiment(0,'gun',0,Vec(250,300),archetype_id='artillery')
        target=Regiment(1,'target',1,Vec(450,300))
        b=Battle([gun,target],seed=17,rules=replace(Rules(),infantry_volley_damage=factor),generate_commanders=False)
        combat.fire(b,gun,target);shots.append(b.projectiles)
    assert shots[0]==shots[1] and len(shots[0])==6


@pytest.mark.parametrize('fractional_roll,expected_losses',[(.1,2),(.9,1)])
def test_woodland_melee_boost_reaches_one_casualty_exchanges_and_morale(fractional_roll,expected_losses,monkeypatch):
    def exchange(boosted):
        original=ARCHETYPES['haudenosaunee_skirmishers']
        definition=original if boosted else replace(original,melee_damage=1.,melee_shock=1.)
        with monkeypatch.context() as patch:
            patch.setitem(ARCHETYPES,original.id,definition)
            wood=Regiment(0,'woodland',0,Vec(250,300),archetype_id=original.id)
            target=Regiment(1,'target',1,Vec(270,300),math.pi)
            b=Battle([wood,target],generate_commanders=False)
            patch.setattr(b.rng,'uniform',lambda low,high:1.)
            patch.setattr(b.rng,'random',lambda:fractional_roll)
            recorded=[]
            patch.setattr(combat,'damage',lambda battle,victim,losses,reason,attacker=None,shock=0:
                          recorded.append((attacker.id,losses,shock)))
            combat.melee(b,wood,target)
            return recorded[0]
    old,new=exchange(False),exchange(True)
    assert old[1]==1 and new[1]==expected_losses
    assert new[2]==pytest.approx(old[2]*1.2)


def test_woodland_melee_boost_also_applies_to_one_time_bayonet_impact(monkeypatch):
    records=[]
    for boosted in (False,True):
        definition=ARCHETYPES['haudenosaunee_skirmishers']
        with monkeypatch.context() as patch:
            if not boosted:patch.setitem(ARCHETYPES,definition.id,replace(definition,melee_damage=1.,melee_shock=1.))
            wood=Regiment(0,'woodland',0,Vec(250,300),archetype_id=definition.id,
                          infantry_charging=True,charge_sequence=1,charge_momentum=.8)
            target=Regiment(1,'target',1,Vec(270,300),math.pi)
            b=Battle([wood,target],generate_commanders=False)
            patch.setattr(b.rng,'uniform',lambda low,high:1.)
            patch.setattr(b.rng,'random',lambda:0.)
            impact=[]
            patch.setattr(combat,'damage',lambda battle,victim,losses,reason,attacker=None,shock=0:impact.append((losses,shock)))
            infantry_charge.impact(b,wood,target);infantry_charge.impact(b,wood,target)
            assert len(impact)==1
            records.append(impact[0])
    assert records[1][0]==math.ceil(records[0][0]*1.2)
    assert records[1][1]==pytest.approx(records[0][1]*1.2)
    assert all(a.melee_damage==a.melee_shock==1 for a in ARCHETYPES.values() if a.id!='haudenosaunee_skirmishers')


def launched(spread,seed=17):
    gun=Regiment(0,'gun',0,Vec(250,300),archetype_id='artillery')
    target=Regiment(1,'aim point',1,Vec(550,300))
    rules=replace(Rules(),artillery_scatter=0.,artillery_vertical_scatter=spread)
    b=Battle([gun],seed=seed,rules=rules,generate_commanders=False)
    for _ in range(40):projectiles.launch(b,gun,target)
    return b


def test_artillery_height_spread_is_independent_of_horizontal_scatter_and_seeded():
    flat=launched(0);varied=launched(3)
    assert varied.projectiles==launched(3).projectiles
    assert len({p.vertical_speed for p in flat.projectiles})==1
    base=flat.projectiles[0].vertical_speed
    assert all(base-3<=p.vertical_speed<=base+3 for p in varied.projectiles)
    heights=[p.height+p.vertical_speed*3-.5*varied.rules.gravity*9 for p in varied.projectiles]
    assert max(heights)>6 and min(heights)<-6 # high overshoots and early ground impacts
    assert all(p.velocity==Vec(100,0) and p.height==1.2 for p in varied.projectiles)


def test_vertical_spread_changes_actual_landing_points_and_balls_terminate():
    b=launched(3);balls=list(b.projectiles);first_ground={}
    for _ in range(150):
        projectiles.update(b)
        for i,p in enumerate(balls):
            if p.bounces and i not in first_ground:first_ground[i]=p.pos.x
    assert len(first_ground)==len(balls)
    assert max(first_ground.values())-min(first_ground.values())>90
    assert not b.projectiles
