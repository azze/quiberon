import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from viewer.application import Application
from scenarios.battle_config import ArmyConfig, BattleConfig
from simulation.geometry import Vec
from simulation.formations import Formation
from simulation.orders import OrderKind

@pytest.fixture
def app(tmp_path):
    pygame.init()
    screen=pygame.display.set_mode((1024,720),pygame.RESIZABLE)
    app=Application(screen,path=str(tmp_path/'battle.json'))
    app.draw()
    yield app
    pygame.quit()


def click(app,key,form=None):
    app.draw()
    form=form or (app.setup.form if app.phase=='setup' else app.deployment.form)
    rect=form.buttons[key][0]
    point=(round(rect.centerx*form.scale+form.origin[0]),round(rect.centery*form.scale+form.origin[1]))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point))
    return point


def test_ui_setup_symmetry_sizes_save_load_and_errors(app):
    click(app,'count:0:infantry:1')
    assert app.setup.config.blue.infantry==app.setup.config.red.infantry==5
    click(app,'symmetric'); click(app,'count:1:cavalry:1')
    assert app.setup.config.blue.cavalry==1 and app.setup.config.red.cavalry==2
    click(app,'size:Large')
    click(app,'save')
    saved=BattleConfig.load(app.setup.path)
    assert saved.seed is not None and saved.width==1600
    click(app,'size:Small'); click(app,'load')
    assert app.setup.config==saved
    app.setup.seed_text='-'
    click(app,'deploy'); assert app.phase=='setup' and 'integer' in app.setup.message
    app.setup.seed_text='17'; click(app,'deploy')
    assert app.phase=='deployment' and app.deployment.session.config.seed==17


def test_frozen_deployment_drag_invalid_rotate_orders_and_start(app):
    click(app,'deploy')
    preview=app.deployment.battle
    before=repr(preview.units)
    for _ in range(10): app.update(.1); app.draw()
    assert preview.tick==0 and repr(preview.units)==before
    unit=preview.units[0]
    origin=app.camera.world_to_screen(unit.pos)
    goal=app.camera.world_to_screen(unit.pos+Vec(-20,0))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=origin))
    app.handle(pygame.event.Event(pygame.MOUSEMOTION,pos=goal))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=goal))
    assert app.deployment.session.config.placements[0].pos==unit.pos+Vec(-20,0)
    saved=app.deployment.session.config
    app.deployment.attempt(pos=Vec(500,300))
    assert not app.deployment.valid and app.deployment.session.config==saved
    for key in (pygame.K_c,pygame.K_q,pygame.K_h):
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=key))
    p=app.deployment.session.config.placements[0]
    assert p.formation==Formation.COLUMN and p.order.kind==OrderKind.HOLD and p.facing!=0
    click(app,'save')
    assert BattleConfig.load(app.deployment.path)==app.deployment.session.config
    click(app,'start')
    assert app.phase=='battle' and app.battle.tick==0
    assert app.battle.units[0].pos==p.pos and app.battle.units[0].formation==Formation.COLUMN
    app.update(.1); assert app.battle.tick==1


def test_app_restart_rematch_and_edit_immutable_recipe(app):
    click(app,'deploy'); click(app,'start')
    recipe=app.start_config
    original=recipe.create_battle()
    for _ in range(40): app.update(.1)
    old=app.battle
    app.battle.units[0].strength=1
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F5))
    assert app.battle is not old
    assert app.battle.units==original.units and app.battle.seed==recipe.seed
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F6))
    assert app.battle.seed!=recipe.seed
    assert app.start_config.placements==recipe.placements
    rematch=app.start_config
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F7))
    assert app.phase=='setup' and app.setup.config==rematch
    click(app,'count:0:infantry:1')
    assert app.setup.config.blue!=rematch.blue
    assert rematch==app.start_config and recipe.placements==app.start_config.placements


@pytest.mark.parametrize('size',[(960,640),(1280,720),(1920,1080)])
def test_menu_fits_and_clicks_at_desktop_sizes(size,tmp_path):
    pygame.init()
    try:
        app=Application(pygame.display.set_mode(size),path=str(tmp_path/'battle.json'))
        app.draw()
        f=app.setup.form
        for rect,enabled in f.buttons.values():
            assert 0<=rect.left and rect.right<=f.canvas.get_width()
            assert 0<=rect.top and rect.bottom<=f.canvas.get_height()
        click(app,'deploy'); app.draw()
        for point in (Vec(0,0),Vec(1000,600)):
            x,y=app.camera.world_to_screen(point)
            assert 0<=x<=size[0] and 0<=y<=size[1]-150
        click(app,'back')
        assert app.phase=='setup'
    finally: pygame.quit()


def test_large_map_move_click_and_camera(app):
    c=replace(BattleConfig(seed=1),width=1600,height=1000).prepared()
    app.start(c); app.controls.selected=0
    point=app.camera.world_to_screen(Vec(1550,950))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=point))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,button=3,pos=point))
    assert app.battle.commands[0].order.destination==Vec(1550,950)
    assert app.camera.screen_to_world(app.camera.world_to_screen(Vec(1500,900)))==Vec(1500,900)


def test_seed_field_text_entry_select_all_and_clear(app):
    app.setup.focus='seed'; app.setup.seed_text='123'
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_a,mod=pygame.KMOD_CTRL,unicode='a'))
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_7,unicode='7'))
    assert app.setup.seed_text=='7'
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_BACKSPACE))
    assert app.setup.recipe().seed is None


def test_terrain_menu_deployment_debug_and_new_seed_preserves_map(app):
    click(app,'terrain:Mixed Terrain')
    app.setup.seed_text='17'
    click(app,'deploy')
    terrain=app.deployment.battle.terrain
    assert terrain.hills and terrain.forests
    app.deployment.selected=0
    before=repr(app.deployment.battle.units),app.deployment.battle.rng.getstate()
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F3))
    app.draw()
    assert app.renderer.terrain_painter.key==terrain
    assert before==(repr(app.deployment.battle.units),app.deployment.battle.rng.getstate())
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F2))
    assert not app.controls.contours
    click(app,'start')
    app.restart(True)
    assert app.battle.terrain==terrain and app.battle.seed!=17
    app.edit_setup(); click(app,'terrain_random'); click(app,'deploy')
    assert app.deployment.battle.terrain.seed!=terrain.seed
    assert app.deployment.battle.terrain!=terrain
