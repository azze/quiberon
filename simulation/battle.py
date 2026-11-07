"""Authoritative fixed-step state. No dependency on the graphical viewer."""
from collections import deque, OrderedDict
from dataclasses import dataclass
import random
from .config import Rules
from .terrain import TerrainMap
from .geometry import Vec, separation, touching, angle_delta
from .orders import Command, OrderKind
from .regiment import Regiment, UnitType
from . import movement, combat, morale, projectiles, ai, positioning, cavalry, infantry_charge
from .archetypes import formation_time, Trait
from .spatial import candidate_pairs, SpatialIndex
from . import commanders

@dataclass(frozen=True)
class Event:
    time: float
    kind: str
    message: str
    unit_id: int | None = None

@dataclass(frozen=True)
class Effect:
    kind: str
    pos: Vec
    expires: float
    facing: float = 0.
    width: float = 0.
    started: float = 0.

class Battle:
    def __init__(self, units: list[Regiment], seed=1, ai_armies=(), rules=None, sandbox=False, terrain=None, ai_strategies=('balanced','balanced'),generate_commanders=True):
        if len({u.id for u in units}) != len(units): raise ValueError('Duplicate regiment IDs')
        self.units = sorted(units, key=lambda u: u.id)
        officer_rng=random.Random(f'commanders:{seed}')
        used_ids=set();used_names={}
        for u in self.units:
            if u.commander is not None:
                u.commander.validate(u.stats.kind)
                if u.commander.id in used_ids:raise ValueError('Duplicate commander IDs')
                used_ids.add(u.commander.id);used_names.setdefault(u.army,set()).add(u.commander.name)
        if generate_commanders:
            for u in self.units:
                if u.commander is None:
                    u.commander=commanders.generate(officer_rng,u.stats.kind,u.archetype.faction,used_names.setdefault(u.army,set()),used_ids)
        for unit in self.units:
            target=self.unit(unit.order.target_id)
            if target and target.army!=unit.army and unit.last_seen_target_pos is None:
                unit.last_seen_target_pos=target.pos
        self.rng = random.Random(seed)
        self.seed = seed
        self.rules = rules or Rules()
        self.terrain = terrain or TerrainMap(self.rules.width,self.rules.height)
        self.terrain.validate()
        if (self.terrain.width,self.terrain.height)!=(self.rules.width,self.rules.height): raise ValueError('Terrain and battlefield dimensions must match.')
        self._visibility_cache = OrderedDict()
        self._visibility_sources = None
        self._firing_group_signature = None
        self._firing_groups = {}
        self.observer = None  # Optional read-only recording sink; no RNG or rule effects.
        self.tick = 0
        self.ai_armies = set(ai_armies)
        if len(ai_strategies)!=2 or any(s not in ai.STRATEGIES for s in ai_strategies): raise ValueError('Invalid AI strategies')
        self.ai_strategies=tuple(ai_strategies)
        self.deployment_positions={u.id:u.pos for u in units}
        self.sandbox = sandbox
        self.projectiles = []
        self.effects = []
        self.events = deque(maxlen=250)
        self.melee_next = {}
        self.pursuit_next = {}
        self.upgrade_next = {}
        self._fire_index = None
        self.metrics = dict(routs=0, rallies=0, cascade_shocks=0, friendly_fire=0)
        self.result = None
        self.defeat_since = {}
        self.commands = []
        self.command_history = []
        self.initial_strength = {a: sum(u.strength for u in units if u.army == a) for a in sorted({u.army for u in units})}
        self.initial_unit_strength = {u.id:u.strength for u in units}
    @property
    def time(self): return self.tick * self.rules.dt
    def unit(self, uid): return next((u for u in self.units if u.id == uid), None)
    def log(self, kind, message, unit_id=None):
        event=Event(self.time,kind,message,unit_id)
        self.events.append(event)
        if self.observer is not None:self.observer.event(event)
    def effect(self, kind, pos, duration, facing=0., width=0., unit_id=None):
        effect=Effect(kind,pos,self.time+duration,facing,width,self.time)
        self.effects.append(effect)
        if self.observer is not None:self.observer.effect(effect,unit_id)
    def activate(self, unit, message):
        """Rate-limited trait signals, with no RNG or simulation feedback."""
        if self.time < unit.trait_next.get(message,0.): return
        unit.trait_next[message]=self.time+10.
        unit.analysis['trait_activations']+=1
        self.log('trait',f'{unit.name}: {message}',unit.id)
    def issue(self, command: Command): self.commands.append(command)
    def visibility(self, observer, target):
        sources=self._visibility_sources
        if sources is None or sources[0] is not self.terrain or sources[1] is not self.rules.terrain:
            self._visibility_cache.clear()
            self._visibility_sources=(self.terrain,self.rules.terrain)
        # Exact pose and observer/target opacity context. Context is part of the
        # key so trait changes cannot reuse another regiment's woodland sight.
        opacity=1.
        if self.terrain.forests:
            if target.archetype.concealment!=1:
                cover=self.terrain.forest_density(target.pos.x,target.pos.y)
                opacity*=1+(target.archetype.concealment-1)*cover
            if observer.archetype.forest_vision!=1:
                cover=self.terrain.forest_density(observer.pos.x,observer.pos.y)
                opacity*=1-(1-observer.archetype.forest_vision)*cover
        key=(observer.pos,target.pos,opacity)
        sight=self._visibility_cache.get(key)
        if sight is None:
            sight=self.terrain.visibility(observer.pos,target.pos,self.rules.terrain,opacity)
            self._visibility_cache[key]=sight
            if len(self._visibility_cache)>32768: self._visibility_cache.popitem(last=False)
        else: self._visibility_cache.move_to_end(key)
        return sight

    def perceives(self, observer, target):
        if self.terrain.empty: return True
        if self.visibility(observer,target).visible: return True
        if observer.stats.kind == UnitType.ARTILLERY:
            return any(friend.effective and friend.army==observer.army and self.visibility(friend,target).visible for friend in self.units)
        return False

    def step(self):
        if self.result is not None: return
        dt = self.rules.dt
        ai.army_plan(self)
        for cmd in self.commands:
            u = self.unit(cmd.regiment_id)
            if not u or not u.effective: continue
            if cmd.order:
                if cmd.order.kind==OrderKind.SKIRMISH and u.stats.kind!=UnitType.INFANTRY: continue
                if cmd.order.kind==OrderKind.CHARGE and u.stats.kind==UnitType.ARTILLERY: continue
                u.order = cmd.order
                if u.stats.kind==UnitType.CAVALRY: cavalry.cancel(u,self)
                if u.stats.kind==UnitType.INFANTRY: infantry_charge.cancel(u)
                u.player_order=True
                u.commander_retreat_until=u.commander_reform_until=0.
                u.commander_retreat_goal=None;u.commander_pursuit_origin=None;u.commander_pursuit_target=None
                u.commander_avoid_target=None;u.commander_avoid_until=0.
                positioning.reset(u)
                u.player_attack = cmd.order.kind in (OrderKind.ATTACK,OrderKind.CHARGE) and cmd.order.target_id is not None
                u.ai_state = 'player attack order' if u.player_attack else f'player order: {cmd.order.kind.value}'
                if u.player_attack:
                    target=self.unit(cmd.order.target_id)
                    u.last_seen_target_pos=target.pos if target else None
                movement.reset_avoidance(u)
                u.skirmish_retreat=False
                u.skirmish_until=0.
            if cmd.formation and cmd.formation in u.archetype.formations and cmd.formation != u.formation and not u.transition_left and u.stats.kind == UnitType.INFANTRY:
                u.next_formation = cmd.formation
                u.transition_left = formation_time(u,self.rules.formation_seconds)
                u.cohesion = max(0, u.cohesion - 6)
                self.log('formation', f'{u.name} changing to {cmd.formation.value}', u.id)
                if u.transition_left<self.rules.formation_seconds:
                    if u.archetype.trait==Trait.DRILL:self.activate(u,'Prussian Drill: rapid formation change')
                    if commanders.has(u,commanders.S.DRILLMASTER) and commanders.drill_strength(u)>0:
                        self.activate(u,f'{u.commander.display_name}: Drillmaster formation change')
            self.command_history.append((self.tick, cmd))
        self.commands.clear()
        active = [u for u in self.units if u.active]
        cohesion_before={u.id:u.cohesion for u in active}
        # Determine intent and congestion from one shared pre-movement snapshot.
        intents = {u.id: ai.destination(self, u) for u in active}
        for u in active:
            if u.stats.kind==UnitType.CAVALRY: intents[u.id]=cavalry.intent(self,u,intents[u.id])
            elif u.stats.kind==UnitType.INFANTRY and (u.order.kind==OrderKind.CHARGE or u.infantry_charging or not u.charge_ready):
                intents[u.id]=infantry_charge.intent(self,u,intents[u.id])
        positioning.pursuit_lanes(self,active,intents)
        overlaps=movement.update_congestion(active, self.rules)
        positioning.settle(self,active,intents,overlaps)
        destinations = {u.id: movement.avoid_friends(u, intents[u.id], active, self.rules, intents) for u in active}
        for u in active:
            if u.combat_state=='melee':
                if u.commander_melee_since is None:u.commander_melee_since=self.time
            else:u.commander_melee_since=None
            u.combat_state = 'idle'
            u.reload_left = max(0., u.reload_left - dt)
            u.charge_cooldown = max(0., u.charge_cooldown - dt)
            destination=movement.terrain_steer(self,u,destinations[u.id])
            arrival_facing = u.order.facing if (u.effective and u.order.kind in (OrderKind.MOVE,OrderKind.ADVANCE)
                                             and destination in (u.order.destination,u.settling_goal)) else None
            if u.settling_facing is not None and destination==u.settling_goal: arrival_facing=u.settling_facing
            was_deploying=u.limbered or u.setup_left>0
            before=u.pos
            options=cavalry.motion(self,u) if u.stats.kind==UnitType.CAVALRY else {}
            if u.infantry_charging:options=infantry_charge.motion(self,u)
            movement.move(u, destination, dt, self.rules.width, self.rules.height, self.terrain, self.rules.terrain, arrival_facing,**options)
            if u.stats.kind==UnitType.CAVALRY: cavalry.after_move(self,u,before)
            elif u.infantry_charging:infantry_charge.after_move(self,u,before)
            if u.settling_goal is not None and u.settling_facing is not None and (u.pos-u.settling_goal).length()<1 and abs(angle_delta(u.facing,u.settling_facing))<.001:
                u.settling_facing=None
            if was_deploying and not u.limbered and u.setup_left==0 and u.archetype.trait==Trait.RAPID:
                self.activate(u,'Rapid Redeployment: battery ready after setup')
            if u.commander and u.commander.upgrades:
                from .upgrades import update_stationary
                update_stationary(u,dt)
            if u.speed>.1: u.analysis['moving_seconds']+=dt
            if u.forest_cover>.1: u.analysis['forest_seconds']+=dt
            if u.speed>.1 and u.forest_cover>.2 and u.archetype.trait==Trait.WOODLAND:
                self.activate(u,'Woodland Warfare: moving through cover')
        movement.update_congestion(active, self.rules, dt)
        if not self.sandbox:
            for a, b in candidate_pairs(active, padding=1.5):
                if a.active and b.active and a.army != b.army and touching(a,b):
                    if a.combat_state != 'melee' and a.cavalry_state.value!='pursuit' and b.cavalry_state.value!='pursuit':
                        self.log('engage', f'{a.name} in contact with {b.name}', a.id) if (min(a.id,b.id),max(a.id,b.id)) not in self.melee_next else None
                    combat.melee(self, a, b)
            cavalry.pursuits(self,active)
            self._fire_index=SpatialIndex(active) if len(active)>=12 else None
            try:
                for u in active:
                    if not u.effective or u.stats.kind == UnitType.CAVALRY or u.combat_state=='melee': continue
                    if u.stats.kind==UnitType.INFANTRY and u.order.kind==OrderKind.CHARGE: continue
                    target = combat.select_fire_target(self,u)
                    if target:
                        u.target_id = target.id
                        combat.fire(self, u, target)
            finally: self._fire_index=None
            for u in active:
                if u.combat_state in ('firing','melee'): u.analysis[u.combat_state+'_seconds']+=dt
            projectiles.update(self)
            morale.update(self)
        else:
            for u in active: morale.recover_cohesion(u, self.rules, dt)
        movement.separate(active, self.rules.width, self.rules.height)
        for u in active:
            u.analysis['cohesion_lost']+=max(0.,cohesion_before[u.id]-u.cohesion)
            u.analysis['cohesion_recovered']+=max(0.,u.cohesion-cohesion_before[u.id])
        self.effects = [e for e in self.effects if e.expires > self.time]
        self.tick += 1
        if not self.sandbox: self.check_victory()
    def check_victory(self):
        defeated = []
        for army, initial in self.initial_strength.items():
            effective = sum(u.strength for u in self.units if u.army == army and u.effective)
            if effective < initial * .18:
                self.defeat_since.setdefault(army, self.time)
                if self.time - self.defeat_since[army] >= 12: defeated.append(army)
            else: self.defeat_since.pop(army, None)
        if defeated:
            survivors = [a for a in self.initial_strength if a not in defeated]
            self.result = f'army_{survivors[0]}' if len(survivors) == 1 else 'draw'
            self.log('result', f'Battle ended: {self.result}; opposing fighting strength collapsed')
