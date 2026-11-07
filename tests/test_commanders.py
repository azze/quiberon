"""Officer identity, situational effects and deterministic personality decisions."""
import random
from dataclasses import replace,FrozenInstanceError
import pytest
from simulation.commanders import Commander,Personality as P,Specialization as S,generate,compatible
from simulation.regiment import Regiment,UnitType as U
from simulation.geometry import Vec
from simulation.battle import Battle
from simulation.orders import Order,OrderKind as O,Command
from scenarios.battle_config import BattleConfig,ConfigError,DeploymentSession


def officer(personality=P.METHODICAL,specialization=S.DRILLMASTER,uid='officer-1'):
    return Commander(uid,'Friedrich Adler','Prussia',personality,specialization,'Major','Fictional test officer.')


@pytest.mark.parametrize('kind',list(U))
def test_generation_is_seeded_unique_and_compatible(kind):
    def roster():
        rng=random.Random(17);names=set();ids=set()
        return [generate(rng,kind,'Prussia',names,ids) for _ in range(100)]
    a,b=roster(),roster()
    assert a==b and len({c.id for c in a})==100 and len({c.name for c in a})==100
    assert all(c.specialization in compatible(kind) for c in a)
    for c in a:c.validate(kind)


def test_haudenosaunee_names_use_the_supplied_pool_without_invented_surnames():
    from simulation.commanders import HAUDENOSAUNEE_NAMES
    c=generate(random.Random(17),U.INFANTRY,'Haudenosaunee Confederacy')
    assert c.name in HAUDENOSAUNEE_NAMES and c.rank==''


def test_commander_data_are_immutable_and_reject_invalid_traits_or_incompatible_assignment():
    c=officer();assert Commander.from_dict(c.to_dict())==c
    with pytest.raises(FrozenInstanceError):c.name='Changed'
    with pytest.raises(ValueError):replace(c,specialization=S.ARTILLERIST).validate(U.CAVALRY)
    with pytest.raises(ValueError):Commander.from_dict({**c.to_dict(),'personality':'unknown'})
    with pytest.raises(ValueError):replace(c,name='').validate()


def test_battle_generation_does_not_consume_combat_rng_and_every_regiment_gets_an_officer():
    units=lambda:[Regiment(i,str(i),i%2,Vec(200+i*90,300)) for i in range(4)]
    a=Battle(units(),seed=17);b=Battle(units(),seed=17,generate_commanders=False)
    assert a.rng.getstate()==b.rng.getstate()
    assert all(u.commander for u in a.units) and all(u.commander is None for u in b.units)
    assert [u.commander for u in a.units]==[u.commander for u in Battle(units(),seed=17).units]


def test_recipe_roundtrip_legacy_defaults_restart_rematch_and_reroll(tmp_path):
    config=BattleConfig(seed=17).prepared();path=tmp_path/'officers.json';config.save(path)
    assert BattleConfig.load(path)==config
    old=config.to_dict();old.pop('commander_seed');old.pop('commander_roll')
    for p in old['placements']:p.pop('commander')
    legacy=BattleConfig.from_dict(old).prepared()
    assert all(p.commander for p in legacy.placements)
    assert [p.commander for p in config.new_seed().placements]==[p.commander for p in config.placements]
    assert config.reroll_commander(0)==config.reroll_commander(0)
    new=config.reroll_commander(0)
    assert new.placements[0].commander!=config.placements[0].commander and new.seed==config.seed
    a,b=config.create_battle(),config.create_battle()
    a.units[0].commander_reform_until=99
    assert b.units[0].commander_reform_until==0 and a.units[0].commander==b.units[0].commander


def test_cross_faction_assignments_and_position_resets_keep_commanders():
    config=BattleConfig(seed=17).prepared();session=DeploymentSession(config)
    p=config.placements[0]
    session.edit(p.id,commander=officer())
    session.reset(p.id)
    assert session.config.placements[0].commander==officer()
    # The regiment stays generic; a Prussian background does not restrict it.
    assert session.config.placements[0].archetype_id==p.archetype_id


