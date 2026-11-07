import math
from .geometry import Vec, angle_to, angle_delta, direction, separation, intersection_area, segment_rect
from .formations import PROFILES
from .orders import OrderKind
from .regiment import MoraleState, Regiment
from .config import Rules
from .terrain import TerrainRules
from .archetypes import manoeuvre_factor
from .spatial import candidate_pairs
from . import commanders

def clamp_to_field(unit, width, height):
    pts = unit.footprint
    dx = max(0, -min(p.x for p in pts)) - max(0, max(p.x for p in pts) - width)
    dy = max(0, -min(p.y for p in pts)) - max(0, max(p.y for p in pts) - height)
    unit.pos = unit.pos + Vec(dx, dy)

def turn_to(unit, facing, dt, multiplier=1.):
    delta = angle_delta(unit.facing, facing)
    limit = unit.stats.turn_rate * PROFILES[unit.formation][3] * dt * multiplier
    turn = max(-limit, min(limit, delta))
    unit.facing += turn
    unit.cohesion = max(0., unit.cohesion - abs(turn) * .6 * manoeuvre_factor(unit))


def move(unit, destination, dt, width, height, terrain=None, terrain_rules=TerrainRules(), arrival_facing=None,
         *, speed_cap=None, acceleration=None, turn_multiplier=1., follow_speed=None):
    previous_speed=unit.speed
    unit.speed = 0.
    unit.velocity = Vec(0,0)
    unit.terrain_loss = 0.
    unit.terrain_speed = 1.
    if terrain is not None and not terrain.empty:
        effect=terrain.movement_effect(unit,Vec(0,0),terrain_rules)
        unit.forest_cover,unit.ground_slope=effect.forest,effect.slope
        unit.terrain_speed=effect.speed
    if unit.transition_left > 0:
        unit.transition_left = max(0., unit.transition_left - dt)
        if unit.transition_left == 0:
            unit.formation = unit.next_formation
            unit.next_formation = None
        return
    if unit.stats.kind.value=='artillery':
        travelling=destination is not None and (destination-unit.pos).length()>=1
        if travelling:
            if not unit.limbered:
                unit.limbered=True
                unit.limber_left=unit.archetype.limber_seconds*commanders.redeploy_factor(unit)
            unit.setup_left=unit.archetype.setup_seconds*commanders.redeploy_factor(unit)
            unit.limber_left=max(0.,unit.limber_left-dt)
            if unit.limber_left>0: return
        else:
            unit.limber_left=0.
            unit.setup_left=max(0.,unit.setup_left-dt)
            if unit.setup_left==0: unit.limbered=False
    if destination is None: return
    offset = destination - unit.pos
    if offset.length() < 1:
        if arrival_facing is not None:
            turn_to(unit, arrival_facing, dt)
            clamp_to_field(unit, width, height)
        return
    delta = angle_delta(unit.facing, angle_to(unit.pos, destination))
    profile = PROFILES[unit.formation]
    turn_to(unit, angle_to(unit.pos, destination), dt, turn_multiplier)
    penalty = .65 if unit.state in (MoraleState.SHAKEN, MoraleState.WAVERING) else 1.
    maximum=unit.stats.speed*profile[2] if speed_cap is None else speed_cap
    unit.speed = maximum * max(0., math.cos(delta)) * penalty * (1 - unit.fatigue * .003) * unit.congestion_speed
    unit.speed*=commanders.advance_factor(unit)
    # Slow tight approaches enough for finite turn rates to converge, not orbit.
    unit.speed *= min(1.,offset.length()*unit.stats.turn_rate*profile[3]/max(.1,unit.stats.speed*profile[2]))
    if terrain is not None and not terrain.empty:
        effect=terrain.movement_effect(unit,direction(unit.facing),terrain_rules)
        unit.terrain_speed=effect.speed
        unit.speed*=effect.speed
    if acceleration is not None: unit.speed=min(unit.speed,previous_speed+acceleration*dt)
    if follow_speed is not None: unit.speed=min(unit.speed,follow_speed)
    before=unit.pos
    unit.pos += direction(unit.facing) * min(offset.length(), unit.speed * dt)
    unit.fatigue = min(100., unit.fatigue + dt * .025)
    clamp_to_field(unit, width, height)
    unit.velocity=(unit.pos-before)*(1/dt)
    if terrain is not None and not terrain.empty:
        unit.terrain_loss=effect.loss_per_metre*(unit.pos-before).length()/dt
        unit.cohesion=max(0.,unit.cohesion-unit.terrain_loss*dt)

def separate(units, width, height):
    # Bounded corrections prevent teleporting; sorted iteration makes ties reproducible.
    for _ in range(3):
        for i, a in enumerate(units):
            for b in units[i + 1:]:
                if a.army == b.army: continue
                correction = separation(a, b)
                if correction is None: continue
                correction = correction.normalized() * min(correction.length() / 2 + .01, .6)
                a.pos += correction
                b.pos -= correction
        for u in units: clamp_to_field(u, width, height)


