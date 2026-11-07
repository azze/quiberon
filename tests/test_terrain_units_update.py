import math
from dataclasses import replace
import pytest

from analysis.performance import fingerprint
from scenarios.battle_config import BattleConfig,ArmyConfig,ConfigError
from simulation import combat
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec
from simulation.regiment import Regiment,UnitType
from simulation.orders import Command,Order,OrderKind as O
from simulation.terrain import TerrainMap,Hill,Forest,generate_terrain,TERRAIN_PRESETS


@pytest.mark.parametrize('preset',['Rolling Hills','Mixed Terrain','Wooded Battlefield'])
def test_larger_fields_add_features_with_fixed_metre_dimensions(preset):
    maps=[generate_terrain(preset,w,h,17) for w,h in ((600,400),(1000,600),(1600,1000),(4800,3000))]
    counts=[len(t.hills)+len(t.forests) for t in maps]
    assert all(b>a for a,b in zip(counts,counts[1:]))
    for t in maps:
        assert all(70<=h.radius_x<=130 and 72<=h.radius_y<=132 and abs(h.height)<=26 for h in t.hills)
        assert all((f.radius_x,f.radius_y) in {(120,108),(140,120),(100,78),(90,84)} for f in t.forests)
        assert TerrainMap.from_dict(t.to_dict())==t
        assert generate_terrain(preset,t.width,t.height,17)==t


@pytest.mark.parametrize('preset',TERRAIN_PRESETS)
def test_all_presets_fit_vast_maps_and_pack_armies(preset):
    config=BattleConfig(width=4800,height=3000,terrain_preset=preset,seed=17).prepared()
    assert config.resolved_terrain().width==4800
    assert len(config.create_battle().units)==12


def test_large_terrain_index_matches_full_feature_queries_exactly():
    t=generate_terrain('Mixed Terrain',4800,3000,17)
    assert t._hill_cells is not None and t._forest_cells is not None
    for x,y in ((0,0),(4800,3000),(1200,700),(400,400),(2400,1500),(4799,399)):
        expected=sum(h.elevation(x,y) for h in t.hills)
        assert t.get_elevation(x,y)==expected
        assert t.forest_density(x,y)==max((f.cover(x,y) for f in t.forests),default=0.)
    assert '_hill_cells' not in t.to_dict()


def test_compact_hills_are_smooth_and_legacy_gaussians_remain_unchanged():
    h=Hill(500,300,100,80,25,compact=True)
    assert h.elevation(500,300)==25
    assert h.elevation(800,300)==0 and h.gradient(800,300)==Vec(0,0)
    assert h.elevation(799.99,300)<1e-12
    x=580;eps=.001
    assert h.gradient(x,300).x==pytest.approx((h.elevation(x+eps,300)-h.elevation(x-eps,300))/(2*eps))
    legacy=Hill(500,300,100,80,25)
    assert legacy.elevation(800,300)>0
    raw=dict(width=1000,height=600,hills=[dict(x=500,y=300,radius_x=100,radius_y=80,height=25)],forests=[])
    assert not TerrainMap.from_dict(raw).hills[0].compact


def woods_pair(key='haudenosaunee_skirmishers',distance=60,forested=True):
    a=Regiment(0,key,0,Vec(250,300),archetype_id=key)
    b=Regiment(1,'enemy',1,Vec(250+distance,300),math.pi)
    terrain=TerrainMap(forests=(Forest(400,300,350,240,1),)) if forested else TerrainMap()
    return Battle([a,b],seed=17,terrain=terrain)


def volley_losses(key,forested):
    battle=woods_pair(key,forested=forested);a,b=battle.units;losses=0
    for _ in range(1000):
        b.strength=240;b.cohesion=100;b.morale=85;a.reload_left=0
        combat.fire(battle,a,b);losses+=240-b.strength;battle.effects.clear()
    return losses


