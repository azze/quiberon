"""Soft-overlap groups must neither suppress fire nor become immune to it."""
import math
import pytest
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.regiment import Regiment, ARTILLERY
from simulation.formations import Formation
from simulation.orders import Order,OrderKind
from simulation import combat, projectiles
from simulation.terrain import TerrainMap, Hill, Forest


def unit(uid,army,x,y=300,facing=None,formation=Formation.LINE):
    return Regiment(uid,f'Unit {uid}',army,Vec(x,y),
                    (0 if army==0 else math.pi) if facing is None else facing,
                    formation=formation)


@pytest.mark.parametrize('formation',list(Formation))
def test_overlapping_friendly_regiments_can_both_fire(formation):
    a,b=unit(0,0,200,formation=formation),unit(1,0,200,formation=formation)
    enemy=unit(2,1,300)
    battle=Battle([a,b,enemy],seed=17)
    for shooter in (a,b):
        assert combat.can_fire(battle,shooter,enemy)
        combat.fire(battle,shooter,enemy)
        assert shooter.combat_state=='firing' and shooter.reload_left>0
    assert enemy.strength<enemy.stats.strength


def test_overlapping_enemies_can_each_be_targeted_and_damaged():
    shooter,a,b=unit(0,0,200),unit(1,1,300),unit(2,1,300)
    battle=Battle([shooter,a,b],seed=17)
    for target in (a,b):
        shooter.order=Order(OrderKind.ATTACK,target_id=target.id)
        assert combat.select_fire_target(battle,shooter) is target
        combat.fire(battle,shooter,target)
        assert target.strength<target.stats.strength
        shooter.reload_left=0


def test_two_overlapping_groups_exchange_fire_in_real_ticks():
    units=[unit(0,0,200),unit(1,0,200),unit(2,1,300),unit(3,1,300)]
    battle=Battle(units,seed=17)
    battle.step()
    assert all(u.combat_state=='firing' and u.reload_left>0 for u in units)
    assert sum(u.strength for u in units if u.army==0)<480
    assert sum(u.strength for u in units if u.army==1)<480


def test_connected_partial_overlaps_do_not_grant_fire_through_separate_front_rank():
    # Each line is 12m deep: neighbours overlap, endpoints do not.
    source=[unit(i,0,200+i*8) for i in range(3)]
    target=[unit(3+i,1,300+i*8) for i in range(3)]
    battle=Battle(source+target)
    assert combat.firing_groups(battle)[0]==frozenset((0,1,2))
    assert not combat.can_fire(battle,source[0],target[0])
    assert combat.can_fire(battle,source[-1],target[0])


def test_rotated_overlaps_are_detected_by_footprints():
    shooter=unit(0,0,200)
    overlap=unit(1,0,203,facing=math.pi/4)
    target=unit(2,1,300)
    battle=Battle([shooter,overlap,target])
    assert combat.firing_groups(battle)[0]==frozenset((0,1))
    assert combat.can_fire(battle,shooter,target)


@pytest.mark.parametrize('screen_army',[0,1])
def test_separate_screen_still_blocks_overlapping_shooters_and_targets(screen_army):
    units=[unit(0,0,200),unit(1,0,200),unit(2,1,300),unit(3,1,300),unit(4,screen_army,250)]
    battle=Battle(units)
    assert combat.firing_blocker(battle,units[0],units[2]) is units[4]
    assert not combat.can_fire(battle,units[0],units[2])


def test_edge_touching_is_not_a_soft_overlap_group():
    shooter=unit(0,0,200); screen=unit(1,0,212); target=unit(2,1,300)
    battle=Battle([shooter,screen,target])
    assert combat.firing_groups(battle)[0]==frozenset((0,))
    assert combat.firing_blocker(battle,shooter,target) is screen


def test_groups_do_not_merge_across_armies():
    shooter=unit(0,0,200); enemy_contact=unit(1,1,200); target=unit(2,1,300)
    battle=Battle([shooter,enemy_contact,target])
    assert combat.firing_groups(battle)[0]==frozenset((0,))
    assert combat.firing_blocker(battle,shooter,target) is enemy_contact


def test_group_cache_tracks_movement_rotation_formation_death_and_withdrawal():
    shooter,friend,target=unit(0,0,200),unit(1,0,204),unit(2,1,300)
    battle=Battle([shooter,friend,target])
    original=combat.firing_groups(battle)
    assert combat.firing_groups(battle) is original
    assert combat.can_fire(battle,shooter,target)
    friend.pos=Vec(225,300)
    assert not combat.can_fire(battle,shooter,target)
    friend.facing=math.pi/2  # wide frontage now extends through shooter
    assert combat.can_fire(battle,shooter,target)
    friend.facing=0; friend.formation=Formation.COLUMN
    assert combat.can_fire(battle,shooter,target)
    assert 0<combat.friendly_fire_factor(battle,shooter,target)<1
    friend.withdrawn=True
    assert combat.can_fire(battle,shooter,target)
    friend.withdrawn=False; friend.strength=0
    assert combat.can_fire(battle,shooter,target)


@pytest.mark.parametrize('terrain',[TerrainMap(hills=(Hill(250,300,15,100,25),)),
                                   TerrainMap(forests=(Forest(250,300,100,100,1),))])
def test_soft_overlap_does_not_bypass_terrain_visibility(terrain):
    units=[unit(0,0,200),unit(1,0,200),unit(2,1,300),unit(3,1,300)]
    battle=Battle(units,terrain=terrain)
    assert combat.firing_blocker(battle,units[0],units[2]) is None
    assert not battle.visibility(units[0],units[2]).visible
    assert not combat.can_fire(battle,units[0],units[2])


def test_cannonballs_still_physically_hit_each_overlapping_regiment():
    gun=Regiment(0,'gun',0,Vec(100,300),stats=ARTILLERY)
    a,b=unit(1,0,180),unit(2,0,180)
    battle=Battle([gun,a,b],seed=17)
    ball=projectiles.Projectile(Vec(150,300),Vec(1000,0),1,0,gun.id)
    battle.projectiles=[ball]
    projectiles.update(battle)
    assert a.strength<240 and b.strength<240
    assert {a.id,b.id}<=ball.hit_ids
    assert battle.metrics['friendly_fire']==2
