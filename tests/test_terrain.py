import math
import pytest
from simulation.geometry import Vec
from simulation.terrain import Hill, Forest, TerrainMap, generate_terrain, TERRAIN_PRESETS


def test_elevation_gradient_and_boundaries():
    t=TerrainMap(hills=(Hill(500,300,100,100,20),))
    assert t.get_elevation(500,300)==20
    assert t.get_elevation(600,300)==pytest.approx(20*math.exp(-.5))
    assert t.gradient(400,300).x>0 and t.gradient(600,300).x<0
    assert t.slope(500,300)==0
    x=430; eps=.001
    assert t.gradient(x,300).x==pytest.approx((t.get_elevation(x+eps,300)-t.get_elevation(x-eps,300))/(2*eps))
    for x,y in [(0,0),(1000,600)]: assert math.isfinite(t.get_elevation(x,y))


def test_forest_queries_smooth_edges():
    t=TerrainMap(forests=(Forest(500,300,100,80,.5),Forest(200,200,60,60,1)))
    assert t.forest_density(500,300)==.5
    assert t.forest_density(600,300)==0
    assert 0<t.forest_density(590,300)<.5
    assert t.terrain_type(200,200)=='dense forest'
    assert t.terrain_type(0,0)=='open'


@pytest.mark.parametrize('preset',TERRAIN_PRESETS)
@pytest.mark.parametrize('size',[(600,400),(1000,600),(1600,1000)])
def test_presets_scale_and_are_deterministic(preset,size):
    a=generate_terrain(preset,*size,17); b=generate_terrain(preset,*size,17)
    assert a==b and TerrainMap.from_dict(a.to_dict())==a
    a.validate()

from simulation.regiment import Regiment, INFANTRY, CAVALRY, ARTILLERY
from simulation.formations import Formation
from simulation.terrain import TerrainRules
from simulation.movement import move
from simulation.battle import Battle
from simulation.config import Rules
from simulation.orders import Order,OrderKind


def test_uphill_downhill_and_steep_disruption():
    gentle=TerrainMap(hills=(Hill(500,300,100,200,20),))
    steep=TerrainMap(hills=(Hill(500,300,100,200,60),))
    u=Regiment(0,'test',0,Vec(400,300))
    up=gentle.movement_effect(u,Vec(1,0))
    down=gentle.movement_effect(u,Vec(-1,0))
    assert up.speed<1 and 1<down.speed<=1.12
    assert steep.movement_effect(u,Vec(1,0)).loss_per_metre>up.loss_per_metre
    assert steep.movement_effect(u,Vec(-1,0)).speed<1.12
    flat=Regiment(1,'flat',0,u.pos)
    move(u,Vec(700,300),.1,1000,600,gentle)
    move(flat,Vec(700,300),.1,1000,600)
    assert u.speed<flat.speed


def test_forest_types_formations_and_density():
    light=TerrainMap(forests=(Forest(500,300,200,200,.4),))
    dense=TerrainMap(forests=(Forest(500,300,200,200,1),))
    u=Regiment(0,'foot',0,Vec(500,300))
    line=dense.movement_effect(u,Vec(1,0))
    assert light.movement_effect(u,Vec(1,0)).speed>line.speed
    assert dense.movement_effect(Regiment(1,'horse',0,u.pos,stats=CAVALRY),Vec(1,0)).speed<line.speed
    assert dense.movement_effect(Regiment(1,'gun',0,u.pos,stats=ARTILLERY),Vec(1,0)).speed<line.speed
    u.formation=Formation.COLUMN
    col=dense.movement_effect(u,Vec(1,0))
    assert col.speed>line.speed and col.loss_per_metre<line.loss_per_metre


def test_stationary_forest_troops_and_recovery_after_exit():
    terrain=TerrainMap(forests=(Forest(250,300,70,90,1),))
    u=Regiment(0,'stationary',0,Vec(250,300),cohesion=80)
    battle=Battle([u],sandbox=True,terrain=terrain)
    for _ in range(100): battle.step()
    assert u.cohesion>80 and u.terrain_loss==0
    u.order=Order(OrderKind.MOVE,Vec(550,300))
    lowest=100
    for _ in range(2400):
        battle.step(); lowest=min(lowest,u.cohesion)
    assert lowest<100
    assert (u.pos-Vec(550,300)).length()<1
    assert u.cohesion>lowest and u.terrain_loss==0

