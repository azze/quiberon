import math
from .geometry import Vec, angle_delta, angle_to, segment_rect, direction, separation, intersection_area
from .formations import PROFILES
from .regiment import UnitType, MoraleState
from .orders import OrderKind
from .spatial import candidate_pairs
from .archetypes import Trait, drill, reload_time, aimed_bonus
from . import commanders


def in_arc(shooter, target, half_arc):
    return abs(angle_delta(shooter.facing, angle_to(shooter.pos, target.pos))) <= half_arc


def firing_groups(battle):
    """Connected positive-area friendly overlaps, cached by current geometry.

    Soft interpenetration must not create mutually opaque rectangles. Groups
    contain only one army; edge touching alone does not join formations.
    """
    units=[unit for unit in battle.units if unit.active]
    signature=tuple((u.id,u.army,u.pos,u.facing,u.width,u.depth) for u in units)
    if signature==battle._firing_group_signature: return battle._firing_groups
    parent=list(range(len(units)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    indices={u.id:i for i,u in enumerate(units)}
    for a,b in candidate_pairs(units):
        if a.army==b.army and separation(a,b) is not None:
            parent[root(indices[b.id])]=root(indices[a.id])
    members={}
    for i,unit in enumerate(units): members.setdefault(root(i),set()).add(unit.id)
    groups={unit.id:frozenset(members[root(i)]) for i,unit in enumerate(units)}
    battle._firing_group_signature=signature
    battle._firing_groups=groups
    return groups


def firing_blocker(battle, shooter, target):
    """Dense screens block fire; source overlaps instead share outgoing frontage.

    Target overlap groups remain hittable, avoiding mutual target immunity.
    """
    if shooter.stats.kind == UnitType.ARTILLERY: return None
    hits = []
    index=getattr(battle,"_fire_index",None)
    candidates=index.segment(shooter.pos,target.pos) if index is not None else battle.units
    for unit in candidates:
        if not unit.active or unit.id in (shooter.id,target.id): continue
        entry = segment_rect(shooter.pos,target.pos,unit)
        if entry is not None: hits.append((entry,unit.id,unit))
    if not hits: return None
    groups=firing_groups(battle)
    source_group=groups.get(shooter.id,frozenset((shooter.id,)))
    target_group=groups.get(target.id,frozenset((target.id,)))
    hits=[hit for hit in hits if (hit[1] not in source_group or intersection_area(shooter,hit[2])<=1e-8) and hit[1] not in target_group and
          (hit[2].army!=shooter.army or (hit[2].formation.value!='skirmish' and lane_cover(battle,shooter,target,hit[2])>=.99))]
    return min(hits,key=lambda hit:(hit[0],hit[1]))[2] if hits else None


def lane_cover(battle,shooter,target,obstacle):
    """Three parallel frontage samples, with a simple absolute-height clearance."""
    side=direction(angle_to(shooter.pos,target.pos)+1.5707963267948966)
    source_z=target_z=obstacle_z=0.
    if not battle.terrain.empty:
        height=battle.rules.terrain.observer_height
        source_z=battle.terrain.get_elevation(shooter.pos.x,shooter.pos.y)+height
        target_z=battle.terrain.get_elevation(target.pos.x,target.pos.y)+height
        obstacle_z=battle.terrain.get_elevation(obstacle.pos.x,obstacle.pos.y)+height
    covered=0
    for fraction in (-.35,0.,.35):
        shift=side*(shooter.width*fraction)
        entry=segment_rect(shooter.pos+shift,target.pos+shift,obstacle)
        if entry is None: continue
        if not battle.terrain.empty and source_z+(target_z-source_z)*entry>obstacle_z+battle.rules.friendly_fire_clearance: continue
        covered+=1
    return covered/3


def friendly_fire_factor(battle,shooter,target):
    """Bounded frontage sharing in overlaps plus partial friendly screening.

    Calculated only for an actual ready volley, not for every target candidate.
    Coincident dense lines share one frontage instead of becoming mutually opaque.
    """
    if shooter.stats.kind!=UnitType.INFANTRY: return 1.
    index=getattr(battle,'_fire_index',None)
    candidates=index.segment(shooter.pos,target.pos,padding=shooter.width/2) if index else battle.units
    shared=1.; cover=0.
    for friend in candidates:
        if friend.id==shooter.id or not friend.active or friend.army!=shooter.army: continue
        density=battle.rules.friendly_loose_density if friend.formation.value=='skirmish' else 1.
        radius=(shooter.width+shooter.depth+friend.width+friend.depth)/2
        area=intersection_area(shooter,friend) if (friend.pos-shooter.pos).length()<radius else 0.
        if area>1e-8:
            shared+=min(1.,area/(shooter.width*shooter.depth))*density
        else: cover=max(cover,lane_cover(battle,shooter,target,friend)*density)
    return max(0.,min(1.,(1-cover)/shared))


def can_fire(battle, shooter, target):
    if shooter.stats.kind==UnitType.ARTILLERY and (shooter.limbered or shooter.setup_left>0): return False
    distance = (target.pos - shooter.pos).length()
    if distance > shooter.stats.range or not in_arc(shooter, target, battle.rules.firing_half_arc): return False
    # Infantry needs a clear shot; artillery ignores LOS but keeps range and arc limits.
    return (shooter.stats.kind == UnitType.ARTILLERY or battle.visibility(shooter,target).visible) and firing_blocker(battle,shooter,target) is None


def attack_target(battle,unit):
    """A live, explicit attack order remains binding until its enemy is gone."""
    if unit.order.kind not in (OrderKind.ATTACK,OrderKind.CHARGE): return None
    target = battle.unit(unit.order.target_id)
    return target if target and target.active and target.army != unit.army else None


def select_fire_target(battle,unit):
    designated = attack_target(battle,unit)
    if designated is not None:
        if unit.stats.kind == UnitType.ARTILLERY and unit.army in battle.ai_armies and not unit.player_attack and not battle.perceives(unit,designated): return None
        return designated if can_fire(battle,unit,designated) else None
    targets = [enemy for enemy in battle.units if enemy.active and enemy.army != unit.army and can_fire(battle,unit,enemy) and battle.perceives(unit,enemy)]
    preferred = next((enemy for enemy in targets if enemy.id == unit.order.target_id),None)
    return preferred or min(targets,key=lambda enemy:((enemy.pos-unit.pos).length(),enemy.id),default=None)


def damage(battle, target, losses, reason, attacker=None, shock=0.):
    losses = min(target.strength, max(0, int(losses)))
    if not target.active: return
    target.strength -= losses
    actual_shock=shock*max(.55 if commanders.upgrades.has(target,"steadfast_defence") else .65,target.archetype.shock_resistance*commanders.shock_factor(target))
    target.morale = max(0., target.morale - (losses / target.stats.strength * battle.rules.casualty_morale + actual_shock) / target.stats.discipline)
    target.cohesion = max(0., target.cohesion - (losses / target.stats.strength * 130 + shock * .35)*commanders.defence_factor(target,attacker))
    if losses >= max(5, target.stats.strength * .04):
        battle.log('casualties', f'{target.name}: {losses} lost to {reason}', target.id)
    if attacker is not None and attacker.army == target.army and losses:
        battle.metrics['friendly_fire'] += 1
        battle.log('friendly_fire', f'{attacker.name} struck {target.name}', target.id)
    if losses and attacker is not None: attacker.morale = min(100., attacker.morale + losses * .025)
    if attacker is not None and (losses or actual_shock):
        target.last_attacker=attacker.id
        attacker.analysis['casualties_inflicted']+=losses
        attacker.analysis['morale_shock']+=actual_shock
        if attacker.commander and attacker.commander.upgrades and attacker.army!=target.army:
            commanders.upgrades.inspired(battle,attacker,target,losses)
            if reason in ('melee','charge impact','bayonet charge','cavalry pursuit'):
                attacker.upgrade_state['last_attack']=battle.time


def scale_casualties(battle,losses,multiplier):
    """Preserve small damage bonuses using seeded fractional rounding."""
    if losses<=0 or multiplier==1:return losses
    scaled=max(0.,losses*multiplier)
    whole=int(scaled);fraction=scaled-whole
    return whole+int(fraction>1e-9 and battle.rng.random()<fraction)


def forest_cover(battle,unit):
    return battle.terrain.movement_effect(unit,Vec(0,0),battle.rules.terrain).forest if battle.terrain.forests else 0.


def forest_fire_factors(battle,unit,target,sight):
    """Outgoing vegetation disruption and directional protection, not extra LOS.

    Target cover uses its actual footprint and vegetation on this firing lane.
    A shallow outward lane interferes less than firing through deep woodland.
    """
    r=battle.rules.terrain
    cover=forest_cover(battle,unit)
    target_cover=forest_cover(battle,target)
    depth=min(1.,sight.vegetation/max(1.,r.forest_firing_depth))
    protection=r.forest_cover_protection*target_cover*min(1.,sight.vegetation/max(1.,r.forest_cover_depth))
    transmission=sight.transmission**(1-(1-unit.archetype.forest_aim)*cover)
    outgoing=(1-r.forest_fire_penalty*cover*unit.archetype.forest_fire*depth)
    accuracy=1+(unit.archetype.forest_accuracy-1)*r.woodland_skill(cover)
    return max(0.,transmission*max(.1,outgoing)*accuracy),max(.15,1-protection),cover


def forest_melee_factors(battle,unit):
    cover=forest_cover(battle,unit)
    skill=battle.rules.terrain.woodland_skill(cover)
    density=.25 if unit.formation.value=='skirmish' else .6 if unit.formation.value=='column' else 1.
    formation=max(.2,1-battle.rules.terrain.forest_melee_penalty*cover*density)
    power=1+(unit.archetype.forest_melee_damage-1)*skill
    shock=unit.archetype.melee_shock*(1+(unit.archetype.forest_melee_shock-1)*skill)
    return formation,power,shock


def fire(battle, unit, target):
    if not unit.effective:return
    if unit.stats.kind==UnitType.INFANTRY and unit.order.kind==OrderKind.CHARGE: return
    if unit.combat_state=='melee': return
    if unit.reload_left > 0 or unit.transition_left > 0 or not can_fire(battle, unit, target): return
    factor=friendly_fire_factor(battle,unit,target)
    unit.fire_lane_factor=factor
    if factor<=0: return
    was_melee=unit.combat_state=='melee'
    unit.reload_left = max(.5,reload_time(unit)*commanders.upgrades.volley_reload(battle,unit))
    unit.combat_state = 'firing'
    unit.analysis['volleys']+=1
    distance = (target.pos - unit.pos).length()
    unit.analysis['firing_distance_total']+=distance
    battle.effect('smoke', unit.pos + direction(unit.facing) * (unit.depth / 2 + 2), 3., unit.facing, unit.width, unit_id=unit.id)
    if unit.stats.kind == UnitType.ARTILLERY:
        from .projectiles import launch_salvo
        launch_salvo(battle, unit, target)
        return
    shots = max(1, int(unit.strength * .42 * PROFILES[unit.formation][4]*factor))
    probability = battle.rules.musket_accuracy * (1 - .65 * distance / unit.stats.range) * (.3 + unit.cohesion / 140)
    probability*=unit.archetype.accuracy
    if unit.archetype.trait==Trait.DRILL:
        probability*=.85+.30*drill(unit)
        if drill(unit)>.2: battle.activate(unit,'Prussian Drill: coordinated volley')
    if target.formation.value=='skirmish': probability*=.65
    sight=battle.visibility(unit,target)
    aimed=1. if was_melee else aimed_bonus(unit,sight.transmission)
    probability*=min(1.5,aimed*(commanders.accuracy_factor(unit,sight.transmission) if not was_melee else 1.))
    if aimed>1.05: battle.activate(unit,'Aimed Fire: stationary precision volley')
    if not battle.terrain.empty:
        outgoing,protection,cover=forest_fire_factors(battle,unit,target,sight)
        probability*=outgoing*protection
        if cover>.2 and unit.archetype.trait==Trait.WOODLAND: battle.activate(unit,'Woodland Warfare: firing from cover')
    if unit.speed > .1: probability *= .45
    if unit.state == MoraleState.SHAKEN: probability *= .8
    if unit.state == MoraleState.WAVERING: probability *= .55
    if not unit.effective: return
    probability=max(0.,min(.95,probability))
    losses = sum(battle.rng.random() < probability for _ in range(shots))
    losses = scale_casualties(battle,losses,battle.rules.infantry_volley_damage)
    before=target.strength
    damage(battle, target, losses, 'musket volley', unit, shock=.9*factor)
    unit.analysis['volley_casualties']+=before-target.strength
    if unit.commander and unit.commander.upgrades:commanders.upgrades.on_volley(battle,unit,target,before-target.strength)


def melee_effectiveness(unit,rules):
    if unit.state==MoraleState.ROUTING: return rules.routing_melee_factor
    if unit.state==MoraleState.RALLYING:
        recovery=max(0.,min(1.,min((unit.morale-28)/20,unit.cohesion/45)))
        return rules.rallying_melee_factor+(rules.rallying_melee_max-rules.rallying_melee_factor)*recovery
    if unit.state==MoraleState.WAVERING: return rules.wavering_melee_factor
    if unit.state==MoraleState.SHAKEN: return rules.shaken_melee_factor
    return 1.


def melee(battle, a, b):
    from . import cavalry,infantry_charge
    if cavalry.contact(battle,a,b): return
    for attacker,target in ((a,b),(b,a)):
        if attacker.stats.kind==UnitType.INFANTRY:infantry_charge.impact(battle,attacker,target)
    key = (min(a.id, b.id), max(a.id, b.id))
    a.combat_state = b.combat_state = 'melee'
    a.target_id,b.target_id=b.id,a.id
    if battle.tick < battle.melee_next.get(key, 0): return
    battle.melee_next[key] = battle.tick + max(1,round(battle.rules.melee_interval / battle.rules.dt))
    for attacker, target in [(a, b), (b, a)]:
        if not attacker.active or not target.active: continue
        # Impact already accounts for this cavalry's outgoing first-contact hit.
        # The organized defender may resist; later intervals use ordinary melee.
        if attacker.charge_impact_tick==battle.tick: continue
        flank_angle = abs(angle_delta(target.facing, angle_to(target.pos, attacker.pos)))
        flank = 1. if flank_angle < math.pi / 3 else (1.6 if flank_angle < 2.3 else 2.2)
        terrain_factor,forest_power,shock_multiplier=forest_melee_factors(battle,attacker)
        if not battle.terrain.empty:
            height_gain=battle.terrain.get_elevation(target.pos.x,target.pos.y)-battle.terrain.get_elevation(attacker.pos.x,attacker.pos.y)
            grade=height_gain/max(10.,(target.pos-attacker.pos).length())
            terrain_factor/=1+max(0.,grade)*battle.rules.terrain.uphill_melee_penalty
        power = attacker.strength * .013 * (.3 + attacker.cohesion / 100) * flank * terrain_factor * attacker.archetype.melee * forest_power
        if attacker.formation.value=='skirmish': power*=.65
        if attacker.stats.kind == UnitType.ARTILLERY: power *= battle.rules.artillery_melee_factor
        if target.stats.kind == UnitType.ARTILLERY: power *= battle.rules.artillery_melee_vulnerability
        if attacker.stats.kind == UnitType.CAVALRY: power *= battle.rules.cavalry_melee_factor
        power*=commanders.frontal_pursuit_penalty(attacker,target)
        state_factor=melee_effectiveness(attacker,battle.rules)
        power *= state_factor
        shock = flank * terrain_factor * state_factor * shock_multiplier
        if attacker.stats.kind == UnitType.ARTILLERY: shock*=battle.rules.artillery_melee_factor
        rolled=power*battle.rng.uniform(.65,1.35)
        # Weak/broken attackers retain occasional resistance without a kill floor.
        if attacker.stats.kind==UnitType.ARTILLERY or not attacker.effective:
            losses = int(rolled)+int(battle.rng.random()<rolled-int(rolled))
        else:
            losses = max(1,int(rolled))
        losses=scale_casualties(battle,losses,attacker.archetype.melee_damage)
        damage(battle, target, losses, 'melee', attacker, shock)
