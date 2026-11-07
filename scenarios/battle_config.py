"""Immutable, JSON-serializable battle recipes. No viewer/Pygame dependency."""
from collections import Counter
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
import secrets
import random
from simulation.battle import Battle
from simulation.config import Rules
from simulation.terrain import TerrainMap, TERRAIN_PRESETS, generate_terrain
from simulation.formations import Formation, PROFILES
from simulation.archetypes import ARCHETYPES, GENERIC_IDS
from simulation.geometry import Vec, separation
from simulation.orders import Order, OrderKind
from simulation.regiment import Regiment, UnitType, INFANTRY, CAVALRY, ARTILLERY
from simulation.commanders import Commander,generate as generate_commander

STATS = {UnitType.INFANTRY: INFANTRY, UnitType.CAVALRY: CAVALRY, UnitType.ARTILLERY: ARTILLERY}
SIZES = {'Small': (600., 400.), 'Medium': (1000., 600.), 'Large': (1600., 1000.),
         'Huge': (2400., 1500.), 'Epic': (3200., 2000.), 'Vast': (4800., 3000.)}

class ConfigError(ValueError):
    """Actionable configuration/deployment error suitable for a UI message."""


def initial_order(config,army,archetype,pos):
    if army==0 and army not in config.ai_armies:return Order(OrderKind.HOLD)
    composition=config.blue if army==0 else config.red
    kind=archetype.stats.kind
    order=Order(OrderKind.HOLD if composition.category_total(UnitType.INFANTRY) else OrderKind.ADVANCE,Vec(config.width/2,pos.y)) if kind==UnitType.ARTILLERY else Order(OrderKind.ATTACK if kind==UnitType.CAVALRY else OrderKind.ADVANCE,Vec(config.width/2,pos.y))
    return Order(OrderKind.SKIRMISH,Vec(config.width/2,pos.y)) if archetype.role in ('skirmisher','rifles') else order

@dataclass(frozen=True)
class ArmyConfig:
    infantry: int = 4
    cavalry: int = 1
    artillery: int = 1
    specialists: tuple[tuple[str,int], ...] = ()

    def __post_init__(self):
        # Canonical ordering makes JSON round trips and symmetry comparisons exact.
        # Malformed values are left for validate() to report as ConfigError.
        if isinstance(self.specialists,tuple) and all(isinstance(p,tuple) and len(p)==2 and isinstance(p[0],str) for p in self.specialists):
            object.__setattr__(self,'specialists',tuple(sorted(self.specialists,key=lambda p:p[0])))

    def count(self, archetype_id):
        if archetype_id in GENERIC_IDS.values(): return getattr(self,archetype_id)
        return dict(self.specialists).get(archetype_id,0)

    def with_count(self, archetype_id, count):
        if archetype_id in GENERIC_IDS.values(): return replace(self,**{archetype_id:count})
        counts=dict(self.specialists); counts[archetype_id]=count
        return replace(self,specialists=tuple(sorted((key,n) for key,n in counts.items() if n)))

    def roster(self): return tuple((a.id,self.count(a.id)) for a in ARCHETYPES.values() if self.count(a.id))
    def category_total(self,kind): return sum(n for key,n in self.roster() if ARCHETYPES[key].stats.kind==kind)

    @property
    def total(self): return self.infantry + self.cavalry + self.artillery + sum(n for _,n in self.specialists)

@dataclass(frozen=True)
class Placement:
    id: int
    army: int
    kind: UnitType
    pos: Vec
    facing: float
    formation: Formation = Formation.LINE
    order: Order = Order()
    archetype_id: str | None = None
    commander: Commander | None = None
    strength: int | None = None
    name: str | None = None

    @property
    def archetype(self): return ARCHETYPES[self.archetype_id or GENERIC_IDS[self.kind]]

    def regiment(self) -> Regiment:
        side = 'Continental' if self.army == 0 else 'Albion'
        return Regiment(self.id, self.name or f'{side} {self.archetype.name} {self.id + 1}', self.army,
                        self.pos, self.facing, STATS[self.kind], self.formation, order=self.order,archetype_id=self.archetype_id,commander=self.commander,strength=self.strength)

