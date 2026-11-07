"""Conditional effects run through existing movement, combat and morale hooks."""
from dataclasses import replace
import math
import pytest
from simulation import upgrades,commanders as cmd,archetypes,morale,combat,cavalry,movement
from simulation.commanders import Commander,Personality as P,Specialization as S
from simulation.battle import Battle
from simulation.regiment import Regiment,MoraleState as M,CavalryState as C
from simulation.formations import Formation as F
from simulation.orders import Order,OrderKind as O,Command
from simulation.geometry import Vec
from simulation.terrain import TerrainMap,Forest
from analysis.performance import fingerprint


def unit(key='infantry',learned=(),uid=0,army=0,pos=Vec(300,300),spec=None,**kwargs):
    kind=archetypes.ARCHETYPES[key].stats.kind
    spec=spec or (S.ARTILLERIST if kind.value=='artillery' else S.PURSUIT if kind.value=='cavalry' else S.DRILLMASTER)
    c=Commander(f'commander-{uid}','Test Officer','Generic',P.METHODICAL,spec,upgrades=tuple(learned))
    return Regiment(uid,'Test',army,pos,archetype_id=key,commander=c,**kwargs)


def test_registry_unique_valid_eligibility_serialization_and_limits():
    assert len(upgrades.REGISTRY)==12
    for key,d in upgrades.REGISTRY.items():
        assert key==d.id and d.max_rank==1
        compatible=[a for a in archetypes.ARCHETYPES.values() if upgrades.eligible(a,key)]
        assert compatible
        u=unit(compatible[0].id,(key,));assert Commander.from_dict(u.commander.to_dict())==u.commander
        assert key not in upgrades.available(u.archetype,u.commander)
    u=unit(learned=('rolling_volley','swift_reform','rallying_presence'))
    assert not upgrades.available(u.archetype,u.commander,3)
    for learned in [('unknown',),('swift_reform','swift_reform'),('mobile_battery',)]:
        with pytest.raises(ValueError):unit(learned=learned)
    with pytest.raises(ValueError):unit('infantry',('woodland_ambush',))


def test_rolling_volley_needs_close_visible_steady_infantry_and_real_fire_uses_it():
    u=unit(learned=('rolling_volley',));ally=unit(uid=1,pos=Vec(300,375));target=unit(uid=2,army=1,pos=Vec(420,300),facing=math.pi)
    b=Battle([u,ally,target],seed=1)
    assert upgrades.volley_reload(b,u)==.8
    combat.fire(b,u,target);assert u.reload_left==pytest.approx(archetypes.reload_time(u)*.8)
    ally.state=M.WAVERING;assert upgrades.volley_reload(b,u)==1
    ally.state=M.STEADY;ally.pos=Vec(300,410);assert upgrades.volley_reload(b,u)==1
    ally.pos=Vec(300,375);u.cohesion=69;assert upgrades.volley_reload(b,u)==1
    u.cohesion=100;u.formation=F.COLUMN;assert upgrades.volley_reload(b,u)==1


def test_swift_reform_changes_real_formation_turn_loss_and_shared_recovery():
    u=unit('prussian_line',('swift_reform',));plain=unit('prussian_line')
    assert archetypes.formation_time(u,7)<archetypes.formation_time(plain,7)
    assert archetypes.formation_time(u,7)>=2.8
    movement.turn_to(u,.5,.1);movement.turn_to(plain,.5,.1)
    assert u.cohesion>plain.cohesion
    u.cohesion=plain.cohesion=70;b=Battle([u])
    morale.recover_cohesion(u,b.rules,2);morale.recover_cohesion(plain,b.rules,2)
    assert u.cohesion>plain.cohesion
    u.congestion_loss=1;before=u.cohesion;morale.recover_cohesion(u,b.rules,2);assert u.cohesion==before


