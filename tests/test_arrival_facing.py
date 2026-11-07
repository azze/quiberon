"""Destination-facing commands, deterministic arrival, and shared GUI gesture."""
import math
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from simulation.battle import Battle
from simulation.geometry import Vec, angle_delta
from simulation.formations import Formation, PROFILES
from simulation.regiment import Regiment, INFANTRY, CAVALRY, ARTILLERY, MoraleState
from simulation.orders import Command, Order, OrderKind
from scenarios.battle_config import ArmyConfig, BattleConfig, ConfigError
from viewer.application import Application
from viewer.controls import Controls
from viewer.camera import Camera
from viewer.renderer import Renderer


@pytest.mark.parametrize('stats,formation',[(INFANTRY,Formation.LINE),(INFANTRY,Formation.COLUMN),
                                          (CAVALRY,Formation.LINE),(ARTILLERY,Formation.LINE)])
def test_arrives_then_turns_at_normal_rate_and_holds_facing(stats,formation):
    goal=Vec(250,300)
    u=Regiment(0,'mover',0,Vec(200,300),stats=stats,formation=formation,
               order=Order(OrderKind.MOVE,goal,facing=math.pi/2))
    battle=Battle([u],sandbox=True)
    turning=False
    for _ in range(800):
        before,heading=u.pos,u.facing
        battle.step()
        assert abs(angle_delta(heading,u.facing))<=stats.turn_rate*PROFILES[formation][3]*.1+1e-9
        if (before-goal).length()>=1:
            assert abs(u.facing)<1e-8  # Arrival heading never steers the approach.
        elif abs(angle_delta(heading,u.facing))>1e-8:
            turning=True
            assert u.pos==before and u.speed==0
    assert turning and (u.pos-goal).length()<1
    assert abs(angle_delta(u.facing,math.pi/2))<1e-8


def test_turn_in_place_shortest_angle_and_transition_delays_rotation():
    u=Regiment(0,'turn',0,Vec(200,300),math.pi-.1,
               order=Order(OrderKind.MOVE,Vec(200,300),facing=-math.pi+.1),
               transition_left=.2,next_formation=Formation.COLUMN)
    battle=Battle([u],sandbox=True)
    battle.step(); assert u.facing==math.pi-.1
    battle.step(); assert u.facing==math.pi-.1
    battle.step(); assert u.facing>math.pi-.1
    for _ in range(20): battle.step()
    assert u.pos==Vec(200,300)
    assert abs(angle_delta(u.facing,-math.pi+.1))<1e-8


def test_arrival_facing_does_not_override_routing_or_new_orders():
    u=Regiment(0,'route',0,Vec(300,300),order=Order(OrderKind.MOVE,Vec(300,300),facing=math.pi/2))
    battle=Battle([u],sandbox=True)
    u.state=MoraleState.ROUTING
    for _ in range(120): battle.step()
    assert u.pos.x<300 and abs(angle_delta(u.facing,math.pi))<.2
    u.state=MoraleState.STEADY
    battle.issue(Command(u.id,Order(OrderKind.MOVE,Vec(400,300))))
    for _ in range(1400): battle.step()
    assert (u.pos-Vec(400,300)).length()<1 and abs(angle_delta(u.facing,0))<.01
    assert u.order.facing is None


def recipe():
    return BattleConfig(blue=ArmyConfig(1,0,0),red=ArmyConfig(1,0,0),seed=19,ai_armies=()).prepared()


def test_facing_roundtrip_old_configs_and_reproducible_headless_battles(tmp_path):
    config=recipe()
    placement=config.placements[0]
    config=replace(config,placements=(replace(placement,order=Order(OrderKind.MOVE,Vec(300,300),facing=1.4)),config.placements[1]))
    path=tmp_path/'facing.json'; config.save(path)
    assert BattleConfig.load(path)==config
    a,b=config.create_battle(),BattleConfig.load(path).create_battle()
    for _ in range(500): a.step(); b.step()
    assert a.units==b.units and a.rng.getstate()==b.rng.getstate()
    old=config.to_dict()
    for p in old['placements']: p['order'].pop('facing')
    assert all(p.order.facing is None for p in BattleConfig.from_dict(old).placements)
    for value in (float('nan'),float('inf'),True,'east'):
        data=config.to_dict(); data['placements'][0]['order']['facing']=value
        with pytest.raises(ConfigError,match='finite angle'): BattleConfig.from_dict(data)


