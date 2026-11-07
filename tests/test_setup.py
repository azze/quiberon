from dataclasses import replace
import json
import math
import pytest
from scenarios.battle_config import ArmyConfig, BattleConfig, ConfigError, DeploymentSession, SIZES
from scenarios.presets import PRESETS, load_preset
from simulation.formations import Formation
from simulation.geometry import Vec, separation
from simulation.orders import Command, Order, OrderKind
from simulation.regiment import UnitType

@pytest.mark.parametrize('composition',[ArmyConfig(1,0,0),ArmyConfig(0,4,0),ArmyConfig(0,0,5),ArmyConfig(),ArmyConfig(12,0,0)])
@pytest.mark.parametrize('size',list(SIZES.values()))
def test_automatic_deployment(composition,size):
    c=BattleConfig(width=size[0],height=size[1],blue=composition,red=composition,seed=7).prepared()
    c.validate(True)
    b=c.create_battle()
    assert len(b.units)==composition.total*2
    assert (b.rules.width,b.rules.height)==size
    assert b.seed==7
    for i,u in enumerate(b.units):
        assert c.zone(u.army).contains(u)
        assert u.facing==pytest.approx(0 if u.army==0 else math.pi)
        assert not any(separation(u,v) for v in b.units[i+1:])


def test_symmetry_and_limits():
    c=BattleConfig().with_army(0,ArmyConfig(2,3,0))
    assert c.blue==c.red==ArmyConfig(2,3,0)
    with pytest.raises(ConfigError): c.with_army(1,ArmyConfig())
    c=replace(c,symmetric=False).with_army(1,ArmyConfig(0,0,1))
    c.prepared()
    for bad in [replace(c,blue=ArmyConfig(0,0,0)),replace(c,red=ArmyConfig(13,0,0)),replace(c,max_total=5),replace(c,width=float('nan'))]:
        with pytest.raises(ConfigError): bad.prepared()
    replace(c,blue=ArmyConfig(13,0,0),max_per_type=16).prepared()


def test_overcrowding_is_bounded_error():
    c=BattleConfig(width=600,height=400,blue=ArmyConfig(12,12,12),red=ArmyConfig(1,0,0),symmetric=False)
    with pytest.raises(ConfigError,match='cannot fit'): c.prepared()


def test_battle_instances_and_restarts_are_independent():
    c=BattleConfig(seed=5).prepared()
    a,b=c.create_battle(),c.create_battle()
    assert a.units==b.units
    assert all(x is not y for x,y in zip(a.units,b.units))
    for sim in (a,b):
        sim.issue(Command(0,Order(OrderKind.HOLD)))
        for _ in range(150): sim.step()
    assert a.units==b.units and list(a.events)==list(b.events)
    initial=c.create_battle()
    assert initial.tick==0 and initial.result is None
    assert not initial.projectiles and not initial.effects and not initial.melee_next
    assert initial.units==[p.regiment() for p in c.placements]
    assert all(u.morale==85 and u.cohesion==100 and u.strength==u.stats.strength for u in initial.units)
    rematch=c.new_seed()
    assert rematch.seed!=c.seed and rematch.placements==c.placements
    assert rematch.create_battle().rng.getstate()!=initial.rng.getstate()
    assert c.placements[0].pos==initial.units[0].pos


def test_json_roundtrip_custom_deployment_and_headless(tmp_path):
    c=BattleConfig(seed=37).prepared()
    session=DeploymentSession(c)
    p=c.placements[0]
    session.edit(p.id,formation=Formation.COLUMN,order=Order(OrderKind.RESERVE))
    path=tmp_path/'custom.json'; session.config.save(path)
    restored=BattleConfig.load(path)
    assert restored==session.config
    assert restored.create_battle().units==restored.create_battle().units
    a,b=restored.create_battle(),session.config.create_battle()
    for _ in range(100): a.step(); b.step()
    assert a.units==b.units


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(version=99),lambda d:d.update(seed='abc'),
    lambda d:d.update(width=float('inf')),lambda d:d.update(blue={'infantry':-1}),
    lambda d:d.update(ai_armies=[[]]),lambda d:d.update(symmetric='yes'),
    lambda d:d['placements'][0].update(position=[1]),
    lambda d:d['placements'][0].update(formation='square'),
    lambda d:d['placements'][0].update(position=[float('nan'),100]),
    lambda d:d['placements'][0]['order'].update(target_id=99999),
])
def test_invalid_loaded_data(mutation,tmp_path):
    data=BattleConfig(seed=1).prepared().to_dict(); mutation(data)
    path=tmp_path/'bad.json'; path.write_text(json.dumps(data))
    with pytest.raises(ConfigError): BattleConfig.load(path)


