"""M3 expectations are generated from current actual Python Battle.step()."""
import json
import os
import subprocess
import pytest
from migration_tools.dynamics_reference import ROOT,FIXTURES,SCENARIOS,calculation,trace,live_scenarios
from migration_tools.movement_reference import compare
from simulation.archetypes import ARCHETYPES


def test_shared_morale_and_cavalry_static_data_matches_python():
    rows=json.loads((ROOT/'simulation_data/movement_archetypes.json').read_text())
    shared={row['id']:row for row in rows if row['id'] in ARCHETYPES}
    assert set(shared)==set(ARCHETYPES), 'Every Python archetype must retain its native reference profile'
    assert all(row.get('campaignCore') for row in rows if row['id'] not in ARCHETYPES), 'Additional profiles must be explicitly native campaign content'
    for row in shared.values():
        a=ARCHETYPES[row['id']]
        assert row['discipline']==a.stats.discipline
        for field,attribute in [('melee','melee'),('shockResistance','shock_resistance'),('chargeSpeed','charge_speed'),('pursuit','pursuit'),('meleeDamage','melee_damage'),('meleeShock','melee_shock')]:assert row[field]==getattr(a,attribute)


@pytest.mark.parametrize('row',json.loads((FIXTURES/'calculations.json').read_text()),ids=lambda r:r['input']['name'])
def test_dynamics_calculation_oracle_still_describes_current_python(row):
    name=row['input']['name'];compare(dict(name=name,**row['expected']),dict(name=name,**calculation(row)))


@pytest.mark.parametrize('row',json.loads((FIXTURES/'traces.json').read_text()),ids=lambda r:r['input']['name'])
def test_actual_python_battle_trace_remains_current(row):
    compare(row['expected'],trace(row['input']))


def test_all_nine_live_scenarios_are_stable_data():
    for id,data in live_scenarios():assert data==json.loads((SCENARIOS/(id+'.json')).read_text())


def test_native_godot_dynamics_when_built(tmp_path):
    engine=ROOT/'.tools/godot-mono/Godot_v4.7.2-stable_mono_linux_x86_64/Godot_v4.7.2-stable_mono_linux.x86_64'
    assembly=ROOT/'godot/.godot/mono/temp/bin/Debug/Quiberon.dll'
    if not engine.exists() or not assembly.exists():pytest.skip('Build Godot .NET bridge to enable native dynamics checks')
    env={**os.environ,'XDG_DATA_HOME':str(tmp_path/'data'),'XDG_CONFIG_HOME':str(tmp_path/'config'),'XDG_CACHE_HOME':str(tmp_path/'cache')}
    result=subprocess.run(['bash',str(ROOT/'tools/godot.sh'),'--headless','--script','tests/test_dynamics.gd'],env=env,text=True,capture_output=True,timeout=45)
    output=result.stdout+result.stderr
    assert result.returncode==0 and 'Godot dynamics checks:' in output and 'failed: false' in output and 'SCRIPT ERROR' not in output,output
