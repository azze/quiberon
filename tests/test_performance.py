"""Correctness guards for faster queries, frame budgets and render interpolation."""
import math
import os
import random
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
import pytest
from simulation.battle import Battle
from simulation.geometry import Vec, corners, separation, intersection_area, angle_delta
from simulation.regiment import Regiment
from simulation.formations import Formation
from simulation.orders import Command, Order, OrderKind
from simulation import combat
from simulation.terrain import generate_terrain, Visibility, TerrainRules
from simulation.projectiles import Projectile
from scenarios.battle_config import BattleConfig
from viewer.interpolation import MotionFrame
from viewer.application import Application
from viewer.renderer import Renderer
from viewer.controls import Controls
from viewer.camera import Camera
from viewer.terrain import TerrainPainter


def test_cached_corners_cannot_be_corrupted_and_track_pose_changes():
    a=Regiment(0,'a',0,Vec(100,100))
    original=a.footprint
    a.footprint.clear()
    assert a.footprint==original
    a.pos+=Vec(50,0)
    assert a.footprint!=original
    a.facing=math.pi/2
    assert a.footprint==corners(a.pos,a.facing,a.width,a.depth)
    a.formation=Formation.COLUMN
    assert a.footprint!=original


def test_broad_phase_matches_independent_polygon_intersection():
    rng=random.Random(7)
    for _ in range(500):
        a=Regiment(0,'a',0,Vec(300,300),rng.uniform(-math.pi,math.pi),formation=rng.choice(list(Formation)))
        b=Regiment(1,'b',1,Vec(rng.uniform(220,380),rng.uniform(220,380)),rng.uniform(-math.pi,math.pi),formation=rng.choice(list(Formation)))
        area=intersection_area(a,b)
        assert (separation(a,b) is not None)==(area>1e-7)


def test_far_collision_rejected_without_building_footprints():
    class FarUnit:
        width=64; depth=12; facing=0
        def __init__(self,pos): self.pos=pos
        @property
        def footprint(self): raise AssertionError('Far rectangles need no exact geometry')
    assert separation(FarUnit(Vec(0,0)),FarUnit(Vec(500,500))) is None


def test_target_range_and_arc_filter_precedes_perception():
    a=Regiment(0,'a',0,Vec(200,300))
    near=Regiment(1,'near',1,Vec(300,300))
    far=Regiment(2,'far',1,Vec(500,300))
    rear=Regiment(3,'rear',1,Vec(100,300))
    battle=Battle([a,near,far,rear]); visited=[]
    def perceives(observer,target): visited.append(target.id); return True
    battle.perceives=perceives
    assert combat.select_fire_target(battle,a) is near
    assert visited==[near.id]


def reference_sight(terrain,a,b,rules):
    # Original Vec-based sampler: fast implementation must retain exact results.
    delta=b-a; distance=delta.length()
    if distance<1e-8: return Visibility()
    count=max(1,math.ceil(distance/terrain.sample_step(rules.sight_step)))
    start=terrain.get_elevation(a.x,a.y)+rules.observer_height
    end=terrain.get_elevation(b.x,b.y)+rules.observer_height
    vegetation=0.
    for i in range(count):
        t=(i+.5)/count; p=a+delta*t
        ground=terrain.get_elevation(p.x,p.y); z=start+(end-start)*t
        if ground>z: return Visibility(False,0.,vegetation,'ridge')
        if z<ground+rules.canopy_height: vegetation+=terrain.forest_density(p.x,p.y)*distance/count
    if vegetation>=rules.forest_visibility_depth: return Visibility(False,0.,vegetation,'forest')
    return Visibility(True,math.exp(-vegetation/rules.forest_accuracy_depth),vegetation,'forest' if vegetation>1 else 'clear')


