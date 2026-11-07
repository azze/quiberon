"""Threat-directed flight, crew-scaled gun salvos and vulnerable gun crews."""
import math
from dataclasses import replace
import pytest
from simulation import ai,combat,projectiles,morale
from simulation.battle import Battle
from simulation.config import Rules
from simulation.geometry import Vec,contains
from simulation.orders import Order,OrderKind as O
from simulation.regiment import Regiment,MoraleState as S
from simulation.formations import Formation as F
from simulation.terrain import TerrainMap,Forest
from analysis.performance import fingerprint
from analysis.battle_report import battle_report


def fleeing(pos=Vec(500,300),army=0):
    return Regiment(0,'fleeing',army,pos,state=S.ROUTING,morale=10,order=Order(O.ATTACK,target_id=1))


@pytest.mark.parametrize('danger,expected',[(Vec(420,300),Vec(1,0)),(Vec(580,300),Vec(-1,0)),
                                            (Vec(500,220),Vec(0,1)),(Vec(500,380),Vec(0,-1))])
def test_routing_steers_away_from_danger_even_when_home_is_unsafe(danger,expected):
    u=fleeing();enemy=Regiment(1,'danger',1,danger)
    b=Battle([u,enemy],generate_commanders=False)
    destination=ai.destination(b,u)
    assert (destination-u.pos).normalized().dot(expected)>.95
    assert u.target_id is None and u.order.kind==O.ATTACK # flight overrides, not rewrites, orders


def test_fleeing_keeps_escaping_after_threat_leaves_sensing_radius():
    u=fleeing();enemy=Regiment(1,'danger',1,Vec(420,300))
    b=Battle([u,enemy],generate_commanders=False)
    ai.destination(b,u);enemy.pos=Vec(100,300);b.tick=11
    assert ai.destination(b,u).x>u.pos.x # don't turn home into danger again
    u.state=S.RALLYING;assert ai.destination(b,u) is None and u.rout_heading is None


def test_enclosed_route_chooses_gap_between_enemies_instead_of_walking_home_through_them():
    u=fleeing();enemies=[Regiment(i+1,'enemy',1,pos) for i,pos in enumerate((Vec(450,300),Vec(580,300)))]
    b=Battle([u,*enemies],generate_commanders=False)
    goal=ai.destination(b,u)
    assert abs((goal-u.pos).normalized().y)>.5
    assert not any(contains(goal,e.pos,e.facing,e.width,e.depth) for e in enemies)


def test_hidden_distant_and_routing_enemies_do_not_divert_flight():
    u=fleeing();enemy=Regiment(1,'hidden',1,Vec(400,300))
    forest=TerrainMap(forests=(Forest(450,300,80,100,1),))
    b=Battle([u,enemy],terrain=forest,generate_commanders=False)
    assert not b.perceives(u,enemy)
    assert ai.destination(b,u).x<u.pos.x
    b.terrain=TerrainMap();enemy.state=S.ROUTING;u.rout_heading=None
    assert ai.destination(b,u).x<u.pos.x


def test_route_plans_are_cached_without_consuming_rng(monkeypatch):
    u=fleeing();enemy=Regiment(1,'danger',1,Vec(400,300))
    b=Battle([u,enemy],generate_commanders=False);before=b.rng.getstate()
    calls=[];old=b.perceives
    def count(*args):calls.append(1);return old(*args)
    monkeypatch.setattr(b,'perceives',count)
    for tick in range(10):b.tick=tick;ai.destination(b,u)
    assert len(calls)==1 and b.rng.getstate()==before
    b.tick=10;ai.destination(b,u);assert len(calls)==2


@pytest.mark.parametrize('pos,danger',[(Vec(992,300),Vec(900,300)),(Vec(8,300),Vec(100,300)),
                                     (Vec(500,33),Vec(500,110)),(Vec(500,567),Vec(500,490))])
def test_routed_units_can_escape_any_edge_without_stalling(pos,danger):
    u=fleeing(pos);enemy=Regiment(1,'danger',1,danger)
    b=Battle([u,enemy],generate_commanders=False)
    assert ai.destination(b,u) is None
    assert u.withdrawn and not u.active and any(e.kind=='withdraw' for e in b.events)


def test_flight_really_increases_distance_and_can_rally_when_safe():
    u=fleeing();enemy=Regiment(1,'danger',1,Vec(420,300),reload_left=9999)
    b=Battle([u,enemy,Regiment(2,'blue reserve',0,Vec(100,100)),Regiment(3,'red reserve',1,Vec(900,100))],sandbox=True,generate_commanders=False)
    start=(u.pos-enemy.pos).length()
    for _ in range(100):b.step()
    assert (u.pos-enemy.pos).length()>start+15
    enemy.withdrawn=True;b.sandbox=False
    for _ in range(600):b.step()
    assert u.state in (S.SHAKEN,S.STEADY) and b.metrics['rallies']==1


