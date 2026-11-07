"""Keep the C# oracle tied to current Python rules, with no game RNG changes."""
import json
import os
import subprocess
import pytest
from migration_tools.combat_reference import ROOT,FIXTURES,SCENARIOS,SplitMix64,calculation_reference,trace,live_scenarios
from migration_tools.movement_reference import compare
from simulation.archetypes import ARCHETYPES


def test_shared_musket_data_matches_current_python():
    infantry=next(row for row in json.loads((ROOT/'simulation_data/movement_archetypes.json').read_text()) if row['id']=='infantry')
    weapon=infantry['weapon'];reference=ARCHETYPES['infantry']
    assert weapon['range']==reference.stats.range
    assert weapon['reloadSeconds']==reference.stats.reload
    assert weapon['accuracy']==reference.accuracy


def test_portable_rng_matches_stored_cross_language_stream():
    rng=SplitMix64(17)
    assert [rng.random() for _ in range(100)]==json.loads((FIXTURES/'rng.json').read_text())


@pytest.mark.parametrize('row',json.loads((FIXTURES/'calculations.json').read_text()),ids=lambda row:row['input']['name'])
def test_calculation_oracle_remains_current(row):
    name=row['input']['name']
    compare(dict(name=name,**row['expected']),dict(name=name,**calculation_reference(row['input'],row['moving'])))


@pytest.mark.parametrize('row',json.loads((FIXTURES/'traces.json').read_text()),ids=lambda row:row['input']['name'])
def test_simplified_combat_trace_remains_current(row):
    compare(row['expected'],trace(row['input']))


def test_live_scenarios_are_reproducible_and_not_regenerated_by_the_viewer():
    for name,data in live_scenarios():assert data==json.loads((SCENARIOS/(name+'.json')).read_text())


def test_godot_combat_integration_when_built(tmp_path):
    engine=ROOT/'.tools/godot-mono/Godot_v4.7.2-stable_mono_linux_x86_64/Godot_v4.7.2-stable_mono_linux.x86_64'
    assembly=ROOT/'godot/.godot/mono/temp/bin/Debug/Quiberon.dll'
    if not engine.exists() or not assembly.exists():pytest.skip('Build Godot .NET adapter to enable native combat checks')
    env={**os.environ,'XDG_DATA_HOME':str(tmp_path/'data'),'XDG_CONFIG_HOME':str(tmp_path/'config'),'XDG_CACHE_HOME':str(tmp_path/'cache')}
    result=subprocess.run(['bash',str(ROOT/'tools/godot.sh'),'--headless','--script','tests/test_combat.gd'],env=env,text=True,capture_output=True,timeout=45)
    output=result.stdout+result.stderr
    assert result.returncode==0 and 'Godot combat checks:' in output and 'failed: false' in output and 'SCRIPT ERROR' not in output,output
