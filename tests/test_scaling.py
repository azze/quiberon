"""Exact broad-phase/cache guards; wall-clock speed is deliberately not asserted."""
from dataclasses import replace
import math
import random
import pytest
from simulation.spatial import SpatialIndex, candidate_pairs
from simulation.geometry import Vec, separation, touching, segment_rect
from simulation.regiment import Regiment
from simulation.formations import Formation
from simulation.terrain import TerrainMap, TerrainRules, generate_terrain
from simulation.battle import Battle
from simulation import ai, movement, combat
from analysis.scaling import scenario, measure
from analysis.performance import fingerprint


def test_spatial_queries_are_conservative_and_keep_original_order():
    rng=random.Random(29)
    units=[Regiment(i,str(i),i%2,Vec(rng.uniform(-150,500),rng.uniform(-100,500)),rng.random()*6,
                    formation=rng.choice(list(Formation))) for i in reversed(range(45))]
    index=SpatialIndex(units,padding=1.5)
    pairs=list(index.pairs()); indices={u.id:i for i,u in enumerate(units)}
    assert [(indices[a.id],indices[b.id]) for a,b in pairs]==sorted((indices[a.id],indices[b.id]) for a,b in pairs)
    candidates={(a.id,b.id) for a,b in pairs}
    for i,a in enumerate(units):
        for b in units[i+1:]:
            if touching(a,b): assert (a.id,b.id) in candidates
    for _ in range(100):
        start,end=(Vec(rng.uniform(-200,600),rng.uniform(-200,600)) for _ in range(2))
        queried=list(index.segment(start,end)); ids={u.id for u in queried}
        assert [indices[u.id] for u in queried]==sorted(indices[u.id] for u in queried)
        assert all(u.id in ids for u in units if segment_rect(start,end,u) is not None)


def test_indexed_tick_matches_all_pairs_reference(monkeypatch):
    from simulation import battle as module
    config=scenario(24,'Mixed Terrain',31)
    fast,slow=config.create_battle(),config.create_battle()
    def all_pairs(units,padding=0): return ((a,b) for i,a in enumerate(units) for b in units[i+1:])
    class LinearIndex:
        def __init__(self,units): self.units=units
        def segment(self,a,b,padding=0.): return self.units
    for _ in range(200):
        fast.step()
        with monkeypatch.context() as patch:
            for mod in (movement,combat,module): patch.setattr(mod,'candidate_pairs',all_pairs)
            patch.setattr(module,'SpatialIndex',LinearIndex)
            slow.step()
    assert fingerprint(fast)==fingerprint(slow) and fast.melee_next==slow.melee_next


def test_nearest_visible_search_is_stable_lazy_and_unbounded():
    source=Regiment(0,'source',0,Vec(200,300))
    near=Regiment(1,'hidden',1,Vec(250,300))
    a=Regiment(2,'tie first',1,Vec(500,250)); b=Regiment(3,'tie second',1,Vec(500,350))
    far=Regiment(4,'far',1,Vec(900,300))
    battle=Battle([source,near,a,b,far]); visited=[]
    def sees(observer,target): visited.append(target.id); return target.id!=1
    battle.perceives=sees
    ai.destination(battle,source)
    assert source.target_id==2 and 4 not in visited and 3 not in visited
    assert (a.pos-source.pos).length()>source.stats.range


def test_exact_sight_cache_tracks_geometry_rules_terrain_and_concealment():
    terrain=generate_terrain('Mixed Terrain',1000,600,17)
    a,b=Regiment(0,'a',0,Vec(200,300)),Regiment(1,'b',1,Vec(400,300))
    battle=Battle([a,b],terrain=terrain)
    first=battle.visibility(a,b)
    assert battle.visibility(a,b) is first
    b.pos=Vec(450,300)
    assert battle.visibility(a,b)==terrain.visibility(a.pos,b.pos,battle.rules.terrain)
    battle.rules=replace(battle.rules,terrain=replace(battle.rules.terrain,observer_height=10))
    assert battle.visibility(a,b)==terrain.visibility(a.pos,b.pos,battle.rules.terrain)
    battle.terrain=TerrainMap()
    assert battle.visibility(a,b).visible and battle.visibility(a,b).transmission==1
    for i in range(32800):
        b.pos=Vec(i*.001,300); battle.visibility(a,b)
    assert len(battle._visibility_cache)<=32768


def test_scalar_terrain_math_matches_original_feature_methods_exactly():
    terrain=generate_terrain('Mixed Terrain',1000,600,17);rng=random.Random(2)
    for _ in range(500):
        x,y=rng.uniform(-50,1050),rng.uniform(-50,650)
        assert terrain.get_elevation(x,y)==sum((h.elevation(x,y) for h in terrain.hills),0.)
        assert terrain.forest_density(x,y)==max((f.cover(x,y) for f in terrain.forests),default=0.)


def test_footprint_cache_tracks_facing_motion_and_formation_without_serialization():
    terrain=generate_terrain('Mixed Terrain',1000,600,17);u=Regiment(0,'unit',0,Vec(300,300))
    for facing,formation,motion in ((0,Formation.LINE,Vec(1,0)),(.2,Formation.LINE,Vec(0,1)),(.2,Formation.COLUMN,Vec(0,0))):
        u.facing=facing;u.formation=formation
        cached=terrain.movement_effect(u,motion)
        fresh=replace(terrain).movement_effect(u,motion)
        assert fresh==cached
    assert terrain==replace(terrain) and '_footprint_cache' not in terrain.to_dict()
    for i in range(2100): u.pos=Vec(i*.1,300);terrain.movement_effect(u,Vec(1,0))
    assert len(terrain._footprint_cache)<=2048


def test_benchmark_activity_and_replays():
    row=measure(scenario(6,'Open Field'),0,2,repeats=2)
    assert row['tick']['mean_ms']>0 and row['active_units_mean']==6
    assert row['measured_ticks']==2 and len(row['repeat_ticks'])==2
    assert row['simulated_seconds']==.2


def test_scaling_cli_json_csv_profile_and_comparison(tmp_path):
    import subprocess
    import sys
    import json
    import csv
    path=tmp_path/'benchmark.csv'
    args=[sys.executable,'-m','analysis.scaling','--counts','6','--terrains','Open Field',
          '--warmup','0','--ticks','2','--repeats','1','--output',str(path)]
    subprocess.run(args+['--profile-dir',str(tmp_path/'profiles')],check=True,capture_output=True,text=True)
    saved=json.loads(path.with_suffix('.json').read_text())
    assert saved['workload']=='forward130-v1'
    assert list(csv.DictReader(path.open()))[0]['units']=='6'
    assert (tmp_path/'profiles'/'6-Open_Field.prof').exists()
    result=subprocess.run(args+['--compare',str(path.with_suffix('.json'))],check=True,capture_output=True,text=True)
    assert 'exact=True' in result.stdout


def test_large_elapsed_time_is_retained_and_eventually_processed():
    import os
    os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
    import pygame
    from viewer.application import Application
    pygame.init()
    try:
        app=Application(pygame.display.set_mode((1280,800)),clock=lambda:0.)
        config=scenario(6,'Open Field');app.start(config)
        app.update(.8)
        assert app.battle.tick==4 and app.accumulator==pytest.approx(.4)
        app.update(0.)
        assert app.battle.tick==8 and app.accumulator==pytest.approx(0.)
        direct=config.create_battle()
        for _ in range(8):direct.step()
        assert fingerprint(app.battle)==fingerprint(direct)
    finally:pygame.quit()
