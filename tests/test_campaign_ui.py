"""Campaign wraps the original viewer and after-action screen; SDL smoke tests."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from dataclasses import replace
import pygame
import pytest
from campaign.state import Campaign
from viewer.application import Application
from viewer.results import BattleResults
from analysis.performance import fingerprint


@pytest.fixture
def app(tmp_path):
    pygame.init();screen=pygame.display.set_mode((960,640))
    a=Application(screen,path=str(tmp_path/'custom.json'));a.open_menu(tmp_path/'run.json',17)
    yield a
    pygame.quit()


def press(app,key):app.handle(pygame.event.Event(pygame.KEYDOWN,key=key,unicode=''))


def click(app,form,key):
    app.draw();rect,enabled=form.buttons[key];assert enabled
    x,y=rect.center;point=(round(form.origin[0]+x*form.scale),round(form.origin[1]+y*form.scale))
    assert 0<=point[0]<app.screen.get_width() and 0<=point[1]<app.screen.get_height()
    assert form.hit(point)==key
    app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point))


@pytest.mark.parametrize('size',[(800,600),(1280,800)])
def test_menu_deployment_original_results_upgrade_reward_resume_and_custom(app,size):
    app.screen=pygame.display.set_mode(size);flow=app.campaign_flow;click(app,flow.form,'new')
    assert app.phase=='campaign' and flow.state.status=='ready' and flow.path.exists()
    click(app,flow.form,'deploy');assert app.phase=='deployment'
    d=app.deployment;before=fingerprint(d.battle)
    app.update(10);app.draw();assert fingerprint(d.battle)==before
    for action in ('officers','load','save'):d.button(action)
    assert d.officers is None and not os.path.exists(app.setup.path)
    d.selected=0;d.attempt(facing=.1)
    click(app,d.form,'start');assert app.phase=='battle' and flow.state.status=='battle'
    assert Campaign.load(flow.path).status=='ready'
    assert app.battle.unit(0).facing==.1
    for key in (pygame.K_F5,pygame.K_F6,pygame.K_F7):press(app,key)
    assert app.phase=='battle'
    app.battle.unit(0).strength-=30;app.battle.result='army_0';app.draw()
    assert type(app.results) is BattleResults and app.results.campaign
    report=app.results.report;click(app,app.results.form,'continue')
    assert app.phase=='reward' and flow.state.wins==1 and app.results.report==report
    offer=next(r for r in flow.state.rewards if r.kind=='upgrade')
    cid,keys=offer.choices[0]
    click(app,flow.form,'reward:'+offer.id)
    click(app,flow.form,'officer:'+cid)
    click(app,flow.form,'upgrade:'+keys[0]);click(app,flow.form,'claim')
    assert app.phase=='campaign' and flow.state.battle_number==2
    assert keys[0] in next(r.commander.upgrades for r in flow.state.army if r.commander.id==cid)
    flow.action('menu');flow.action('continue');assert app.phase=='campaign' and flow.state.battle_number==2
    flow.action('menu');click(app,flow.form,'custom');assert app.phase=='setup' and not app.in_campaign
    app.draw();saved=Campaign.load(flow.path);app.setup.action('deploy')
    # Custom editing and restarting has its original independent lifecycle.
    app.start(app.setup.config);app.battle.unit(0).strength=1;app.restart();assert app.battle.unit(0).strength>1
    app.edit_setup();assert app.phase=='setup' and Campaign.load(flow.path)==saved


def test_deployment_back_and_defeat_flow(app):
    f=app.campaign_flow;f.action('new');f.action('deploy');app.deployment.button('back')
    app.handle(pygame.event.Event(pygame.MOUSEMOTION,pos=(10,10)))
    assert app.phase=='campaign'
    f.action('deploy');f.start_battle(app.deployment.session.config)
    app.battle.result='army_1';app.draw();press(app,pygame.K_RETURN)
    assert app.phase=='campaign_end' and f.state.status=='defeat'
    app.draw();f.action('menu');f.action('continue');assert app.phase=='campaign_end'
    assert len(app.results.report['regiments'])==9


def test_invalid_continue_is_shown_and_failed_save_cannot_claim_twice(app,monkeypatch):
    f=app.campaign_flow;f.path.write_text('{')
    f.action('continue');assert app.phase=='menu' and 'Invalid campaign save' in f.message
    f.action('new');f.action('deploy');f.start_battle(app.deployment.session.config)
    app.battle.result='army_0';f.finish();old=f.state
    r=next(r for r in old.rewards if r.kind=='recruit');f.action('reward:'+r.id)
    def fail(*args):raise OSError('disk unavailable')
    with monkeypatch.context() as m:
        m.setattr(Campaign,'save',fail);f.action('claim')
    assert f.state==old and 'disk unavailable' in f.message
    f.action('claim');assert len(f.state.army)==6 and f.state.status=='ready'
    f.action('claim');assert len(f.state.army)==6


def test_campaign_completion_uses_same_report_then_offers_fresh_run(app,monkeypatch):
    f=app.campaign_flow;f.action('new')
    # Complete four controlled encounters through immutable campaign transitions.
    state=f.state
    for _ in range(4):
        b=state.create_battle();b.result='army_0';state=state.start_battle().finish_battle(b)
        r=next(r for r in state.rewards if r.kind=='recruit');state=state.claim(r.id)
    f.commit(state);f.show_state();f.action('deploy');f.start_battle(app.deployment.session.config)
    app.battle.result='army_0';app.draw();assert type(app.results) is BattleResults
    click(app,app.results.form,'continue');app.draw()
    assert app.phase=='campaign_end' and f.state.wins==5
    assert Campaign.load(f.path).status=='victory'
    monkeypatch.setattr('viewer.campaign.secrets.randbits',lambda bits:12345)
    click(app,f.form,'new')
    assert app.phase=='campaign' and f.state.seed==12345 and f.state.wins==0


def test_back_to_army_saves_manual_deployment_and_recipe_edits_are_locked(app):
    f=app.campaign_flow;f.action('new');f.action('deploy');d=app.deployment
    d.selected=0;d.attempt(facing=.2)
    app.edit_setup();assert app.phase=='campaign'
    loaded=Campaign.load(f.path)
    assert loaded.encounter.placements[0].facing==.2
    with pytest.raises(ValueError):loaded.start_battle(replace(loaded.encounter,ai_strategies=('all_out_attack','all_out_attack')))
