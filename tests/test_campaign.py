"""Persistent records and transactions; controlled results test all five stages."""
from dataclasses import replace
import json
import pytest
from campaign.state import Campaign,CampaignRules,ENCOUNTERS
from simulation import upgrades
from simulation.archetypes import ARCHETYPES
from simulation.regiment import MoraleState
from simulation.geometry import Vec
from scenarios.battle_config import BattleConfig,DeploymentSession
from analysis.performance import fingerprint


def won(state,loss=40,destroy=None):
    running=state.start_battle();battle=running.create_battle()
    for u in battle.units:
        if u.army==0:u.strength=max(0,u.strength-loss)
    if destroy is not None:battle.unit(destroy).strength=0
    battle.result='army_0'
    return running.finish_battle(battle)


def test_new_campaign_is_seeded_and_separates_rng_streams():
    a=Campaign.new(77);assert a==Campaign.new(77)
    assert a.status=='ready' and a.wins==0 and len(a.army)==5
    assert {r.archetype_id for r in a.army}=={'infantry','haudenosaunee_skirmishers','cavalry','artillery'}
    assert len({r.id for r in a.army})==len({r.commander.id for r in a.army})==5
    assert a.encounter.ai_armies==(1,)
    assert all(p.order.kind.value=='hold' for p in a.encounter.placements if p.army==0)
    b=a.create_battle();rng=b.rng.getstate()
    a.make_rewards();assert rng==a.create_battle().rng.getstate()
    assert a.make_encounter()==a.encounter


def test_casualties_identity_retirement_and_no_transient_battle_state_carries():
    s=Campaign.new(23);running=s.start_battle();battle=running.create_battle();uid=s.army[0].id
    battle.unit(uid).strength=0
    u=battle.unit(s.army[1].id);u.strength-=100;u.state=MoraleState.ROUTING;u.cohesion=2;u.fatigue=90
    u.upgrade_state['temporary']=42;u.reload_left=100;u.commander_retreat_until=500
    battle.result='army_0';after=running.finish_battle(battle)
    assert after.casualties==s.army[0].strength+100
    assert s.army[0].commander in after.retired and len(after.army)==4
    survivor=next(r for r in after.army if r.id==u.id)
    assert survivor.strength==s.army[1].strength-70
    assert survivor.name==s.army[1].name and survivor.commander==s.army[1].commander
    reward=next(r for r in after.rewards if r.kind=='replenish');n=after.claim(reward.id)
    fresh=n.create_battle().unit(u.id)
    assert fresh.cohesion==100 and fresh.fatigue==0 and fresh.state==MoraleState.STEADY
    assert fresh.reload_left==0 and fresh.commander_retreat_until==0 and fresh.upgrade_state=={}
    assert fresh.strength==survivor.replenish(.65).strength
    assert not n.create_battle().projectiles
    assert s.army[1].strength==s.army[1].maximum


def test_recruitment_adds_fresh_regiment_new_commander_and_stable_ids():
    s=won(Campaign.new(81));r=next(r for r in s.rewards if r.kind=='recruit');n=s.claim(r.id)
    assert n.army[-1]==r.recruit and len(n.army)==6
    assert n.army[-1].strength==n.army[-1].maximum
    assert n.army[-1].commander.id not in {r.commander.id for r in s.army}
    assert n.next_id==s.next_id+1
    assert {r.id for r in s.army}<{r.id for r in n.army}
    assert n.create_battle().unit(r.recruit.id).commander==r.recruit.commander


def test_upgrade_ownership_validation_and_one_reward_transaction():
    s=won(Campaign.new(82));r=next(r for r in s.rewards if r.kind=='upgrade');cid,keys=r.choices[0]
    n=s.claim(r.id,cid,keys[0]);c=next(x.commander for x in n.army if x.commander.id==cid)
    old=next(x.commander for x in s.army if x.commander.id==cid)
    assert c.upgrades==(keys[0],) and c.personality==old.personality and c.specialization==old.specialization
    assert c.id==old.id and c.name==old.name
    with pytest.raises(ValueError):n.claim(r.id,cid,keys[0])
    with pytest.raises(ValueError):s.claim('unknown')
    with pytest.raises(ValueError):s.claim(r.id,cid,'mobile_battery' if 'mobile_battery' not in keys else 'rolling_volley')
    assert all(not c.commander.upgrades for c in s.army)


def test_army_cap_and_exhausted_upgrade_offers_are_valid():
    rules=CampaignRules(max_army=5,upgrade_limit=1)
    s=Campaign.new(84,rules)
    army=tuple(replace(r,commander=replace(r.commander,upgrades=(upgrades.available(ARCHETYPES[r.archetype_id],r.commander,1)[0],))) for r in s.army)
    s=replace(s,army=army);s=replace(s,encounter=s.make_encounter())
    s=won(s)
    assert len(s.rewards)==3 and all(r.kind=='replenish' for r in s.rewards)
    s.validate()
    s=s.claim(s.rewards[0].id)
    assert len(s.army)==5 and all(len(r.commander.upgrades)==1 for r in s.army)
    # A perfect victory with no recruitment/training/healing opportunities.
    s=replace(s,army=tuple(replace(r,strength=r.maximum) for r in s.army));s=replace(s,encounter=s.make_encounter())
    full=won(s,loss=0)
    assert len(full.rewards)==1 and full.rewards[0].kind=='continue'
    full.claim(full.rewards[0].id).validate()


