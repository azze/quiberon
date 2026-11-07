import math
from dataclasses import replace

import pytest

from analysis.cavalry_balance import create, run, aggregate
from analysis.performance import fingerprint
from simulation import cavalry, combat, movement
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec
from simulation.orders import Command, Order, OrderKind as O
from simulation.regiment import Regiment, CavalryState as C, MoraleState as S


def first_impact(battle,limit=900):
    horse=battle.units[0]
    for _ in range(limit):
        battle.step()
        if horse.analysis['charges']: return horse
    return horse


def test_charge_starts_only_at_bounded_range_and_accelerates_over_time():
    battle=create('standard-routing',17); horse=battle.units[0]
    battle.step()
    assert horse.cavalry_state==C.APPROACH
    for _ in range(200):
        previous=horse.speed; battle.step()
        if horse.cavalry_state==C.CHARGING:
            assert horse.speed<=previous+battle.rules.charge_acceleration*battle.rules.dt+1e-9
            break
    assert horse.cavalry_state==C.CHARGING
    assert 0<horse.charge_momentum<1
    assert horse.analysis['charge_initiations']==1
    assert any(e.kind=='charge_start' for e in battle.events)


def test_stationary_start_does_not_gain_instant_charge_speed():
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',order=Order(O.ATTACK,target_id=1))
    target=Regiment(1,'target',1,Vec(290,300),state=S.ROUTING,morale=10)
    battle=Battle([horse,target,Regiment(2,'reserve',1,Vec(900,100))])
    for i in range(10):
        previous=horse.speed; battle.step()
        assert horse.cavalry_state==C.CHARGING
        assert horse.speed-previous<=battle.rules.charge_acceleration*.1+1e-9
    assert horse.speed<3 and horse.charge_momentum==0


def test_long_approach_builds_impact_but_close_start_does_not():
    long=create('standard-routing',3); close=create('standard-routing',3)
    close.units[0].pos=Vec(330,300)  # Only five metres of clear space.
    first_impact(long)
    for _ in range(350):close.step()
    assert long.units[0].analysis['charges']==1 and long.units[0].charge_last_momentum>.5
    assert close.units[0].analysis['charges']==0
    assert close.units[0].analysis['pursuit_casualties']>0


def test_charging_turn_rate_is_lower_than_normal_turn_rate():
    a=Regiment(0,'a',0,Vec(200,300),archetype_id='cavalry',speed=9,cavalry_state=C.CHARGING)
    b=replace(a,cavalry_state=C.APPROACH)
    destination=Vec(280,330); battle=Battle([a])
    movement.move(a,destination,.1,1000,600,**cavalry.motion(battle,a))
    movement.move(b,destination,.1,1000,600)
    assert a.facing==pytest.approx(b.facing*battle.rules.charge_turn_multiplier)


def test_speed_flag_alone_cannot_produce_an_impact():
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',speed=12)
    target=Regiment(1,'target',1,Vec(215,300))
    battle=Battle([horse,target]); combat.melee(battle,horse,target)
    assert horse.analysis['charges']==0


def test_initial_impact_does_not_also_apply_an_outgoing_melee_hit(charging):
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',speed=12)
    foot=Regiment(1,'foot',1,Vec(215,300))
    battle=Battle([horse,foot],seed=17);charging(horse)
    combat.melee(battle,horse,foot)
    assert foot.stats.strength-foot.strength==horse.analysis['impact_casualties']>0
    assert foot.analysis['casualties_inflicted']>0


def test_impact_requires_forward_motion_and_occurs_once_even_when_contact_flickers(charging):
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',speed=12)
    target=Regiment(1,'target',1,Vec(215,300),math.pi)
    battle=Battle([horse,target]); charging(horse)
    cavalry.impact(battle,horse,target)
    strength=target.strength
    for tick in range(1,300):
        battle.tick=tick;horse.charge_cooldown=0
        # Artificial boundary flicker must never regenerate the spent charge.
        horse.cavalry_state=C.CHARGING
        cavalry.impact(battle,horse,target)
    assert horse.analysis['charges']==1 and target.strength==strength
    assert not horse.charge_ready
    backwards=Regiment(2,'backwards',0,Vec(200,300),archetype_id='cavalry',speed=12)
    charging(backwards);backwards.velocity=Vec(-12,0)
    before=target.strength
    cavalry.impact(battle,backwards,target)
    assert target.strength==before and backwards.charge_last_momentum==0