def test_bad_files_and_empty_armies(tmp_path):
    path=tmp_path/'bad.json'; path.write_text('{broken')
    with pytest.raises(ConfigError): BattleConfig.load(path)
    with pytest.raises(ConfigError): BattleConfig.load(tmp_path/'missing')
    with pytest.raises(ConfigError): BattleConfig.from_dict([])
    with pytest.raises(ConfigError): replace(BattleConfig(),blue=ArmyConfig(0,0,0),symmetric=False).prepared()


def test_transactional_manual_placement_and_reset():
    c=BattleConfig(seed=1).prepared(); editor=DeploymentSession(c)
    blue=next(p for p in c.placements if p.army==0)
    red=next(p for p in c.placements if p.army==1)
    for pos in [Vec(-50,100),Vec(c.width/2,c.height/2),red.pos]:
        with pytest.raises(ConfigError): editor.edit(blue.id,pos=pos)
        assert editor.config==c
    second=next(p for p in c.placements if p.army==0 and p.id!=blue.id)
    with pytest.raises(ConfigError,match='overlap'): editor.edit(blue.id,pos=second.pos)
    editor.edit(blue.id,pos=blue.pos+Vec(-20,0),facing=.15,formation=Formation.COLUMN)
    editor.config.validate(True)
    editor.reset(blue.id)
    assert editor.config==c
    # Red deployment is editable through the data layer, independently of GUI restrictions.
    editor.edit(red.id,order=Order(OrderKind.HOLD))
    assert editor.config!=c


def test_arbitrary_loaded_ids_can_reset():
    c=BattleConfig(seed=1).prepared()
    c=replace(c,placements=tuple(replace(p,id=p.id+100) for p in c.placements))
    editor=DeploymentSession(c)
    editor.edit(100,order=Order(OrderKind.HOLD)); editor.reset(100)
    assert editor.config==c

@pytest.mark.parametrize('name',PRESETS)
def test_presets(name): load_preset(name).prepared().validate(True)

@pytest.mark.parametrize('blue,red',[(ArmyConfig(2,0,0),ArmyConfig(2,0,0)),
    (ArmyConfig(0,2,0),ArmyConfig(0,2,0)),(ArmyConfig(0,0,2),ArmyConfig(0,0,2)),
    (ArmyConfig(1,0,0),ArmyConfig(8,3,2))])
def test_ai_compositions_and_dimensions(blue,red):
    c=BattleConfig(width=1600,height=1000,blue=blue,red=red,symmetric=False,seed=13,ai_armies=(0,1)).prepared()
    b=c.create_battle()
    for _ in range(200): b.step()
    assert b.tick==200
    for u in b.units:
        assert all(0<=p.x<=1600 and 0<=p.y<=1000 for p in u.footprint)
        if u.order.destination:
            assert 0<=u.order.destination.y<=1000


def test_battery_only_ai_closes_to_weapon_range():
    c=BattleConfig(width=1600,height=1000,blue=ArmyConfig(0,0,1),red=ArmyConfig(0,0,1),seed=1,ai_armies=(0,1)).prepared()
    b=c.create_battle(); before=(b.units[0].pos-b.units[1].pos).length()
    for _ in range(50): b.step()
    assert (b.units[0].pos-b.units[1].pos).length()<before


def test_saved_configuration_batch_cli_and_no_pygame_dependency(tmp_path):
    import subprocess
    import sys
    path=tmp_path/'headless.json'
    BattleConfig(seed=17).prepared().save(path)
    output=tmp_path/'results.json'
    subprocess.run([sys.executable,'-m','analysis.batch_simulation','--config',str(path),
                    '--runs','2','--duration','.2','--output',str(output)],check=True,capture_output=True,text=True)
    rows=json.loads(output.read_text())['battles']
    assert [r['seed'] for r in rows]==[17,18]
    assert all(r['duration']==.2 for r in rows)
    subprocess.run([sys.executable,'-c',
                    'import sys; from scenarios.battle_config import BattleConfig; '
                    'b=BattleConfig.load(sys.argv[1]).create_battle(); b.step(); '
                    'assert "pygame" not in sys.modules',str(path)],check=True,capture_output=True,text=True)


def test_valid_dense_import_does_not_require_grid_capacity():
    from scenarios.battle_config import Placement
    placements=[Placement(i,0,UnitType.INFANTRY,Vec(40+(i//4)*35,60+(i%4)*90),0) for i in range(13)]
    placements.append(Placement(13,1,UnitType.INFANTRY,Vec(500,200),math.pi))
    c=BattleConfig(width=600,height=400,blue=ArmyConfig(13,0,0),red=ArmyConfig(1,0,0),symmetric=False,
                   max_per_type=16,seed=1,placements=tuple(placements))
    c.validate(True)
    session=DeploymentSession(c)
    assert session.config==session.automatic==c.prepared()
    session.edit(0,order=Order(OrderKind.RESERVE)); session.reset(0)
    assert session.config==c.prepared()
