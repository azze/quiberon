import math
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from scenarios.battle_config import BattleConfig, SIZES
from simulation.archetypes import ARCHETYPES
from simulation.battle import Battle
from simulation.geometry import Vec
from simulation.regiment import Regiment
from simulation import combat, morale
from simulation.terrain import generate_terrain
from analysis.battle_report import battle_report
from viewer.application import Application
from viewer.camera import Camera
from viewer.controls import Controls
from viewer.renderer import Renderer
from viewer.terrain import TerrainPainter
from viewer.ranges import SELECTED_RANGE, ENEMY_RANGE


@pytest.fixture
def screen():
    pygame.init()
    screen=pygame.display.set_mode((1280,800))
    yield screen
    pygame.quit()


def click_form(app,key,form):
    rect,enabled=form.buttons[key]
    assert enabled
    pos=(round(form.origin[0]+rect.centerx*form.scale),round(form.origin[1]+rect.centery*form.scale))
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos))
    app.draw()


@pytest.mark.parametrize('size',['Huge','Epic','Vast'])
def test_larger_maps_fit_and_roundtrip_headlessly(size,tmp_path):
    width,height=SIZES[size]
    config=replace(BattleConfig(seed=19),width=width,height=height).prepared()
    battle=config.create_battle()
    camera=Camera(width=960,height=640); camera.fit(width,height)
    for point in (Vec(0,0),Vec(width,height)):
        x,y=camera.world_to_screen(point)
        assert 0<=x<=960 and 0<=y<=490
        assert (camera.screen_to_world((x,y))-point).length()<1e-8
    assert battle.units[0].stats.range==155 and battle.units[0].width==64
    for _ in range(10): battle.step()
    assert battle.tick==10
    path=tmp_path/'large.json'; config.save(path)
    assert BattleConfig.load(path)==config


def test_largest_terrain_has_bounded_cosmetic_cache(screen):
    terrain=generate_terrain('Mixed Terrain',*SIZES['Vast'],19)
    painter=TerrainPainter(); painter.build(terrain)
    assert painter.surface.get_width()<=320 and painter.surface.get_height()<=240
    assert painter.contours
    # Rendering does not replace or rescale authoritative feature geometry.
    assert terrain.width==4800 and terrain.height==3000 and terrain.hills[0].height>0


def test_browser_side_selection_filters_stats_and_counts(screen):
    app=Application(screen); app.draw()
    menu=app.setup
    click_form(app,'unit:0:infantry',menu.form)
    assert menu.info_open=='infantry' and menu.info_army==0
    labels=[]; text=menu.form.text
    def capture(value,*args,**kwargs):
        labels.append(str(value)); return text(value,*args,**kwargs)
    menu.form.text=capture
    click_form(app,'filter:infantry',menu.form)
    assert all(ARCHETYPES[key.split(':')[1]].stats.kind.value=='infantry' for key in menu.form.buttons if key.startswith('choose:'))
    click_form(app,'choose:revolutionary_rifles',menu.form)
    assert any('Range 235 m' in s and '22 s' in s for s in labels)
    assert any('Strength 140' in s for s in labels)
    click_form(app,'count:0:revolutionary_rifles:1',menu.form)
    assert menu.config.blue.count('revolutionary_rifles')==menu.config.red.count('revolutionary_rifles')==1
    click_form(app,'close_info',menu.form)
    click_form(app,'unit:1:infantry',menu.form)
    assert menu.info_army==1 and not menu.form.buttons['count:1:infantry:1'][1]
    click_form(app,'close_info',menu.form); click_form(app,'symmetric',menu.form)
    click_form(app,'browse:1',menu.form); click_form(app,'filter:artillery',menu.form)
    click_form(app,'choose:french_horse_artillery',menu.form)
    click_form(app,'count:1:french_horse_artillery:1',menu.form)
    assert menu.config.red.count('french_horse_artillery')==1 and menu.config.blue.count('french_horse_artillery')==0