@dataclass(frozen=True)
class Zone:
    left: float
    top: float
    right: float
    bottom: float

    def contains(self, unit) -> bool:
        return all(self.left - 1e-7 <= p.x <= self.right + 1e-7 and
                   self.top - 1e-7 <= p.y <= self.bottom + 1e-7 for p in unit.footprint)

@dataclass(frozen=True)
class BattleConfig:
    name: str = 'Custom battle'
    width: float = 1000.
    height: float = 600.
    blue: ArmyConfig = ArmyConfig()
    red: ArmyConfig = ArmyConfig()
    seed: int | None = None
    symmetric: bool = True
    max_per_type: int = 12
    max_total: int = 48
    placements: tuple[Placement, ...] = ()
    ai_armies: tuple[int, ...] = (1,)
    version: int = 1
    terrain_preset: str = 'Open Field'
    terrain_seed: int | None = None
    terrain: TerrainMap | None = None
    ai_strategies: tuple[str,str] = ('balanced','balanced')
    commander_seed: int | None = None
    commander_roll: int = 0

    def resolved_terrain(self):
        if self.terrain is not None: return self.terrain
        seed=self.terrain_seed if self.terrain_seed is not None else (self.seed or 0) if self.terrain_preset!='Open Field' else 0
        return generate_terrain(self.terrain_preset,self.width,self.height,seed)

    def zone(self, army: int) -> Zone:
        return Zone(20 if army == 0 else self.width * .68, 20,
                    self.width * .32 if army == 0 else self.width - 20, self.height - 20)

    def with_army(self, army: int, composition: ArmyConfig):
        if army == 0:
            if composition == self.blue: return self
            return replace(self, blue=composition, red=composition if self.symmetric else self.red, placements=())
        if self.symmetric: raise ConfigError('Disable symmetric armies before editing red.')
        return replace(self, red=composition, placements=())

    def with_ai_armies(self,armies):
        config=replace(self,ai_armies=tuple(armies))
        if (0 in self.ai_armies)!=(0 in config.ai_armies):
            config=replace(config,placements=tuple(replace(p,order=initial_order(config,p.army,p.archetype,p.pos)) if p.army==0 else p for p in config.placements))
        return config

    def validate(self, require_deployment=False) -> None:
        from simulation.ai import STRATEGIES
        if not isinstance(self.ai_strategies,tuple) or len(self.ai_strategies)!=2 or any(s not in STRATEGIES for s in self.ai_strategies): raise ConfigError('Choose a valid AI strategy for each army.')
        if type(self.version) is not int or self.version != 1: raise ConfigError('Unsupported configuration version.')
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 100: raise ConfigError('Name must contain 1–100 characters.')
        for label, value, lower, upper in [('Width', self.width, 300, 5000), ('Height', self.height, 240, 3000)]:
            if type(value) not in (int,float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ConfigError(f'{label} must be between {lower} and {upper} metres.')
        for label, value, upper in [('max_per_type', self.max_per_type, 64), ('max_total', self.max_total, 256)]:
            if type(value) is not int or not 1 <= value <= upper: raise ConfigError(f'{label} must be an integer from 1 to {upper}.')
        if not isinstance(self.terrain_preset,str) or (self.terrain_preset not in TERRAIN_PRESETS and self.terrain is None):
            raise ConfigError('Unknown terrain preset.')
        if self.terrain_seed is not None and (type(self.terrain_seed) is not int or not -(2**63)<=self.terrain_seed<2**63):
            raise ConfigError('Terrain seed must be a signed 64-bit integer.')
        if self.terrain is not None:
            if not isinstance(self.terrain,TerrainMap) or (self.terrain.width,self.terrain.height)!=(self.width,self.height):
                raise ConfigError('Terrain dimensions must match the battlefield.')
            try: self.terrain.validate()
            except ValueError as exc: raise ConfigError(str(exc)) from exc
        if type(self.symmetric) is not bool: raise ConfigError('symmetric must be true or false.')
        if self.seed is not None and (type(self.seed) is not int or not -(2**63) <= self.seed < 2**63):
            raise ConfigError('Seed must be an integer in the signed 64-bit range, or null.')
        if self.commander_seed is not None and (type(self.commander_seed) is not int or not -(2**63)<=self.commander_seed<2**63):
            raise ConfigError('Commander seed must be a signed 64-bit integer or null.')
        if type(self.commander_roll) is not int or not 0<=self.commander_roll<2**63:raise ConfigError('Invalid commander reroll counter.')
        if not isinstance(self.ai_armies,tuple) or any(type(a) is not int or a not in (0,1) for a in self.ai_armies) or len(set(self.ai_armies)) != len(self.ai_armies):
            raise ConfigError('ai_armies must contain unique army IDs 0 and/or 1.')
        for label, army in [('Blue',self.blue),('Red',self.red)]:
            if not isinstance(army,ArmyConfig): raise ConfigError(f'{label} needs an ArmyConfig.')
            for kind in UnitType:
                count = getattr(army, kind.value)
                if type(count) is not int or not 0 <= count <= self.max_per_type:
                    raise ConfigError(f'{label} {kind.value}: count must be 0–{self.max_per_type}.')
            if not isinstance(army.specialists,tuple): raise ConfigError('Specialist counts must be immutable pairs.')
            seen=set()
            for item in army.specialists:
                if not isinstance(item,tuple) or len(item)!=2: raise ConfigError('Invalid specialist count pair.')
                key,count=item
                if not isinstance(key,str) or key not in ARCHETYPES or key in GENERIC_IDS.values() or key in seen:
                    raise ConfigError('Unknown, duplicate or generic specialist ID.')
                seen.add(key)
                if type(count) is not int or not 0<=count<=self.max_per_type: raise ConfigError(f'{key}: count must be 0–{self.max_per_type}.')
            if army.total < 1: raise ConfigError(f'{label} army needs at least one regiment.')
        if self.symmetric and self.blue != self.red: raise ConfigError('Symmetric armies must have matching counts.')
        if self.blue.total + self.red.total > self.max_total: raise ConfigError(f'Total regiment limit is {self.max_total}.')
        if not isinstance(self.placements,tuple) or not all(isinstance(p,Placement) for p in self.placements):
            raise ConfigError('placements must be a tuple of Placement values.')
        if not self.placements:
            if require_deployment: raise ConfigError('Generate deployment before starting.')
            return
        for p in self.placements:
            if not isinstance(p.kind,UnitType) or not isinstance(p.pos,Vec) or not isinstance(p.order,Order):
                raise ConfigError('Invalid placement type, position or order.')
        expected = Counter({(a,key): n for a,composition in enumerate((self.blue,self.red)) for key,n in composition.roster()})
        for p in self.placements:
            if p.archetype_id is not None and (not isinstance(p.archetype_id,str) or p.archetype_id not in ARCHETYPES): raise ConfigError('Unknown regiment archetype.')
        actual = Counter((p.army,p.archetype.id) for p in self.placements)
        if actual != +expected: raise ConfigError('Deployment does not match army compositions.')
        ids = [p.id for p in self.placements]
        if any(type(i) is not int or i < 0 for i in ids) or len(set(ids)) != len(ids): raise ConfigError('Regiment IDs must be unique nonnegative integers.')
        units = []
        officer_ids=set()
        by_id = {p.id:p for p in self.placements}
        for p in self.placements:
            if type(p.army) is not int or p.army not in (0,1): raise ConfigError('Invalid army ID.')
            if not isinstance(p.kind,UnitType) or not isinstance(p.formation,Formation): raise ConfigError('Unknown unit type or formation.')
            if p.archetype.stats.kind!=p.kind: raise ConfigError('Archetype category does not match placement.')
            if p.strength is not None and (type(p.strength) is not int or not 1<=p.strength<=p.archetype.stats.strength):raise ConfigError('Starting strength must be positive and no greater than maximum strength.')
            if p.name is not None and (not isinstance(p.name,str) or not p.name.strip() or len(p.name)>100 or not p.name.isprintable()):raise ConfigError('Invalid regiment name.')
            if p.commander is not None:
                if not isinstance(p.commander,Commander):raise ConfigError('Invalid commander data.')
                try:p.commander.validate(p.kind)
                except ValueError as exc:raise ConfigError(f'Regiment {p.id}: {exc}') from exc
                if p.commander.id in officer_ids:raise ConfigError('Commander IDs must be unique within the battle.')
                officer_ids.add(p.commander.id)
            if p.formation not in p.archetype.formations: raise ConfigError('Formation not supported by this archetype.')
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (p.pos.x,p.pos.y,p.facing)): raise ConfigError('Deployment coordinates and facing must be finite numbers.')
            if not isinstance(p.order.kind,OrderKind): raise ConfigError('Unknown order.')
            if p.order.kind==OrderKind.SKIRMISH and p.kind!=UnitType.INFANTRY: raise ConfigError('Skirmish orders need infantry.')
            if p.order.kind==OrderKind.CHARGE and p.kind==UnitType.ARTILLERY: raise ConfigError('Artillery cannot receive charge orders.')
            if p.order.facing is not None:
                if type(p.order.facing) not in (int,float) or not math.isfinite(p.order.facing):
                    raise ConfigError('Order facing must be a finite angle in radians.')
                if p.order.kind not in (OrderKind.MOVE,OrderKind.ADVANCE):
                    raise ConfigError('Only move/advance orders support arrival facing.')
                if p.order.destination is None: raise ConfigError('Arrival facing needs a destination.')
            dest = p.order.destination
            if dest is not None and (not all(type(v) in (int,float) and math.isfinite(v) for v in (dest.x,dest.y)) or not (0 <= dest.x <= self.width and 0 <= dest.y <= self.height)):
                raise ConfigError('Order destination must be inside the battlefield.')
            if p.order.kind in (OrderKind.MOVE,OrderKind.DEFEND) and dest is None: raise ConfigError('Move/defend orders need a destination.')
            if p.order.target_id is not None:
                if type(p.order.target_id) is not int: raise ConfigError('Target ID must be an integer.')
                target = by_id.get(p.order.target_id)
                if target is None or target.army == p.army: raise ConfigError('Attack target must identify an enemy regiment.')
            unit = p.regiment()
            if not self.zone(p.army).contains(unit): raise ConfigError(f'Regiment {p.id}: footprint must stay inside its deployment zone.')
            if any(separation(unit, other) is not None for other in units): raise ConfigError(f'Regiment {p.id}: starting formations overlap.')
            units.append(unit)

    def prepared(self):
        self.validate()
        config = replace(self, seed=secrets.randbits(63)) if self.seed is None else self
        if config.terrain is None and config.terrain_preset!='Open Field':
            terrain=config.resolved_terrain()
            config=replace(config,terrain=terrain,terrain_seed=terrain.seed)
        if config.terrain is not None and config.terrain_seed is None:
            label=config.terrain_preset
            if label=='Open Field' and not config.terrain.empty:
                label=config.terrain.preset if config.terrain.preset!='Open Field' else 'Custom'
            config=replace(config,terrain_seed=config.terrain.seed,terrain_preset=label)
        if not config.placements: config = replace(config, placements=automatic_deployment(config))
        if config.commander_seed is None:config=replace(config,commander_seed=config.seed)
        if any(p.commander is None for p in config.placements):
            rng=random.Random(f'commanders:{config.commander_seed}');names={};ids=set()
            for p in config.placements:
                if p.commander:
                    names.setdefault(p.army,set()).add(p.commander.name);ids.add(p.commander.id)
            placements=[]
            for p in sorted(config.placements,key=lambda p:p.id):
                officer=p.commander or generate_commander(rng,p.kind,p.archetype.faction,names.setdefault(p.army,set()),ids)
                placements.append(replace(p,commander=officer))
            config=replace(config,placements=tuple(placements))
        config.validate(require_deployment=True)
        return config

    def create_battle(self, spectator=False) -> Battle:
        config = (self.with_ai_armies((0,1)) if spectator else self).prepared()
        return Battle([p.regiment() for p in config.placements], config.seed,
                      ai_armies=(0,1) if spectator else config.ai_armies,
                      rules=Rules(width=config.width,height=config.height),terrain=config.resolved_terrain(),ai_strategies=config.ai_strategies)

    def new_seed(self):
        seed = secrets.randbits(63)
        if seed == self.seed: seed = (seed + 1) % (2**63)
        base=self.prepared() if self.placements and self.commander_seed is None else self
        return replace(base,seed=seed)

    def reroll_commander(self,uid,background=None):
        config=self.prepared()
        p=next((p for p in config.placements if p.id==uid),None)
        if p is None:raise ConfigError('Unknown regiment.')
        rng=random.Random(f'commander-reroll:{config.commander_seed}:{config.commander_roll}:{uid}')
        names={q.commander.name for q in config.placements if q.army==p.army and q.id!=uid}
        ids={q.commander.id for q in config.placements}
        officer=generate_commander(rng,p.kind,background or p.commander.background,names,ids)
        result=replace(config,commander_roll=config.commander_roll+1,
                       placements=tuple(replace(q,commander=officer) if q.id==uid else q for q in config.placements))
        result.validate(True);return result

    def to_dict(self):
        def counts(a): return dict(infantry=a.infantry,cavalry=a.cavalry,artillery=a.artillery,specialists=dict(a.specialists))
        def point(p): return None if p is None else [p.x,p.y]
        return dict(version=self.version,name=self.name,width=self.width,height=self.height,
                    blue=counts(self.blue),red=counts(self.red),seed=self.seed,symmetric=self.symmetric,
                    max_per_type=self.max_per_type,max_total=self.max_total,ai_armies=list(self.ai_armies),ai_strategies=list(self.ai_strategies),
                    terrain_preset=self.terrain_preset,terrain_seed=self.terrain_seed,terrain=None if self.terrain is None else self.terrain.to_dict(),
                    commander_seed=self.commander_seed,commander_roll=self.commander_roll,
                    placements=[dict(id=p.id,army=p.army,kind=p.kind.value,position=point(p.pos),facing=p.facing,
                                     formation=p.formation.value,archetype_id=p.archetype_id,commander=None if p.commander is None else p.commander.to_dict(),strength=p.strength,name=p.name,order=dict(kind=p.order.kind.value,destination=point(p.order.destination),target_id=p.order.target_id,facing=p.order.facing)) for p in self.placements])

    def save(self, path):
        self.validate()
        Path(path).write_text(json.dumps(self.to_dict(),indent=2,allow_nan=False)+'\n',encoding='utf-8')

    @classmethod
    def from_dict(cls, data):
        try:
            if not isinstance(data,dict): raise ConfigError('Configuration must be a JSON object.')
            data = dict(data)
            if data.get('version') != 1: raise ConfigError('Unsupported or missing configuration version.')
            for side in ('blue','red'):
                army=dict(data[side]); army['specialists']=tuple(sorted(army.get('specialists',{}).items()))
                data[side]=ArmyConfig(**army)
            placements = []
            for item in data.get('placements',[]):
                order = item['order']
                destination = order.get('destination')
                placements.append(Placement(item['id'],item['army'],UnitType(item['kind']),Vec(*item['position']),item['facing'],Formation(item['formation']),
                                            Order(OrderKind(order['kind']),None if destination is None else Vec(*destination),order.get('target_id'),order.get('facing')),item.get('archetype_id'),
                                            Commander.from_dict(item['commander']) if item.get('commander') is not None else None,item.get('strength'),item.get('name')))
            data['placements'] = tuple(placements)
            data['ai_armies'] = tuple(data.get('ai_armies',[1]))
            data['ai_strategies']=tuple(data.get('ai_strategies',['balanced','balanced']))
            if data.get('terrain') is not None: data['terrain']=TerrainMap.from_dict(data['terrain'])
            config = cls(**data)
            config.validate()
            return config
        except (TypeError,KeyError,ValueError,AttributeError,OverflowError) as exc:
            raise ConfigError(f'Invalid battle configuration: {exc}') from exc

    @classmethod
    def load(cls,path):
        try:
            path = Path(path)
            if path.stat().st_size > 1_000_000: raise ConfigError('Configuration exceeds 1 MB.')
            return cls.from_dict(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,UnicodeError,json.JSONDecodeError,RecursionError) as exc:
            raise ConfigError(f'Cannot load configuration: {exc}') from exc


