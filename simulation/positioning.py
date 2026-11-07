"""Bounded settling of stationary overlaps, without replacing tactical orders."""
import math
from dataclasses import replace
from types import SimpleNamespace
from .geometry import Vec, direction, separation, segment_rect, corners
from .orders import OrderKind as O
from .regiment import UnitType
from .spatial import SpatialIndex


def reset(unit):
    unit.settling_goal=None; unit.settling_facing=None; unit.position_preference=None; unit.position_key=None
    unit.stationary_overlap=0.; unit.settling_retry_at=0.


def pursuit_lanes(battle,units,intents):
    groups={}
    for u in units:
        if u.pursuit_id is not None and intents[u.id] is not None:
            groups.setdefault(u.pursuit_id,[]).append(u)
    for target_id,followers in groups.items():
        target=battle.unit(target_id)
        if target is None or len(followers)<2: continue
        side=direction(target.facing+math.pi/2)
        limit=min(24.,target.width*.3)
        for i,u in enumerate(followers):
            offset=max(-limit,min(limit,(i-(len(followers)-1)/2)*battle.rules.pursuit_lane_spacing))
            distance=(u.pos-target.pos).length()
            offset*=max(0.,min(1.,(distance-25)/80))
            point=target.pos+side*offset
            radius=math.hypot(u.width,u.depth)/2+1
            intents[u.id]=Vec(max(radius,min(battle.rules.width-radius,point.x)),max(radius,min(battle.rules.height-radius,point.y)))


def priority(u):
    return (4 if u.player_order and u.order.kind==O.HOLD else 3 if u.order.kind in (O.HOLD,O.RESERVE) else 2 if u.combat_state=='firing' else 1,
            u.rest_time,-u.id)


def eligible(u,intent):
    if not u.effective or u.transition_left or u.combat_state=='melee': return False
    if u.order.kind not in (O.HOLD,O.RESERVE,O.DEFEND,O.MOVE,O.ADVANCE): return False
    if u.order.kind==O.ADVANCE: return intent is None
    return intent is None or (intent-u.pos).length()<12 or u.settling_goal is not None


def alternative(battle,u,units,index):
    """At most 24 endpoint/straight-route candidates; all terrain stays passable."""
    rules=battle.rules; facing=u.order.facing if u.order.facing is not None else u.facing
    radius=math.hypot(u.width,u.depth)/2+1
    candidates=[]
    for distance in (max(u.depth+rules.settling_gap,18.),u.width+rules.settling_gap,rules.settling_radius):
        if distance>rules.settling_radius: continue
        for angle in (0,math.pi,math.pi/2,-math.pi/2,math.pi/4,-math.pi/4,3*math.pi/4,-3*math.pi/4):
            point=u.pos+direction(facing+angle)*distance
            preference=u.position_preference or u.pos
            if (point-preference).length()>rules.settling_radius: continue
            if not(radius<=point.x<=rules.width-radius and radius<=point.y<=rules.height-radius): continue
            width,depth=u.width+2*rules.settling_gap,u.depth+2*rules.settling_gap
            clearance=SimpleNamespace(pos=point,facing=facing,width=width,depth=depth,footprint=corners(point,facing,width,depth))
            nearby=index.segment(point,point,padding=radius+2*rules.settling_gap)
            if any(other.id!=u.id and separation(clearance,other) is not None for other in nearby): continue
            if any(other.id!=u.id and other.settling_goal is not None and separation(clearance,replace(other,pos=other.settling_goal,
                   facing=other.settling_facing if other.settling_facing is not None else other.facing)) is not None for other in units): continue
            if any(other.army!=u.army and segment_rect(u.pos,point,other,radius) is not None for other in index.segment(u.pos,point,padding=radius)): continue
            difficulty=battle.terrain.forest_density(point.x,point.y)*2+battle.terrain.slope(point.x,point.y)*4 if not battle.terrain.empty else 0.
            candidates.append(((point-preference).length()+difficulty, len(candidates), point))
    return min(candidates,key=lambda item:item[:2])[2] if candidates else None


def settle(battle,units,intents,overlaps):
    dt=battle.rules.dt; allowed={}
    for u in units:
        u.rest_time=u.rest_time+dt if u.speed<.1 else 0.
        key=(u.order.kind,u.order.destination if u.order.kind in (O.MOVE,O.DEFEND) else None,u.order.facing)
        if u.position_key!=key:
            reset(u); u.position_key=key
        allowed[u.id]=eligible(u,intents[u.id])
        if not allowed[u.id]:
            u.settling_goal=None; u.settling_facing=None; u.stationary_overlap=0.
    losers=set(); blocked=set()
    for a,b,fa,fb in overlaps:
        if min(fa,fb)<battle.rules.settling_overlap or not allowed[a.id] or not allowed[b.id]: continue
        blocked.update((a.id,b.id))
        losers.add(b.id if priority(a)>=priority(b) else a.id)
    for u in units:
        u.stationary_overlap=u.stationary_overlap+dt if u.id in blocked else 0.
    planning=[]
    for u in units:
        if not allowed[u.id]: continue
        if u.settling_goal is not None:
            if battle.time-u.settling_started>battle.rules.settling_timeout and (u.pos-u.settling_goal).length()>1:
                u.settling_goal=None;u.settling_facing=None;u.settling_retry_at=battle.time+battle.rules.settling_retry
            else:
                intents[u.id]=u.settling_goal
                continue
        if u.id not in losers or u.stationary_overlap<battle.rules.settling_delay or battle.time<u.settling_retry_at: continue
        planning.append(u)
    if not planning: return
    index=SpatialIndex(units)
    for u in sorted(planning,key=priority,reverse=True):
        u.position_preference=u.order.destination if u.order.kind in (O.MOVE,O.DEFEND) else u.pos
        point=alternative(battle,u,units,index)
        u.settling_retry_at=battle.time+battle.rules.settling_retry
        if point is not None:
            u.settling_goal=point;u.settling_facing=u.order.facing if u.order.facing is not None else u.facing
            u.settling_started=battle.time;intents[u.id]=point
            battle.log('position',f'{u.name}: occupied frontage; settling nearby',u.id)
