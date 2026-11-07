"""Charge lifecycle and close pursuit; ordinary melee stays in combat.py.

No independent orders or RNG: these functions interpret the existing order,
reuse its target, and resolve contact in Battle's fixed geometry phase.
"""
import math

from .geometry import Vec, direction, angle_to, angle_delta, touching
from .regiment import UnitType as T, MoraleState as S, CavalryState as C
from .orders import OrderKind as O
from .archetypes import exploit_bonus
from . import commanders,commander_ai


def clamp(value,low=0.,high=1.): return max(low,min(high,value))


def support(unit,axis):
    return abs(direction(unit.facing).dot(axis))*unit.depth/2+abs(direction(unit.facing+math.pi/2).dot(axis))*unit.width/2


def gap(a,b):
    offset=b.pos-a.pos; axis=offset.normalized()
    return offset.length()-support(a,axis)-support(b,axis)


def readiness(attacker,target):
    """Prepared defence belongs to stationary, steady, front-facing dense foot."""
    if target.stats.kind!=T.INFANTRY or target.state!=S.STEADY or target.transition_left or target.formation.value=='skirmish': return 0.
    front=clamp(1-abs(angle_delta(target.facing,angle_to(target.pos,attacker.pos)))/(math.pi/3))
    stationary=clamp(1-target.speed/1.5)
    return front*stationary*clamp((target.cohesion-40)/50)


def can_pursue(battle,u,target):
    return (u.effective and target.active and target.state==S.ROUTING and
            u.order.kind in (O.ATTACK,O.ADVANCE,O.CHARGE) and target.id in (u.target_id,u.order.target_id) and
            u.cohesion>=battle.rules.pursuit_min_cohesion and u.fatigue<battle.rules.pursuit_max_fatigue)


def cancel(u,battle=None):
    if u.cavalry_state==C.CHARGING:
        u.analysis['aborted_charges']+=1
        if battle: battle.log('charge',f'{u.name}: charge aborted',u.id)
    u.cavalry_state=C.APPROACH
    u.cavalry_target_id=None;u.charge_momentum=0.;u.charge_distance=0.
    u.recoil_goal=None;u.pursuit_speed_limit=None;u.pursuit_id=None
    # Never clear the impact lock/cooldown merely because an order was repeated.


def recoil(battle,u,target):
    away=(u.pos-target.pos).normalized()
    if away.length()<.1: away=direction(u.facing+math.pi)
    point=u.pos+away*battle.rules.charge_recoil_distance
    radius=math.hypot(u.width,u.depth)/2+1
    u.recoil_goal=Vec(clamp(point.x,radius,battle.rules.width-radius),clamp(point.y,radius,battle.rules.height-radius))
    u.cavalry_state=C.RECOIL;u.cavalry_retreat_until=battle.time+10.
    u.charge_momentum=0.
    battle.log('recoil',f'{u.name}: charge held; recoil and reform',u.id)