def update_congestion(units: list[Regiment], rules: Rules, dt: float = 0.) -> list[tuple[Regiment, Regiment, float, float]]:
    """Worst per-pair overlap fraction, never an additive pile-up penalty.

    Sample before movement for speed, after movement for time-based cohesion loss.
    A stationary unit is disrupted only when another unit is actually moving.
    """
    severity = {u.id: 0. for u in units}
    disruption = {u.id: 0. for u in units}
    impedance = {u.id: 0. for u in units}
    overlaps=[]
    for a, b in candidate_pairs(units):
        if a.army != b.army: continue
        # Cheap circle rejection before exact OBB clipping.
        radii = math.hypot(a.width, a.depth) / 2 + math.hypot(b.width, b.depth) / 2
        if (a.pos - b.pos).length() >= radii: continue
        area = intersection_area(a, b)
        if area <= 1e-8: continue
        va=a.velocity if a.velocity is not None else direction(a.facing)*a.speed
        vb=b.velocity if b.velocity is not None else direction(b.facing)*b.speed
        sa,sb=va.length(),vb.length()
        moving_a, moving_b = sa>.1,sb>.1
        alignment = 1.
        if moving_a and moving_b:
            cosine=max(-1.,min(1.,va.dot(vb)/(sa*sb)))
            same=(1+cosine)/2
            low=rules.congestion_same_direction
            if a.stats.kind.value==b.stats.kind.value=='cavalry':
                low=rules.congestion_cavalry_same_direction
                if a.pursuit_id is not None and a.pursuit_id==b.pursuit_id and cosine>.8: low=rules.congestion_shared_pursuit
            alignment=max(0.,min(1.,1-same*(1-low)+rules.congestion_overtaking*same*abs(sa-sb)/max(sa,sb)))
        overlaps.append((a,b,min(1.,area/(a.width*a.depth)),min(1.,area/(b.width*b.depth))))
        for u, moving in ((a, moving_a), (b, moving_b)):
            fraction = min(1., area / (u.width * u.depth))
            severity[u.id] = max(severity[u.id], fraction)
            impedance[u.id]=max(impedance[u.id],fraction*alignment)
            loss = fraction * alignment * (1. if moving else rules.congestion_stationary_loss)
            if not moving_a and not moving_b: loss = 0.
            disruption[u.id] = max(disruption[u.id], loss)
    for u in units:
        u.congestion = severity[u.id]
        profile = rules.congestion_profiles[u.formation]
        u.congestion_speed = max(rules.congestion_min_speed, 1 - profile.speed_reduction * impedance[u.id])
        u.congestion_loss = profile.cohesion_loss * disruption[u.id] * manoeuvre_factor(u)*commanders.pursuit_cohesion_factor(u)
        u.cohesion = max(0., u.cohesion - u.congestion_loss * dt)
    return overlaps


def reset_avoidance(unit: Regiment) -> None:
    unit.terrain_waypoint=None
    unit.terrain_destination=None
    unit.terrain_route_used=False
    unit.avoidance_goal = None
    unit.avoidance_destination = None
    unit.avoidance_left = 0.
    unit.avoidance_used = False