def test_rallying_presence_uses_existing_nonstacking_aura_and_inactive_routes():
    guard=unit('royal_grenadiers',('rallying_presence',),spec=S.INSPIRER)
    another=unit('royal_grenadiers',('rallying_presence',),uid=1,pos=Vec(300,400),spec=S.INSPIRER)
    ally=unit(uid=2,pos=Vec(300,350),morale=50)
    b=Battle([guard,another,ally]);before=ally.morale;morale.update(b)
    assert morale.aura_amount(guard)==.3 and morale.aura_amount(guard,True)==.45
    # One source, even with Royal Prestige + Inspirer + two upgrade auras.
    assert ally.morale-before<.2
    assert morale.prestige_support(b,ally) in (guard,another)
    guard.state=another.state=M.ROUTING
    assert morale.prestige_support(b,ally) is None


def test_controlled_charge_changes_turn_cooldown_and_failed_impact_disorder(charging):
    def pair(learned):
        u=unit('cavalry',learned,pos=Vec(360,300),speed=11)
        target=unit(uid=1,army=1,pos=Vec(390,300),facing=math.pi,order=Order(O.HOLD))
        b=Battle([u,target],seed=5);charging(u,.8);return b,u,target
    b,u,t=pair(('controlled_charge',));base,v,other=pair(())
    assert cavalry.motion(b,u)['turn_multiplier']>cavalry.motion(base,v)['turn_multiplier']
    cavalry.impact(b,u,t);cavalry.impact(base,v,other)
    assert u.charge_cooldown<v.charge_cooldown and u.cohesion>v.cohesion
    sequence=u.analysis['charges'];cavalry.impact(b,u,t);assert u.analysis['charges']==sequence==1


def test_relentless_pursuit_power_and_one_recovery_per_enemy_rout():
    u=unit('commonwealth_uhlans',('relentless_pursuit',),cohesion=50)
    t=unit(uid=1,army=1,pos=Vec(330,300),morale=1);t.last_attacker=u.id
    b=Battle([u,t]);assert cmd.pursuit_factor(u)>cmd.pursuit_factor(unit('commonwealth_uhlans'))
    morale.update(b);assert t.state==M.ROUTING
    assert u.cohesion>=58
    before=u.cohesion;upgrades.on_rout(b,t,u);assert u.cohesion==before
    t.state=M.SHAKEN;t.morale=1;morale.update(b)
    assert u.cohesion<before+1 # rerouting same target cannot farm cohesion


def test_shock_commander_rewards_exposed_impacts_without_firebrand_drawback():
    u=unit('commonwealth_uhlans',('shock_commander',));t=unit(uid=1,army=1,pos=Vec(400,300),facing=math.pi)
    t.state=M.WAVERING
    assert cmd.charge_shock_factor(u,t,.6)==pytest.approx(1.35)
    assert cmd.charge_shock_factor(u,t,.6,True)==1
    assert cmd.charge_shock_factor(u,t,.1)==1
    b=Battle([u,t]);cohesion=u.cohesion;cmd.charge_aftermath(b,u,.6,1.35);assert u.cohesion==cohesion
    u.commander=replace(u.commander,specialization=S.FIREBRAND)
    assert 1.35<cmd.charge_shock_factor(u,t,.6)<=1.8


def test_woodland_ambush_harasses_without_repeat_until_genuine_reset():
    u=unit('haudenosaunee_skirmishers',('woodland_ambush','harassing_fire'),pos=Vec(350,300),spec=S.PATHFINDER)
    t=unit(uid=1,army=1,pos=Vec(405,300),facing=math.pi)
    terrain=TerrainMap(1000,600,forests=(Forest(330,300,100,150,.8),))
    b=Battle([u,t],terrain=terrain,seed=4)
    assert b.visibility(t,u).transmission<.7 and b.visibility(u,t).visible
    before=(t.morale,t.cohesion);combat.fire(b,u,t)
    assert 'ambush_position' in u.upgrade_state and t.morale<before[0] and t.cohesion<before[1]
    count=lambda:len([e for e in b.events if 'Woodland Ambush:' in e.message])
    assert count()==1
    u.forest_cover=.8
    b.tick=100;upgrades.on_volley(b,u,t,0);assert count()==1
    b.tick=500;u.pos=Vec(340,300);upgrades.on_volley(b,u,t,0);assert count()==1
    b.tick=900;u.pos=Vec(300,300);upgrades.on_volley(b,u,t,0);assert count()==2
    old=t.cohesion;upgrades.on_volley(b,u,t,1);assert t.cohesion==pytest.approx(old-3)


