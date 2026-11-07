"""The migration harness isolates current movement, not an older approximation."""
import json
from pathlib import Path
import os
import subprocess
import pytest
from migration_tools.movement_reference import create,queue_scheduled,movement_tick,state,compare,definitions,ROOT
from simulation.archetypes import ARCHETYPES


def test_shared_movement_data_matches_python_archetypes():
    rows=json.loads((ROOT/'simulation_data/movement_archetypes.json').read_text())
    shared={row['id']:row for row in rows if row['id'] in ARCHETYPES}
    assert set(shared)==set(ARCHETYPES), 'Every Python archetype must retain its native reference profile'
    assert all(row.get('campaignCore') for row in rows if row['id'] not in ARCHETYPES), 'Additional profiles must be explicitly native campaign content'
    for row in shared.values():
        a=ARCHETYPES[row['id']]
        assert (row['speed'],row['turnRate'],row['strength'])==(a.stats.speed,a.stats.turn_rate,a.stats.strength)
        assert row['formations']==[f.value for f in a.formations]
        assert (row['forestSlow'],row['forestLoss'],row['slopeLoss'])==(a.forest_slow,a.forest_loss,a.slope_loss)


@pytest.mark.parametrize('name',['straight','turning','formation','friendly-crossing','cavalry-overtaking','stationary-separation','artillery-march','woodland-march'])
def test_isolated_movement_matches_original_battle_sandbox(name):
    data=next(d for d in definitions() if d['name']==name)
    original,schedule=create(data);isolated,_=create(data)
    for _ in range(300):
        queue_scheduled(original,schedule);queue_scheduled(isolated,schedule)
        original.step();movement_tick(isolated)
    compare(dict(name=name,**state(original)),dict(name=name,**state(isolated)))


def test_godot_live_integration_when_dotnet_build_is_available(tmp_path):
    engine=ROOT/'.tools/godot-mono/Godot_v4.7.2-stable_mono_linux_x86_64/Godot_v4.7.2-stable_mono_linux.x86_64'
    assembly=ROOT/'godot/.godot/mono/temp/bin/Debug/Quiberon.dll'
    if not engine.exists() or not assembly.exists():pytest.skip('Build Godot .NET adapter to enable native live integration checks')
    env={**os.environ,'XDG_DATA_HOME':str(tmp_path/'data'),'XDG_CONFIG_HOME':str(tmp_path/'config'),'XDG_CACHE_HOME':str(tmp_path/'cache')}
    result=subprocess.run(['bash',str(ROOT/'tools/godot.sh'),'--headless','--quit-after','180','--script','tests/test_live.gd'],env=env,text=True,capture_output=True,timeout=45)
    output=result.stdout+result.stderr
    assert result.returncode==0 and 'failed: false' in output and 'SCRIPT ERROR' not in output,output