def test_visibility_early_exit_preserves_visibility_and_exact_visible_samples():
    terrain=generate_terrain('Mixed Terrain',1000,600,17); rng=random.Random(3)
    for _ in range(50):
        a,b=(Vec(rng.uniform(0,1000),rng.uniform(0,600)) for _ in range(2))
        actual=terrain.visibility(a,b);reference=reference_sight(terrain,a,b,TerrainRules())
        assert actual.visible==reference.visible and actual.transmission==reference.transmission
        if actual.visible:assert actual==reference
        else:assert actual.vegetation<=reference.vegetation+1e-10


def test_unit_interpolation_and_shortest_angle_are_read_only():
    u=Regiment(0,'a',0,Vec(200,300),math.pi-.1)
    battle=Battle([u]); motion=MotionFrame(battle)
    u.pos=Vec(220,310); u.facing=-math.pi+.1
    before=repr(u),battle.rng.getstate()
    midpoint=motion.unit_pose(u,.5)
    assert midpoint.pos==Vec(210,305)
    assert abs(angle_delta(midpoint.facing,math.pi))<1e-8
    assert motion.unit_pose(u,0).pos==Vec(200,300)
    assert motion.unit_pose(u,1).pos==u.pos
    assert before==(repr(u),battle.rng.getstate())


def test_projectile_interpolation_birth_and_bounce():
    battle=Battle([])
    p=Projectile(Vec(400,300),Vec(100,0),10,0,-1)
    battle.projectiles=[p]; frame=MotionFrame(battle)
    p.pos=Vec(410,300); p.height=8
    assert frame.ball_pose(p,.5).pos==Vec(405,300)
    assert frame.ball_pose(p,.5).height==9
    born=Projectile(Vec(500,300),Vec(100,0),5,0,-1)
    assert frame.ball_pose(born,.5).pos==born.pos
    p.bounces=1
    assert frame.ball_pose(p,.5).pos==p.pos


@pytest.fixture
def screen():
    pygame.init()
    surface=pygame.display.set_mode((1280,800))
    yield surface
    pygame.quit()


def test_budgeted_updates_stay_responsive_and_keep_deterministic_ticks(screen):
    class Clock:
        value=0.
        def __call__(self): return self.value
    clock=Clock(); app=Application(screen,clock=clock)
    config=BattleConfig(seed=17).prepared(); app.start(config)
    app.controls.speed=10; old_step=app.battle.step; ticks=[]
    def slow_step():
        ticks.append(app.battle.tick); old_step(); clock.value+=.020
    app.battle.step=slow_step
    for _ in range(10):
        app.update(.1)
        assert app.accumulator>=app.battle.rules.dt
    assert app.battle.tick==10 and ticks==list(range(10))
    assert app.accumulator==pytest.approx(9.)
    assert app.controls.slow and app.controls.actual_speed==pytest.approx(1.)
    direct=config.create_battle()
    for _ in range(10): direct.step()
    assert direct.units==app.battle.units and direct.rng.getstate()==app.battle.rng.getstate()
    app.controls.speed=1; app.update(.1)
    assert app.battle.tick==11 and app.accumulator==pytest.approx(9.)


def test_tick_count_cap_works_even_with_a_nonadvancing_clock(screen):
    app=Application(screen,clock=lambda:0.)
    app.start(BattleConfig(seed=1)); app.controls.speed=10; app.max_steps=2
    app.update(.25)
    assert app.battle.tick==2 and app.accumulator==pytest.approx(2.3) and app.controls.slow


def test_different_frame_rates_have_identical_simulation_at_matching_ticks(screen):
    config=BattleConfig(seed=17).prepared()
    snapshots=[]
    for fps in (30,60,120):
        app=Application(screen,clock=lambda:0.); app.start(config)
        for _ in range(fps*2): app.update(1/fps)
        assert app.battle.tick==20
        snapshots.append((app.battle.units,app.battle.rng.getstate()))
    assert snapshots[0]==snapshots[1]==snapshots[2]