def test_ambush_inactive_in_open_or_while_moving():
    u=unit('haudenosaunee_skirmishers',('woodland_ambush',));t=unit(uid=1,army=1,pos=Vec(340,300))
    b=Battle([u,t]);upgrades.on_volley(b,u,t,1);assert 'ambush_position' not in u.upgrade_state
    b.terrain=TerrainMap(1000,600,forests=(Forest(300,300,100,150,.8),));u.speed=2
    upgrades.on_volley(b,u,t,1);assert 'ambush_position' not in u.upgrade_state


def test_steadfast_defence_is_conditional_and_stacks_within_caps():
    u=unit('prussian_line',('steadfast_defence',),spec=S.DEFENSIVE,order=Order(O.HOLD))
    attacker=unit('cavalry',uid=1,army=1,pos=Vec(400,300))
    assert .65<=cmd.defence_factor(u,attacker)<.9 and cmd.shock_factor(u)<1
    attacker.pos=Vec(200,300);assert cmd.defence_factor(u,attacker)==1
    u.speed=2;assert cmd.defence_factor(u)==1 and cmd.shock_factor(u)==1
    u.speed=0;u.order=Order(O.ADVANCE);assert cmd.defence_factor(u)==1
    u.order=Order(O.HOLD);u.cohesion=59;assert cmd.defence_factor(u)==1


def test_mobile_battery_shortens_real_limber_and_setup_without_changing_physics():
    u=unit('french_horse_artillery',('mobile_battery',));base=unit('french_horse_artillery')
    movement.move(u,Vec(500,300),.1,1000,600)
    movement.move(base,Vec(500,300),.1,1000,600)
    assert u.limber_left<base.limber_left and u.setup_left<base.setup_left
    assert cmd.redeploy_factor(u)==pytest.approx(cmd.redeploy_factor(base)*.6)


def test_calculated_fire_preparation_resets_and_bounds_scatter():
    u=unit('artillery',('calculated_fire',));plain=unit('artillery')
    assert cmd.scatter_factor(u)==cmd.scatter_factor(plain)
    for _ in range(61):upgrades.update_stationary(u,.1)
    assert .45<=cmd.scatter_factor(u)<cmd.scatter_factor(plain)
    u.speed=1;upgrades.update_stationary(u,.1);assert u.upgrade_stationary==0 and cmd.scatter_factor(u)==1
    u.speed=0;u.setup_left=1;upgrades.update_stationary(u,.1);assert u.upgrade_stationary==0


def test_inspired_attack_is_event_based_nonstacking_and_capped():
    u=unit(learned=('inspired_attack',));other=unit(uid=1,learned=('inspired_attack',),pos=Vec(300,370))
    ally=unit(uid=2,pos=Vec(300,340),morale=98);t=unit(uid=3,army=1,pos=Vec(400,300),state=M.WAVERING)
    b=Battle([u,other,ally,t]);combat.damage(b,t,1,'musket volley',u)
    assert ally.morale==100
    ally.morale=90;combat.damage(b,t,1,'musket volley',other);assert ally.morale==90
    b.tick=200;combat.damage(b,t,1,'melee',other);assert ally.morale==93
    b.tick=400;t.state=M.STEADY;combat.damage(b,t,1,'melee',u);assert ally.morale==93


def test_upgrade_state_fresh_and_fixed_seed_orders_reproducible():
    from campaign.state import Campaign
    s=Campaign.new(17);army=tuple(replace(r,commander=replace(r.commander,upgrades=tuple(upgrades.available(archetypes.ARCHETYPES[r.archetype_id],r.commander)[:3]))) for r in s.army)
    s=replace(s,army=army);s=replace(s,encounter=s.make_encounter())
    a,b=s.create_battle(),s.create_battle()
    for tick in range(50):
        if tick==0:
            for battle in (a,b):battle.issue(Command(0,order=Order(O.ADVANCE,Vec(500,300))))
        a.step();b.step()
    assert fingerprint(a)==fingerprint(b)
    a.unit(0).upgrade_state['expired']=100
    assert s.create_battle().unit(0).upgrade_state=={}