def automatic_deployment(config: BattleConfig) -> tuple[Placement,...]:
    """Bounded grid packing: centre infantry, flank cavalry, rear batteries."""
    config.validate()
    placements = []
    terrain=config.resolved_terrain()
    for army,composition in enumerate((config.blue,config.red)):
        zone = config.zone(army)
        ys = []
        margin=max([32.]+[PROFILES[ARCHETYPES[key].default_formation][0]/2 for key,n in composition.roster() if ARCHETYPES[key].stats.kind==UnitType.INFANTRY])
        y = zone.top + margin
        while y <= zone.bottom - margin:
            ys.append(y); y += 90
        xs = []
        x = zone.right - 18 if army == 0 else zone.left + 18
        while zone.left + 18 <= x <= zone.right - 18:
            xs.append(x); x += -56 if army == 0 else 56
        cells = [(depth,row) for depth in range(len(xs)) for row in range(len(ys))]
        if composition.total > len(cells):
            raise ConfigError(f'{"Blue" if army == 0 else "Red"} army cannot fit: {composition.total} regiments, {len(cells)} deployment slots. Reduce counts or choose a larger field.')
        infantry_rows = set()
        roster=sorted(composition.roster(),key=lambda item:(list(UnitType).index(ARCHETYPES[item[0]].stats.kind), ARCHETYPES[item[0]].role in ("skirmisher","rifles")))
        for archetype_id,count in roster:
            archetype=ARCHETYPES[archetype_id]
            kind=archetype.stats.kind
            for _ in range(count):
                if archetype.role in ("skirmisher","rifles"):
                    key = lambda c: (c[0],-abs(ys[c[1]]-config.height/2),c[1])
                elif kind == UnitType.INFANTRY:
                    key = lambda c: (c[0],abs(ys[c[1]]-config.height/2),c[1])
                elif kind == UnitType.CAVALRY:
                    key = lambda c: (c[0],-abs(ys[c[1]]-config.height/2),c[1])
                else:
                    key = lambda c: (abs(c[0] - (1 if composition.category_total(UnitType.INFANTRY) else 0)), c[1] in infantry_rows, abs(ys[c[1]]-config.height/2), c[1])
                if kind == UnitType.ARTILLERY and not terrain.empty:
                    def terrain_key(cell):
                        point=Vec(xs[cell[0]],ys[cell[1]])
                        penalty=terrain.forest_density(point.x,point.y)*5+terrain.slope(point.x,point.y)*8
                        return (penalty,key(cell))
                    depth,row=min(cells,key=terrain_key)
                else:
                    depth,row = min(cells,key=key)
                cells.remove((depth,row))
                if kind == UnitType.INFANTRY: infantry_rows.add(row)
                pos = Vec(xs[depth],ys[row])
                order=initial_order(config,army,archetype,pos)
                placements.append(Placement(len(placements),army,kind,pos,0. if army == 0 else math.pi,
                    archetype.default_formation,order, None if archetype_id in GENERIC_IDS.values() else archetype_id))
    return tuple(placements)


