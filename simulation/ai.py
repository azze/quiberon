import math
from .formations import PROFILES
from .geometry import Vec, angle_to, angle_delta, separation, touching
from .orders import Order, OrderKind as O
from .regiment import UnitType as T, MoraleState as S
from .combat import attack_target, firing_blocker
from .archetypes import Trait
from . import commanders,commander_ai,routing

STRATEGIES = ("balanced", "all_out_attack", "hold_the_line", "skirmish")
STRATEGY_NAMES = {"balanced":"Balanced", "all_out_attack":"All out attack", "hold_the_line":"Hold the line", "skirmish":"Skirmish"}


def army_plan(battle):
    """Infrequent, imperfect orders; only explicitly AI-controlled armies are changed."""
    if battle.tick % 50: return
    for army in sorted(battle.ai_armies):
        strategy=battle.ai_strategies[army]
        friends = [u for u in battle.units if u.effective and u.army == army]
        enemies = [u for u in battle.units if u.effective and u.army != army]
        if not enemies and not any(e.active and e.army!=army for e in battle.units): continue
        infantry = sorted((f for f in friends if f.stats.kind == T.INFANTRY), key=lambda f:f.id)
        reserve_id = infantry[-1].id if len(infantry) >= 4 else None
        for u in friends:
            if u.player_order:
                if u.order.kind in (O.ATTACK,O.CHARGE) and attack_target(battle,u) is None:
                    u.player_order=False;u.player_attack=False
                else:
                    u.ai_state='player attack order' if u.order.kind in (O.ATTACK,O.CHARGE) else 'explicit player order';continue
            if u.player_attack and attack_target(battle,u) is not None:
                u.ai_state = 'player attack order'
                continue
            if u.stats.kind==T.CAVALRY and u.cavalry_state.value in ('charging','pursuit','recoil','reforming'):
                continue
            u.player_attack = False
            u.player_order = False
            candidates=[e for e in battle.units if e.active and e.army!=army] if u.stats.kind==T.CAVALRY else enemies
            detected=[e for e in candidates if battle.perceives(u,e)]
            if u.commander_avoid_target is not None and battle.time<u.commander_avoid_until:
                detected=[e for e in detected if e.id!=u.commander_avoid_target]
            if not detected:
                if strategy=='hold_the_line' and u.stats.kind!=T.ARTILLERY:
                    anchor=battle.deployment_positions[u.id]
                    u.order=Order(O.MOVE,anchor) if (u.pos-anchor).length()>8 else Order(O.HOLD)
                    u.ai_state='hold the line: no visible threat'
                continue
            nearest = min(detected, key=lambda e: (e.pos - u.pos).length())
            if commander_ai.plan(battle,u,detected,nearest):continue
            nearest=commander_ai.select_target(battle,u,detected,nearest)
            if u.stats.kind!=T.ARTILLERY and strategy=='hold_the_line':
                anchor=battle.deployment_positions[u.id]
                if (u.pos-anchor).length()>8: u.order=Order(O.MOVE,anchor)
                elif (nearest.pos-u.pos).length()<120 and u.stats.kind==T.CAVALRY: u.order=Order(O.ATTACK,target_id=nearest.id)
                else: u.order=Order(O.HOLD)
                u.ai_state='hold the line: defend deployment'
                continue
            if u.stats.kind == T.ARTILLERY:
                if u.order.kind==O.MOVE and u.order.destination and battle.time<u.ai_position_until and (u.pos-u.order.destination).length()>15:
                    continue
                if u.limbered or battle.time<u.ai_position_until: continue
                if not battle.terrain.empty and battle.visibility(u,nearest).reason=='ridge':
                    from dataclasses import replace
                    candidates=[]
                    for dx,dy in ((60,0),(-60,0),(0,60),(0,-60),(40,40),(40,-40),(-40,40),(-40,-40)):
                        point=u.pos+Vec(dx,dy)
                        candidate=replace(u,pos=point)
                        if not all(0<p.x<battle.rules.width and 0<p.y<battle.rules.height for p in candidate.footprint): continue
                        if any(e.active and e.army!=u.army and separation(candidate,e) is not None for e in battle.units): continue
                        if battle.terrain.visibility(point,nearest.pos,battle.rules.terrain).visible:
                            score=battle.terrain.forest_density(point.x,point.y)*3+battle.terrain.slope(point.x,point.y)
                            candidates.append((score,dx,dy,point))
                    if candidates:
                        u.order=Order(O.MOVE,min(candidates,key=lambda item:item[:3])[3])
                        u.ai_state='battery: seek a clear firing position'
                        u.ai_position_until=battle.time+60
                        continue
                closing=(nearest.pos-u.pos).length()>u.stats.range*.85
                u.ai_state = 'battery: advance into firing distance' if closing else 'battery: hold and bombard'
                u.order = Order(O.ADVANCE, nearest.pos) if closing else Order(O.HOLD)
            elif u.archetype.role in ('skirmisher','rifles') and strategy!='all_out_attack':
                u.ai_state='light infantry: skirmish at effective range'
                u.order=Order(O.SKIRMISH,nearest.pos)
            elif u.stats.kind == T.CAVALRY:
                # Keep a living target throughout the approach and contact.
                current=attack_target(battle,u)
                if current is None and u.cavalry_target_id is not None:
                    current=next((e for e in detected if e.id==u.cavalry_target_id),None)
                from .cavalry import readiness
                exposed=current or min(detected,key=lambda e: e.cohesion+(e.pos-u.pos).length()*.12+
                    (60 if e.stats.kind==T.INFANTRY else -40)+50*readiness(u,e)- (90 if e.state in (S.WAVERING,S.ROUTING) else 0))
                if current is None: u.cavalry_target_id=exposed.id
                if not u.cavalry_commit_at: u.cavalry_commit_at=battle.time+18*commanders.policy(u).commitment
                if strategy=='all_out_attack' or battle.time>=u.cavalry_commit_at or (exposed.pos-u.pos).length()<150:
                    u.order=Order(O.ATTACK,target_id=exposed.id)
                    u.ai_state='cavalry: committed attack'
                else:
                    if u.cavalry_waypoint is None:
                        sign=-1 if u.pos.y<battle.rules.height/2 else 1
                        point=exposed.pos+Vec(-100 if u.army==0 else 100,sign*100)
                        u.cavalry_waypoint=Vec(max(40,min(battle.rules.width-40,point.x)),max(40,min(battle.rules.height-40,point.y)))
                    if (u.pos-u.cavalry_waypoint).length()<15:
                        u.order=Order(O.ATTACK,target_id=exposed.id)
                    else: u.order=Order(O.MOVE,u.cavalry_waypoint)
                    u.ai_state='cavalry: bounded flank approach'
            elif (u.commander and u.commander.personality in (commanders.P.AGGRESSIVE,commanders.P.OPPORTUNISTIC) and
                  commander_ai.vulnerable(nearest) and (nearest.pos-u.pos).length()<90 and u.cohesion>=50):
                u.order=Order(O.CHARGE,target_id=nearest.id);u.ai_state='commander: exploit weakness with bayonets'
                commander_ai.note(battle,u,'committing an exposed-target assault')
            elif strategy=='skirmish':
                u.order=Order(O.SKIRMISH,nearest.pos); u.ai_state='skirmish strategy: maintain range'
            elif strategy=='all_out_attack':
                u.order=Order(O.ATTACK,target_id=nearest.id); u.ai_state='all out attack: commit centre'
            elif u.id == reserve_id and battle.time < 75 and (nearest.pos - u.pos).length() > 190 and not commanders.personality(u,commanders.P.AGGRESSIVE):
                u.ai_state = 'reserve: waiting'
                u.order = Order(O.RESERVE)
            else:
                u.ai_state = 'centre: advance to firing line'
                holding=(commanders.personality(u,commanders.P.STALWART) or commanders.has(u,commanders.S.DEFENSIVE) or commanders.upgrades.has(u,"steadfast_defence")) and (nearest.pos-u.pos).length()<u.stats.range*.85
                u.order = Order(O.HOLD) if holding else Order(O.ADVANCE,nearest.pos,target_id=nearest.id if commanders.personality(u,commanders.P.OPPORTUNISTIC) else None)