def test_woodlanders_have_useful_firing_advantage_in_woods_but_lower_open_firepower():
    woodland=volley_losses('haudenosaunee_skirmishers',True)
    line=volley_losses('infantry',True)
    assert woodland>line
    assert volley_losses('haudenosaunee_skirmishers',False)<volley_losses('infantry',False)*.5


def test_woodland_observation_uses_cover_and_never_sees_through_ridges():
    battle=woods_pair(distance=100);a,b=battle.units
    assert battle.visibility(a,b).visible
    ordinary=Regiment(2,'line observer',0,a.pos)
    assert not battle.visibility(ordinary,b).visible
    battle.terrain=replace(battle.terrain,hills=(Hill(300,300,12,100,25),))
    assert not battle.visibility(a,b).visible and battle.visibility(a,b).reason=='ridge'
    battle.terrain=TerrainMap(forests=(Forest(350,300,25,200,1),))
    assert battle.terrain.forest_density(a.pos.x,a.pos.y)==0
    assert battle.visibility(a,b)==battle.visibility(ordinary,b)


def test_opaque_long_forest_rays_exit_early_without_granting_woodland_xray_vision():
    calls=[]
    class CountingTerrain(TerrainMap):
        def get_elevation(self,x,y):
            calls.append((x,y));return super().get_elevation(x,y)
    t=CountingTerrain(width=4800,height=3000,forests=(Forest(2400,1500,3000,1400,1),))
    a=Regiment(0,'wood',0,Vec(200,1500),archetype_id='haudenosaunee_skirmishers')
    b=Regiment(1,'enemy',1,Vec(4600,1500))
    battle=Battle([a,b],terrain=t,rules=replace(Rules(),width=4800,height=3000))
    assert not battle.visibility(a,b).visible
    assert len(calls)<100


def test_covered_loose_skirmishers_do_not_panic_solely_from_regiment_headcount():
    from simulation import morale
    values=[]
    for key in ('infantry','haudenosaunee_skirmishers'):
        battle=woods_pair(key);unit=battle.units[0]
        unit.strength=140;unit.order=Order(O.SKIRMISH);unit.forest_cover=1
        for _ in range(1000):morale.update(battle)
        values.append(unit.morale)
    assert values[1]>80 and values[0]<60


def test_skirmish_withdrawal_allows_finite_turn_time_before_six_seconds_of_movement():
    from simulation import ai
    battle=woods_pair(distance=50);unit=battle.units[0];unit.order=Order(O.SKIRMISH,target_id=1)
    unit.strength=60 # Retreat when depleted, not from a favourable woodland ambush.
    ai.destination(battle,unit)
    assert unit.skirmish_retreat and 6<unit.skirmish_until-battle.time<=10


def test_nearby_fugitives_do_not_remove_safe_skirmish_composure():
    from simulation import morale
    from simulation.regiment import MoraleState
    a,b=woods_pair(),woods_pair()
    for battle in (a,b):
        u=battle.units[0];u.order=Order(O.SKIRMISH);u.forest_cover=1
    b.units.append(Regiment(2,'fugitive',1,Vec(260,300),state=MoraleState.ROUTING,morale=0))
    morale.update(a);morale.update(b)
    assert a.units[0].morale==b.units[0].morale


def test_high_ground_reduces_uphill_melee_without_a_universal_damage_bonus():
    losses=[]
    for terrain in (TerrainMap(),TerrainMap(hills=(Hill(500,300,50,100,30),))):
        lost=0
        for seed in range(30):
            a=Regiment(0,'uphill',0,Vec(448,300));b=Regiment(1,'defender',1,Vec(460,300),math.pi)
            battle=Battle([a,b],seed=seed,terrain=terrain);combat.melee(battle,a,b)
            lost+=240-b.strength
        losses.append(lost)
    assert losses[1]<losses[0]*.8


def charge_pair():
    a=Regiment(0,'bayonets',0,Vec(250,300),order=Order(O.CHARGE,target_id=1))
    b=Regiment(1,'line',1,Vec(300,300),math.pi)
    return Battle([a,b],seed=17)