def test_fresh_orders_cannot_reset_impact_lock_without_disengagement(charging):
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',speed=12,
                   order=Order(O.ATTACK,target_id=1))
    target=Regiment(1,'target',1,Vec(215,300),math.pi)
    battle=Battle([horse,target]);charging(horse);cavalry.impact(battle,horse,target)
    for tick in range(300,500):
        battle.tick=tick; horse.charge_cooldown=0
        cavalry.cancel(horse);horse.target_id=target.id
        cavalry.intent(battle,horse,target.pos)
        assert not horse.charge_ready and horse.cavalry_state!=C.CHARGING
    # Actual disengagement permits reforming during Hold, before another attack.
    horse.pos=Vec(100,100);horse.order=Order(O.HOLD)
    for tick in range(500,560):
        battle.tick=tick;cavalry.intent(battle,horse,None)
    assert horse.charge_ready


def test_interrupting_charge_clears_momentum_target_and_pending_impact():
    battle=create('standard-routing',17); horse=battle.units[0]
    for _ in range(200):
        battle.step()
        if horse.cavalry_state==C.CHARGING:break
    battle.issue(Command(horse.id,Order(O.HOLD)));battle.step()
    assert horse.cavalry_state==C.APPROACH and horse.cavalry_target_id is None
    assert horse.charge_momentum==0 and horse.speed==0 and horse.analysis['charges']==0
    assert horse.analysis['aborted_charges']==1


@pytest.mark.parametrize('seed',[1,7,31])
def test_prepared_frontal_infantry_resists_but_flank_charge_can_break_it(seed):
    front=run('steady-front',seed);flank=run('steady-flank',seed)
    assert front['result']=='infantry'
    assert front['failed_charges']>=1
    assert flank['result']=='cavalry'
    assert flank['mean_impact_damage']>front['mean_impact_damage']*2


def test_dense_forest_reduces_mobility_and_denies_organized_charge():
    open_battle=create('open-front',17);woods=create('forest-front',17)
    open_battle.sandbox=woods.sandbox=True  # Isolate movement from musket casualties.
    for _ in range(60):open_battle.step();woods.step()
    a,b=open_battle.units[0],woods.units[0]
    assert a.pos.x-200>(b.pos.x-200)*2
    assert b.cohesion<a.cohesion and b.analysis['charge_initiations']==0


def test_pursuit_continues_moving_and_uses_interval_damage_instead_of_melee():
    battle=create('uhlans-routing',3);horse,target=battle.units[:2]
    for _ in range(500):
        battle.step()
        if horse.cavalry_state==C.PURSUIT:break
    assert horse.cavalry_state==C.PURSUIT
    start=horse.pos;before=horse.analysis['pursuit_casualties']
    for _ in range(100):battle.step()
    assert horse.pos.x>start.x+10
    assert horse.analysis['pursuit_casualties']>before
    assert horse.analysis['melee_seconds']==0 and horse.analysis['pursuit_seconds']>5
    assert horse.analysis['charges']==1
    # A successful rally ends the pursuit rules immediately.
    target.state=S.STEADY;target.morale=80;target.cohesion=80
    previous=horse.analysis['pursuit_casualties'];battle.step()
    assert horse.cavalry_state!=C.PURSUIT and horse.analysis['pursuit_casualties']==previous


def test_multiple_pursuers_share_bounded_damage_and_keep_pace():
    battle=create('double-pursuit',3);horses=battle.units[:2];target=battle.units[2]
    modifiers=[];rounds=0
    for _ in range(1200):
        before=target.strength;impacts=sum(u.analysis['charges'] for u in horses)
        battle.step()
        if sum(u.analysis['charges'] for u in horses)==impacts:
            assert before-target.strength<=int(target.stats.strength*battle.rules.pursuit_max_fraction)
        if before>target.strength:rounds+=1
        modifiers.extend(u.congestion_speed for u in horses if u.cavalry_state==C.PURSUIT and u.velocity.length()>1)
        if not target.active:break
    assert not target.active and rounds>5
    assert sum(u.analysis['charges'] for u in horses)==2
    assert modifiers and min(modifiers)>.95
    assert all(u.effective and u.strength>=70 for u in horses)


@pytest.mark.parametrize('reason',['distance','exhaustion','new_order'])
def test_pursuit_stops_when_contact_condition_or_order_is_lost(reason):
    battle=create('uhlans-routing',17);horse,target=battle.units[:2]
    for _ in range(500):
        battle.step()
        if horse.cavalry_state==C.PURSUIT:break
    before=horse.analysis['pursuit_casualties']
    if reason=='distance':target.pos+=Vec(100,0)
    elif reason=='exhaustion':horse.cohesion=20;horse.fatigue=90
    else:battle.issue(Command(horse.id,Order(O.WITHDRAW)))
    for _ in range(20):battle.step()
    assert horse.cavalry_state!=C.PURSUIT
    assert horse.analysis['pursuit_casualties']==before


