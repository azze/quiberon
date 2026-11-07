"""Pursuit must not turn broken troops into dependable melee damage sources."""
import math
from dataclasses import replace

import pytest

from analysis.performance import fingerprint
from simulation import combat
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind
from simulation.regiment import Regiment, MoraleState as S


def pursuit(seed):
    horse=Regiment(0,'Uhlans',0,Vec(200,300),archetype_id='commonwealth_uhlans',
                   order=Order(OrderKind.ATTACK,target_id=1))
    foot=Regiment(1,'Fleeing infantry',1,Vec(270,300),state=S.ROUTING,morale=10)
    # Distant reserves keep army defeat from ending the pursuit prematurely.
    return Battle([horse,foot,Regiment(2,'Red reserve',1,Vec(900,100)),
                   Regiment(3,'Blue reserve',0,Vec(100,100))],seed=seed)


@pytest.mark.parametrize('seed',[1,7,31])
def test_full_strength_uhlans_overrun_routed_infantry_without_routing(seed):
    battle=pursuit(seed); horse,foot=battle.units[:2]
    for _ in range(2200):
        battle.step()
        assert horse.effective
        if not foot.active: break
    assert not foot.active
    assert horse.strength>=horse.stats.strength*.75
    assert horse.state==S.STEADY and horse.morale>60
    assert horse.analysis['charges']>0
    assert horse.analysis['casualties_inflicted']==foot.stats.strength
    # Counterattacks remain possible, but do not become guaranteed attrition.
    assert 0<=foot.analysis['casualties_inflicted']<horse.stats.strength*.25


@pytest.mark.parametrize('state,factor',[(S.ROUTING,.1),(S.RALLYING,.25)])
def test_broken_units_have_no_guaranteed_kill_and_scale_morale_shock(state,factor,monkeypatch):
    broken=Regiment(0,'broken',1,Vec(215,300),math.pi,state=state,morale=10,strength=1,cohesion=0)
    horse=Regiment(1,'horse',0,Vec(200,300),archetype_id='commonwealth_uhlans')
    battle=Battle([broken,horse],seed=17)
    hits=[]; original=combat.damage
    def record(battle,target,losses,reason,attacker=None,shock=0.):
        hits.append((attacker.id,losses,shock))
        original(battle,target,losses,reason,attacker,shock)
    monkeypatch.setattr(combat,'damage',record)
    combat.melee(battle,broken,horse)
    assert hits[0]==pytest.approx((broken.id,0,factor))
    assert horse.strength==horse.stats.strength


@pytest.mark.parametrize('state',[S.ROUTING,S.RALLYING])
def test_broken_cavalry_cannot_deliver_a_charge(state):
    horse=Regiment(0,'broken horse',0,Vec(200,300),archetype_id='commonwealth_uhlans',
                   speed=9,state=state,morale=10)
    foot=Regiment(1,'enemy',1,Vec(215,300))
    battle=Battle([horse,foot],seed=17)
    combat.melee(battle,horse,foot)
    assert horse.analysis['charges']==0 and horse.charge_cooldown==0
    assert not any(e.kind=='charge' for e in battle.events)


@pytest.mark.parametrize('state,description',[(S.STEADY,'prepared front'),(S.ROUTING,'exposed formation'),(S.RALLYING,'exposed formation')])
def test_only_organized_infantry_can_receive_prepared_front_protection(state,description,charging):
    horse=Regiment(0,'Uhlans',0,Vec(200,300),archetype_id='commonwealth_uhlans',speed=9)
    foot=Regiment(1,'infantry',1,Vec(215,300),math.pi,state=state,cohesion=100)
    battle=Battle([horse,foot],seed=17)
    charging(horse)
    combat.melee(battle,horse,foot)
    assert any(e.kind=='charge' and description in e.message for e in battle.events)


def test_routing_resistance_factors_are_configurable():
    broken=Regiment(0,'broken',1,Vec(215,300),math.pi,state=S.ROUTING,morale=10)
    horse=Regiment(1,'horse',0,Vec(200,300),archetype_id='commonwealth_uhlans')
    battle=Battle([broken,horse],seed=17,rules=replace(Rules(),routing_melee_factor=0))
    combat.melee(battle,broken,horse)
    assert horse.strength==horse.stats.strength and horse.morale>=horse.archetype.initial_morale


def test_sustained_pursuit_is_deterministic_across_frame_groupings():
    a,b=pursuit(17),pursuit(17)
    for _ in range(1800):a.step()
    for _ in range(450):
        for _ in range(4):b.step()
    assert fingerprint(a)==fingerprint(b)
