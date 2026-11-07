"""Idle player deployment and clickable commands using the existing command queue."""
import math
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from scenarios.battle_config import BattleConfig,ArmyConfig,DeploymentSession
from scenarios.standard_battle import create as standard
from simulation.archetypes import ARCHETYPES
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.regiment import Regiment,UnitType,MoraleState
from simulation.formations import Formation as F
from simulation.orders import Order,OrderKind as O
from viewer.controls import Controls
from viewer.camera import Camera
from viewer.command_bar import buttons
from viewer.application import Application
from analysis.performance import fingerprint


def test_all_new_player_archetypes_start_holding_and_ai_armies_retain_plans():
    roster=ArmyConfig(1,1,1,tuple((key,1) for key in ARCHETYPES if key not in ('infantry','cavalry','artillery')))
    config=BattleConfig(seed=17,blue=roster,red=roster).prepared()
    assert all(p.order==Order(O.HOLD) for p in config.placements if p.army==0)
    assert any(p.order.kind!=O.HOLD for p in config.placements if p.army==1)
    battle=config.create_battle();positions={u.id:u.pos for u in battle.units if u.army==0}
    for _ in range(50):battle.step()
    assert all(u.order==Order(O.HOLD) and u.pos==positions[u.id] for u in battle.units if u.army==0)
    spectator=replace(config,placements=(),ai_armies=(0,1)).prepared()
    assert any(p.order.kind!=O.HOLD for p in spectator.placements if p.army==0)


def test_standard_scenario_idles_player_but_spectator_and_explicit_deployment_orders_work():
    assert all(u.order==Order(O.HOLD) for u in standard(17).units if u.army==0)
    assert any(u.order.kind!=O.HOLD for u in standard(17,spectator=True).units if u.army==0)
    editor=DeploymentSession(BattleConfig(seed=17));p=editor.config.placements[0]
    order=Order(O.ADVANCE,Vec(500,p.pos.y),facing=.3)
    editor.edit(p.id,order=order)
    assert editor.config.create_battle().unit(p.id).order==order


@pytest.fixture
def screen():
    pygame.init();yield pygame.display.set_mode((1280,800));pygame.quit()


def pair(key='infantry'):
    u=Regiment(0,'friendly',0,Vec(250,300),archetype_id=key)
    enemy=Regiment(1,'enemy',1,Vec(550,300),math.pi,reload_left=9999)
    b=Battle([u,enemy],generate_commanders=False);c=Controls();c.selected=0
    return b,c,Camera(width=1280,height=800)


def click_button(b,c,camera,key):
    button=next(item for item in buttons(camera.width,camera.height,b,c) if item.key==key)
    c.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=button.rect.center),b,camera)
    return button


def click_world(b,c,camera,point,button=1):
    c.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=button,pos=camera.world_to_screen(point)),b,camera)


@pytest.mark.parametrize('kind',[O.HOLD,O.RESERVE,O.WITHDRAW,O.SKIRMISH])
def test_immediate_order_buttons_issue_one_command_and_preserve_selection(screen,kind):
    b,c,camera=pair();click_button(b,c,camera,'order:'+kind.value)
    assert len(b.commands)==1 and b.commands[0].order==Order(kind) and c.selected==0
    b.step();assert b.units[0].order==Order(kind) and b.units[0].player_order


@pytest.mark.parametrize('kind',[O.ATTACK,O.CHARGE])
def test_targeted_order_buttons_wait_for_an_enemy_and_never_click_through_ui(screen,kind):
    b,c,camera=pair();click_button(b,c,camera,'order:'+kind.value)
    assert c.pending_order==kind and not b.commands and c.selected==0
    click_world(b,c,camera,b.units[0].pos)
    assert not b.commands and c.pending_order==kind and c.selected==0
    click_world(b,c,camera,b.units[1].pos)
    assert len(b.commands)==1 and b.commands[0].order==Order(kind,target_id=1)
    assert c.pending_order is None and c.selected==0


@pytest.mark.parametrize('kind',[O.MOVE,O.ADVANCE])
def test_ground_buttons_support_dragged_arrival_facing_and_ghost(screen,kind):
    b,c,camera=pair();click_button(b,c,camera,'order:'+kind.value)
    target=Vec(400,300);click_world(b,c,camera,target)
    assert c.move_gesture is not None and c.move_gesture.destination==target and not b.commands
    end=camera.world_to_screen(target+Vec(0,70))
    c.handle(pygame.event.Event(pygame.MOUSEMOTION,pos=end),b,camera)
    c.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=end),b,camera)
    assert len(b.commands)==1 and c.move_gesture is None
    order=b.commands[0].order
    assert order.kind==kind and order.destination==target and order.facing==pytest.approx(math.pi/2)


