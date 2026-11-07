import math
from dataclasses import replace
import pytest
from simulation.battle import Battle
from simulation.regiment import Regiment, MoraleState
from simulation.geometry import Vec, touching, separation
from simulation.orders import Order, OrderKind
from simulation import ai
from scenarios.battle_config import BattleConfig, ConfigError


def duel(seed):
    horse=Regiment(0,'Uhlans',0,Vec(200,300),archetype_id='commonwealth_uhlans',order=Order(OrderKind.ATTACK,target_id=1))
    gun=Regiment(1,'Battery',1,Vec(350,300),math.pi,archetype_id='artillery')
    return Battle([horse,gun],seed=seed)


@pytest.mark.parametrize('seed',range(1,6))
def test_uhlans_overrun_battery_with_sustained_contact(seed):
    battle=duel(seed); horse,gun=battle.units
    # Isolate crew melee: surviving a six-gun frontal approach is a separate matchup.
    gun.reload_left=9999
    contacted=False; contact_rounds=0
    for _ in range(1400):
        before=gun.strength; volleys=gun.analysis['volleys']
        battle.step()
        if gun.combat_state=='melee':
            contacted=True
            assert gun.analysis['volleys']==volleys
            if gun.strength<before: contact_rounds+=1
        if battle.result: break
    assert contacted and contact_rounds>=1
    assert horse.analysis['casualties_inflicted']>horse.analysis['impact_casualties']
    assert battle.result=='army_0' and horse.effective
    assert gun.state==MoraleState.ROUTING or not gun.active


def test_close_nonoverlapping_rectangles_stay_in_melee_between_resolutions():
    horse=Regiment(0,'horse',0,Vec(300,300),archetype_id='commonwealth_uhlans',order=Order(OrderKind.ATTACK,target_id=1))
    gun=Regiment(1,'gun',1,Vec(318.1,300),math.pi,archetype_id='artillery')
    battle=Battle([horse,gun],seed=3)
    assert separation(horse,gun) is None and touching(horse,gun)
    for _ in range(100):
        battle.step()
        assert horse.combat_state==gun.combat_state=='melee'
        assert gun.analysis['volleys']==0
    assert gun.strength<=43  # At least five sustained resolutions, not just impact.


def test_old_contact_does_not_stop_a_fresh_charge():
    battle=duel(1); horse,gun=battle.units
    horse.pos=Vec(331.5,300)
    battle.tick=500; battle.melee_next[(0,1)]=20
    assert ai.destination(battle,horse)==gun.pos


@pytest.mark.parametrize('key',['cavalry','commonwealth_uhlans'])
def test_cavalry_flank_is_fixed_and_attack_commits(key):
    u=Regiment(0,'cavalry',0,Vec(200,300),archetype_id=key)
    enemy=Regiment(1,'enemy',1,Vec(600,300))
    battle=Battle([u,enemy],ai_armies=(0,))
    ai.army_plan(battle); first=u.order.destination
    enemy.pos+=Vec(30,10); battle.tick=50; ai.army_plan(battle)
    assert u.order.destination==first
    for tick in (100,150,200): battle.tick=tick; ai.army_plan(battle)
    assert u.order.kind==OrderKind.ATTACK and u.order.target_id==enemy.id


def test_standard_artillery_moves_into_range_even_with_infantry():
    gun=Regiment(0,'gun',0,Vec(100,300),archetype_id='artillery')
    friend=Regiment(1,'foot',0,Vec(200,400))
    enemy=Regiment(2,'enemy',1,Vec(800,300))
    battle=Battle([gun,friend,enemy],ai_armies=(0,))
    for _ in range(3200): battle.step()
    assert gun.pos.x>300 and gun.analysis['volleys']>0


@pytest.mark.parametrize('strategy,kind',[('all_out_attack',OrderKind.ATTACK),('hold_the_line',OrderKind.HOLD),('skirmish',OrderKind.SKIRMISH)])
def test_strategies_generate_distinct_orders_and_serialize(strategy,kind,tmp_path):
    config=replace(BattleConfig(seed=17),ai_strategies=(strategy,strategy),ai_armies=(0,1)).prepared()
    battle=config.create_battle(); ai.army_plan(battle)
    assert battle.units[0].order.kind==kind
    path=tmp_path/'strategy.json'; config.save(path)
    assert BattleConfig.load(path)==config
    old=config.to_dict(); old.pop('ai_strategies')
    assert BattleConfig.from_dict(old).ai_strategies==('balanced','balanced')
    a,b=config.create_battle(),config.create_battle()
    for _ in range(150): a.step(); b.step()
    assert a.units==b.units and a.rng.getstate()==b.rng.getstate()


def test_invalid_strategy_fails_validation():
    with pytest.raises(ConfigError): replace(BattleConfig(),ai_strategies=('unknown','balanced')).prepared()


def test_hold_strategy_does_not_advance_when_enemies_are_hidden():
    config=replace(BattleConfig(seed=3),ai_strategies=('hold_the_line','hold_the_line'),ai_armies=(0,1)).prepared()
    battle=config.create_battle(); battle.perceives=lambda a,b:False
    ai.army_plan(battle)
    assert all(u.order.kind==OrderKind.HOLD for u in battle.units if u.stats.kind.value!='artillery')


def test_add_unit_popup_amount_cancel_filters_and_limits(monkeypatch):
    import os
    os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
    import pygame
    from viewer.application import Application
    pygame.init()
    try:
        app=Application(pygame.display.set_mode((1280,800))); menu=app.setup
        original=menu.config
        menu.action('add:0'); menu.action('filter:cavalry'); menu.action('choose:commonwealth_uhlans')
        menu.action('amount:1'); menu.action('amount:1'); app.draw()
        assert menu.amount==3 and menu.config==original
        assert 'confirm_add' in menu.form.buttons
        menu.action('close_info'); assert menu.config==original
        menu.action('add:0'); menu.action('choose:commonwealth_uhlans'); menu.action('amount:1')
        menu.action('confirm_add')
        assert menu.config.blue.count('commonwealth_uhlans')==menu.config.red.count('commonwealth_uhlans')==2
        assert menu.info_open is None
        menu.action('strategy:1'); assert menu.config.ai_strategies[1]=='all_out_attack'
        menu.action('add:0'); menu.action('choose:commonwealth_uhlans'); menu.amount=12
        before=menu.config; menu.action('confirm_add'); assert menu.config==before
    finally: pygame.quit()