def test_duplicate_ids_and_incompatible_loaded_officers_are_rejected():
    config=BattleConfig(seed=17).prepared();a,b=config.placements[:2]
    with pytest.raises(ConfigError):replace(config,placements=tuple(replace(p,commander=a.commander) if p.id==b.id else p for p in config.placements)).validate()
    with pytest.raises(ConfigError):replace(config,placements=tuple(replace(p,commander=replace(officer(),specialization=S.ARTILLERIST)) if p.id==a.id else p for p in config.placements)).validate()

from simulation import commanders as cmd,commander_ai,archetypes,morale,combat,ai,movement,projectiles,cavalry
from simulation.regiment import MoraleState as M,CavalryState as C
from simulation.terrain import TerrainMap,Forest
from simulation.formations import Formation as F
import math


def led(spec=S.DRILLMASTER,personality=P.METHODICAL,kind=U.INFANTRY,**kw):
    return Regiment(0,'Led regiment',0,Vec(300,300),stats={U.INFANTRY:archetypes.INFANTRY,U.CAVALRY:archetypes.CAVALRY,U.ARTILLERY:archetypes.ARTILLERY}[kind],commander=officer(personality,spec),**kw)


def test_drill_changes_real_formation_time_turn_disruption_and_recovery():
    u=led();control=replace(u,commander=None)
    assert archetypes.formation_time(u,7)<archetypes.formation_time(control,7)
    movement.turn_to(u,math.pi/2,.1);movement.turn_to(control,math.pi/2,.1)
    assert u.cohesion>control.cohesion
    u.cohesion=control.cohesion=70
    morale.recover_cohesion(u,Battle([],sandbox=True).rules,1)
    morale.recover_cohesion(control,Battle([],sandbox=True).rules,1)
    assert u.cohesion>control.cohesion
    u.cohesion=30
    assert archetypes.formation_time(u,7)==7
    prussian=Regiment(2,'P',0,Vec(300,300),archetype_id='prussian_line',commander=officer())
    assert 3.5<=archetypes.formation_time(prussian,7)<4.2


def test_pathfinder_modifies_existing_forest_cost_not_open_field():
    u=led(S.PATHFINDER);control=replace(u,commander=None)
    terrain=TerrainMap(forests=(Forest(300,300,200,200,1),))
    benefit=terrain.movement_effect(u,Vec(1,0));ordinary=terrain.movement_effect(control,Vec(1,0))
    assert benefit.speed>ordinary.speed and benefit.loss_per_metre<ordinary.loss_per_metre
    assert TerrainMap().movement_effect(u,Vec(1,0))==TerrainMap().movement_effect(control,Vec(1,0))


def test_sharpshooter_improves_actual_volley_but_reloads_slower_and_requires_setup():
    totals=[]
    for officer_value in (officer(specialization=S.SHARPSHOOTER),None):
        u=Regiment(0,'fire',0,Vec(300,300),commander=officer_value)
        target=Regiment(1,'target',1,Vec(400,300),strength=100000)
        b=Battle([u,target],seed=5,generate_commanders=False)
        for _ in range(200):
            u.reload_left=0;combat.fire(b,u,target)
        totals.append(100000-target.strength)
        if officer_value:assert u.reload_left>u.stats.reload
    assert totals[0]>totals[1]
    u=led(S.SHARPSHOOTER)
    assert cmd.accuracy_factor(u,1)>cmd.accuracy_factor(u,.2)==1
    for state in ('moving','disordered','melee'):
        changed=replace(u,speed=1 if state=='moving' else 0,cohesion=20 if state=='disordered' else 100,combat_state='melee' if state=='melee' else 'idle')
        assert cmd.accuracy_factor(changed,1)==1


def test_artillerist_tightens_launched_trajectory_and_redeploys_slower():
    offsets=[]
    for has_commander in (False,True):
        u=led(S.ARTILLERIST,kind=U.ARTILLERY) if has_commander else Regiment(0,'control',0,Vec(300,300),stats=archetypes.ARTILLERY)
        target=Regiment(1,'target',1,Vec(550,300))
        b=Battle([u,target],seed=8,generate_commanders=False)
        projectiles.launch(b,u,target)
        shot=b.projectiles[0];offsets.append(abs(shot.velocity.y))
        movement.move(u,Vec(400,300),.1,1000,600)
        assert u.limbered
        if has_commander:assert u.limber_left>u.archetype.limber_seconds-.2
    assert offsets[1]<offsets[0]
    u.speed=2;assert cmd.scatter_factor(u)==1