from simulation import combat, ai


def test_visibility_ridge_high_observer_and_forests():
    flat=TerrainMap()
    assert flat.visibility(Vec(100,300),Vec(800,300)).visible
    ridge=TerrainMap(hills=(Hill(500,300,40,200,30),))
    assert not ridge.visibility(Vec(400,300),Vec(600,300)).visible
    assert ridge.visibility(Vec(500,300),Vec(700,300)).visible
    forest=TerrainMap(forests=(Forest(500,300,160,150,1),))
    assert not forest.visibility(Vec(300,300),Vec(700,300)).visible
    close=forest.visibility(Vec(490,300),Vec(510,300))
    assert close.visible and 0<close.transmission<1
    edge=forest.visibility(Vec(300,300),Vec(350,300))
    assert edge.visible and edge.transmission>close.transmission


def test_hidden_infantry_cannot_fire_and_ai_does_not_acquire():
    terrain=TerrainMap(hills=(Hill(500,300,30,150,30),))
    a=Regiment(0,'a',0,Vec(440,300),order=Order(OrderKind.ADVANCE,Vec(500,300)))
    b=Regiment(1,'b',1,Vec(560,300),math.pi)
    battle=Battle([a,b],terrain=terrain,ai_armies={0})
    assert not battle.perceives(a,b)
    assert not combat.can_fire(battle,a,b)
    ai.army_plan(battle)
    assert a.order.target_id is None
    battle.step()
    assert a.target_id is None and a.pos.x>440 and b.strength==240


def test_forest_cover_reduces_statistical_musket_losses():
    losses=[]
    for terrain in (TerrainMap(),TerrainMap(forests=(Forest(350,300,45,60,.6),))):
        a=Regiment(0,'shooter',0,Vec(230,300))
        b=Regiment(1,'target',1,Vec(350,300),math.pi)
        battle=Battle([a,b],seed=17,terrain=terrain)
        for _ in range(10):
            a.reload_left=0; combat.fire(battle,a,b)
        losses.append(240-b.strength)
    assert losses[1]<losses[0]


def test_cavalry_charge_suppressed_by_forest(charging):
    losses=[]
    for cover in (0,1):
        a=Regiment(0,'horse',0,Vec(300,300),stats=CAVALRY,speed=7,forest_cover=cover)
        b=Regiment(1,'foot',1,Vec(315,300),forest_cover=cover)
        terrain=TerrainMap(forests=(Forest(300,300,100,100,cover),)) if cover else TerrainMap()
        battle=Battle([a,b],seed=17,terrain=terrain)
        from simulation import cavalry
        charging(a);a.cavalry_target_id=b.id;cavalry.after_move(battle,a,a.pos)
        combat.melee(battle,a,b); losses.append(240-b.strength)
    assert losses[1]<losses[0]

from simulation import projectiles


def test_projectile_launch_uses_absolute_elevations():
    terrain=TerrainMap(hills=(Hill(300,300,80,100,30),))
    gun=Regiment(0,'gun',0,Vec(300,300),stats=ARTILLERY)
    target=Regiment(1,'enemy',1,Vec(600,300))
    battle=Battle([gun,target],terrain=terrain)
    projectiles.launch(battle,gun,target)
    p=battle.projectiles[0]
    assert p.height==pytest.approx(31.2)
    flight=(target.pos-gun.pos).length()/100
    assert math.isfinite(p.vertical_speed)


