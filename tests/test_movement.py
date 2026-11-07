import math
import pytest
from simulation.geometry import Vec, contains, separation, angle_delta
from simulation.regiment import Regiment
from simulation.movement import move, separate
from viewer.camera import Camera

def test_move_arrives():
    u = Regiment(1, 'test', 0, Vec(100, 100))
    for _ in range(1000): move(u, Vec(200, 100), .1, 1000, 600)
    assert (u.pos - Vec(200, 100)).length() < 1

def test_turn_is_limited():
    u = Regiment(1, 'test', 0, Vec(100, 100))
    move(u, Vec(100, 200), .1, 1000, 600)
    assert 0 < u.facing <= u.stats.turn_rate * .1
    assert abs(angle_delta(math.pi - .1, -math.pi + .1) - .2) < 1e-8

def test_geometry_and_separation():
    a = Regiment(1, 'a', 0, Vec(100, 100), math.pi / 4)
    b = Regiment(2, 'b', 1, Vec(105, 100))
    assert contains(a.pos, a.pos, a.facing, a.width, a.depth)
    assert not contains(Vec(300, 300), a.pos, a.facing, a.width, a.depth)
    assert separation(a, b) is not None
    for _ in range(100): separate([a, b], 1000, 600)
    assert separation(a, b) is None

def test_camera_roundtrip_and_anchor():
    c = Camera()
    p = Vec(132, 478)
    assert c.screen_to_world(c.world_to_screen(p)) == p
    before = c.screen_to_world((77, 55))
    c.zoom_at((77, 55), 1.5)
    assert (before - c.screen_to_world((77, 55))).length() < 1e-8


def test_oncoming_friends_take_detours():
    from simulation.battle import Battle
    from simulation.orders import Order, OrderKind
    a=Regiment(0,'a',0,Vec(200,300),order=Order(OrderKind.MOVE,Vec(400,300)))
    b=Regiment(1,'b',0,Vec(400,300),math.pi,order=Order(OrderKind.MOVE,Vec(200,300)))
    sim=Battle([a,b],sandbox=True)
    for _ in range(2200): sim.step()
    assert (a.pos-Vec(400,300)).length()<2
    assert (b.pos-Vec(200,300)).length()<2
    assert separation(a,b) is None

# Soft-collision integration tests use real Battle ticks, including sandbox recovery.
from dataclasses import replace
from simulation.battle import Battle
from simulation.config import Rules
from simulation.formations import Formation, CongestionProfile
from simulation.geometry import intersection_area
from simulation.orders import Order, OrderKind
from simulation.movement import update_congestion
from simulation.regiment import CAVALRY, MoraleState


def mover(uid, start, goal, formation=Formation.LINE):
    return Regiment(uid, f'mover {uid}', 0, Vec(*start),
                    angle_delta(0, math.atan2(goal[1]-start[1], goal[0]-start[0])),
                    formation=formation, order=Order(OrderKind.MOVE, Vec(*goal)))


def trace(battle, ticks):
    rows = []
    for _ in range(ticks):
        battle.step()
        rows.append([(u.pos, u.speed, u.cohesion, u.congestion, u.congestion_speed, u.avoidance_goal) for u in battle.units])
    return rows


def test_cross_stationary_friend_speed_loss_recovery_and_arrival():
    moving = mover(0, (200,300), (450,300))
    stationary = Regiment(1, 'screen', 0, Vec(320,300))
    b = Battle([moving, stationary], sandbox=True, rules=Rules(avoidance_enabled=False))
    rows = trace(b, 1800)
    congested = [r[0] for r in rows if r[0][3] > .75]
    assert congested
    assert min(r[4] for r in congested) < .7
    assert min(r[1] for r in congested) < 1.6
    assert min(r[2] for r in congested) < 99
    assert min(r[1][2] for r in rows) < 100  # stationary screen is disrupted too
    assert (moving.pos - Vec(450,300)).length() < 1
    assert moving.congestion == 0 and moving.congestion_speed == 1
    assert rows[1200][0][1] > 1.9  # restored speed after crossing
    assert moving.cohesion > min(r[0][2] for r in rows)  # shared recovery
    assert stationary.pos == Vec(320,300)  # no collision shove