def test_firebrand_charge_shock_is_situational_and_costs_cohesion(charging):
    shocks=[]
    for commander in (None,officer(P.AGGRESSIVE,S.FIREBRAND)):
        u=Regiment(0,'charger',0,Vec(300,300),stats=archetypes.CAVALRY,speed=10,commander=commander)
        target=Regiment(1,'exposed',1,Vec(320,300),0,cohesion=30)
        b=Battle([u,target],seed=8,generate_commanders=False);charging(u,.8)
        cavalry.impact(b,u,target)
        shocks.append((target.morale,u.cohesion))
    assert shocks[1][0]<shocks[0][0] and shocks[1][1]<shocks[0][1]
    assert cmd.charge_shock_factor(u,target,.1)==1
    assert cmd.charge_shock_factor(u,target,.8,prepared=True)==1


def test_pursuit_specialist_improves_bounded_pursuit_but_not_prepared_front():
    losses=[]
    for commander in (None,officer(P.AGGRESSIVE,S.PURSUIT)):
        u=Regiment(0,'cavalry',0,Vec(300,300),stats=archetypes.CAVALRY,commander=commander,cavalry_state=C.PURSUIT,cavalry_target_id=1,order=Order(O.ATTACK,target_id=1))
        enemy=Regiment(1,'fugitive',1,Vec(320,300),math.pi,state=M.ROUTING,morale=5,cohesion=20)
        b=Battle([u,enemy],seed=17,generate_commanders=False);b.pursuit_next[1]=0
        cavalry.pursuits(b,[u]);losses.append(enemy.stats.strength-enemy.strength)
    assert losses[1]>losses[0] and losses[1]<=enemy.stats.strength*b.rules.pursuit_max_fraction
    enemy.state=M.STEADY
    assert cmd.frontal_pursuit_penalty(u,enemy)==.9
    enemy.facing=0;assert cmd.frontal_pursuit_penalty(u,enemy)==1
    u.pursuit_id=enemy.id;assert cmd.pursuit_cohesion_factor(u)<1


def test_defensive_tactician_requires_prepared_frontal_position():
    u=led(S.DEFENSIVE,personality=P.STALWART);enemy=Regiment(1,'enemy',1,Vec(350,300))
    assert cmd.defence_factor(u,enemy)==.9
    assert cmd.recovery_factor(u)>1
    enemy.pos=Vec(250,300);assert cmd.defence_factor(u,enemy)==1
    u.order=Order(O.ATTACK,target_id=1)
    assert cmd.defence_factor(u)==1 and cmd.advance_factor(u)<1
    for state in (M.WAVERING,M.ROUTING):
        u.order=Order(O.HOLD);u.state=state;assert cmd.defence_factor(u)==1


def test_inspirer_and_royal_prestige_use_one_strongest_aura_and_stop_when_routing():
    def support(count,royal=False,routed=False):
        friend=Regiment(0,'friend',0,Vec(300,300),morale=50)
        allies=[Regiment(i+1,'support',0,Vec(300,350+i*4),archetype_id='royal_grenadiers' if royal and i==0 else 'infantry',
            commander=officer(specialization=S.INSPIRER,uid=f'officer-{i+1}') if i<count else None,
            state=M.ROUTING if routed else M.STEADY) for i in range(3)]
        b=Battle([friend,*allies],generate_commanders=False)
        morale.update(b);return friend.morale
    assert support(1)>support(0)
    assert support(1)==pytest.approx(support(3))
    assert support(1,royal=True)==pytest.approx(support(3,royal=True))
    assert support(1,routed=True)<support(1)


def decision_pair(personality,kind=U.INFANTRY,**kw):
    spec=S.PURSUIT if kind==U.CAVALRY else S.PATHFINDER
    u=led(spec,personality,kind,**kw)
    e=Regiment(1,'enemy',1,Vec(370,300),math.pi,strength=600)
    return Battle([u,e],ai_armies=(0,),generate_commanders=False),u,e


