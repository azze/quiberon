import math
import pytest
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.orders import Order, OrderKind, Command
from simulation.regiment import Regiment, MoraleState
from simulation import ai, combat
from viewer.targeting import current_target, ordered_target, target_status


def engagement():
    shooter=Regiment(0,'Selected infantry',0,Vec(200,300),order=Order(OrderKind.ATTACK,target_id=2))
    near=Regiment(1,'Near enemy',1,Vec(270,270),math.pi)
    ordered=Regiment(2,'Ordered enemy',1,Vec(315,330),math.pi)
    return Battle([shooter,near,ordered],seed=17),shooter,near,ordered


def test_volley_prefers_valid_ordered_target_over_nearest():
    battle,shooter,near,ordered=engagement()
    assert combat.can_fire(battle,shooter,near) and combat.can_fire(battle,shooter,ordered)
    battle.step()
    assert shooter.target_id==ordered.id
    assert ordered.strength<ordered.stats.strength
    assert near.strength==near.stats.strength
    assert current_target(battle,shooter) is ordered


def test_explicit_attack_keeps_focus_while_approaching_out_of_range_target():
    battle,shooter,near,ordered=engagement()
    ordered.pos=Vec(500,330)
    battle.step()
    assert shooter.target_id==ordered.id and near.strength==near.stats.strength
    assert shooter.reload_left==0
    assert shooter.pos.x>200
    assert current_target(battle,shooter) is ordered
    assert ordered_target(battle,shooter) is ordered


def test_target_feedback_explains_range_arc_blocking_and_reload():
    battle,shooter,near,ordered=engagement()
    assert 'clear line of sight' in target_status(battle,shooter,ordered)
    shooter.reload_left=5
    assert target_status(battle,shooter,ordered)=='Reloading: 5.0s'
    ordered.pos=Vec(500,330)
    assert 'Out of range' in target_status(battle,shooter,ordered)
    ordered.pos=Vec(100,300)
    assert 'firing arc' in target_status(battle,shooter,ordered)
    ordered.pos=Vec(315,330)
    battle.units.append(Regiment(3,'Friendly screen',0,Vec(255,315)))
    assert 'Friendly screen [#3]' in target_status(battle,shooter,ordered)
    assert 'Moving to clear' in target_status(battle,shooter,ordered)
    shooter.transition_left=2
    assert target_status(battle,shooter,ordered)=='Changing formation — cannot fire'


def test_retreat_clears_target_and_display_filters_invalid_targets():
    battle,shooter,near,ordered=engagement()
    shooter.target_id=near.id
    assert current_target(battle,shooter) is near
    near.strength=0
    assert current_target(battle,shooter) is None
    shooter.target_id=shooter.id
    assert current_target(battle,shooter) is None
    for state in (MoraleState.ROUTING,MoraleState.RALLYING):
        shooter.state=state; shooter.target_id=ordered.id
        ai.destination(battle,shooter)
        assert shooter.target_id is None and current_target(battle,shooter) is None
    shooter.state=MoraleState.STEADY
    shooter.order=Order(OrderKind.WITHDRAW)
    shooter.target_id=ordered.id
    ai.destination(battle,shooter)
    assert shooter.target_id is None
    # Withdrawal still permits existing automatic fire; show its real aim target.
    battle.step()
    assert shooter.target_id == ordered.id
    assert current_target(battle,shooter) is ordered