def destination(battle, u):
    u.target_id = None
    u.pursuit_id = None
    if u.state == S.ROUTING:return routing.destination(battle,u)
    u.rout_heading=None;u.rout_next_plan=0.
    if u.order.kind == O.WITHDRAW:
        if u.order.kind == O.WITHDRAW:
            if u.pos.x < 18 or u.pos.x > battle.rules.width - 18: u.withdrawn = True
        return Vec(10 if u.army == 0 else battle.rules.width - 10, u.pos.y)
    if u.state == S.RALLYING: return None
    target = battle.unit(u.order.target_id)
    if target is None or not target.active or target.army == u.army:
        # Stable distance ordering yields exactly the old nearest visible enemy,
        # without casting rays to every more-distant candidate. No range cutoff.
        candidates=sorted((e for e in battle.units if e.active and e.army!=u.army),key=lambda e:(e.pos-u.pos).length())
        target=next((e for e in candidates if battle.perceives(u,e)),None)
    # A move must complete even if an unrelated enemy becomes concealed. An
    # explicit arrival heading remains in force until another order interrupts it.
    if u.order.kind == O.MOVE or (u.order.kind == O.ADVANCE and u.order.facing is not None
                                 and u.order.destination is not None and (u.pos-u.order.destination).length()<1):
        if target and battle.perceives(u,target):
            u.target_id=target.id
            u.last_seen_target_pos=target.pos
        return u.order.destination
    if target and not battle.perceives(u,target) and (u.stats.kind != T.ARTILLERY or (u.army in battle.ai_armies and not u.player_attack)):
        if u.stats.kind == T.ARTILLERY: return None
        if u.order.kind in (O.ATTACK,O.ADVANCE,O.CHARGE,O.SKIRMISH): return u.last_seen_target_pos or u.order.destination
        return None
    if target:
        u.target_id = target.id
        u.last_seen_target_pos=target.pos
        if u.stats.kind==T.CAVALRY and target.state==S.ROUTING and u.order.kind in (O.ATTACK,O.ADVANCE,O.CHARGE): u.pursuit_id=target.id
    kind = u.order.kind
    if kind in (O.ATTACK,O.ADVANCE,O.CHARGE) and target is not None:
        key=(min(u.id,target.id),max(u.id,target.id))
        pursuing=(u.stats.kind==T.CAVALRY and target.state==S.ROUTING and u.cohesion>=battle.rules.pursuit_min_cohesion and u.fatigue<battle.rules.pursuit_max_fatigue)
        if not pursuing and battle.tick<=battle.melee_next.get(key,-1) and touching(u,target):
            turn_toward(battle,u,target.pos)
            return None
    if kind == O.SKIRMISH:
        return skirmish_destination(battle,u,target)
    if kind==O.CHARGE and u.stats.kind==T.INFANTRY:
        return target.pos if target else u.order.destination
    if kind in (O.ATTACK, O.ADVANCE,O.CHARGE):
        designated = attack_target(battle,u)
        if designated and u.stats.kind != T.CAVALRY and (designated.pos-u.pos).length() <= u.stats.range:
            if u.stats.kind != T.ARTILLERY and not battle.visibility(u,designated).visible:
                return designated.pos
            blocker = firing_blocker(battle,u,designated)
            # Soft friendly collisions make walking through the screen a valid
            # way to clear a firing lane. Do not stop merely because range is OK.
            if blocker is not None and blocker.army == u.army:
                return designated.pos
            turn_toward(battle,u,designated.pos)
            return None
        if target:
            distance = (target.pos - u.pos).length()
            engagement=commanders.policy(u).firing_distance if commander_ai.autonomous(battle,u) and u.stats.kind==T.INFANTRY else .85
            if u.stats.kind != T.CAVALRY and distance <= u.stats.range * engagement and (u.stats.kind == T.ARTILLERY or battle.visibility(u,target).visible):
                turn_toward(battle, u, target.pos)
                return None
            return target.pos
        return u.order.destination
    if kind == O.DEFEND and u.order.destination and (u.pos - u.order.destination).length() > 20:
        return u.order.destination
    # Holding troops may face threats in their forward hemisphere, not magically spin at flankers.
    if target and (target.pos - u.pos).length() <= u.stats.range and abs(angle_delta(u.facing, angle_to(u.pos, target.pos))) < math.pi / 2:
        turn_toward(battle, u, target.pos)
    return None


