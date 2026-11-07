import math
from dataclasses import replace
import pytest
from simulation.archetypes import ARCHETYPES, Trait, drill, reload_time, formation_time, aimed_bonus, exploit_bonus
from simulation.battle import Battle
from simulation.config import Rules
from simulation.formations import Formation, PROFILES
from simulation.geometry import Vec, separation
from simulation.regiment import Regiment, UnitType, MoraleState
from simulation.orders import Command, Order, OrderKind
from simulation.terrain import TerrainMap, Forest
from simulation import combat, morale, movement, ai, projectiles
from scenarios.battle_config import ArmyConfig, BattleConfig, ConfigError, DeploymentSession, SIZES
from scenarios.presets import SPECIALIST_PRESETS, load_preset
from analysis.matchups import swap_sides
from analysis.batch_simulation import type_statistics


def unit(key='infantry',uid=0,army=0,pos=Vec(250,300),**kwargs):
    return Regiment(uid,key,army,pos,0 if army==0 else math.pi,archetype_id=key,**kwargs)


@pytest.mark.parametrize('key',list(ARCHETYPES))
def test_archetype_definitions_and_supported_formations(key):
    a=ARCHETYPES[key]; u=unit(key)
    assert a.id==key and a.stats==u.stats and u.morale==a.initial_morale
    assert u.strength==a.stats.strength>0 and 0<u.stats.speed<12 and 0<u.stats.reload<60
    assert a.default_formation in a.formations and u.formation==a.default_formation
    assert len({x.id for x in ARCHETYPES.values()})==len(ARCHETYPES)==9
    for formation in a.formations:
        assert formation in PROFILES
        u.formation=formation
        assert u.width>0 and u.depth>0 and len(u.footprint)==4
    for value in (a.accuracy,a.melee,a.shock_resistance,a.recovery,a.forest_slow,a.forest_loss,a.projectile_power):
        assert 0<value<3


def test_generic_custom_stats_and_mutable_state_stay_independent():
    from simulation.regiment import INFANTRY
    stats=replace(INFANTRY,range=170)
    a,b=Regiment(0,'custom',0,Vec(200,300),stats=stats),unit('prussian_line',uid=1)
    assert a.stats.range==170 and a.archetype.id=='infantry'
    battle=Battle([a,b]); battle.activate(b,'drill')
    assert a.analysis['trait_activations']==0 and not a.trait_next


def test_prussian_drill_fades_with_cohesion_and_changes_manoeuvres():
    u=unit('prussian_line'); ordinary=unit()
    assert drill(u)==1 and reload_time(u)<reload_time(ordinary)
    assert formation_time(u,7)<7
    moving=replace(u); moving.cohesion=100
    movement.turn_to(moving,math.pi/2,.1)
    movement.turn_to(ordinary,math.pi/2,.1)
    assert moving.cohesion>ordinary.cohesion
    u.cohesion=40
    assert drill(u)==0 and reload_time(u)==u.stats.reload and formation_time(u,7)==7
    u.cohesion=65
    assert drill(u)==.5
    battle=Battle([u],sandbox=True)
    battle.issue(Command(u.id,formation=Formation.COLUMN)); battle.step()
    assert 0<u.transition_left<7 and battle.events


def wooded(density=1): return TerrainMap(forests=(Forest(300,300,240,200,density),))


def test_woodland_terrain_and_column_or_loose_formation_advantages():
    terrain=wooded(); rules=Rules().terrain
    ordinary=unit(pos=Vec(300,300)); prussian=unit('prussian_line',pos=ordinary.pos)
    wood=unit('haudenosaunee_skirmishers',pos=ordinary.pos)
    cavalry=unit('commonwealth_uhlans',pos=ordinary.pos)
    effect=lambda u:terrain.movement_effect(u,Vec(1,0),rules)
    assert effect(wood).speed>effect(ordinary).speed>effect(cavalry).speed
    assert effect(wood).loss_per_metre<effect(ordinary).loss_per_metre<effect(prussian).loss_per_metre
    wood.formation=Formation.COLUMN
    assert effect(wood).loss_per_metre<effect(ordinary).loss_per_metre
    wood.formation=Formation.SKIRMISH; wood.cohesion=70
    battle=Battle([wood],terrain=terrain,sandbox=True)
    for _ in range(50): battle.step()
    assert wood.cohesion>=70 and wood.terrain_loss==0


def test_concealment_modifies_existing_visibility_without_hiding_open_troops():
    observer=unit(pos=Vec(250,300))
    ordinary=unit(uid=1,army=1,pos=Vec(305,300))
    wood=unit('haudenosaunee_skirmishers',uid=2,army=1,pos=ordinary.pos)
    battle=Battle([observer,ordinary,wood],terrain=wooded())
    assert battle.visibility(observer,ordinary).visible
    assert not battle.visibility(observer,wood).visible
    assert not combat.can_fire(battle,observer,wood)
    battle.terrain=TerrainMap()
    assert battle.visibility(observer,wood).visible and battle.visibility(observer,wood).transmission==1


