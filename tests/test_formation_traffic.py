import math
from dataclasses import replace
import pytest
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec,intersection_area,touching
from simulation.regiment import Regiment,CAVALRY,MoraleState
from simulation.formations import Formation
from simulation.orders import Order,OrderKind as O,Command
from simulation.movement import update_congestion
from simulation import combat
from analysis.performance import fingerprint
from analysis.scaling import scenario
from scenarios.traffic_tests import create
from simulation.terrain import TerrainMap, Hill


def pair(kind='infantry',angle=0,speed=4):
    a=Regiment(0,'a',0,Vec(300,300),archetype_id=kind,speed=4,velocity=Vec(4,0))
    b=Regiment(1,'b',0,a.pos,facing=0,archetype_id=kind,speed=speed,velocity=Vec(math.cos(angle)*speed,math.sin(angle)*speed))
    return a,b


def test_velocity_angle_and_overtaking_control_both_penalties():
    results=[]
    for angle in (0,math.pi/2,math.pi):
        a,b=pair(angle=angle); update_congestion([a,b],Rules(),1)
        results.append((a.congestion_speed,a.congestion_loss))
    assert results[0][0]>results[1][0]>results[2][0]>=.5
    assert results[0][1]<results[1][1]<results[2][1]
    # Facing intentionally stays identical while real velocity points backwards.
    a,b=pair('commonwealth_uhlans'); update_congestion([a,b],Rules(),1); aligned=a.congestion_speed
    a,b=pair('commonwealth_uhlans',speed=2); update_congestion([a,b],Rules(),1)
    assert aligned>a.congestion_speed>.85
    a,b=pair('commonwealth_uhlans',angle=math.pi);a.pursuit_id=b.pursuit_id=3
    update_congestion([a,b],Rules(),1)
    assert a.congestion_speed<.7


def test_shared_pursuit_requires_aligned_motion():
    a,b=pair('commonwealth_uhlans');a.pursuit_id=b.pursuit_id=9
    update_congestion([a,b],Rules(),1)
    assert a.congestion_speed>.98 and a.congestion_loss<.1


@pytest.mark.parametrize('seed',[1,7,31])
def test_two_uhlans_catch_fleeing_cavalry_before_boundary(seed):
    battle=create(seed,mode='pursuit'); target=battle.unit(2)
    caught=False; speed_modifiers=[]
    for _ in range(650):
        battle.step()
        for u in battle.units[:2]:
            if u.congestion>.5 and u.velocity.length()>1:speed_modifiers.append(u.congestion_speed)
            if touching(u,target):caught=True
        if caught:break
    assert caught and target.pos.x<800
    assert speed_modifiers and min(speed_modifiers[5:])>.95
    assert all(u.cohesion>85 for u in battle.units[:2])


def test_stationary_triple_separates_gently_and_stably_with_player_hold_priority():
    units=[Regiment(i,str(i),0,Vec(300,300)) for i in range(3)]
    battle=Battle(units,sandbox=True)
    battle.issue(Command(2,Order(O.HOLD)))
    last=[u.pos for u in units]
    for _ in range(1200):
        battle.step()
        for i,u in enumerate(units):
            assert (u.pos-last[i]).length()<1
            last[i]=u.pos
    assert units[2].pos==Vec(300,300)
    assert all(intersection_area(a,b)<1e-6 for i,a in enumerate(units) for b in units[i+1:])
    settled=[u.pos for u in units]
    for _ in range(300):battle.step()
    assert [u.pos for u in units]==settled


def test_player_common_destination_preserved_but_actual_stops_differ():
    goal=Vec(350,300)
    units=[Regiment(0,'first',0,Vec(250,300)),Regiment(1,'second',0,Vec(200,300))]
    battle=Battle(units,sandbox=True)
    for u in units:battle.issue(Command(u.id,Order(O.MOVE,goal,facing=0)))
    for _ in range(1500):battle.step()
    assert all(u.order.destination==goal and u.order.facing==0 for u in units)
    assert all((u.pos-(u.settling_goal or goal)).length()<1 for u in units)
    assert intersection_area(*units)<1e-6
    assert max((u.pos-goal).length() for u in units)<Rules().settling_radius


def test_temporary_opposing_crossing_still_completes():
    a=Regiment(0,'a',0,Vec(200,300),order=Order(O.MOVE,Vec(420,300)))
    b=Regiment(1,'b',0,Vec(420,300),math.pi,order=Order(O.MOVE,Vec(200,300)))
    battle=Battle([a,b],sandbox=True); minimum=1
    for _ in range(1800):
        battle.step();minimum=min(minimum,a.congestion_speed)
    assert minimum<.75
    assert all((u.pos-u.order.destination).length()<1 and u.settling_goal is None for u in (a,b))


