from dataclasses import dataclass, field
from enum import Enum
import math
from .geometry import Vec, corners
from .formations import Formation, PROFILES
from .orders import Order
from .unit_stats import UnitType, UnitStats, INFANTRY, CAVALRY, ARTILLERY
from .archetypes import ARCHETYPES, GENERIC_IDS
from .commanders import Commander

class MoraleState(str, Enum):
    STEADY = 'steady'
    SHAKEN = 'shaken'
    WAVERING = 'wavering'
    ROUTING = 'routing'
    RALLYING = 'rallying'

class CavalryState(str, Enum):
    APPROACH = 'approach'
    CHARGING = 'charging'
    MELEE = 'melee'
    PURSUIT = 'pursuit'
    RECOIL = 'recoil'
    REFORMING = 'reforming'

@dataclass
class Regiment:
    id: int
    name: str
    army: int
    pos: Vec
    facing: float = 0.
    stats: UnitStats = INFANTRY
    formation: Formation | None = None
    strength: int | None = None
    morale: float | None = None
    cohesion: float = 100.
    fatigue: float = 0.
    order: Order = field(default_factory=Order)
    state: MoraleState = MoraleState.STEADY
    combat_state: str = 'idle'
    target_id: int | None = None
    speed: float = 0.
    reload_left: float = 0.
    transition_left: float = 0.
    next_formation: Formation | None = None
    safe_time: float = 0.
    rout_heading: Vec | None = None
    rout_next_plan: float = 0.
    charge_cooldown: float = 0.
    withdrawn: bool = False
    ai_state: str = 'standing orders'
    player_attack: bool = False
    ai_position_until: float = 0.
    terrain_speed: float = 1.
    terrain_loss: float = 0.
    forest_cover: float = 0.
    ground_slope: float = 0.
    terrain_waypoint: Vec | None = None
    terrain_destination: Vec | None = None
    terrain_route_used: bool = False
    terrain_route_left: float = 0.
    last_seen_target_pos: Vec | None = None
    congestion: float = 0.
    congestion_speed: float = 1.
    congestion_loss: float = 0.  # current cohesion disruption, points per second
    avoidance_goal: Vec | None = None
    avoidance_destination: Vec | None = None
    avoidance_left: float = 0.
    avoidance_used: bool = False
    velocity: Vec | None = None
    pursuit_id: int | None = None
    player_order: bool = False
    rest_time: float = 0.
    stationary_overlap: float = 0.
    settling_goal: Vec | None = None
    settling_facing: float | None = None
    position_preference: Vec | None = None
    position_key: tuple | None = None
    settling_retry_at: float = 0.
    settling_started: float = 0.
    fire_lane_factor: float = 1.

    archetype_id: str | None = None
    skirmish_retreat: bool = False
    skirmish_until: float = 0.
    cavalry_commit_at: float = 0.
    cavalry_retreat_until: float = 0.
    cavalry_target_id: int | None = None
    cavalry_waypoint: Vec | None = None
    cavalry_state: CavalryState = CavalryState.APPROACH
    charge_sequence: int = 0
    charge_impacted_sequence: int = -1
    charge_impact_tick: int = -1
    charge_impact_target_id: int | None = None
    charge_ready: bool = True
    charge_clear_since: float | None = None
    charge_started: float = 0.
    charge_distance: float = 0.
    charge_momentum: float = 0.
    charge_last_momentum: float = 0.
    charge_contact_at: float = -1e9
    charge_melee_since: float = 0.
    charge_result: str = 'none'
    recoil_goal: Vec | None = None
    pursuit_speed_limit: float | None = None
    infantry_charging: bool = False
    infantry_charge_target_id: int | None = None
    limbered: bool = False
    limber_left: float = 0.
    setup_left: float = 0.
    trait_next: dict[str, float] = field(default_factory=dict)
    last_attacker: int | None = None
    analysis: dict[str, float] = field(default_factory=lambda: dict(volleys=0,casualties_inflicted=0,
        morale_shock=0,charges=0,routs_caused=0,moving_seconds=0,firing_seconds=0,melee_seconds=0,
        trait_activations=0,cohesion_lost=0,cohesion_recovered=0,forest_seconds=0,volley_casualties=0,
        firing_distance_total=0,charge_successes=0,rout_events=0,rallies=0,
        charge_initiations=0,impact_casualties=0,impact_momentum=0,impact_morale_shock=0,failed_charges=0,aborted_charges=0,
        pursuit_seconds=0,pursuit_casualties=0,pursuit_losses=0,artillery_shots=0))
    commander: Commander | None = None
    upgrade_state: dict = field(default_factory=dict)
    upgrade_stationary: float = 0.
    commander_decision_until: float = 0.
    commander_reform_until: float = 0.
    commander_next_reform: float = 0.
    commander_retreat_until: float = 0.
    commander_retreat_goal: Vec | None = None
    commander_next_retreat: float = 0.
    commander_target_id: int | None = None
    commander_avoid_target: int | None = None
    commander_avoid_until: float = 0.
    commander_melee_since: float | None = None
    commander_pursuit_origin: Vec | None = None
    commander_pursuit_target: int | None = None

    @property
    def archetype(self): return ARCHETYPES[self.archetype_id or GENERIC_IDS[self.stats.kind]]

    def __post_init__(self):
        if self.archetype_id is not None: self.stats = self.archetype.stats
        if self.formation is None: self.formation = self.archetype.default_formation
        if self.morale is None: self.morale = self.archetype.initial_morale
        if self.strength is None: self.strength = self.stats.strength
        if self.commander is not None:
            self.commander.validate(self.stats.kind)
            if self.commander.upgrades:
                from .upgrades import validate_assignment
                validate_assignment(self)
    @property
    def width(self): return PROFILES[self.formation][0] if self.stats.kind == UnitType.INFANTRY else (40 if self.stats.kind == UnitType.CAVALRY else 28)
    @property
    def depth(self): return PROFILES[self.formation][1] if self.stats.kind == UnitType.INFANTRY else 18
    @property
    def footprint(self): return corners(self.pos, self.facing, self.width, self.depth)
    @property
    def active(self): return self.strength > 0 and not self.withdrawn
    @property
    def available_guns(self):
        """Surviving crew fraction, rounded up to retain a last operational gun."""
        if self.stats.kind!=UnitType.ARTILLERY or not self.active:return 0
        return min(self.archetype.guns,math.ceil(self.archetype.guns*self.strength/max(1,self.stats.strength)))
    @property
    def effective(self): return self.active and self.state not in (MoraleState.ROUTING, MoraleState.RALLYING)