def intent(battle,u,destination):
    """O(1) per cavalry regiment, using the target already selected by AI."""
    r=battle.rules;u.pursuit_speed_limit=None
    reform=r.charge_reform_seconds*(commanders.upgrades.TUNING.controlled_reform if commanders.upgrades.has(u,"controlled_charge") else 1.)
    if not u.charge_ready:
        previous=battle.unit(u.charge_impact_target_id)
        clear=previous is None or not previous.active or gap(u,previous)>=r.charge_clearance
        if clear and battle.time-u.charge_contact_at>reform:
            if u.charge_clear_since is None: u.charge_clear_since=battle.time
            if battle.time-u.charge_clear_since>=reform and u.charge_cooldown<=0:
                u.charge_ready=True
        else: u.charge_clear_since=None
    target=battle.unit(u.target_id)
    if not u.effective or u.order.kind not in (O.ATTACK,O.ADVANCE,O.CHARGE) or target is None or not target.active:
        cancel(u,battle)
        return destination
    if u.cavalry_target_id is not None and u.cavalry_target_id!=target.id:
        cancel(u,battle)
    u.cavalry_target_id=target.id
    if commander_ai.pursuit_limit(battle,u,target):
        cancel(u,battle)
        return u.commander_retreat_goal
    distance=(target.pos-u.pos).length(); clearance=gap(u,target)
    # Rearming above also runs during Hold/Move, never just on target changes.
    if can_pursue(battle,u,target):
        u.pursuit_id=target.id
        if clearance<=commanders.pursuit_gap(u,r.pursuit_contact_gap):
            if u.cavalry_state==C.CHARGING: return target.pos
            if u.cavalry_state!=C.PURSUIT and u.cavalry_state!=C.CHARGING:
                battle.log('pursuit',f'{u.name}: pursuing broken {target.name}',u.id)
            if u.cavalry_state!=C.CHARGING: u.cavalry_state=C.PURSUIT
            # Match the fleeing edge instead of pushing its entire rectangle.
            axis=(target.pos-u.pos).normalized()
            velocity=target.velocity or direction(target.facing)*target.speed
            u.pursuit_speed_limit=max(0.,velocity.dot(axis))+max(0.,clearance-.25)/r.dt
            return target.pos
        if u.cavalry_state==C.PURSUIT:
            u.cavalry_state=C.APPROACH;u.charge_momentum=0.
    elif u.cavalry_state==C.PURSUIT:
        u.cavalry_state=C.MELEE if touching(u,target) else C.APPROACH
        u.charge_momentum=0.;u.pursuit_id=None
    if u.cavalry_state==C.RECOIL:
        if (u.pos-u.recoil_goal).length()<4 or battle.time>=u.cavalry_retreat_until:
            if touching(u,target):
                u.cavalry_state=C.MELEE;u.charge_melee_since=battle.time
            else: u.cavalry_state=C.REFORMING;u.cavalry_retreat_until=battle.time+reform
        else: return u.recoil_goal
    if u.cavalry_state==C.REFORMING:
        if battle.time<u.cavalry_retreat_until: return None
        u.cavalry_state=C.APPROACH
    if u.cavalry_state==C.MELEE:
        if not touching(u,target): u.cavalry_state=C.APPROACH
        elif (u.army in battle.ai_armies and not u.player_order and not u.player_attack and battle.time-u.charge_melee_since>commanders.policy(u).disengage_seconds and
              target.state in (S.STEADY,S.SHAKEN) and target.cohesion>=50 and
              (u.cohesion<50 or target.strength>u.strength*commanders.policy(u).overmatch)):
            recoil(battle,u,target)
            return u.recoil_goal
    if u.cavalry_state==C.CHARGING:
        if (u.cohesion<r.pursuit_min_cohesion or u.fatigue>=r.pursuit_max_fatigue or
            u.forest_cover>max(.65,r.charge_max_forest) or
            abs(angle_delta(u.facing,angle_to(u.pos,target.pos)))>1.3 or battle.time-u.charge_started>r.charge_max_seconds):
            cancel(u,battle);u.charge_cooldown=max(u.charge_cooldown,3.)
        return destination
    aligned=abs(angle_delta(u.facing,angle_to(u.pos,target.pos)))<.55
    if battle.tick==0 and not battle.terrain.empty:
        ground=battle.terrain.movement_effect(u,direction(u.facing),r.terrain)
        u.forest_cover=ground.forest;u.ground_slope=ground.slope
    if (u.charge_ready and u.charge_cooldown<=0 and destination is not None and
        r.charge_min_run<=clearance and distance<=r.charge_range and aligned and
        u.cohesion>=r.charge_min_cohesion and u.fatigue<75 and
        u.forest_cover<=r.charge_max_forest and u.ground_slope<=r.charge_max_slope and
        u.terrain_waypoint is None and u.avoidance_goal is None):
        u.cavalry_state=C.CHARGING;u.charge_sequence+=1;u.charge_distance=0.;u.charge_started=battle.time
        u.charge_momentum=0.;u.analysis['charge_initiations']+=1
        battle.log('charge_start',f'{u.name}: charging {target.name} from {distance:.0f} m',u.id)
    return destination


def motion(battle,u):
    if u.cavalry_state==C.CHARGING:
        return dict(speed_cap=battle.rules.charge_max_speed*u.archetype.charge_speed,
                    acceleration=battle.rules.charge_acceleration,turn_multiplier=battle.rules.charge_turn_multiplier*(commanders.upgrades.TUNING.controlled_turn if commanders.upgrades.has(u,"controlled_charge") else 1.),
                    follow_speed=u.pursuit_speed_limit)
    return dict(follow_speed=u.pursuit_speed_limit) if u.pursuit_speed_limit is not None else {}


