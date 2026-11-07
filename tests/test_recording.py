"""Read-only export, tick timing, event history, byte offsets and stable IDs."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from migration_tools.recording import BattleRecorder,plain
from migration_tools.record_battle import create_battle,record
from analysis.performance import fingerprint
from simulation.projectiles import Projectile,launch
from simulation.geometry import Vec


def lines(path):return [json.loads(row) for row in path.read_text(encoding='utf-8').splitlines()]


def test_metadata_snapshots_static_identity_terrain_coordinates_and_offsets(tmp_path):
    b,name=create_battle(seed=2);b.seed=2**63-1
    with BattleRecorder(b,tmp_path,name,3) as writer:
        for _ in range(7):b.step();writer.capture()
    m=json.loads((tmp_path/'metadata.json').read_text());frames=lines(tmp_path/'frames.jsonl');index=lines(tmp_path/'index.jsonl')
    assert m['version']==1 and m['seed']==str(2**63-1) and m['scenario']==name
    assert m['terrain']==b.terrain.to_dict() and m['world']['width']==b.rules.width
    assert m['dt']==.1 and m['interval_ticks']==3 and m['status']=='limit'
    assert [f['tick'] for f in frames]==[0,3,6,7]
    assert [f['time'] for f in frames]==[t*.1 for t in (0,3,6,7)]
    assert all([u['id'] for u in f['units']]==[u.id for u in b.units] for f in frames)
    assert frames[-1]['units'][0]['position']==[b.units[0].pos.x,b.units[0].pos.y]
    assert frames[-1]['units'][0]['facing']==b.units[0].facing
    assert m['regiments'][0]['commander']==plain(b.units[0].commander.to_dict())
    with (tmp_path/'frames.jsonl').open('rb') as source:
        for entry,frame in zip(index,frames):
            source.seek(entry['offset']);assert json.loads(source.readline())==frame
    assert writer.closed and b.observer is None


def test_recording_does_not_consume_rng_change_outcomes_and_repeats_exact_bytes(tmp_path):
    def run(path):
        b,name=create_battle(seed=17)
        record(b,path,name,6.,2)
        return b
    a=run(tmp_path/'a');b=run(tmp_path/'b');control,_=create_battle(seed=17)
    for _ in range(60):control.step()
    assert fingerprint(a)==fingerprint(b)==fingerprint(control)
    assert a.rng.getstate()==control.rng.getstate()
    for key in ('metadata.json','frames.jsonl','index.jsonl','events.jsonl'):
        assert (tmp_path/'a'/key).read_bytes()==(tmp_path/'b'/key).read_bytes()


def test_projectile_identity_monotonic_in_frames_and_even_for_short_lived_shots(tmp_path):
    b,name=create_battle();gun=next(u for u in b.units if u.stats.kind.value=='artillery');target=next(u for u in b.units if u.army!=gun.army)
    with BattleRecorder(b,tmp_path,name) as w:
        launch(b,gun,target);first=b.projectiles[-1];fid=w.projectile(first)['id']
        # The same ball survives multiple captures, and position changes.
        b.tick+=1;w.capture();first.pos=first.pos+Vec(1,2);b.tick+=1;w.capture()
        b.projectiles.clear();b.tick+=1;w.capture()
        launch(b,gun,target);second=b.projectiles[-1];sid=w.projectile(second)['id']
        # Remove before a snapshot: its spawn event still exists.
        b.projectiles.clear();b.tick+=1;w.capture()
        assert sid>fid
    frames=lines(tmp_path/'frames.jsonl');events=lines(tmp_path/'events.jsonl')
    assert frames[1]['projectiles'][0]['id']==frames[2]['projectiles'][0]['id']==fid
    assert frames[1]['projectiles'][0]['position']!=frames[2]['projectiles'][0]['position']
    assert [e['projectile']['id'] for e in events if e['kind']=='projectile_spawn']==[fid,sid]
    assert not frames[-1]['projectiles']


def test_events_are_streamed_once_in_order_even_if_original_deque_overflows(tmp_path):
    b,name=create_battle()
    with BattleRecorder(b,tmp_path,name,5) as w:
        for i in range(300):b.log('casualties',f'event {i}',0)
        b.effect('smoke',Vec(10,20),3.,unit_id=0)
        b.tick=1;b.log('rout','routed',0)
        b.tick=5;w.capture()
    events=lines(tmp_path/'events.jsonl')
    assert len(events)==302 and len(b.events)==250
    assert [e['seq'] for e in events]==list(range(302))
    assert [e['time'] for e in events]==sorted(e['time'] for e in events)
    assert events[-2]['kind']=='volley' and events[-2]['position']==[10,20]
    assert events[-1]['unit_id']==0 and events[-1]['kind']=='rout'


def test_optional_observer_cleanup_errors_closed_and_existing_files(tmp_path):
    b,name=create_battle()
    with pytest.raises(ValueError):BattleRecorder(b,tmp_path,name,0)
    with pytest.raises(RuntimeError):
        with BattleRecorder(b,tmp_path,name) as w:
            with pytest.raises(ValueError):BattleRecorder(b,tmp_path/'duplicate')
            raise RuntimeError('stop')
    assert b.observer is None
    assert json.loads((tmp_path/'metadata.json').read_text())['status']=='incomplete'
    w.close()
    with pytest.raises(ValueError):w.capture()
    with pytest.raises(FileExistsError):BattleRecorder(b,tmp_path,name)


def test_actual_headless_battle_completion_recorded_not_invented(tmp_path):
    from scenarios.standard_battle import create
    b=create(1);name='standard'
    result=record(b,tmp_path,name,1200,20)
    assert result['result'] in ('army_0','army_1','draw')
    metadata=json.loads((tmp_path/'metadata.json').read_text())
    assert metadata['status']=='complete' and metadata['result']==b.result
    assert lines(tmp_path/'frames.jsonl')[-1]['result']==b.result
    assert metadata['report']['result']==b.result and any(e['kind']=='result' for e in lines(tmp_path/'events.jsonl'))


def test_godot_playback_contract_when_engine_is_available(tmp_path):
    import os
    import shutil
    import subprocess
    executable=shutil.which('godot') or shutil.which('godot4')
    if executable is None:pytest.skip('Godot 4 is not installed')
    root=Path(__file__).resolve().parents[1]
    env={**os.environ,'XDG_DATA_HOME':str(tmp_path/'data'),'XDG_CONFIG_HOME':str(tmp_path/'config'),'XDG_CACHE_HOME':str(tmp_path/'cache')}
    completed=subprocess.run([executable,'--headless','--path',str(root/'godot'),'--script','tests/test_playback.gd'],
                             env=env,text=True,capture_output=True,timeout=45)
    output=completed.stdout+completed.stderr
    assert completed.returncode==0,output
    assert 'failed: false' in output and 'SCRIPT ERROR' not in output,output