def test_defend_button_sets_an_area_and_escape_cancels_pending_commands_first(screen):
    b,c,camera=pair();click_button(b,c,camera,'order:defend')
    click_world(b,c,camera,Vec(450,350))
    assert b.commands[0].order==Order(O.DEFEND,Vec(450,350))
    b.commands.clear();click_button(b,c,camera,'order:charge')
    c.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE),b,camera)
    assert c.pending_order is None and not b.commands and c.selected==0 and c.running


@pytest.mark.parametrize('key',list(ARCHETYPES))
def test_formation_and_order_buttons_respect_archetype_capabilities(screen,key):
    b,c,camera=pair(key);u=b.units[0]
    entries={e.key:e for e in buttons(camera.width,camera.height,b,c)}
    for formation in F:
        expected=u.stats.kind==UnitType.INFANTRY and formation in u.archetype.formations
        assert entries['formation:'+formation.value].enabled==expected
    assert entries['order:charge'].enabled==(u.stats.kind!=UnitType.ARTILLERY)
    assert entries['order:skirmish'].enabled==(u.stats.kind==UnitType.INFANTRY)
    u.state=MoraleState.ROUTING
    assert not any(e.enabled for e in buttons(camera.width,camera.height,b,c))
    click_button(b,c,camera,'order:hold');assert not b.commands


def test_formation_buttons_apply_through_simulation_and_ui_disables_during_transition(screen):
    b,c,camera=pair();click_button(b,c,camera,'formation:column');b.step()
    assert b.units[0].next_formation==F.COLUMN and b.units[0].transition_left>0
    assert not any(e.enabled for e in buttons(camera.width,camera.height,b,c) if e.key.startswith('formation:'))


@pytest.mark.parametrize('size',[(960,640),(1280,800),(1920,1080)])
def test_button_layout_is_visible_disjoint_and_rendering_is_read_only(screen,size):
    screen=pygame.display.set_mode(size)
    app=Application(screen);app.start(BattleConfig(seed=17));app.controls.selected=0
    before=fingerprint(app.battle);app.draw()
    entries=buttons(*size,app.battle,app.controls)
    assert len(entries)==12
    for entry in entries:
        assert screen.get_rect().contains(entry.rect) and entry.rect.top>=size[1]-150
        assert not any(entry.rect.colliderect(other.rect) for other in entries if other is not entry)
    assert fingerprint(app.battle)==before
    # Resized input hit tests use the same rectangles, without depending on old drawing.
    app.camera.width,app.camera.height=size
    click_button(app.battle,app.controls,app.camera,'order:hold')
    assert app.battle.commands[0].order==Order(O.HOLD)


def test_restart_and_rematch_restore_idle_orders_and_clear_targeting_mode(screen):
    app=Application(screen);app.start(BattleConfig(seed=17));app.controls.selected=0
    app.controls.action('order:charge',app.battle);app.restart()
    assert app.controls.pending_order is None
    assert all(u.order==Order(O.HOLD) for u in app.battle.units if u.army==0)
    app.restart(True)
    assert all(u.order==Order(O.HOLD) for u in app.battle.units if u.army==0)


def test_finished_battle_disables_commands_and_unsupported_clicks_do_nothing(screen):
    b,c,camera=pair('artillery')
    click_button(b,c,camera,'order:charge');click_button(b,c,camera,'formation:column')
    assert not b.commands and c.pending_order is None and c.selected==0
    b.result='army_0'
    assert not any(e.enabled for e in buttons(camera.width,camera.height,b,c))
    click_button(b,c,camera,'order:hold');assert not b.commands


def test_switching_from_ai_to_player_clears_orders_without_losing_deployment_or_commanders():
    config=BattleConfig(seed=17,ai_armies=(0,1)).prepared()
    player=config.with_ai_armies((1,))
    assert all(p.order==Order(O.HOLD) for p in player.placements if p.army==0)
    assert [(p.id,p.pos,p.facing,p.commander) for p in player.placements]==[(p.id,p.pos,p.facing,p.commander) for p in config.placements]
    restored=player.with_ai_armies((0,1))
    assert [p.order for p in restored.placements]==[p.order for p in config.placements]
    assert any(u.order.kind!=O.HOLD for u in player.create_battle(spectator=True).units if u.army==0)