def test_three_coincident_lines_share_one_firing_frontage_without_immunity():
    units=[Regiment(i,str(i),0,Vec(200,300)) for i in range(3)]
    target=Regiment(3,'enemy',1,Vec(300,300),math.pi)
    battle=Battle([*units,target],seed=17)
    factors=[combat.friendly_fire_factor(battle,u,target) for u in units]
    assert factors==pytest.approx([1/3]*3)
    assert sum(factors)==pytest.approx(1)
    for u in units:combat.fire(battle,u,target)
    assert all(u.analysis['volleys']==1 and u.fire_lane_factor==pytest.approx(1/3) for u in units)
    assert target.strength<240 and all(combat.can_fire(battle,target,u) for u in units)


def test_clear_flank_and_loose_screen_restore_partial_fire():
    shooter=Regiment(0,'shooter',0,Vec(200,300))
    target=Regiment(1,'target',1,Vec(330,300),math.pi)
    friend=Regiment(2,'screen',0,Vec(260,300))
    battle=Battle([shooter,target,friend])
    assert not combat.can_fire(battle,shooter,target)
    friend.formation=Formation.SKIRMISH
    assert combat.can_fire(battle,shooter,target)
    assert 0<combat.friendly_fire_factor(battle,shooter,target)<1
    friend.pos=Vec(260,390)
    assert combat.can_fire(battle,shooter,target) and combat.friendly_fire_factor(battle,shooter,target)==1


def test_elevated_firing_lane_can_clear_a_lower_friend():
    shooter=Regiment(0,'hilltop',0,Vec(200,300))
    target=Regiment(1,'target',1,Vec(330,300),math.pi)
    friend=Regiment(2,'lower screen',0,Vec(260,300))
    terrain=TerrainMap(hills=(Hill(200,300,12,100,15),))
    battle=Battle([shooter,target,friend],terrain=terrain)
    assert combat.can_fire(battle,shooter,target)
    assert combat.friendly_fire_factor(battle,shooter,target)==1


def test_no_nearby_stopping_space_retries_without_pushing_or_changing_orders():
    units=[Regiment(i,str(i),0,Vec(300,300)) for i in range(2)]
    battle=Battle(units,sandbox=True,rules=replace(Rules(),settling_radius=15))
    for _ in range(200):battle.step()
    assert all(u.pos==Vec(300,300) and u.settling_goal is None and u.order.kind==O.HOLD for u in units)
    assert units[1].settling_retry_at>battle.time
    assert all(u.cohesion==100 for u in units)


def test_settling_does_not_override_attack_withdrawal_or_melee():
    units=[Regiment(0,'hold',0,Vec(300,300)),Regiment(1,'attack',0,Vec(300,300),order=Order(O.ATTACK,target_id=2)),
           Regiment(2,'enemy',1,Vec(500,300),math.pi)]
    battle=Battle(units,sandbox=True)
    for _ in range(100):battle.step()
    assert units[1].settling_goal is None
    units[1].order=Order(O.WITHDRAW)
    for _ in range(100):battle.step()
    assert units[1].settling_goal is None


def test_crowded_tick_order_and_seed_are_reproducible():
    config=scenario(36,'Open Field',41)
    a,b=config.create_battle(),config.create_battle()
    for _ in range(400):a.step()
    for _ in range(100):
        for _ in range(4):b.step()
    assert fingerprint(a)==fingerprint(b)
    assert all(0<=u.cohesion<=100 and 0<=u.morale<=100 and u.strength>=0 for u in a.units)


def test_crowded_36_regiment_battle_separates_and_keeps_fighting():
    units=[Regiment(army*18+row*2+k,f'{army}-{row}-{k}',army,
                    Vec(400+army*130,70+row*55),army*math.pi)
           for army in range(2) for row in range(9) for k in range(2)]
    battle=Battle(units,seed=41)
    for _ in range(600):battle.step()
    assert sum(u.analysis['volleys'] for u in units)>50
    assert sum(u.stats.strength-u.strength for u in units)>100
    assert all(intersection_area(a,b)/min(a.width*a.depth,b.width*b.depth)<.25
               for i,a in enumerate(units) for b in units[i+1:]
               if a.army==b.army and a.effective and b.effective)