def test_dispersal_reduces_incoming_fire_but_also_volume_and_melee():
    results=[]
    for formation in (Formation.LINE,Formation.SKIRMISH):
        shooter=unit(); target=unit('revolutionary_rifles',uid=1,army=1,pos=Vec(350,300),formation=formation,strength=2000)
        battle=Battle([shooter,target],seed=11)
        for _ in range(80):
            shooter.reload_left=0; combat.fire(battle,shooter,target)
        results.append(2000-target.strength)
    assert results[1]<results[0]*.8
    assert PROFILES[Formation.SKIRMISH][4]<PROFILES[Formation.LINE][4]
    wood=unit('haudenosaunee_skirmishers'); cavalry=unit('commonwealth_uhlans',uid=1,army=1,pos=Vec(260,300),speed=9)
    battle=Battle([wood,cavalry],seed=1); combat.melee(battle,cavalry,wood)
    assert wood.strength<wood.stats.strength and wood.cohesion<100


def test_prestige_support_is_capped_and_ends_when_guards_rout():
    def shock(guards,routed=False):
        friend=unit(pos=Vec(300,300),morale=55)
        source=unit(uid=1,pos=Vec(330,300),morale=1)
        # Equal ordinary support counts isolate the aura, rather than baseline nearby-friend bonuses.
        allies=[unit('royal_grenadiers' if i<guards else 'infantry',uid=i+2,pos=Vec(300,350+i*3),
                     state=MoraleState.ROUTING if routed and i<guards else MoraleState.STEADY) for i in range(3)]
        battle=Battle([friend,source,*allies]); morale.update(battle)
        return friend.morale
    assert shock(1)>shock(0)
    assert shock(1)==pytest.approx(shock(3))
    assert shock(1,routed=True)<shock(1)
    a=unit('royal_grenadiers'); assert morale.prestige_support(Battle([a]),a) is None


def test_aimed_fire_requires_stationary_cohesion_and_visibility():
    rifle=unit('revolutionary_rifles')
    assert aimed_bonus(rifle,1)==1.35
    rifle.speed=1; assert aimed_bonus(rifle,1)==1
    rifle.speed=0; rifle.cohesion=20; assert aimed_bonus(rifle,1)==1
    rifle.cohesion=100; assert aimed_bonus(rifle,.3)==1
    rifle.combat_state='melee'; assert aimed_bonus(rifle,1)==1
    assert rifle.stats.reload>ARCHETYPES['infantry'].stats.reload and rifle.stats.range>155


def test_exploit_break_is_charge_only_and_prepared_front_counters_it(charging):
    uhlan=unit('commonwealth_uhlans',speed=9)
    target=unit(uid=1,army=1,pos=Vec(260,300),cohesion=30)
    assert exploit_bonus(uhlan,target,False)>1
    assert exploit_bonus(uhlan,target,True)==1
    uhlan.speed=2; assert exploit_bonus(uhlan,target,False)==1
    losses=[]
    for prepared in (True,False):
        horse=unit('commonwealth_uhlans',speed=9)
        foot=unit(uid=1,army=1,pos=Vec(260,300),cohesion=100 if prepared else 30)
        battle=Battle([horse,foot],seed=3); charging(horse); combat.melee(battle,horse,foot)
        losses.append(240-foot.strength)
    assert losses[1]>losses[0]


def test_rapid_redeployment_blocks_firing_during_movement_and_shortens_setup():
    ready=[]
    for key in ('artillery','french_horse_artillery'):
        gun=unit(key); target=unit(uid=1,army=1,pos=Vec(450,300))
        battle=Battle([gun,target],seed=1)
        movement.move(gun,Vec(300,300),.1,1000,600)
        assert gun.limbered and not combat.can_fire(battle,gun,target)
        assert gun.pos==Vec(250,300)
        for _ in range(40): movement.move(gun,Vec(300,300),.1,1000,600)
        assert gun.pos.x>250
        elapsed=0
        while gun.limbered:
            movement.move(gun,None,.1,1000,600); elapsed+=.1
            assert elapsed<10
        assert combat.can_fire(battle,gun,target)
        projectiles.launch(battle,gun,target)
        assert battle.projectiles[0].energy==gun.archetype.projectile_power
        ready.append(elapsed)
    assert ready[1]<ready[0]/2


def test_skirmish_withdrawal_has_hysteresis_and_explicit_orders_take_priority():
    wood=unit('haudenosaunee_skirmishers',order=Order(OrderKind.SKIRMISH))
    enemy=unit(uid=1,army=1,pos=Vec(300,300))
    battle=Battle([wood,enemy],sandbox=True)
    start=wood.pos
    signs=[]
    for _ in range(230):
        battle.step(); signs.append(wood.skirmish_retreat)
    assert wood.pos.x<start.x
    changes=sum(a!=b for a,b in zip(signs,signs[1:]))
    assert 1<=changes<=4 and any(not x for x in signs[70:140])
    battle.issue(Command(wood.id,Order(OrderKind.MOVE,Vec(400,300))))
    battle.step()
    assert not wood.skirmish_retreat and ai.destination(battle,wood)==Vec(400,300)
    battle.issue(Command(wood.id,Order(OrderKind.HOLD))); battle.step()
    assert ai.destination(battle,wood) is None


