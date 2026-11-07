"""Deployment transactions, officer editing, restart and read-only rendering."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from scenarios.battle_config import BattleConfig
from viewer.application import Application
from viewer.setup import CommanderEditor
from simulation.commanders import Personality as P,Specialization as S
from analysis.performance import fingerprint


@pytest.fixture
def screen():
    pygame.init()
    yield pygame.display.set_mode((960,640))
    pygame.quit()


def test_officer_editor_is_transactional_compatible_and_can_edit_both_armies(screen):
    config=BattleConfig(seed=17).prepared()
    e=CommanderEditor(config)
    original=config.placements[0].commander
    e.action('personality:cautious');e.action('specialization:sharpshooter')
    assert e.placement.commander.id==original.id
    assert e.placement.commander.personality==P.CAUTIOUS and e.placement.commander.specialization==S.SHARPSHOOTER
    e.action('specialization:artillerist')
    assert e.placement.commander.specialization==S.SHARPSHOOTER
    while e.placement.army==0:e.action('next')
    before=e.placement.commander;e.action('reroll_army')
    assert e.placement.commander!=before
    e.draw(screen)
    assert config.placements[0].commander==original
    e.action('cancel');assert e.closed and not e.accepted


def test_deployment_editing_resets_save_rematch_and_live_input_authority(screen,tmp_path):
    app=Application(screen,path=str(tmp_path/'officers.json'))
    app.deploy(BattleConfig(seed=17));d=app.deployment
    original=d.session.config
    d.selected=0;d.button('officers');editor=d.officers
    editor.action('personality:aggressive');editor.action('specialization:firebrand');editor.action('apply')
    d.handle(pygame.event.Event(pygame.MOUSEMOTION,pos=(10,10)),app.camera)
    assert d.officers is None
    changed=d.session.config.placements[0].commander
    assert changed!=original.placements[0].commander
    d.button('reset');assert d.session.config.placements[0].commander==changed
    d.button('save');assert BattleConfig.load(tmp_path/'officers.json')==d.session.config
    start=d.session.config
    app.start(start);before=fingerprint(app.battle)
    for _ in range(60):app.battle.step()
    app.restart();assert fingerprint(app.battle)==before
    app.restart(True)
    assert app.battle.seed!=start.seed and app.battle.units[0].commander==changed
    # O has no live-game officer-editor handler.
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_o))
    assert app.phase=='battle' and app.battle.units[0].commander==changed
    app.controls.selected=0
    snapshot=fingerprint(app.battle)
    for debug in (False,True):app.controls.debug=debug;app.draw()
    assert fingerprint(app.battle)==snapshot
    app.edit_setup();assert app.setup.config.placements[0].commander==changed


@pytest.mark.parametrize('size',[(960,640),(1280,800)])
def test_officer_modal_draw_and_scaled_button_hit_tests(screen,size):
    screen=pygame.display.set_mode(size)
    app=Application(screen);app.deploy(BattleConfig(seed=17));app.deployment.button('officers')
    editor=app.deployment.officers
    app.draw()
    rect,enabled=editor.form.buttons['apply']
    x,y=rect.center;f=editor.form
    point=(round(f.origin[0]+x*f.scale),round(f.origin[1]+y*f.scale))
    assert enabled and editor.form.hit(point)=='apply'
    assert 0<=point[0]<size[0] and 0<=point[1]<size[1]
    before=editor.placement.commander
    editor.action('reroll');editor.action('reset')
    assert editor.placement.commander==before


def test_legacy_scenario_rematch_retains_original_commanders(screen):
    from scenarios.standard_battle import create
    app=Application(screen,legacy_factory=create,legacy_seed=17)
    officers=[u.commander for u in app.battle.units]
    app.restart(True)
    assert app.battle.seed!=17 and [u.commander for u in app.battle.units]==officers
    app.restart()
    assert [u.commander for u in app.battle.units]==officers