def avoid_friends(unit: Regiment, destination: Vec | None, units: list[Regiment],
                  rules: Rules | None = None,
                  intents: dict[int, Vec | None] | None = None) -> Vec | None:
    """One short detour per destination; moving allies are crossed instead.

    Conservative swept-circle clearance accounts for the entire formation during
    turns. Both legs must be clear of all other units and field boundaries. A
    timeout or any actual congestion cancels the detour permanently for this
    destination, so soft passage always remains the fallback.
    """
    rules = rules or Rules()
    if (destination is None or not rules.avoidance_enabled or
            unit.state in (MoraleState.ROUTING, MoraleState.RALLYING) or
            unit.order.kind not in (OrderKind.MOVE, OrderKind.ADVANCE, OrderKind.DEFEND)):
        unit.avoidance_goal = None
        return destination
    if unit.avoidance_destination is None or (destination - unit.avoidance_destination).length() > 20:
        reset_avoidance(unit)
        unit.avoidance_destination = destination
    if unit.avoidance_goal is not None:
        unit.avoidance_left -= rules.dt
        if (unit.avoidance_left > 0 and unit.congestion < .01 and
                (unit.avoidance_goal - unit.pos).length() > 4):
            return unit.avoidance_goal
        unit.avoidance_goal = None
    if unit.avoidance_used: return destination
    delta = destination - unit.pos
    if delta.length() < 1: return destination
    # A single evaluation budget also prevents repeated failed attempts in crowds.
    radius = math.hypot(unit.width, unit.depth) / 2
    forward = delta.normalized()
    side = Vec(-forward.y, forward.x)
    ahead = unit.pos + forward * min(rules.avoidance_lookahead, delta.length())
    obstacles = []
    for other in units:
        if other.id == unit.id or other.army != unit.army: continue
        t = segment_rect(unit.pos, ahead, other, radius)
        if t is not None:
            obstacles.append((t, other.id, other))
    if not obstacles: return destination
    unit.avoidance_used = True
    if unit.congestion > .01: return destination
    _, _, obstacle = min(obstacles, key=lambda item: (item[0], item[1]))
    moving = (intents is not None and intents.get(obstacle.id) is not None and
              (intents[obstacle.id] - obstacle.pos).length() > 1)
    if moving or obstacle.speed > .1: return destination
    relative = [p - unit.pos for p in obstacle.footprint]
    along = sum(p.dot(forward) for p in relative) / 4
    if along <= 0: return destination
    candidates = []
    for sign in (1, -1):
        edge = max(sign * p.dot(side) for p in relative)
        offset = sign * (max(0., edge) + radius + rules.avoidance_margin) * 1.5
        goal = unit.pos + forward * along + side * offset
        length = (goal - unit.pos).length() + (destination - goal).length()
        if length > delta.length() + rules.avoidance_max_extra or length > delta.length() * rules.avoidance_max_ratio: continue
        # A circle bounds the turning footprint; a rectangle's centre may legally
        # approach closer to an edge when travelling straight through congestion.
        if not all(radius <= point.x <= rules.width - radius and
                   radius <= point.y <= rules.height - radius
                   for point in (unit.pos, goal, destination)): continue
        if any(other.id != unit.id and
               (segment_rect(unit.pos, goal, other, radius) is not None or
                segment_rect(goal, destination, other, radius) is not None)
               for other in units): continue
        candidates.append((length, 0 if sign == 1 else 1, goal))
    if candidates:
        unit.avoidance_goal = min(candidates, key=lambda item: (item[0], item[1]))[2]
        unit.avoidance_left = rules.avoidance_max_seconds
        return unit.avoidance_goal
    return destination


def terrain_steer(battle,unit,destination):
    """One bounded local detour for cavalry/guns; passable direct fallback."""
    terrain=battle.terrain
    if terrain.empty or destination is None or unit.avoidance_goal is not None or unit.cavalry_state.value=='charging' or unit.state in (MoraleState.ROUTING,MoraleState.RALLYING) or unit.order.kind==OrderKind.WITHDRAW:
        unit.terrain_waypoint=None
        return destination
    profile=getattr(battle.rules.terrain,unit.stats.kind.value)
    if profile.route_aversion==0: return destination
    if unit.terrain_destination is None or (destination-unit.terrain_destination).length()>30:
        unit.terrain_destination=destination; unit.terrain_route_used=False; unit.terrain_waypoint=None
    if unit.terrain_waypoint is not None:
        unit.terrain_route_left-=battle.rules.dt
        if unit.terrain_route_left>0 and (unit.terrain_waypoint-unit.pos).length()>5:
            return unit.terrain_waypoint
        unit.terrain_waypoint=None
    if unit.terrain_route_used: return destination
    distance=(destination-unit.pos).length()
    if distance<80: return destination
    unit.terrain_route_used=True
    def cost(a,b):
        delta=b-a; length=delta.length(); samples=min(20,max(3,math.ceil(length/25)))
        difficulty=0.
        for i in range(samples):
            p=a+delta*((i+.5)/samples)
            difficulty+=terrain.forest_density(p.x,p.y)*2+terrain.slope(p.x,p.y)*5
        return length*(1+profile.route_aversion*difficulty/samples)
    direct=cost(unit.pos,destination)
    forward=(destination-unit.pos).normalized(); side=Vec(-forward.y,forward.x)
    choices=[]; radius=math.hypot(unit.width,unit.depth)/2
    for sign in (1,-1):
        point=unit.pos+forward*min(100,distance/2)+side*(sign*min(130,distance*.35))
        length=(point-unit.pos).length()+(destination-point).length()
        if length>distance*1.4 or length>distance+100: continue
        if not (radius<=point.x<=battle.rules.width-radius and radius<=point.y<=battle.rules.height-radius): continue
        if any(other.active and other.army!=unit.army and (segment_rect(unit.pos,point,other,radius) is not None or segment_rect(point,destination,other,radius) is not None) for other in battle.units): continue
        value=cost(unit.pos,point)+cost(point,destination)
        if value<direct*.85: choices.append((value,0 if sign==1 else 1,point))
    if choices:
        unit.terrain_waypoint=min(choices,key=lambda item:(item[0],item[1]))[2]
        unit.terrain_route_left=120.
        return unit.terrain_waypoint
    return destination