def test_opposing_friendly_movers_cross_with_penalties():
    a = mover(0, (200,300), (440,300))
    b = mover(1, (440,300), (200,300))
    battle = Battle([a,b], sandbox=True)
    rows = trace(battle, 1800)
    assert any(r[0][3] > .5 and r[1][3] > .5 for r in rows)
    assert all(r[0][5] is None and r[1][5] is None for r in rows)
    for unit, goal in [(a, Vec(440,300)), (b, Vec(200,300))]:
        assert (unit.pos-goal).length() < 1
    assert min(r[0][2] for r in rows) < 99


def test_crowd_penalties_bounded_and_no_endless_detour():
    moving = mover(0, (200,300), (620,300))
    screens = [Regiment(i+1,'screen',0,Vec(x,y)) for i,(x,y) in enumerate(
        [(x,y) for x in (350,380,410) for y in (235,300,365)])]
    battle = Battle([moving,*screens], sandbox=True)
    rows = trace(battle, 3500)
    assert max(r[0][3] for r in rows) > .9
    assert min(r[0][4] for r in rows) >= battle.rules.congestion_min_speed
    assert min(r[0][4] for r in rows) >= .55 - 1e-8  # line cap, regardless of crowd count
    assert (moving.pos-Vec(620,300)).length() < 1
    assert all(r[0][5] is None for r in rows)  # dense detours rejected
    assert 0 <= moving.cohesion <= 100
    # Direct progress through the crowd; no lateral steering oscillation.
    assert all(abs(r[0][0].y-300) < 1e-8 for r in rows)


def test_short_detour_is_preferred_and_distance_bounded():
    moving = mover(0, (200,300), (600,300))
    stationary = Regiment(1,'screen',0,Vec(360,300))
    battle = Battle([moving,stationary], sandbox=True)
    rows = trace(battle, 3000)
    assert any(r[0][5] is not None for r in rows)
    assert max(abs(r[0][0].y-300) for r in rows) > 50
    assert (moving.pos-Vec(600,300)).length() < 1
    positions = [Vec(200,300)] + [r[0][0] for r in rows]
    length = sum((b-a).length() for a,b in zip(positions,positions[1:]))
    assert length < 400 + battle.rules.avoidance_max_extra + 10
    assert max(r[0][3] for r in rows) < .05


def test_formation_congestion_profiles_are_configurable():
    outcomes = []
    for formation in (Formation.LINE, Formation.COLUMN):
        a = mover(0,(300,300),(600,300),formation)
        a.speed = 2
        b = Regiment(1,'screen',0,Vec(300,300),formation=formation)
        update_congestion([a,b],Rules(),1.)
        outcomes.append((a.congestion_speed,100-a.cohesion))
    assert outcomes[1][0] > outcomes[0][0]
    assert outcomes[1][1] < outcomes[0][1]
    a,b = mover(0,(300,300),(600,300)), Regiment(1,'screen',0,Vec(300,300))
    a.speed=2
    rules=Rules(congestion_profiles={f:CongestionProfile(0,0) for f in Formation})
    update_congestion([a,b],rules,1.)
    assert a.congestion_speed==1 and a.cohesion==100


def test_overlap_geometry_edges_rotation_and_containment():
    a=Regiment(0,'a',0,Vec(300,300))
    b=Regiment(1,'b',0,Vec(300,300))
    assert intersection_area(a,b)==pytest.approx(a.width*a.depth)
    b.pos=Vec(312,300)  # touching front edge
    assert intersection_area(a,b)==pytest.approx(0)
    b.pos=Vec(306,300)
    assert intersection_area(a,b)==pytest.approx(a.width*a.depth/2)
    b.pos=a.pos; b.facing=math.pi/2
    assert intersection_area(a,b)==pytest.approx(12*12)
    assert intersection_area(a,b)==pytest.approx(intersection_area(b,a))
    b.pos=Vec(500,500)
    assert intersection_area(a,b)==0


def test_overlap_penalties_depend_on_time_direction_and_moving_state():
    def loss(direction, stationary=False, steps=1):
        a,b=Regiment(0,'a',0,Vec(300,300)),Regiment(1,'b',0,Vec(300,300),direction)
        a.speed=2
        b.speed=0 if stationary else 2
        for _ in range(steps): update_congestion([a,b],Rules(),1/steps)
        return 100-a.cohesion, 100-b.cohesion
    assert loss(0)[0] < loss(math.pi)[0]
    assert loss(0,True)[1] < loss(0,True)[0]
    assert loss(0,steps=10)==pytest.approx(loss(0))