@pytest.mark.parametrize('start,target_x',[(200,300),(250,350)])
def test_attack_joins_a_separate_screen_or_fires_from_existing_soft_overlap(start,target_x):
    shooter=Regiment(0,'Shooter',0,Vec(start,300))
    friend=Regiment(1,'Friendly screen',0,Vec(250,300),reload_left=9999)
    target=Regiment(2,'Target',1,Vec(target_x,300),math.pi,reload_left=9999)
    battle=Battle([shooter,friend,target],seed=17)
    battle.issue(Command(0,Order(OrderKind.ATTACK,target_id=2)))
    assert (target.pos-shooter.pos).length()<=shooter.stats.range
    assert combat.can_fire(battle,shooter,target)==(start==250)
    for _ in range(600):
        battle.step()
        if shooter.combat_state=='firing': break
    assert shooter.combat_state=='firing'
    assert friend.id in combat.firing_groups(battle)[shooter.id]
    assert shooter.pos.x>=start
    assert shooter.target_id==target.id
    assert target.strength<target.stats.strength
    assert friend.pos==Vec(250,300)


def test_manual_attack_survives_ai_replan_and_turns_to_enemy_behind():
    shooter=Regiment(0,'Shooter',0,Vec(200,300))
    near=Regiment(1,'Front enemy',1,Vec(300,300),math.pi,reload_left=9999)
    ordered=Regiment(2,'Ordered rear enemy',1,Vec(100,300),reload_left=9999)
    battle=Battle([shooter,near,ordered],seed=17,ai_armies={0})
    battle.issue(Command(0,Order(OrderKind.ATTACK,target_id=2)))
    for _ in range(90): battle.step()
    assert shooter.player_attack
    assert shooter.order==Order(OrderKind.ATTACK,target_id=2)
    assert shooter.ai_state=='player attack order'
    assert shooter.target_id==ordered.id
    assert ordered.strength<ordered.stats.strength
    assert near.strength==near.stats.strength
    assert shooter.pos==Vec(200,300)


def test_player_attack_protection_ends_when_target_dies_or_order_changes():
    battle,shooter,near,ordered=engagement()
    battle.ai_armies={0}
    battle.issue(Command(0,Order(OrderKind.ATTACK,target_id=2))); battle.step()
    assert shooter.player_attack
    ordered.strength=0
    battle.tick=50; ai.army_plan(battle)
    assert not shooter.player_attack
    assert shooter.order.kind!=OrderKind.ATTACK
    battle.issue(Command(0,Order(OrderKind.ATTACK,target_id=1))); battle.step()
    assert shooter.player_attack
    battle.issue(Command(0,Order(OrderKind.HOLD))); battle.step()
    assert not shooter.player_attack and shooter.order.kind==OrderKind.HOLD


def test_explicit_attack_does_not_shoot_an_intervening_enemy_instead():
    shooter=Regiment(0,'Shooter',0,Vec(200,300),order=Order(OrderKind.ATTACK,target_id=2))
    blocker=Regiment(1,'Blocking enemy',1,Vec(275,300),math.pi,reload_left=9999)
    target=Regiment(2,'Ordered enemy',1,Vec(350,300),math.pi,reload_left=9999)
    battle=Battle([shooter,blocker,target])
    for _ in range(100): battle.step()
    assert shooter.target_id==target.id and shooter.reload_left==0
    assert shooter.pos==Vec(200,300)
    assert blocker.strength==blocker.stats.strength and target.strength==target.stats.strength
    assert 'Blocking enemy [#1]' in target_status(battle,shooter,target)
    assert 'blocked' in target_status(battle,shooter,target)


def test_dead_ordered_target_allows_automatic_fallback():
    battle,shooter,near,ordered=engagement()
    ordered.strength=0
    battle.step()
    assert shooter.target_id==near.id
    assert near.strength<near.stats.strength


def test_switching_attack_target_preserves_reload_timer():
    battle,shooter,near,ordered=engagement()
    near.reload_left=ordered.reload_left=9999
    battle.step()
    reload=shooter.reload_left
    old_strength=ordered.strength
    battle.issue(Command(0,Order(OrderKind.ATTACK,target_id=1)))
    for _ in range(30): battle.step()
    assert shooter.target_id==near.id
    assert shooter.reload_left==pytest.approx(reload-3)
    assert near.strength==near.stats.strength
    for _ in range(110): battle.step()
    assert near.strength<near.stats.strength
    assert ordered.strength==old_strength
