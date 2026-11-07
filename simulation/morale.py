from .regiment import MoraleState as S
from .archetypes import Trait
from .orders import OrderKind
from . import commanders


def aura_source(unit):
    return unit.effective and unit.state==S.STEADY and unit.morale>60 and (unit.archetype.trait==Trait.PRESTIGE or commanders.has(unit,commanders.S.INSPIRER) or commanders.upgrades.has(unit,"rallying_presence"))


def aura_amount(source,rallying=False):
    base=(.35 if rallying else .22) if source.archetype.trait==Trait.PRESTIGE else (commanders.TUNING.inspirer_rally if rallying else commanders.TUNING.inspirer_morale)
    return max(base,(commanders.upgrades.TUNING.aura_rally if rallying else commanders.upgrades.TUNING.aura_morale) if commanders.upgrades.has(source,'rallying_presence') else 0.)


def prestige_support(battle,unit,anchors=None):
    anchors=anchors if anchors is not None else sorted((a for a in battle.units if aura_source(a)),key=lambda a:-aura_amount(a))
    return next((a for a in anchors if a.id!=unit.id and a.army==unit.army and aura_source(a) and
                 (a.pos-unit.pos).length()<125 and battle.visibility(unit,a).visible),None)


def update(battle):
    dt = battle.rules.dt
    newly_routed = []
    anchors=sorted((a for a in battle.units if aura_source(a)),key=lambda a:-aura_amount(a))
    for u in battle.units:
        if not u.active: continue
        enemies = [e for e in battle.units if e.active and e.army != u.army and (e.pos - u.pos).length() < battle.rules.threat_radius and battle.perceives(u,e)]
        friends = [f for f in battle.units if f.effective and f.army == u.army and f.id != u.id and (f.pos - u.pos).length() < 130]
        # Aura is applied before other morale changes. A full-morale regiment
        # cannot benefit here; avoid needless terrain rays (rout shocks below
        # still query support when it actually affects their result).
        anchor=prestige_support(battle,u,anchors) if u.morale<100 and u.state!=S.ROUTING else None
        if anchor and u.state!=S.ROUTING:
            before=u.morale
            u.morale=min(100.,u.morale+dt*min(.45,aura_amount(anchor,u.state==S.RALLYING)))
            if u.morale>before:
                message='Royal Prestige: steady support within 125 m' if anchor.archetype.trait==Trait.PRESTIGE else f'{anchor.commander.display_name}: inspiring support within 125 m'
                battle.activate(anchor,message)
        if u.state == S.ROUTING:
            u.safe_time = 0 if enemies else u.safe_time + dt
            if u.safe_time >= battle.rules.rally_safe_seconds and u.strength > u.stats.strength * .15:
                u.state = S.RALLYING
                u.morale = max(28, u.morale)
                u.safe_time = 0
                battle.metrics['rallies'] += 1
                u.analysis['rallies']+=1
                battle.log('rally', f'{u.name} is rallying away from danger', u.id)
        elif u.state == S.RALLYING:
            if enemies:
                u.state = S.ROUTING
                u.safe_time = 0
                u.rout_heading=None;u.rout_next_plan=0.
                # A broken formation abandons an unfinished drill manoeuvre.
                u.transition_left=0.;u.next_formation=None
            else:
                u.morale = min(60., u.morale + dt * .9*u.archetype.recovery)
                if u.congestion_loss < 1e-6 and u.terrain_loss < 1e-6: u.cohesion = min(100., u.cohesion + dt * 1.2)
                if u.morale >= 48 and u.cohesion >= 45:
                    u.state = S.SHAKEN
                    battle.log('rally', f'{u.name} returned to duty', u.id)
        else:
            if u.morale <= battle.rules.rout_threshold:
                u.state = S.ROUTING
                u.safe_time = 0
                newly_routed.append(u)
                u.rout_heading=None;u.rout_next_plan=0.
                u.transition_left=0.;u.next_formation=None
                battle.metrics['routs'] += 1
                u.analysis['rout_events']+=1
                attacker=battle.unit(u.last_attacker)
                if attacker is not None: attacker.analysis['routs_caused']+=1
                commanders.upgrades.on_rout(battle,u,attacker)
                battle.log('rout', f'{u.name} broke: morale {u.morale:.0f}, cohesion {u.cohesion:.0f}', u.id)
            elif u.morale < 40: u.state = S.WAVERING
            elif u.morale < 60 and u.state == S.STEADY: u.state = S.SHAKEN
            elif u.morale > 66: u.state = S.STEADY
            elif u.morale > 46 and u.state == S.WAVERING: u.state = S.SHAKEN
            if enemies:
                hostile = sum(e.strength for e in enemies if e.effective)
                support = u.strength + sum(f.strength for f in friends)
                if hostile > support * 1.6:
                    pressure=1.
                    if u.order.kind==OrderKind.SKIRMISH and u.formation.value=='skirmish' and u.combat_state!='melee' and u.forest_cover>0:
                        distance=min((e.pos-u.pos).length() for e in enemies if e.effective)
                        safe=max(0.,min(1.,(distance-battle.rules.skirmish_panic_distance)/
                                       (battle.rules.skirmish_safe_distance-battle.rules.skirmish_panic_distance)))
                        pressure-=battle.rules.skirmish_cover_composure*u.forest_cover*safe
                    if (u.archetype.trait==Trait.WOODLAND and u.forest_cover>0 and
                        not any(e.effective and e.stats.kind.value=='cavalry' and (e.pos-u.pos).length()<100 for e in enemies)):
                        pressure=min(pressure,1-battle.rules.terrain.woodland_composure*battle.rules.terrain.woodland_skill(u.forest_cover))
                    u.morale -= dt * .35*max(.1,pressure)
            else:
                u.morale += dt * (.35 + .08 * len(friends)) * u.stats.discipline*u.archetype.recovery
                u.fatigue = max(0., u.fatigue - dt * .1)
        recover_cohesion(u, battle.rules, dt)
        if commanders.personality(u,commanders.P.STALWART) and commanders.defending(u) and u.state in (S.SHAKEN,S.WAVERING):
            u.morale=min(66.,u.morale+dt*.04)
            battle.activate(u,f'{u.commander.display_name}: steadying the defensive position')
        u.morale = max(0., min(100., u.morale))
        u.cohesion = max(0., min(100., u.cohesion))
    # Each transition emits one shock. Resulting routs happen next tick, never recursively.
    for source in newly_routed:
        for u in battle.units:
            distance = (u.pos - source.pos).length()
            if u.id == source.id or not u.effective or distance >= battle.rules.rout_radius: continue
            if not battle.visibility(u,source).visible: continue
            if u.army == source.army:
                factor=u.archetype.shock_resistance*commanders.shock_factor(u)
                supporter=prestige_support(battle,u,anchors)
                if supporter:factor*=.8 if commanders.upgrades.has(supporter,'rallying_presence') else .85 if supporter.archetype.trait==Trait.PRESTIGE else .9
                shock = battle.rules.rout_shock * (1 - distance / battle.rules.rout_radius) / u.stats.discipline*max(.6,factor)
                u.morale = max(0., u.morale - shock)
                battle.metrics['cascade_shocks'] += 1
                battle.log('morale', f'{u.name}: -{shock:.0f} morale as {source.name} routed nearby', u.id)
            else: u.morale = min(100., u.morale + 3)


def recover_cohesion(unit, rules, dt):
    """Shared recovery for battles and drill sandbox; no recovery during active friendly crossings."""
    if unit.state==S.ROUTING:
        unit.cohesion=max(0.,unit.cohesion-rules.routing_cohesion_loss*dt)
        return
    if unit.combat_state == 'idle' and unit.congestion_loss < 1e-6 and unit.terrain_loss < 1e-6:
        rate = rules.cohesion_rest_recovery if unit.speed < .1 else rules.cohesion_move_recovery
        unit.cohesion = min(100., unit.cohesion + dt * rate*min(1.8 if commanders.upgrades.has(unit,"swift_reform") else 1.5,unit.archetype.recovery*commanders.recovery_factor(unit)))