def test_detour_timeout_falls_back_without_replanning():
    a=mover(0,(200,300),(600,300))
    b=Regiment(1,'screen',0,Vec(360,300))
    battle=Battle([a,b],sandbox=True,rules=Rules(avoidance_max_seconds=.1))
    battle.step()
    assert a.avoidance_goal is not None
    rows=trace(battle,2700)
    assert all(r[0][5] is None for r in rows)
    assert (a.pos-Vec(600,300)).length()<1


def test_enemy_contact_remains_solid_and_melee_fires():
    a=Regiment(0,'horse',0,Vec(200,300),stats=CAVALRY,
               order=Order(OrderKind.ATTACK,target_id=1))
    b=Regiment(1,'enemy',1,Vec(350,300),math.pi,stats=CAVALRY)
    battle=Battle([a,b],seed=5)
    engaged=False
    for _ in range(380):
        battle.step()
        if a.active and b.active:
            assert a.pos.x < b.pos.x
            assert a.congestion==b.congestion==0
        engaged |= bool(battle.melee_next)
    assert engaged
    assert a.strength<CAVALRY.strength or b.strength<CAVALRY.strength


def test_congestion_replay_independent_of_render_calls():
    from scenarios.movement_test import create
    a,b=create(19),create(19)
    # Different groupings stand in for different rendering frame schedules.
    for _ in range(1200): a.step()
    for _ in range(300):
        for _ in range(4): b.step()
    assert a.units==b.units
    assert a.metrics==b.metrics and a.rng.getstate()==b.rng.getstate()


@pytest.mark.parametrize('state,kind',[(MoraleState.ROUTING,OrderKind.HOLD),
                                      (MoraleState.STEADY,OrderKind.WITHDRAW)])
def test_retreat_can_cross_friendly_screen(state,kind):
    a=Regiment(0,'retreat',0,Vec(400,300),math.pi,state=state,order=Order(kind))
    b=Regiment(1,'screen',0,Vec(280,300))
    battle=Battle([a,b],sandbox=True)
    rows=trace(battle,2300)
    assert a.pos.x<100
    assert any(r[0][3]>.5 for r in rows)


def test_stationary_overlap_does_not_trap_a_rally():
    from simulation import morale
    a=Regiment(0,'rally',0,Vec(300,300),state=MoraleState.RALLYING,
               cohesion=20,morale=28)
    b=Regiment(1,'stationary friend',0,Vec(300,300))
    battle=Battle([a,b])
    update_congestion(battle.units,battle.rules,.1)
    assert a.congestion==1 and a.congestion_loss==0
    for _ in range(400): morale.update(battle)
    assert a.cohesion>45
    assert a.state in (MoraleState.SHAKEN,MoraleState.STEADY)


def test_column_crossing_has_less_total_disruption_than_line():
    costs=[]
    for formation in (Formation.LINE,Formation.COLUMN):
        a=mover(0,(200,300),(450,300),formation)
        b=Regiment(1,'same stationary screen',0,Vec(320,300))
        battle=Battle([a,b],sandbox=True,rules=Rules(avoidance_enabled=False))
        total=0.
        for _ in range(1800):
            battle.step()
            total+=a.congestion_loss*battle.rules.dt
        assert (a.pos-Vec(450,300)).length()<1
        costs.append(total)
    assert costs[0]>costs[1]*1.5


def test_many_simultaneous_overlaps_do_not_stack_penalties():
    def penalties(count):
        a=mover(0,(300,300),(600,300)); a.speed=2
        friends=[Regiment(i+1,'screen',0,a.pos) for i in range(count)]
        update_congestion([a,*friends],Rules(),.1)
        return a.congestion_speed,a.congestion_loss,a.cohesion
    assert penalties(1)==penalties(6)


def test_interactive_demo_orders_all_complete_headlessly():
    from scenarios.movement_test import create
    battle=create()
    movers=[u for u in battle.units if u.order.destination is not None]
    assert len(movers)==8
    for _ in range(4000): battle.step()
    for unit in movers:
        assert (unit.pos-(unit.settling_goal or unit.order.destination)).length()<1
        if unit.settling_goal: assert (unit.settling_goal-unit.order.destination).length()<120
        assert all(-1e-6<=p.x<=1000.000001 and -1e-6<=p.y<=600.000001 for p in unit.footprint)