def test_fast_ball_hits_narrow_hill_without_hitting_unit_behind():
    terrain=TerrainMap(hills=(Hill(500,300,1,50,25),))
    gun=Regiment(0,'gun',0,Vec(450,300),stats=ARTILLERY)
    enemy=Regiment(1,'behind ridge',1,Vec(540,300))
    battle=Battle([gun,enemy],terrain=terrain)
    p=projectiles.Projectile(Vec(450,300),Vec(1000,0),2,0,0)
    battle.projectiles=[p]
    projectiles.update(battle)
    assert p.bounces>0
    assert enemy.strength==240
    assert p.pos.x<540


def test_ball_clears_low_ridge_and_eventually_terminates():
    terrain=TerrainMap(hills=(Hill(500,300,20,100,4),))
    battle=Battle([],terrain=terrain)
    p=projectiles.Projectile(Vec(450,300),Vec(100,0),20,0,-1)
    battle.projectiles=[p]
    for _ in range(10): projectiles.update(battle)
    assert p.pos.x>500 and p.bounces==0
    for _ in range(200): projectiles.update(battle)
    assert not battle.projectiles


def test_sloping_impact_bounces_above_surface_and_loses_energy():
    terrain=TerrainMap(hills=(Hill(500,300,100,100,15),))
    battle=Battle([],terrain=terrain)
    p=projectiles.Projectile(Vec(430,300),Vec(30,0),terrain.get_elevation(430,300)+.3,-8,-1)
    battle.projectiles=[p]
    projectiles.update(battle)
    assert p.bounces>=1 and p.energy<1
    assert p.height>=terrain.get_elevation(p.pos.x,p.pos.y)
    assert p.vertical_speed>0


def test_forest_absorbs_projectile_energy_without_removing_friendly_fire():
    terrain=TerrainMap(forests=(Forest(500,300,200,200,1),))
    friend=Regiment(1,'friend',0,Vec(480,300))
    battle=Battle([friend],terrain=terrain)
    p=projectiles.Projectile(Vec(450,300),Vec(100,0),2,4,-1)
    battle.projectiles=[p]
    for _ in range(4): projectiles.update(battle)
    assert p.energy<.75 and friend.strength<240

from dataclasses import replace
from scenarios.battle_config import BattleConfig, ArmyConfig, ConfigError, DeploymentSession


@pytest.mark.parametrize('preset',TERRAIN_PRESETS)
def test_terrain_config_save_restart_rematch_and_legacy(preset,tmp_path):
    c=BattleConfig(seed=17,terrain_preset=preset).prepared()
    path=tmp_path/'map.json'; c.save(path)
    loaded=BattleConfig.load(path)
    assert loaded==c
    a,b=c.create_battle(),loaded.create_battle()
    assert a.terrain==b.terrain
    assert c.new_seed().create_battle().terrain==a.terrain
    assert c.new_seed().placements==c.placements
    for _ in range(30): a.step(); b.step()
    assert a.units==b.units and a.projectiles==b.projectiles
    legacy=c.to_dict()
    for key in ('terrain','terrain_preset','terrain_seed'): legacy.pop(key)
    assert BattleConfig.from_dict(legacy).create_battle().terrain.empty


def test_malformed_terrain_config_rejected():
    c=BattleConfig(seed=1,terrain_preset='Mixed Terrain').prepared().to_dict()
    c['terrain']['hills'][0]['radius_x']=0
    with pytest.raises(ConfigError): BattleConfig.from_dict(c)
    with pytest.raises(ConfigError): replace(BattleConfig(),terrain_preset='Ocean').prepared()
    with pytest.raises(ConfigError): replace(BattleConfig(),terrain=TerrainMap(500,500)).prepared()


def test_artillery_deployment_avoids_woods_without_forbidding_manual_placement():
    terrain=TerrainMap(forests=(Forest(250,300,100,200,1),))
    c=BattleConfig(seed=1,blue=ArmyConfig(0,0,2),red=ArmyConfig(0,0,2),terrain=terrain).prepared()
    assert all(terrain.forest_density(p.pos.x,p.pos.y)<.1 for p in c.placements)
    editor=DeploymentSession(c)
    editor.edit(0,pos=Vec(250,300))
    assert editor.config.placements[0].pos==Vec(250,300)