def test_infantry_charge_closes_through_musket_range_with_small_boost_and_single_impact():
    battle=charge_pair();a,b=battle.units;normal=a.stats.speed*.75;maximum=0
    for _ in range(250):
        battle.step();maximum=max(maximum,a.speed)
        if a.analysis['charges']:break
    assert a.analysis['charges']==1 and normal<maximum<=normal*battle.rules.infantry_charge_speed+1e-6
    assert a.analysis['volleys']==0 and a.combat_state=='melee'
    assert a.charge_last_momentum>0 and a.analysis['impact_casualties']>0
    for _ in range(100):
        battle.issue(Command(a.id,Order(O.CHARGE,target_id=b.id)));battle.step()
    assert a.analysis['charges']==1


def test_normal_attack_stays_a_firefight_and_charge_can_be_interrupted():
    battle=charge_pair();a,b=battle.units
    a.order=Order(O.ATTACK,target_id=b.id);battle.step()
    assert not a.infantry_charging and a.speed==0 and a.analysis['volleys']==1
    battle.issue(Command(a.id,Order(O.CHARGE,target_id=b.id)));battle.step()
    assert a.infantry_charging
    battle.issue(Command(a.id,Order(O.HOLD)));battle.step()
    assert not a.infantry_charging and a.charge_momentum==0 and a.speed==0


def test_infantry_charge_saved_orders_and_headless_determinism(tmp_path):
    config=BattleConfig(seed=17,blue=ArmyConfig(1,0,0),red=ArmyConfig(1,0,0),ai_armies=()).prepared()
    placements=tuple(replace(p,order=Order(O.CHARGE,target_id=1)) if p.id==0 else p for p in config.placements)
    config=replace(config,placements=placements);path=tmp_path/'charge.json';config.save(path)
    assert BattleConfig.load(path)==config
    a,b=config.create_battle(),config.create_battle()
    for _ in range(1000):a.step()
    for _ in range(250):
        for _ in range(4):b.step()
    assert fingerprint(a)==fingerprint(b)


def test_charge_commands_reject_artillery_and_initial_config_rejects_it():
    a=Regiment(0,'gun',0,Vec(200,300),archetype_id='artillery')
    b=Regiment(1,'enemy',1,Vec(300,300))
    battle=Battle([a,b]);battle.issue(Command(0,Order(O.CHARGE,target_id=1)));battle.step()
    assert a.order.kind==O.HOLD
    config=BattleConfig(seed=17,blue=ArmyConfig(0,0,1),red=ArmyConfig(1,0,0),symmetric=False).prepared()
    placements=tuple(replace(p,order=Order(O.CHARGE)) if p.army==0 else p for p in config.placements)
    with pytest.raises(ConfigError):replace(config,placements=placements).validate()


def test_ctrl_click_and_b_emit_charge_commands(monkeypatch):
    import os
    os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
    import pygame
    from viewer.camera import Camera
    from viewer.controls import Controls
    pygame.init()
    try:
        battle=charge_pair();a,b=battle.units;controls=Controls();controls.selected=a.id
        camera=Camera(width=1280,height=800);camera.fit(1000,600)
        monkeypatch.setattr(pygame.key,'get_mods',lambda:pygame.KMOD_CTRL)
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=camera.world_to_screen(b.pos)),battle,camera)
        assert battle.commands[-1].order==Order(O.CHARGE,target_id=b.id)
        battle.commands.clear();a.target_id=b.id
        controls.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_b),battle,camera)
        assert battle.commands[-1].order==Order(O.CHARGE,target_id=b.id)
        battle.units.append(Regiment(2,'dead target',1,Vec(500,300),strength=0))
        battle.commands.clear();a.order=Order(O.ATTACK,target_id=2)
        controls.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_b),battle,camera)
        assert battle.commands[-1].order==Order(O.CHARGE,target_id=b.id)
    finally:pygame.quit()