def test_cautious_disengages_before_stalwart_and_methodical_wait_is_bounded():
    cautious,u,e=decision_pair(P.CAUTIOUS)
    assert commander_ai.plan(cautious,u,[e],e) and u.order.kind==O.MOVE
    assert u.commander_retreat_until==10
    stalwart,v,f=decision_pair(P.STALWART)
    assert not commander_ai.plan(stalwart,v,[f],f)
    v.commander_melee_since=0;stalwart.tick=250
    assert not commander_ai.plan(stalwart,v,[f],f) # 2.5x opponent is below stalwart tolerance
    methodical,u,e=decision_pair(P.METHODICAL,cohesion=40)
    assert commander_ai.plan(methodical,u,[e],e) and u.order.kind==O.HOLD
    methodical.tick=100
    assert not commander_ai.plan(methodical,u,[e],e)


def test_aggressive_exploits_weak_enemy_and_cautious_keeps_firing_distance():
    aggressive,u,e=decision_pair(P.AGGRESSIVE);e.strength=100;e.cohesion=30;e.state=M.WAVERING
    ai.army_plan(aggressive)
    assert u.order.kind==O.CHARGE and u.order.target_id==e.id
    cautious,v,f=decision_pair(P.CAUTIOUS);f.strength=100;f.cohesion=30;f.state=M.WAVERING
    ai.army_plan(cautious)
    assert v.order.kind!=O.CHARGE
    assert cmd.policy(u).firing_distance<cmd.policy(v).firing_distance


def test_opportunistic_target_commitment_does_not_chatter():
    b,u,e=decision_pair(P.OPPORTUNISTIC);e.pos=Vec(420,300);e.strength=240
    weak=Regiment(2,'weak',1,Vec(460,350),cohesion=20,state=M.WAVERING)
    b.units.append(weak)
    chosen=commander_ai.select_target(b,u,[e,weak],e)
    assert chosen==weak
    e.cohesion=1;e.state=M.ROUTING
    b.tick=50
    assert commander_ai.select_target(b,u,[e,weak],e)==weak
    weak.cohesion=100;weak.state=M.STEADY
    b.tick=150;assert commander_ai.select_target(b,u,[e,weak],e)==e


@pytest.mark.parametrize('order',[Order(O.HOLD),Order(O.WITHDRAW),Order(O.ATTACK,target_id=1),Order(O.CHARGE,target_id=1)])
@pytest.mark.parametrize('personality',list(P))
def test_player_orders_take_priority_over_personality(order,personality):
    b,u,e=decision_pair(personality,cohesion=35)
    b.issue(Command(u.id,order));b.step()
    b.tick=50;ai.army_plan(b)
    assert u.order==order and u.player_order
    assert not commander_ai.plan(b,u,[e],e)


def test_cavalry_commitment_and_pursuit_limits_depend_on_personality():
    distances=[];commit=[]
    for p in (P.CAUTIOUS,P.AGGRESSIVE,P.OPPORTUNISTIC):
        b,u,e=decision_pair(p,kind=U.CAVALRY);e.pos=Vec(650,300)
        ai.army_plan(b);commit.append(u.cavalry_commit_at)
        e.state=M.ROUTING;u.cavalry_state=C.PURSUIT
        assert not commander_ai.pursuit_limit(b,u,e)
        u.pos+=Vec(150,0)
        distances.append(commander_ai.pursuit_limit(b,u,e))
    assert commit[2]<commit[1]<commit[0] and distances==[True,False,False]


def test_commander_replays_include_ai_state_and_rng():
    config=replace(BattleConfig(seed=6),ai_armies=(0,1)).prepared()
    a,b=config.create_battle(),config.create_battle()
    for _ in range(300):a.step();b.step()
    assert a.units==b.units and a.rng.getstate()==b.rng.getstate() and a.events==b.events