def after_move(battle,u,before):
    if u.cavalry_state!=C.CHARGING: return
    r=battle.rules;u.charge_distance+=(u.pos-before).length()
    target=battle.unit(u.cavalry_target_id)
    if target is None: u.charge_momentum=0.;return
    velocity=u.velocity or Vec(0,0)
    speed=velocity.length()
    alignment=clamp(velocity.normalized().dot((target.pos-u.pos).normalized())*(commanders.upgrades.TUNING.controlled_alignment if commanders.upgrades.has(u,"controlled_charge") else 1.))
    speed_factor=clamp((speed-r.charge_min_speed)/max(.1,r.charge_max_speed*u.archetype.charge_speed-r.charge_min_speed))
    terrain=clamp(1-r.terrain.charge_forest_penalty*u.forest_cover)/(1+u.ground_slope*r.terrain.charge_slope_penalty)
    u.charge_momentum=clamp(speed_factor*clamp(u.charge_distance/r.charge_min_run)*u.cohesion/100*alignment*terrain)


def impact(battle,u,target):
    """Consume one charge sequence on its first enemy contact, before melee."""
    if not u.effective or u.cavalry_state!=C.CHARGING or u.charge_impacted_sequence==u.charge_sequence: return
    from .combat import damage
    r=battle.rules
    u.charge_impacted_sequence=u.charge_sequence;u.charge_impact_target_id=target.id
    u.charge_impact_tick=battle.tick
    u.charge_ready=False;u.charge_clear_since=None
    u.charge_cooldown=r.charge_cooldown_seconds*(commanders.upgrades.TUNING.controlled_cooldown if commanders.upgrades.has(u,"controlled_charge") else 1.);u.charge_contact_at=battle.time
    u.charge_melee_since=battle.time;u.cavalry_state=C.MELEE
    velocity=u.velocity or Vec(0,0)
    alignment=clamp(velocity.normalized().dot((target.pos-u.pos).normalized())*(commanders.upgrades.TUNING.controlled_alignment if commanders.upgrades.has(u,"controlled_charge") else 1.))
    momentum=u.charge_momentum*alignment
    u.charge_last_momentum=momentum;u.charge_momentum=0.
    ready=readiness(u,target)
    flank_angle=abs(angle_delta(target.facing,angle_to(target.pos,u.pos)))
    flank=1. if flank_angle<math.pi/3 else 1.5 if flank_angle<2.3 else 1.9
    exploit=exploit_bonus(u,target,ready>.5)
    resistance=(1-.85*ready)*(commanders.defence_factor(target,u) if ready>.5 else 1.)
    power=u.strength*r.charge_damage*momentum*flank*resistance*exploit*commanders.frontal_pursuit_penalty(u,target)
    if target.formation.value=='column': power*=.85
    losses=max(0,int(power*battle.rng.uniform(.8,1.2)))
    shock=r.charge_shock*momentum*flank*resistance*exploit
    commander_boost=commanders.charge_shock_factor(u,target,momentum,ready>.5)
    shock*=commander_boost
    before=target.strength
    damage(battle,target,losses,'charge impact',u,shock)
    target.cohesion=max(0.,target.cohesion-r.charge_cohesion_damage*momentum*resistance)
    inflicted=before-target.strength
    u.analysis['charges']+=1;u.analysis['impact_casualties']+=inflicted;u.analysis['impact_momentum']+=momentum
    u.analysis['impact_morale_shock']+=shock*target.archetype.shock_resistance
    commanders.charge_aftermath(battle,u,momentum,commander_boost)
    if commanders.defence_factor(target,u)<1 and ready>.5:
        battle.activate(target,f'{target.commander.display_name}: prepared frontal charge defence')
    success=momentum>.1 and (inflicted>=target.stats.strength*.05 or (target.morale<=r.rout_threshold and ready<.5))
    if success:u.analysis['charge_successes']+=1
    failed=ready>.5 and target.active and target.morale>r.rout_threshold
    if failed:
        u.analysis['failed_charges']+=1
        u.cohesion=max(0.,u.cohesion-14*momentum*ready*(commanders.upgrades.TUNING.controlled_disorder if commanders.upgrades.has(u,"controlled_charge") else 1.))
        u.morale=max(0.,u.morale-6*momentum*ready)
    u.charge_result='prepared front' if failed else 'breakthrough' if success and target.effective else 'exposed formation'
    battle.effect('charge_impact',u.pos,1.,u.facing,u.width)
    battle.log('charge',f'{u.name} impact on {target.name}: {inflicted} losses, momentum {momentum:.0%} ({u.charge_result})',u.id)
    if exploit>1:battle.activate(u,'Exploit the Break: disrupted enemy charged')
    if failed: recoil(battle,u,target)