def test_many_pursuers_have_one_shared_damage_and_resistance_budget():
    horses=[Regiment(i,str(i),0,Vec(200,300),archetype_id='cavalry',
                     order=Order(O.ATTACK,target_id=6),target_id=6,cavalry_target_id=6,
                     cavalry_state=C.PURSUIT) for i in range(6)]
    foot=Regiment(6,'fleeing',1,Vec(215.25,300),state=S.ROUTING,morale=0)
    battle=Battle([*horses,foot],seed=17);battle.pursuit_next[foot.id]=0
    cavalry.pursuits(battle,battle.units)
    lost=foot.stats.strength-foot.strength
    assert 0<lost<=int(foot.stats.strength*battle.rules.pursuit_max_fraction)
    assert sum(u.analysis['pursuit_casualties'] for u in horses)==lost
    before=foot.strength;cavalry.pursuits(battle,battle.units)
    assert foot.strength==before


def test_failed_charge_recoils_without_replacing_attack_order():
    battle=create('steady-front',17);horse=first_impact(battle)
    assert horse.analysis['failed_charges']==1 and horse.cavalry_state==C.RECOIL
    assert horse.recoil_goal is not None
    order=horse.order;previous=horse.pos
    battle.step()
    assert horse.order==order and (horse.pos-previous).length()<2


def test_recoil_turn_is_not_cancelled_by_contact_facing_and_can_reform():
    battle=create('steady-front',17);battle.units[1].strength=120
    horse=first_impact(battle);position=horse.pos;states=[];minimum=horse.pos.x
    for _ in range(150):
        battle.step();states.append(horse.cavalry_state);minimum=min(minimum,horse.pos.x)
    assert minimum<position.x-15
    assert C.REFORMING in states and horse.effective


def test_swapped_forest_experiment_preserves_cover_for_both_armies():
    a,b=create('forest-front',17),create('forest-front',17,swapped=True)
    for left,right in zip(a.units,b.units):
        assert a.terrain.forest_density(left.pos.x,left.pos.y)==pytest.approx(b.terrain.forest_density(right.pos.x,right.pos.y))
    assert b.terrain.forest_density(b.units[0].pos.x,b.units[0].pos.y)>.8


@pytest.mark.parametrize('state,expected',[(S.STEADY,C.RECOIL),(S.WAVERING,C.MELEE)])
def test_ai_disengages_from_organized_superiority_but_commits_against_wavering_foot(state,expected):
    horse=Regiment(0,'horse',0,Vec(200,300),archetype_id='cavalry',target_id=1,
                   cavalry_target_id=1,cavalry_state=C.MELEE,order=Order(O.ATTACK,target_id=1))
    foot=Regiment(1,'foot',1,Vec(215,300),math.pi,state=state,cohesion=80)
    # Isolate the generic disengagement rule; personality timings are tested separately.
    battle=Battle([horse,foot],ai_armies=(0,),generate_commanders=False);battle.tick=200
    cavalry.intent(battle,horse,None)
    assert horse.cavalry_state==expected


def test_melee_state_factors_and_rally_recovery_are_monotone():
    unit=Regiment(0,'foot',0,Vec(200,300));rules=Rules();values=[]
    for state in (S.STEADY,S.SHAKEN,S.WAVERING,S.ROUTING):
        unit.state=state;values.append(combat.melee_effectiveness(unit,rules))
    assert values==[1.,.7,.4,.1]
    unit.state=S.RALLYING;unit.morale=28;unit.cohesion=20
    low=combat.melee_effectiveness(unit,rules)
    unit.morale=48;unit.cohesion=45
    assert low<combat.melee_effectiveness(unit,rules)<=.6


def test_balance_scenarios_and_state_replays_are_deterministic():
    a,b=create('double-pursuit',17),create('double-pursuit',17)
    for _ in range(650):a.step()
    for _ in range(130):
        for _ in range(5):b.step()
    assert fingerprint(a)==fingerprint(b)
    rows=[run('standard-wavering',17),run('standard-wavering',17,swapped=True)]
    summary=aggregate(rows)['standard-wavering']
    assert summary['runs']==2 and summary['results']=={'cavalry':2}
