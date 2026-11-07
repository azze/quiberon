import math
import sys
import pytest
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec, segment_rect
from simulation.regiment import Regiment, MoraleState as S, INFANTRY, CAVALRY, ARTILLERY
from simulation.orders import Command, Order, OrderKind
from simulation.formations import Formation
from simulation import combat, morale, projectiles
from scenarios.standard_battle import create


def pair(distance=100):
    return Battle([Regiment(0,'blue',0,Vec(200,300)),Regiment(1,'red',1,Vec(200+distance,300),math.pi)],seed=17)


def snapshot(b):
    return (b.tick,b.result,b.metrics,[(u.id,u.pos,u.facing,u.strength,u.morale,u.cohesion,u.state,u.order) for u in b.units],list(b.events),b.projectiles)


def test_determinism_with_commands():
    a,b=create(37),create(37)
    for tick in range(800):
        if tick in (5,100):
            for sim in (a,b): sim.issue(Command(0,Order(OrderKind.MOVE,Vec(350,150)),Formation.COLUMN))
        a.step(); b.step()
    assert snapshot(a)==snapshot(b)


def test_seed_changes_volley():
    a,b=pair(),pair()
    b.rng.seed(3)
    combat.fire(a,a.units[0],a.units[1]); combat.fire(b,b.units[0],b.units[1])
    assert a.units[1].strength!=b.units[1].strength


def test_arc_range_and_los():
    b=pair()
    a,t=b.units
    assert combat.can_fire(b,a,t)
    t.pos=Vec(400,300)
    assert not combat.can_fire(b,a,t)
    t.pos=Vec(100,300)
    assert not combat.can_fire(b,a,t)
    t.pos=Vec(300,300)
    blocker=Regiment(2,'screen',0,Vec(250,300))
    b.units.append(blocker)
    assert not combat.can_fire(b,a,t)


def test_line_outfires_column():
    losses=[]
    for formation in (Formation.LINE,Formation.COLUMN):
        b=pair(); a,t=b.units; a.formation=formation
        for _ in range(20):
            a.reload_left=0
            combat.fire(b,a,t)
        losses.append(t.stats.strength-t.strength)
    assert losses[0]>losses[1]*1.5


def test_finite_formation_change():
    b=pair(500)
    b.issue(Command(0,formation=Formation.COLUMN)); b.step()
    assert b.units[0].formation==Formation.LINE
    for _ in range(72): b.step()
    assert b.units[0].formation==Formation.COLUMN
    assert b.units[0].transition_left==0


def test_hysteresis_and_rout_shock_once():
    b=pair(500)
    a=b.units[0]
    friend=Regiment(2,'friend',0,Vec(240,300),morale=80)
    b.units.append(friend)
    a.morale=55; morale.update(b); assert a.state==S.SHAKEN
    a.morale=61; morale.update(b); assert a.state==S.SHAKEN
    a.morale=68; morale.update(b); assert a.state==S.STEADY
    a.morale=20; morale.update(b)
    assert a.state==S.ROUTING
    assert friend.morale<80
    shocks=b.metrics['cascade_shocks']
    morale.update(b)
    assert b.metrics['cascade_shocks']==shocks==1


def test_rally_away_from_threat():
    b=pair(500); a=b.units[0]; a.state=S.ROUTING; a.morale=10
    for _ in range(650): morale.update(b)
    assert a.state in (S.SHAKEN,S.STEADY)
    assert b.metrics['rallies']==1


def test_projectile_ballistics_swept_collision_and_friendly_fire():
    b=Battle([Regiment(0,'gun',0,Vec(100,300),stats=ARTILLERY),
              Regiment(1,'friend',0,Vec(180,300)),Regiment(2,'enemy',1,Vec(220,300))])
    p=projectiles.Projectile(Vec(150,300),Vec(1000,0),1,0,0)
    b.projectiles=[p]
    projectiles.update(b)
    assert p.height==pytest.approx(1-.5*9.81*.1**2)
    assert b.units[1].strength<240 and b.units[2].strength<240
    assert b.metrics['friendly_fire']==1
    old=b.units[2].strength
    # IDs prevent a ball damaging the same footprint a second time.
    p.pos=Vec(210,300); p.velocity=Vec(20,0)
    projectiles.update(b)
    assert b.units[2].strength==old
    for _ in range(200): projectiles.update(b)
    assert not b.projectiles


def test_charge_prepared_front_vs_rear(charging):
    loss=[]
    for facing in (math.pi,0):
        horse=Regiment(0,'horse',0,Vec(200,300),stats=CAVALRY,speed=7)
        foot=Regiment(1,'foot',1,Vec(215,300),facing)
        b=Battle([horse,foot],seed=5)
        charging(horse)
        combat.melee(b,horse,foot)
        loss.append(240-foot.strength)
        assert any(e.kind=='charge' for e in b.events)
    assert loss[1]>loss[0]


def test_victory_by_effective_strength():
    b=pair(); b.units[1].state=S.ROUTING
    b.units[1].morale=0
    for _ in range(130): b.step()
    assert b.result=='army_0'
    assert b.units[1].strength>0


def test_damage_clamped():
    b=pair(); t=b.units[1]
    combat.damage(b,t,10000,'test',shock=10000)
    assert t.strength==0 and t.morale==0 and t.cohesion==0


def test_headless_battle_completion_and_invariants():
    b=create(1)
    # Congestion changes battle pacing; this checks completion, not the old balance window.
    for _ in range(12000):
        b.step()
        if b.result: break
    assert b.result is not None
    assert 0 < b.time <= 1200  # completion invariant, independent of artillery balance
    for u in b.units:
        assert 0<=u.strength<=u.stats.strength
        assert 0<=u.morale<=100 and 0<=u.cohesion<=100 and 0<=u.fatigue<=100
        assert all(-1e-6<=p.x<=1000.000001 and -1e-6<=p.y<=600.000001 for p in u.footprint)
    assert b.metrics['routs']>0