def contact(battle,a,b):
    """True means pursuit replaces this pair's ordinary melee exchange."""
    for u,target in ((a,b),(b,a)):
        if u.stats.kind!=T.CAVALRY or not u.effective: continue
        impact(battle,u,target)
        u.charge_contact_at=battle.time
        if can_pursue(battle,u,target):
            if u.cavalry_state!=C.PURSUIT:
                battle.log('pursuit',f'{u.name}: pursuing broken {target.name}',u.id)
            u.cavalry_state=C.PURSUIT
            # Give first impact its own interval rather than double-resolving it.
            battle.pursuit_next.setdefault(target.id,battle.tick+max(1,round(battle.rules.pursuit_interval/battle.rules.dt)))
            return True
        if u.cavalry_state not in (C.RECOIL,C.REFORMING):
            if u.cavalry_state!=C.MELEE: u.charge_melee_since=battle.time
            u.cavalry_state=C.MELEE
    return False


def pursuits(battle,units):
    """One bounded aggregate exchange per target/interval, with sqrt(n) sharing."""
    from .combat import damage
    r=battle.rules;groups={}
    for u in units:
        if u.stats.kind!=T.CAVALRY or u.cavalry_state!=C.PURSUIT or u.combat_state=='melee': continue
        target=battle.unit(u.cavalry_target_id)
        if target is None or not can_pursue(battle,u,target) or gap(u,target)>commanders.pursuit_gap(u,r.pursuit_contact_gap): continue
        u.combat_state='pursuit';u.target_id=target.id;u.charge_contact_at=battle.time
        target.combat_state='pursuit'
        u.analysis['pursuit_seconds']+=r.dt
        groups.setdefault(target.id,[]).append(u)
    for target_id,followers in sorted(groups.items()):
        target=battle.unit(target_id)
        due=battle.pursuit_next.setdefault(target_id,battle.tick+max(1,round(r.pursuit_interval/r.dt)))
        if battle.tick<due:continue
        battle.pursuit_next[target_id]=battle.tick+max(1,round(r.pursuit_interval/r.dt))
        weights=[u.strength*(.3+.7*u.cohesion/100)*min(1.8 if commanders.upgrades.has(u,"relentless_pursuit") else 1.45,u.archetype.pursuit*commanders.pursuit_factor(u))*
                 max(.15,1-r.terrain.charge_forest_penalty*u.forest_cover)/(1+u.ground_slope*r.terrain.charge_slope_penalty) for u in followers]
        total=sum(weights)
        casualties=min(target.strength,int(target.stats.strength*r.pursuit_max_fraction),
                       max(0,int(total*r.pursuit_damage/math.sqrt(len(followers))*battle.rng.uniform(.85,1.15))))
        # Allocate a shared integer budget deterministically, with no extra RNG.
        remaining=casualties
        for i,(u,weight) in enumerate(zip(followers,weights)):
            losses=remaining if i==len(followers)-1 else min(remaining,int(casualties*weight/max(.001,total)))
            remaining-=losses
            before=target.strength
            damage(battle,target,losses,'cavalry pursuit',u,shock=.8*weight/max(.001,total))
            u.analysis['pursuit_casualties']+=before-target.strength
        target.cohesion=max(0.,target.cohesion-2.)
        # The fugitive formation gets one scattered-resistance budget, not one
        # guaranteed counterattack against every overlapping pursuer.
        if target.active:
            resistance=target.strength*r.pursuit_resistance*r.routing_melee_factor*(.3+target.cohesion/100)
            rolled=resistance*battle.rng.uniform(.65,1.35)
            losses=int(rolled)+int(battle.rng.random()<rolled-int(rolled))
            victim=followers[(battle.tick//max(1,round(r.pursuit_interval/r.dt)))%len(followers)]
            before=victim.strength
            damage(battle,victim,losses,'pursuit resistance',target,shock=r.routing_melee_factor*.5)
            victim.analysis['pursuit_losses']+=before-victim.strength
