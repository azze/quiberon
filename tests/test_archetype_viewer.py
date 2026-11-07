import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from viewer.application import Application
from scenarios.presets import load_preset, SPECIALIST_PRESETS
from scenarios.battle_config import ArmyConfig, BattleConfig
from simulation.archetypes import ARCHETYPES
from simulation.formations import Formation
from simulation.orders import OrderKind
from analysis.matchups import main as matchups_main


@pytest.mark.parametrize('size',[(960,640),(1280,800)])
def test_roster_pages_details_mixed_counts_symmetry_and_specialist_deployment(size,tmp_path):
    pygame.init()
    try:
        app=Application(pygame.display.set_mode(size),path=str(tmp_path/'units.json'))
        app.draw()
        menu=app.setup
        seen=set()
        for offset in (0,3,6):
            menu.scrolls=[offset,offset]; app.draw()
            for key,(rect,enabled) in menu.form.buttons.items():
                assert 0<=rect.left<=rect.right<=960 and 0<=rect.top<=rect.bottom<=740
                if key.startswith('unit:'): seen.add(key.split(':')[-1])
        assert seen=={'infantry','cavalry','artillery'}
        menu.action('browse:0'); app.draw()
        assert {key.split(':')[1] for key in menu.form.buttons if key.startswith('choose:')}==set(ARCHETYPES)
        menu.action('close_info')
        menu.action('count:0:haudenosaunee_skirmishers:1')
        assert menu.config.blue.count('haudenosaunee_skirmishers')==menu.config.red.count('haudenosaunee_skirmishers')==1
        menu.action('symmetric'); menu.action('count:1:commonwealth_uhlans:1')
        assert menu.config.red.count('commonwealth_uhlans')==1 and menu.config.blue.count('commonwealth_uhlans')==0
        for key in ARCHETYPES:
            menu.action('info:'+key); app.draw()
            assert 'close_info' in menu.form.buttons
            app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
            assert menu.info_open is None and app.running
        menu.action('save')
        assert BattleConfig.load(menu.path)==menu.config
        menu.action('preset:Woodland Encounter'); menu.action('deploy')
        app.deploy(menu.next_config); app.deployment.selected=0
        assert app.deployment.battle.unit(0).formation==Formation.SKIRMISH
        app.draw()
        app.start(app.deployment.session.config); app.controls.selected=0
        before=repr(app.battle.units),app.battle.rng.getstate()
        app.draw()
        assert before==(repr(app.battle.units),app.battle.rng.getstate())
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_s)); app.battle.step()
        assert app.battle.unit(0).order.kind==OrderKind.SKIRMISH
        app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_c)); app.battle.step()
        assert app.battle.unit(0).next_formation==Formation.COLUMN
        app.restart(); assert app.battle.unit(0).formation==Formation.SKIRMISH
    finally: pygame.quit()


def test_preset_paging_reaches_every_specialist():
    pygame.init()
    try:
        app=Application(pygame.display.set_mode((960,640)))
        names=set()
        from scenarios.presets import PRESETS
        for _ in range(len(PRESETS)):
            app.setup.action('preset_next'); names.add(app.setup.config.name)
        assert set(SPECIALIST_PRESETS)<=names
    finally: pygame.quit()


def test_mirrored_matchup_cli_statistics_and_reproducibility(tmp_path,monkeypatch):
    import json
    import sys
    paths=[tmp_path/'first.json',tmp_path/'second.json']
    for path in paths:
        monkeypatch.setattr(sys,'argv',['matchups','--preset','Prussian Drill','--runs','1','--duration','1','--seed','3','--output',str(path)])
        matchups_main()
    first,second=[json.loads(p.read_text()) for p in paths]
    assert first==second and len(first['battles'])==2
    assert {r['swapped'] for r in first['battles']}=={True,False}
    assert 'army0_prussian_line_volleys' in first['battles'][0]
    assert 'army1_prussian_line_volleys' in first['battles'][1]