def test_local_terrain_route_is_bounded_and_can_complete():
    terrain=TerrainMap(forests=(Forest(400,300,55,55,1),))
    horse=Regiment(0,'horse',0,Vec(250,300),stats=CAVALRY,order=Order(OrderKind.MOVE,Vec(650,300)))
    battle=Battle([horse],sandbox=True,terrain=terrain)
    used=False; distance=0.; previous=horse.pos
    for _ in range(1600):
        battle.step(); distance+=(horse.pos-previous).length(); previous=horse.pos
        used|=horse.terrain_waypoint is not None
    assert used and (horse.pos-Vec(650,300)).length()<1
    assert distance<550


def test_hidden_explicit_attack_approaches_initial_last_known_position():
    terrain=TerrainMap(hills=(Hill(500,300,30,150,30),))
    a=Regiment(0,'attacker',0,Vec(440,300),order=Order(OrderKind.ATTACK,target_id=1))
    b=Regiment(1,'hidden',1,Vec(560,300))
    battle=Battle([a,b],terrain=terrain)
    assert not battle.visibility(a,b).visible
    battle.step()
    assert a.pos.x>440 and a.target_id is None
    assert a.last_seen_target_pos==Vec(560,300)


def test_ai_artillery_needs_spotting_but_explicit_player_bombardment_can_be_blind():
    terrain=TerrainMap(hills=(Hill(500,300,30,150,30),))
    gun=Regiment(0,'gun',0,Vec(440,300),stats=ARTILLERY,order=Order(OrderKind.ATTACK,target_id=1))
    target=Regiment(1,'hidden',1,Vec(560,300))
    battle=Battle([gun,target],terrain=terrain,ai_armies={0})
    assert not battle.perceives(gun,target)
    assert combat.select_fire_target(battle,gun) is None
    from viewer.targeting import target_status
    assert 'unspotted' in target_status(battle,gun,target)
    gun.player_attack=True
    assert combat.select_fire_target(battle,gun) is target
    combat.fire(battle,gun,target)
    assert battle.projectiles


def test_negative_gaussian_is_a_smooth_valley():
    valley=TerrainMap(hills=(Hill(500,300,100,100,-15),))
    assert valley.get_elevation(500,300)==-15
    assert valley.gradient(400,300).x<0


def test_visibility_cache_keys_include_terrain_and_rules():
    a=Regiment(0,'a',0,Vec(440,300)); b=Regiment(1,'b',1,Vec(560,300))
    battle=Battle([a,b])
    assert battle.visibility(a,b).visible
    battle.terrain=TerrainMap(hills=(Hill(500,300,30,150,30),))
    assert not battle.visibility(a,b).visible


def test_cavalry_in_the_same_forest_can_close_to_contact():
    terrain=TerrainMap(forests=(Forest(500,300,200,100,1),))
    a=Regiment(0,'horse',0,Vec(490,300),stats=CAVALRY,order=Order(OrderKind.ATTACK,target_id=1))
    b=Regiment(1,'enemy',1,Vec(510,300),math.pi,stats=CAVALRY)
    battle=Battle([a,b],terrain=terrain)
    for _ in range(30): battle.step()
    assert battle.melee_next


def test_elevated_battery_clears_ridge_that_blocks_low_battery():
    outcomes=[]
    for elevated in (False,True):
        hills=(Hill(300,300,20,80,8),)
        if elevated: hills+=(Hill(200,300,30,80,20),)
        terrain=TerrainMap(hills=hills)
        gun=Regiment(0,'gun',0,Vec(200,300),stats=ARTILLERY)
        target=Regiment(1,'target',1,Vec(400,300))
        # Isolate elevation geometry from the independently varied gun pitch.
        battle=Battle([gun,target],terrain=terrain,seed=17,rules=replace(Rules(),artillery_vertical_scatter=0.))
        projectiles.launch(battle,gun,target); p=battle.projectiles[0]
        for _ in range(20):
            projectiles.update(battle)
            if p.bounces or p.pos.x>335: break
        outcomes.append(p.bounces)
    assert outcomes[0]>0 and outcomes[1]==0