class DeploymentSession:
    """Transactional deployment edits: invalid candidates never alter the recipe."""
    def __init__(self,config: BattleConfig):
        self.config = config.prepared()
        try:
            generated = replace(self.config,placements=()).prepared()
        except ConfigError:
            # A valid imported layout can be denser than the conservative grid.
            self.automatic = self.config
            return
        # Loaded files may use arbitrary stable IDs, not the generator's IDs.
        remapped = []
        for army in (0,1):
            for archetype_id in ARCHETYPES:
                original = sorted((p for p in self.config.placements if p.army==army and p.archetype.id==archetype_id),key=lambda p:p.id)
                defaults = [p for p in generated.placements if p.army==army and p.archetype.id==archetype_id]
                remapped.extend(replace(auto,id=old.id,commander=old.commander,strength=old.strength,name=old.name) for old,auto in zip(original,defaults))
        self.automatic = replace(self.config,placements=tuple(sorted(remapped,key=lambda p:p.id)))

    def candidate(self,uid,**changes):
        if not any(p.id == uid for p in self.config.placements): raise ConfigError('Unknown regiment.')
        return replace(self.config,placements=tuple(replace(p,**changes) if p.id == uid else p for p in self.config.placements))

    def edit(self,uid,**changes):
        candidate = self.candidate(uid,**changes)
        candidate.validate(require_deployment=True)
        self.config = candidate

    def reset(self,uid):
        auto = next(p for p in self.automatic.placements if p.id == uid)
        self.edit(uid,pos=auto.pos,facing=auto.facing,formation=auto.formation,order=auto.order)