def test_skirmishers_can_fire_after_retreat_and_interact_with_friends():
    wood=unit('haudenosaunee_skirmishers',order=Order(OrderKind.SKIRMISH))
    enemy=unit(uid=1,army=1,pos=Vec(300,300),reload_left=9999)
    friend=unit(uid=2,pos=wood.pos)
    battle=Battle([wood,enemy,friend],seed=2)
    overlap=False
    for _ in range(900):
        battle.step(); overlap|=wood.congestion>.1
    assert overlap and wood.analysis['volleys']>0 and wood.analysis['trait_activations']>0
    assert wood.analysis['moving_seconds']>0


@pytest.mark.parametrize('size',SIZES.values())
def test_mixed_armies_deployment_save_load_reset_and_restarts(size,tmp_path):
    roster=ArmyConfig(1,1,1,tuple((key,1) for key,a in ARCHETYPES.items() if a.trait))
    config=BattleConfig(width=size[0],height=size[1],blue=roster,red=roster,seed=31).prepared()
    config.validate(True)
    battle=config.create_battle()
    assert len(battle.units)==18 and len({u.archetype.id for u in battle.units})==9
    for u in battle.units:
        assert config.zone(u.army).contains(u)
        assert not any(separation(u,v) for v in battle.units if v.id!=u.id)
    path=tmp_path/'mixed.json'; config.save(path)
    assert BattleConfig.load(path)==config
    editor=DeploymentSession(config)
    specialist=next(p for p in config.placements if p.archetype_id)
    editor.edit(specialist.id,order=Order(OrderKind.HOLD)); editor.reset(specialist.id)
    assert editor.config==config
    a,b=config.create_battle(),config.create_battle()
    for _ in range(100): a.step(); b.step()
    assert a.units==b.units and a.rng.getstate()==b.rng.getstate()
    assert config.new_seed().placements==config.placements
    swapped=swap_sides(config); swapped.validate(True)
    assert swapped.terrain==config.terrain and swap_sides(swapped).blue==config.blue


def test_invalid_specialist_rosters_and_unsupported_formations():
    for roster in (ArmyConfig(0,0,0,(('unknown',1),)),ArmyConfig(0,0,0,(('prussian_line',13),)),
                   ArmyConfig(0,0,0,(('infantry',1),)),ArmyConfig(0,0,0,(('prussian_line',1),('prussian_line',2)))):
        with pytest.raises(ConfigError): BattleConfig(blue=roster,red=roster).prepared()
    config=load_preset('Woodland Encounter').prepared(); p=config.placements[0]
    with pytest.raises(ConfigError): replace(config,placements=(replace(p,formation=Formation.LINE),*config.placements[1:])).validate(True)
    battle=config.create_battle(); battle.issue(Command(p.id,formation=Formation.LINE)); battle.step()
    assert battle.unit(p.id).formation==Formation.SKIRMISH and not battle.unit(p.id).transition_left


@pytest.mark.parametrize('preset',SPECIALIST_PRESETS)
def test_specialist_ai_runs_without_invalid_states(preset):
    config=replace(load_preset(preset),seed=3,ai_armies=(0,1)).prepared()
    battle=config.create_battle()
    for _ in range(250): battle.step()
    assert battle.tick==250
    for u in battle.units:
        assert 0<=u.strength<=u.stats.strength and 0<=u.cohesion<=100 and 0<=u.morale<=100
        assert all(-1e-6<=p.x<=1000.00001 and -1e-6<=p.y<=600.00001 for p in u.footprint)
    assert type_statistics(battle)


def test_uhlans_choose_disrupted_target_and_commit_instead_of_circling():
    u=unit('commonwealth_uhlans',order=Order(OrderKind.HOLD))
    steady=unit(uid=1,army=1,pos=Vec(600,300))
    routed=unit(uid=2,army=1,pos=Vec(610,350),state=MoraleState.ROUTING,cohesion=20)
    battle=Battle([u,steady,routed],ai_armies=(0,))
    ai.army_plan(battle)
    battle.tick=200; ai.army_plan(battle)
    assert u.order.kind==OrderKind.ATTACK and u.order.target_id==routed.id
    steady.withdrawn=True
    u.order=Order(OrderKind.HOLD)
    ai.army_plan(battle)
    assert u.order.kind==OrderKind.ATTACK and u.order.target_id==routed.id


def test_mobile_battery_finishes_redeployment_and_fires():
    gun=unit('french_horse_artillery',order=Order(OrderKind.MOVE,Vec(300,300)))
    target=unit(uid=1,army=1,pos=Vec(480,300),reload_left=9999)
    battle=Battle([gun,target],ai_armies=(0,),seed=8)
    battle.issue(Command(gun.id,Order(OrderKind.MOVE,Vec(300,300))))
    for _ in range(900): battle.step()
    assert gun.analysis['moving_seconds']>0 and gun.analysis['volleys']>0
    assert gun.analysis['trait_activations']>0 and not gun.limbered