@pytest.fixture
def ui():
    pygame.init()
    screen=pygame.display.set_mode((1280,800))
    yield screen
    pygame.quit()


def event(kind,**kwargs): return pygame.event.Event(kind,**kwargs)


@pytest.mark.parametrize('zoom',[.4,1.,2.])
def test_drag_previews_then_commits_world_heading_and_click_keeps_default(ui,zoom):
    battle=Battle([Regiment(0,'mover',0,Vec(300,300))],sandbox=True)
    camera=Camera(height=800,zoom=zoom); controls=Controls(); controls.selected=0
    anchor=camera.world_to_screen(Vec(500,300))
    end=camera.world_to_screen(Vec(500,350))
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
    controls.handle(event(pygame.MOUSEMOTION,pos=end),battle,camera)
    assert not battle.commands
    gesture=controls.move_gesture
    assert gesture.destination==Vec(500,300) and gesture.facing==pytest.approx(math.pi/2)
    before=repr(battle.units),battle.rng.getstate()
    renderer=Renderer(ui,camera); renderer.draw(battle,controls)
    assert before==(repr(battle.units),battle.rng.getstate())
    # A forward arrow is visible past the ghost's front edge.
    arrow=camera.world_to_screen(Vec(500,320))
    assert ui.get_at((round(arrow[0]),round(arrow[1])))[:3]==(100,245,155)
    controls.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=end),battle,camera)
    order=battle.commands[-1].order
    assert order.destination==Vec(500,300) and order.facing==pytest.approx(math.pi/2)
    assert controls.move_gesture is None
    battle.step(); renderer.draw(battle,controls)
    assert ui.get_at((round(arrow[0]),round(arrow[1])))[:3]==(240,223,129)
    # Short click / hand jitter retains the original automatic arrival heading.
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
    controls.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=(anchor[0]+2,anchor[1]+1)),battle,camera)
    assert battle.commands[-1].order.facing is None


def test_cancel_focus_loss_dead_unit_and_hud_release_do_not_issue_moves(ui):
    unit=Regiment(0,'unit',0,Vec(300,300))
    battle=Battle([unit],sandbox=True); camera=Camera(height=800); controls=Controls(); controls.selected=0
    anchor=camera.world_to_screen(Vec(500,300))
    for cancel in (event(pygame.KEYDOWN,key=pygame.K_ESCAPE),event(pygame.WINDOWFOCUSLOST),
                   event(pygame.MOUSEBUTTONUP,button=3,pos=(640,780))):
        controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
        controls.handle(cancel,battle,camera)
        controls.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=anchor),battle,camera)
        assert not battle.commands and controls.move_gesture is None and controls.selected==0
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
    unit.strength=0
    controls.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=anchor),battle,camera)
    assert not battle.commands


def test_shift_advance_drag_enemy_click_and_boundary_preview(ui,monkeypatch):
    shooter=Regiment(0,'unit',0,Vec(300,300)); enemy=Regiment(1,'enemy',1,Vec(550,300),math.pi)
    battle=Battle([shooter,enemy]); camera=Camera(height=800); controls=Controls(); controls.selected=0
    monkeypatch.setattr(pygame.key,'get_mods',lambda:pygame.KMOD_SHIFT)
    anchor=camera.world_to_screen(Vec(500,300)); end=camera.world_to_screen(Vec(500,250))
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
    controls.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=end),battle,camera)
    assert battle.commands[-1].order.kind==OrderKind.ADVANCE
    assert battle.commands[-1].order.facing==pytest.approx(-math.pi/2)
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=camera.world_to_screen(enemy.pos)),battle,camera)
    assert battle.commands[-1].order==Order(OrderKind.ATTACK,target_id=enemy.id)
    anchor=camera.world_to_screen(Vec(1,1))
    controls.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor),battle,camera)
    ghost=controls.move_gesture
    for facing in (0,math.pi/4,math.pi/2):
        preview=replace(shooter,pos=ghost.destination,facing=facing)
        assert all(0<=p.x<=battle.rules.width and 0<=p.y<=battle.rules.height for p in preview.footprint)