@pytest.mark.parametrize('zoom',[.5,1.,1.5])
def test_selected_and_enemy_hover_range_without_debug_is_read_only(screen,monkeypatch,zoom):
    a=Regiment(0,'selected',0,Vec(400,300))
    b=Regiment(1,'hover',1,Vec(700,400),math.pi,archetype_id='revolutionary_rifles')
    battle=Battle([a,b],sandbox=True)
    controls=Controls(); controls.selected=0
    camera=Camera(height=800,zoom=zoom); renderer=Renderer(screen,camera)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:camera.world_to_screen(b.pos))
    before=repr(battle.units),battle.rng.getstate(),dict(battle.metrics)
    renderer.draw(battle,controls)
    assert renderer.hovered_id==1 and not controls.debug
    for pos,color in ((Vec(400-155,300),SELECTED_RANGE),(Vec(700-235,400),ENEMY_RANGE)):
        x,y=camera.world_to_screen(pos)
        assert any(screen.get_at((round(x)+dx,round(y)+dy))[:3]==color for dx in range(-2,3) for dy in range(-2,3))
    assert before==(repr(battle.units),battle.rng.getstate(),dict(battle.metrics))
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:(600,760))
    renderer.draw(battle,controls)
    assert renderer.hovered_id is None


def test_hover_uses_interpolated_pose_and_ignores_dead_units(screen,monkeypatch):
    from viewer.interpolation import MotionFrame
    unit=Regiment(0,'moving',0,Vec(200,300))
    battle=Battle([unit],sandbox=True); motion=MotionFrame(battle)
    unit.pos=Vec(400,300)
    camera=Camera(height=800); renderer=Renderer(screen,camera)
    monkeypatch.setattr(pygame.mouse,'get_pos',lambda:camera.world_to_screen(Vec(300,300)))
    renderer.draw(battle,Controls(),motion=motion,alpha=.5)
    assert renderer.hovered_id==0
    unit.strength=0
    renderer.draw(battle,Controls(),motion=motion,alpha=.5)
    assert renderer.hovered_id is None


def test_report_uses_actual_starting_strength_and_persistent_morale_counts():
    wounded=Regiment(0,'wounded',0,Vec(200,300),strength=100)
    enemy=Regiment(1,'enemy',1,Vec(700,300))
    battle=Battle([wounded,enemy],seed=2)
    combat.damage(battle,wounded,10,'test',enemy)
    wounded.morale=1
    morale.update(battle)
    assert wounded.analysis['rout_events']==1
    for _ in range(230): morale.update(battle)
    assert wounded.analysis['rallies']==1
    wounded.withdrawn=True
    for _ in range(300): battle.log('test','overflow the short event log')
    before=repr(battle.units),battle.rng.getstate()
    report=battle_report(battle)
    assert report['armies'][0]['initial']==100 and report['armies'][0]['remaining']==90
    assert report['armies'][0]['lost']==10 and report['armies'][0]['withdrawn']==1
    assert report['armies'][0]['rout_events']==1 and report['armies'][0]['rallies']==1
    assert report['regiments'][0]['status']=='withdrawn'
    assert report['regiments'][1]['casualties_inflicted']==10
    assert report['archetypes'][0]['lost']==10
    assert before==(repr(battle.units),battle.rng.getstate())


@pytest.mark.parametrize('size',[(960,640),(1280,800),(1920,1080)])
def test_results_auto_open_paging_filters_and_restart(size,tmp_path):
    pygame.init()
    try:
        app=Application(pygame.display.set_mode(size),path=str(tmp_path/'battle.json'))
        app.start(BattleConfig(seed=7).prepared())
        app.battle.units[0].strength-=20
        app.battle.units[1].analysis['casualties_inflicted']=17
        app.battle.result='army_0'; app.draw()
        assert app.results_visible and app.results.report['armies'][0]['lost']==20
        form=app.results.form
        for rect,_ in form.buttons.values():
            assert 0<=rect.left<rect.right<=960 and 0<=rect.top<rect.bottom<=740
        click_form(app,'page:1',form); assert app.results.page==1
        click_form(app,'army:0',form); assert app.results.page==0 and len(app.results.rows())==6
        click_form(app,'view:archetypes',form); assert len(app.results.rows())==3
        before=repr(app.battle.units),app.battle.rng.getstate(),app.battle.tick
        for _ in range(4): app.update(.1); app.draw()
        assert before==(repr(app.battle.units),app.battle.rng.getstate(),app.battle.tick)
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB)); app.draw()
        assert not app.results_visible
        app.controls.selected=0
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_c))
        assert not app.battle.commands
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB)); app.draw()
        assert app.results_visible
        click_form(app,'restart',form)
        assert app.battle.result is None and app.results is None
        assert app.battle.units[0].strength==240
        app.battle.result='army_1'; app.draw()
        click_form(app,'setup',app.results.form)
        assert app.phase=='setup' and app.results is None
    finally: pygame.quit()