def test_pause_restart_and_deployment_reset_interpolation(screen):
    app=Application(screen,clock=lambda:0.); app.start(BattleConfig(seed=17))
    # Player troops now idle by default; explicitly move to exercise interpolation.
    app.battle.issue(Command(0,Order(OrderKind.MOVE,app.battle.units[0].pos+Vec(100,0))))
    app.update(.15); app.draw()
    u=app.battle.units[0]
    assert app.renderer.unit_poses[u.id].pos!=u.pos
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE)); app.update(.2); app.draw()
    assert app.battle.tick==1 and app.renderer.unit_poses[u.id].pos==u.pos
    app.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE)); app.draw()
    assert app.renderer.unit_poses[u.id].pos==u.pos
    app.restart(); app.draw()
    assert app.battle.tick==0 and app.accumulator==0 and app.controls.actual_speed is None
    assert app.renderer.unit_poses[0].pos==app.battle.units[0].pos
    app.deploy(app.start_config); app.update(1.)
    assert app.deployment.battle.tick==0 and app.motion is None


def test_interpolated_hit_tests_and_projectiles_work_with_smoke(screen):
    u=Regiment(0,'selected',0,Vec(200,300))
    battle=Battle([u]); p=Projectile(Vec(500,450),Vec(100,0),5,0,-1)
    battle.projectiles=[p]; frame=MotionFrame(battle)
    u.pos=Vec(400,300); p.pos=Vec(520,450); p.height=7
    battle.effect('smoke',Vec(100,100),3,width=60)
    renderer=Renderer(screen,Camera(height=800)); controls=Controls()
    before=repr(battle.units),repr(battle.projectiles),battle.rng.getstate()
    renderer.draw(battle,controls,motion=frame,alpha=.5)
    assert renderer.unit_poses[0].pos==Vec(300,300)
    point=renderer.camera.world_to_screen(Vec(300,300))
    controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point),battle,renderer.camera,poses=renderer.unit_poses)
    assert controls.selected==0
    x,y=renderer.camera.world_to_screen(Vec(510,450))
    assert screen.get_at((round(x),round(y-6)))[:3]==(255,219,129)
    assert before==(repr(battle.units),repr(battle.projectiles),battle.rng.getstate())
    # A removed ball must not remain visible just because the old frame retained it.
    battle.projectiles=[]
    renderer.draw(battle,controls,motion=frame,alpha=.5)
    assert screen.get_at((round(x),round(y-6)))[:3]!=(255,219,129)


def test_cached_terrain_view_matches_uncached_and_invalidates(screen):
    terrain=generate_terrain('Mixed Terrain',1000,600,17)
    painter=TerrainPainter(); camera=Camera(height=800)
    screen.fill((40,59,41)); painter.draw(screen,camera,terrain)
    expected=pygame.image.tobytes(screen,'RGB'); first=painter._view; base=painter.surface
    screen.fill((40,59,41)); painter._draw_view(screen,camera,terrain,True)
    assert pygame.image.tobytes(screen,'RGB')==expected
    painter.draw(screen,camera,terrain)
    assert painter._view is first
    camera.center+=Vec(5,0); painter.draw(screen,camera,terrain)
    assert painter._view is not first and painter.surface is base
    previous=painter._view; painter.draw(screen,camera,terrain,False)
    assert painter._view is not previous
    previous=painter._view; camera.zoom*=1.2; painter.draw(screen,camera,terrain,False)
    assert painter._view is not previous


def test_benchmark_cli_emits_reproducible_headless_state(tmp_path):
    import json
    import subprocess
    import sys
    path=tmp_path/'performance.json'
    args=[sys.executable,'-m','analysis.performance','--terrain','Open Field','--warmup','0','--ticks','2','--output',str(path)]
    a=subprocess.run(args,check=True,capture_output=True,text=True)
    b=subprocess.run(args,check=True,capture_output=True,text=True)
    first,second=json.loads(a.stdout),json.loads(b.stdout)
    assert first['state_sha256']==second['state_sha256']
    assert first['end_tick']==2 and first['mean_tick_ms']>0
    assert json.loads(path.read_text())['battles'][0]==second