def test_advance_arrival_heading_is_not_overwritten_by_nearby_enemy():
    shooter=Regiment(0,'unit',0,Vec(300,300),order=Order(OrderKind.ADVANCE,Vec(300,300),facing=math.pi/2))
    enemy=Regiment(1,'enemy',1,Vec(420,300),math.pi)
    battle=Battle([shooter,enemy],sandbox=True)
    for _ in range(200): battle.step()
    assert shooter.pos==Vec(300,300) and abs(angle_delta(shooter.facing,math.pi/2))<1e-8


def test_facing_order_finishes_friendly_detour_before_final_turn():
    mover=Regiment(0,'unit',0,Vec(200,300),order=Order(OrderKind.MOVE,Vec(600,300),facing=1.2))
    screen=Regiment(1,'screen',0,Vec(360,300))
    battle=Battle([mover,screen],sandbox=True)
    detoured=False
    for _ in range(3000):
        battle.step()
        detoured|=mover.avoidance_goal is not None
    assert detoured and (mover.pos-Vec(600,300)).length()<1
    assert abs(angle_delta(mover.facing,1.2))<1e-8 and mover.speed==0


def test_deployment_shared_drag_valid_invalid_cancel_and_save(ui,tmp_path):
    app=Application(ui,path=str(tmp_path/'deployment.json')); app.deploy(recipe())
    deployment=app.deployment; deployment.selected=0
    start=deployment.session.config
    anchor=app.camera.world_to_screen(Vec(160,300))
    end=app.camera.world_to_screen(Vec(160,360))
    app.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor))
    app.handle(event(pygame.MOUSEMOTION,pos=end))
    assert deployment.valid and deployment.ghost.facing==pytest.approx(math.pi/2)
    app.draw()
    assert deployment.session.config==start and deployment.battle.tick==0
    app.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=end))
    p=deployment.session.config.placements[0]
    assert p.pos==Vec(160,300) and p.facing==pytest.approx(math.pi/2)
    committed=deployment.session.config
    # Invalid zone is shown red and cannot modify the stored layout.
    bad=app.camera.world_to_screen(Vec(500,300))
    app.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=bad))
    assert not deployment.valid
    app.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=bad))
    assert not deployment.valid and deployment.session.config==committed
    app.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor))
    app.handle(event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
    assert app.phase=='deployment' and deployment.facing_gesture is None and deployment.ghost is None
    app.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=end))
    assert deployment.session.config==committed
    deployment.button('save')
    assert BattleConfig.load(deployment.path)==committed
    app.start(committed)
    assert app.battle.unit(0).facing==p.facing and app.battle.unit(0).pos==p.pos


def test_deployment_rotation_into_neighbour_rejects_entire_gesture(ui):
    config=BattleConfig(blue=ArmyConfig(2,0,0),red=ArmyConfig(1,0,0),symmetric=False,seed=1).prepared()
    a,b,enemy=config.placements
    config=replace(config,placements=(replace(a,pos=Vec(160,300)),replace(b,pos=Vec(190,300)),enemy))
    app=Application(ui); app.deploy(config); app.deployment.selected=a.id
    anchor=app.camera.world_to_screen(Vec(160,300)); end=app.camera.world_to_screen(Vec(160,350))
    app.handle(event(pygame.MOUSEBUTTONDOWN,button=3,pos=anchor))
    assert app.deployment.valid
    app.handle(event(pygame.MOUSEMOTION,pos=end))
    assert not app.deployment.valid and app.deployment.ghost.facing==pytest.approx(math.pi/2)
    app.handle(event(pygame.MOUSEBUTTONUP,button=3,pos=end))
    assert app.deployment.session.config==config and not app.deployment.valid