def turn_toward(battle, u, pos):
    if u.settling_facing is not None or u.infantry_charging: return
    # Movement owns the heading while accelerating or turning out of contact.
    # Otherwise contact-facing would exactly cancel every recoil turn.
    if u.stats.kind==T.CAVALRY and u.cavalry_state.value in ('charging','recoil','reforming'): return
    if u.transition_left: return
    delta = angle_delta(u.facing, angle_to(u.pos, pos))
    limit = u.stats.turn_rate * .65 * battle.rules.dt
    u.facing += max(-limit, min(limit, delta))


def skirmish_destination(battle,u,target):
    """Bounded six-second retreat, then ten seconds of committed re-engagement.

    Only a skirmish order invokes this behaviour. Move/hold/attack remain literal.
    """
    if target is None: return u.order.destination
    if battle.tick==0 and battle.terrain.forests:
        u.forest_cover=battle.terrain.movement_effect(u,Vec(0,0),battle.rules.terrain).forest
    distance=(target.pos-u.pos).length()
    close=100. if target.stats.kind==T.CAVALRY else min(80.,u.stats.range*.45)
    stronger=target.strength*target.archetype.melee>u.strength*.8 or target.stats.kind==T.CAVALRY
    if u.forest_cover>0 and u.archetype.forest_melee_damage>1 and target.stats.kind==T.INFANTRY:
        # Woodland specialists need not abandon a favourable ambush solely
        # because a conventional regiment has a larger headcount.
        stronger=target.strength*target.archetype.melee>u.strength*.8*(1+(u.archetype.forest_melee_damage-1)*battle.rules.terrain.woodland_skill(u.forest_cover))
    if u.skirmish_retreat and battle.time>=u.skirmish_until:
        u.skirmish_retreat=False; u.skirmish_until=battle.time+10
    if not u.skirmish_retreat and battle.time>=u.skirmish_until and distance<close and stronger:
        away=angle_to(target.pos,u.pos)
        turning=abs(angle_delta(u.facing,away))/max(.1,u.stats.turn_rate*PROFILES[u.formation][3])
        u.skirmish_retreat=True; u.skirmish_until=battle.time+6+min(4.,turning)
        battle.activate(u,'Skirmish: turn out, then bounded withdrawal')
    if u.skirmish_retreat:
        radius=math.hypot(u.width,u.depth)/2+1
        away=(u.pos-target.pos).normalized()
        if away.length()<.1: away=Vec(-1 if u.army==0 else 1,0)
        point=u.pos+away*65
        u.ai_state='skirmish: turning out / withdrawing'
        return Vec(max(radius,min(battle.rules.width-radius,point.x)),max(radius,min(battle.rules.height-radius,point.y)))
    desired=u.stats.range*(.82 if u.archetype.role=='rifles' else .72)
    if distance>desired or not battle.visibility(u,target).visible:
        u.ai_state='skirmish: approaching firing distance'
        return target.pos
    turn_toward(battle,u,target.pos)
    u.ai_state='skirmish: fire and hold distance'
    return None
