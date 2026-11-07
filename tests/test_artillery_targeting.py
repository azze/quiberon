import math
import pytest
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind
from simulation.regiment import Regiment, ARTILLERY, INFANTRY
from simulation import ai, combat, projectiles
from viewer.targeting import target_status


def screened_battery(screen_army=0, screen_x=250):
    gun=Regiment(0,'Battery',0,Vec(200,300),stats=ARTILLERY,
                 order=Order(OrderKind.ATTACK,target_id=2))
    screen=Regiment(1,'Screen',screen_army,Vec(screen_x,300),reload_left=9999)
    target=Regiment(2,'Target',1,Vec(350,300),math.pi,reload_left=9999)
    return Battle([gun,screen,target],seed=17),gun,screen,target


@pytest.mark.parametrize('screen_army',[0,1])
def test_artillery_fires_at_ordered_enemy_through_friendly_or_enemy_screen(screen_army):
    battle,gun,screen,target=screened_battery(screen_army)
    assert combat.firing_blocker(battle,gun,target) is None
    assert combat.can_fire(battle,gun,target)
    assert combat.select_fire_target(battle,gun) is target
    assert ai.destination(battle,gun) is None  # do not walk forward to clear a firing lane
    assert 'ignores line of sight' in target_status(battle,gun,target)
    battle.step()
    assert gun.pos==Vec(200,300)
    assert gun.target_id==target.id and gun.combat_state=='firing'
    assert gun.reload_left>0 and len(battle.projectiles)==gun.available_guns
    assert battle.projectiles[0].owner_id==gun.id
    assert 'blocked' not in target_status(battle,gun,target)


@pytest.mark.parametrize('target_pos,reason',[(Vec(650,300),'range'),(Vec(100,300),'firing arc')])
def test_artillery_still_respects_range_and_facing(target_pos,reason):
    battle,gun,screen,target=screened_battery()
    target.pos=target_pos
    assert not combat.can_fire(battle,gun,target)
    assert reason in target_status(battle,gun,target)
    combat.fire(battle,gun,target)
    assert not battle.projectiles and gun.reload_left==0


def test_artillery_still_respects_reload_and_formation_timer():
    battle,gun,screen,target=screened_battery()
    gun.reload_left=3
    combat.fire(battle,gun,target)
    assert not battle.projectiles and 'Reloading' in target_status(battle,gun,target)
    gun.reload_left=0; gun.transition_left=2
    combat.fire(battle,gun,target)
    assert not battle.projectiles and 'Changing formation' in target_status(battle,gun,target)


@pytest.mark.parametrize('screen_army',[0,1])
def test_infantry_still_requires_line_of_sight(screen_army):
    battle,gun,screen,target=screened_battery(screen_army)
    gun.stats=INFANTRY
    assert (target.pos-gun.pos).length()<=gun.stats.range
    assert combat.firing_blocker(battle,gun,target) is screen
    assert not combat.can_fire(battle,gun,target)
    combat.fire(battle,gun,target)
    assert gun.reload_left==0 and target.strength==target.stats.strength


def test_ignoring_los_does_not_disable_physical_friendly_fire():
    battle,gun,screen,target=screened_battery(screen_x=225)
    combat.fire(battle,gun,target)
    assert len(battle.projectiles)==gun.available_guns
    for _ in range(10): projectiles.update(battle)
    assert screen.strength<screen.stats.strength
    assert 1<=battle.metrics['friendly_fire']<=gun.archetype.guns