@pytest.mark.parametrize('result',['army_1','draw'])
def test_defeat_ends_run_and_cannot_advance(result):
    s=Campaign.new(85).start_battle();b=s.create_battle();b.result=result;n=s.finish_battle(b)
    assert n.status=='defeat' and not n.rewards and n.wins==0
    n.validate()
    with pytest.raises(ValueError):n.start_battle()
    with pytest.raises(ValueError):n.finish_battle(b)
    with pytest.raises(ValueError):n.claim('whatever')


def test_deployment_keeps_persistent_state_and_cannot_change_composition():
    s=Campaign.new(17);session=DeploymentSession(s.encounter);p=session.config.placements[0]
    session.edit(p.id,facing=.15)
    started=s.start_battle(session.config)
    assert started.encounter.placements[0].facing==.15
    assert s.encounter.placements[0].facing==0
    session.reset(p.id)
    assert {p.id:(p.strength,p.name,p.commander) for p in session.automatic.placements}=={p.id:(p.strength,p.name,p.commander) for p in s.encounter.placements}
    with pytest.raises(ValueError):s.start_battle(replace(s.encounter,seed=12))
    bad=replace(s.encounter,placements=tuple(replace(x,strength=1) if x.id==p.id else x for x in s.encounter.placements))
    with pytest.raises(ValueError):s.start_battle(bad)


def test_save_load_pending_reward_exactly_once_and_reproducible_next_encounter(tmp_path):
    s=won(Campaign.new(31));path=tmp_path/'nested'/'campaign.json';s.save(path);loaded=Campaign.load(path)
    assert loaded==s and loaded.rewards==s.rewards
    r=next(r for r in s.rewards if r.kind=='upgrade');cid,keys=r.choices[0]
    a=s.claim(r.id,cid,keys[0]);b=loaded.claim(r.id,cid,keys[0]);assert a==b
    b.save(path);c=Campaign.load(path)
    assert c.army==a.army and c.encounter==a.encounter
    with pytest.raises(ValueError):c.claim(r.id,cid,keys[0])
    x,y=c.create_battle(),a.create_battle()
    for _ in range(30):x.step();y.step()
    assert fingerprint(x)==fingerprint(y)


def test_invalid_saves_and_transition_restrictions(tmp_path):
    path=tmp_path/'bad.json'
    for bad in ['{','[]','{}','{"version":3}',json.dumps({**Campaign.new(44).to_dict(),'wins':5}),json.dumps({**Campaign.new(44).to_dict(),'status':'battle'})]:
        path.write_text(bad)
        with pytest.raises(ValueError,match='Invalid campaign save'):Campaign.load(path)
    s=Campaign.new(44);b=s.create_battle()
    with pytest.raises(ValueError):s.finish_battle(b)
    with pytest.raises(ValueError):s.start_battle().save(path)
    b.result='army_0';b.seed+=1
    with pytest.raises(ValueError):s.start_battle().finish_battle(b)


def test_five_battle_headless_run_with_all_reward_types_and_resume(tmp_path):
    s=Campaign.new(212);path=tmp_path/'run.json';identities={r.id:r.commander.id for r in s.army}
    for stage in range(1,6):
        assert s.battle_number==stage and s.title==ENCOUNTERS[stage-1][0]
        s.validate();s.save(path);s=Campaign.load(path)
        running=s.start_battle();b=running.create_battle()
        for _ in range(3):b.step()
        for r in s.army:b.unit(r.id).strength-=10
        b.result='army_0';s=running.finish_battle(b)
        s.save(path);assert Campaign.load(path)==s
        if stage==5:break
        category=('recruit','upgrade','replenish','upgrade')[stage-1]
        r=next(r for r in s.rewards if r.kind==category)
        if r.kind=='upgrade':cid,keys=r.choices[0];s=s.claim(r.id,cid,keys[0])
        else:s=s.claim(r.id)
    assert s.status=='victory' and s.wins==5 and len(s.army)==6 and s.casualties>0
    assert all(r.commander.id==identities[r.id] for r in s.army if r.id in identities)
    assert any(r.commander.upgrades for r in s.army)
    s.validate()


def test_legacy_custom_config_defaults_and_campaign_not_shared():
    data=BattleConfig(seed=17).prepared().to_dict()
    for p in data['placements']:
        p.pop('strength',None);p.pop('name',None);p['commander'].pop('upgrades',None)
    custom=BattleConfig.from_dict(data);a=custom.create_battle();campaign=Campaign.new(17)
    b=campaign.create_battle();b.units[0].strength=1
    assert a.units[0].strength==a.units[0].stats.strength and not a.units[0].commander.upgrades
    assert campaign.create_battle().units[0].strength==campaign.army[0].strength