@pytest.mark.parametrize('name',__import__('scenarios.commander_comparisons',fromlist=['COMMANDER_PRESETS']).COMMANDER_PRESETS)
def test_commander_presets_are_editable_serializable_and_run_headlessly(name):
    from scenarios.presets import load_preset
    config=load_preset(name);config.validate(True)
    assert config==BattleConfig.from_dict(config.to_dict()) and config==load_preset(name)
    b=config.create_battle()
    for _ in range(100):b.step()
    assert all(u.commander and 0<=u.cohesion<=100 and 0<=u.morale<=100 for u in b.units)


def test_malformed_loaded_commander_is_a_clear_config_error():
    config=BattleConfig(seed=17).prepared().to_dict()
    config['placements'][0]['commander']['specialization']='unknown'
    with pytest.raises(ConfigError,match='Invalid battle configuration'):BattleConfig.from_dict(config)


def test_modifier_bounds_across_archetypes_formations_and_traits():
    for a in archetypes.ARCHETYPES.values():
        for spec in cmd.compatible(a.stats.kind):
            for personality in P:
                u=Regiment(0,'bounds',0,Vec(300,300),archetype_id=a.id,commander=officer(personality,spec))
                for cohesion in (0,30,60,100):
                    u.cohesion=cohesion
                    assert .5<=cmd.formation_factor(u)<=1
                    assert .4<=archetypes.manoeuvre_factor(u)<=1
                    assert archetypes.reload_time(u)>=.5
                    assert 1<=cmd.recovery_factor(u)<=1.25
                    assert .65<=cmd.shock_factor(u)<=1


def test_full_morale_support_skips_irrelevant_visibility_queries(monkeypatch):
    units=[Regiment(i,'support',0,Vec(200,150+i*80),morale=100,
        commander=officer(specialization=S.INSPIRER,uid=f'support-{i}')) for i in range(3)]
    battle=Battle(units)
    def unnecessary(*args):raise AssertionError('No morale benefit means no aura sight ray needed')
    monkeypatch.setattr(battle,'visibility',unnecessary)
    morale.update(battle)
    assert all(u.morale==100 for u in units)


@pytest.mark.parametrize('seed',[1,17,31])
def test_supplied_haudenosaunee_names_are_unique_before_pool_exhaustion_and_keep_accents(seed):
    from simulation.commanders import HAUDENOSAUNEE_NAMES
    expected=('Tyorhansera','Akiatonharónkwen','Tekarihoga','Thayendanegea','Sagoyewatha',
              'Skenandoah','Tewahongalahkon','Tyonajanegen','Atayataghlonghta')
    assert HAUDENOSAUNEE_NAMES==expected
    def roster():
        names=set();ids=set();rng=random.Random(seed)
        return [generate(rng,U.INFANTRY,'Haudenosaunee Confederacy',names,ids) for _ in range(12)]
    officers=roster();assert officers==roster()
    assert {c.name for c in officers[:9]}==set(expected)
    assert len({c.name for c in officers})==12 and len({c.id for c in officers})==12
    assert all(c.name.split(' (')[0] in expected and c.rank=='' for c in officers)
    assert [Commander.from_dict(c.to_dict()) for c in officers]==officers


def test_haudenosaunee_save_load_and_rematch_preserve_supplied_names(tmp_path):
    from scenarios.battle_config import ArmyConfig
    from simulation.commanders import HAUDENOSAUNEE_NAMES
    roster=ArmyConfig(0,0,0,(('haudenosaunee_skirmishers',3),))
    config=BattleConfig(seed=17,blue=roster,red=ArmyConfig(1,0,0),symmetric=False).prepared()
    path=tmp_path/'names.json';config.save(path);loaded=BattleConfig.load(path)
    assert loaded==config and loaded.new_seed().placements==config.placements
    assert all(p.commander.name in HAUDENOSAUNEE_NAMES for p in loaded.placements if p.army==0)
    # Explicit old assignments remain intact rather than being silently renamed.
    p=config.placements[0];legacy=replace(p.commander,name='Confederacy Delegate 001')
    updated=replace(config,placements=(replace(p,commander=legacy),*config.placements[1:]))
    assert BattleConfig.from_dict(updated.to_dict()).prepared().placements[0].commander==legacy