def test_rout_abandons_unfinished_formation_drill_and_new_route_replans():
    u=Regiment(0,'changing',0,Vec(500,300),morale=5,transition_left=6,next_formation=F.COLUMN)
    enemy=Regiment(1,'danger',1,Vec(420,300))
    b=Battle([u,enemy],generate_commanders=False)
    morale.update(b)
    assert u.state==S.ROUTING and u.transition_left==0 and u.next_formation is None
    assert ai.destination(b,u).x>500


def battery(key='artillery',strength=None,rules=None):
    gun=Regiment(0,'battery',0,Vec(250,300),archetype_id=key,strength=strength)
    target=Regiment(1,'enemy',1,Vec(450,300),math.pi,reload_left=9999)
    return Battle([gun,target],seed=17,rules=rules,generate_commanders=False),gun,target


@pytest.mark.parametrize('key,capacity', [('artillery',6),('french_horse_artillery',4)])
@pytest.mark.parametrize('fraction',[1.,.75,.5,.25,0.])
def test_salvo_size_scales_with_crew_strength_and_shares_one_reload(key,capacity,fraction):
    b,u,target=battery(key);u.strength=int(u.stats.strength*fraction)
    expected=math.ceil(capacity*u.strength/u.stats.strength)
    assert u.available_guns==expected
    combat.fire(b,u,target)
    assert len(b.projectiles)==expected and u.analysis['artillery_shots']==expected
    assert u.analysis['volleys']==int(expected>0)
    if expected:
        assert len({p.pos for p in b.projectiles})==expected
        assert all(p.owner_id==u.id and p.energy==u.archetype.projectile_power for p in b.projectiles)
        assert u.reload_left==u.stats.reload
        combat.fire(b,u,target);assert len(b.projectiles)==expected
        assert battle_report(b)['regiments'][0]['guns']==expected


def test_further_casualties_reduce_next_salvo_and_count_is_bounded():
    b,u,target=battery();combat.fire(b,u,target)
    assert len(b.projectiles)==6
    u.strength=24;u.reload_left=0;combat.fire(b,u,target)
    assert len(b.projectiles)==9 and u.analysis['artillery_shots']==9
    u.strength=1;assert u.available_guns==1
    u.strength=1000;assert u.available_guns==6
    u.withdrawn=True;assert u.available_guns==0


def test_more_scatter_is_actual_independent_seeded_aim_error():
    def aims(scatter):
        b,u,target=battery(rules=replace(Rules(),artillery_scatter=scatter))
        for _ in range(30):u.reload_left=0;combat.fire(b,u,target)
        return [p.velocity for p in b.projectiles]
    narrow=aims(18);wide=aims(45)
    assert wide==aims(45) and len(wide)==180
    assert len(set(wide))==180
    assert sum(v.y**2 for v in wide)>sum(v.y**2 for v in narrow)*3
    assert Rules().artillery_scatter==45


@pytest.mark.parametrize('state',[S.ROUTING,S.RALLYING])
def test_broken_batteries_do_not_fire_even_when_given_a_target(state):
    b,u,target=battery();u.state=state
    combat.fire(b,u,target)
    assert not b.projectiles and u.analysis['artillery_shots']==0


def test_artillery_crews_are_weaker_in_melee_without_changing_ranged_damage():
    def exchange(rules):
        b,u,target=battery(rules=rules)
        target.pos=Vec(270,300);hits=[];original=combat.damage
        # Capture the actual arguments rather than asserting a noisy battle winner.
        def record(battle,victim,losses,reason,attacker=None,shock=0):
            hits.append((attacker.id,losses,shock));original(battle,victim,losses,reason,attacker,shock)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(combat,'damage',record)
            combat.melee(b,u,target)
        return hits,u.strength
    old,remaining_old=exchange(replace(Rules(),artillery_melee_factor=.25,artillery_melee_vulnerability=1.))
    new,remaining_new=exchange(Rules())
    assert new[0][2]==pytest.approx(old[0][2]*.4)
    assert new[0][1]<=old[0][1] and remaining_new<remaining_old


def test_salvo_and_flight_replays_match_across_frame_groupings():
    def create():
        b,u,target=battery();b.units.extend([fleeing(Vec(600,450)),Regiment(3,'pursuer',1,Vec(550,450))])
        # Unique IDs matter for targeting and independent geometry.
        b.units[2].id=2
        return b
    a,b=create(),create()
    for _ in range(120):a.step()
    for _ in range(30):
        for _ in range(4):b.step()
    assert fingerprint(a)==fingerprint(b)


def test_wide_scatter_does_not_send_point_blank_shots_backwards():
    b,u,target=battery();target.pos=Vec(270,300)
    for _ in range(30):u.reload_left=0;combat.fire(b,u,target)
    assert all(p.velocity.dot((target.pos-p.pos).normalized())>0 for p in b.projectiles)


def test_balance_tool_distinguishes_escaping_from_destroying_a_fugitive(monkeypatch):
    from analysis import cavalry_balance
    from scenarios.cavalry_tests import create
    b=create('uhlans-routing',17);b.units[1].withdrawn=True
    monkeypatch.setattr(cavalry_balance,'create',lambda *args:b)
    result=cavalry_balance.run('uhlans-routing',17,duration=1)
    assert result['result']=='escaped' and result['infantry_lost']==0
