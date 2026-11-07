"""Explicit bayonet charge: a modest rush, then ordinary regimental melee.

Uses the same charge sequence, impact counters and movement constraints as the
cavalry system, without its mounted pursuit or recoil mechanics.
"""
import math
from .geometry import Vec, angle_to, angle_delta
from .regiment import UnitType
from .formations import PROFILES
from .orders import OrderKind
from .cavalry import gap, clamp
from . import commanders


def cancel(unit):
    if unit.infantry_charging: unit.analysis['aborted_charges']+=1
    unit.infantry_charging=False;unit.infantry_charge_target_id=None
    unit.charge_momentum=0.;unit.charge_distance=0.


def intent(battle,unit,destination):
    r=battle.rules
    if not unit.charge_ready:
        previous=battle.unit(unit.charge_impact_target_id)
        clear=previous is None or not previous.active or gap(unit,previous)>=r.infantry_charge_clearance
        if clear and unit.combat_state!='melee':
            if unit.charge_clear_since is None:unit.charge_clear_since=battle.time
            if battle.time-unit.charge_clear_since>=r.infantry_charge_reform and unit.charge_cooldown<=0:unit.charge_ready=True
        else:unit.charge_clear_since=None
    target=battle.unit(unit.target_id)
    if (unit.order.kind!=OrderKind.CHARGE or not unit.effective or target is None or not target.active or
        unit.transition_left or unit.cohesion<r.infantry_charge_min_cohesion or unit.fatigue>=85):
        cancel(unit);return destination
    if unit.infantry_charge_target_id not in (None,target.id):cancel(unit)
    unit.infantry_charge_target_id=target.id
    if (not unit.infantry_charging and unit.charge_ready and unit.charge_cooldown<=0 and destination is not None and
        (target.pos-unit.pos).length()<=r.infantry_charge_range and gap(unit,target)>=r.infantry_charge_min_run and
        abs(angle_delta(unit.facing,angle_to(unit.pos,target.pos)))<.7):
        unit.infantry_charging=True;unit.charge_sequence+=1;unit.charge_started=battle.time;unit.charge_distance=0.
        unit.analysis['charge_initiations']+=1
        battle.log('charge_start',f'{unit.name}: bayonet charge against {target.name}',unit.id)
    if unit.infantry_charging and (battle.time-unit.charge_started>30 or abs(angle_delta(unit.facing,angle_to(unit.pos,target.pos)))>1.4):
        cancel(unit);unit.charge_cooldown=max(unit.charge_cooldown,3.)
    return destination


def motion(battle,unit):
    return dict(speed_cap=unit.stats.speed*PROFILES[unit.formation][2]*battle.rules.infantry_charge_speed,
                acceleration=battle.rules.infantry_charge_acceleration,turn_multiplier=.85)


def after_move(battle,unit,before):
    r=battle.rules;unit.charge_distance+=(unit.pos-before).length()
    target=battle.unit(unit.infantry_charge_target_id)
    if target is None:unit.charge_momentum=0.;return
    velocity=unit.velocity or Vec(0,0)
    maximum=unit.stats.speed*PROFILES[unit.formation][2]*r.infantry_charge_speed
    unit.charge_momentum=clamp(velocity.length()/maximum)*clamp(unit.charge_distance/r.infantry_charge_min_run)*unit.cohesion/100*clamp(velocity.normalized().dot((target.pos-unit.pos).normalized()))
    if unit.speed>.1:unit.fatigue=min(100.,unit.fatigue+battle.rules.dt*.06)


def impact(battle,unit,target):
    if (unit.stats.kind!=UnitType.INFANTRY or not unit.infantry_charging or not unit.effective or
        unit.charge_impacted_sequence==unit.charge_sequence):return
    from .combat import damage,melee_effectiveness,scale_casualties,forest_melee_factors
    r=battle.rules;momentum=unit.charge_momentum
    unit.infantry_charging=False;unit.charge_ready=False;unit.charge_clear_since=None
    unit.charge_impacted_sequence=unit.charge_sequence;unit.charge_impact_target_id=target.id;unit.charge_impact_tick=battle.tick
    unit.charge_contact_at=battle.time;unit.charge_cooldown=r.infantry_charge_cooldown
    unit.charge_last_momentum=momentum;unit.charge_momentum=0.
    angle=abs(angle_delta(target.facing,angle_to(target.pos,unit.pos)))
    flank=1. if angle<math.pi/3 else 1.3 if angle<2.3 else 1.6
    terrain,forest_power,shock_multiplier=forest_melee_factors(battle,unit)
    if not battle.terrain.empty:
        gain=battle.terrain.get_elevation(target.pos.x,target.pos.y)-battle.terrain.get_elevation(unit.pos.x,unit.pos.y)
        terrain/=1+max(0.,gain)/max(10.,(target.pos-unit.pos).length())*r.terrain.uphill_melee_penalty
    power=unit.strength*r.infantry_charge_damage*momentum*unit.archetype.melee*melee_effectiveness(unit,r)*flank*terrain*forest_power
    if unit.formation.value=='skirmish':power*=.65
    shock=r.infantry_charge_shock*momentum*flank*terrain*shock_multiplier
    commander_boost=commanders.charge_shock_factor(unit,target,momentum)
    shock*=commander_boost
    losses=scale_casualties(battle,int(power*battle.rng.uniform(.8,1.2)),unit.archetype.melee_damage)
    before=target.strength;damage(battle,target,losses,'bayonet charge',unit,shock)
    target.cohesion=max(0.,target.cohesion-4*momentum*terrain)
    unit.charge_result='bayonet impact';unit.analysis['charges']+=1
    unit.analysis['impact_casualties']+=before-target.strength;unit.analysis['impact_momentum']+=momentum
    unit.analysis['impact_morale_shock']+=shock*target.archetype.shock_resistance
    commanders.charge_aftermath(battle,unit,momentum,commander_boost)
    if before-target.strength>=target.stats.strength*.03:unit.analysis['charge_successes']+=1
    battle.effect('charge_impact',unit.pos,.8,unit.facing,unit.width)
    battle.log('charge',f'{unit.name}: bayonet impact on {target.name}, {before-target.strength} losses',unit.id)
