from dataclasses import dataclass, field
from .terrain import TerrainRules
from .formations import Formation, CongestionProfile, CONGESTION_PROFILES

@dataclass(frozen=True)
class Rules:
    terrain: TerrainRules = TerrainRules()
    dt: float = .1
    width: float = 1000.
    height: float = 600.
    formation_seconds: float = 7.
    firing_half_arc: float = .65
    musket_accuracy: float = .14
    infantry_volley_damage: float = 1.10
    casualty_morale: float = 95.
    rout_threshold: float = 23.
    routing_cohesion_loss: float = 1.  # cohesion points per simulated second
    rout_radius: float = 145.
    rout_shock: float = 15.
    rally_safe_seconds: float = 22.
    threat_radius: float = 160.
    rout_threat_radius: float = 240.
    rout_plan_seconds: float = 1.
    rout_lookahead: float = 60.
    rout_exit_margin: float = 2.
    gravity: float = 9.81
    projectile_lifetime: float = 14.
    artillery_scatter: float = 45.  # independent horizontal aim error, metres per axis
    artillery_vertical_scatter: float = 3.  # independent elevation error, m/s
    artillery_melee_factor: float = .10
    artillery_melee_vulnerability: float = 1.25
    melee_interval: float = 2.
    # Broken-state fractions apply to both melee damage and morale shock.
    routing_melee_factor: float = .10
    rallying_melee_factor: float = .25
    rallying_melee_max: float = .60
    shaken_melee_factor: float = .70
    wavering_melee_factor: float = .40
    charge_range: float = 100.
    charge_min_run: float = 12.
    charge_max_speed: float = 12.
    charge_acceleration: float = 2.
    charge_turn_multiplier: float = .5
    charge_min_cohesion: float = 50.
    charge_min_speed: float = 3.
    charge_max_forest: float = .45
    charge_max_slope: float = .25
    charge_max_seconds: float = 16.
    charge_cooldown_seconds: float = 20.
    charge_reform_seconds: float = 4.
    charge_clearance: float = 30.
    charge_damage: float = .20
    charge_shock: float = 24.
    charge_cohesion_damage: float = 18.
    charge_recoil_distance: float = 40.
    cavalry_melee_factor: float = .80
    pursuit_interval: float = 2.
    pursuit_contact_gap: float = 6.
    pursuit_min_cohesion: float = 25.
    pursuit_max_fatigue: float = 85.
    pursuit_damage: float = .12
    pursuit_max_fraction: float = .12
    pursuit_resistance: float = .03
    infantry_charge_range: float = 55.
    infantry_charge_speed: float = 1.20
    infantry_charge_acceleration: float = .8
    infantry_charge_min_cohesion: float = 35.
    infantry_charge_min_run: float = 4.
    infantry_charge_cooldown: float = 20.
    infantry_charge_clearance: float = 18.
    infantry_charge_reform: float = 3.
    infantry_charge_damage: float = .035
    infantry_charge_shock: float = 6.
    skirmish_cover_composure: float = .9
    skirmish_safe_distance: float = 55.
    skirmish_panic_distance: float = 25.

    congestion_profiles: dict[Formation, CongestionProfile] = field(default_factory=lambda: dict(CONGESTION_PROFILES))
    congestion_min_speed: float = .5
    congestion_stationary_loss: float = .35
    # Fractions of full crossing cost for compatible measured velocities.
    congestion_same_direction: float = .20
    congestion_cavalry_same_direction: float = .06
    congestion_shared_pursuit: float = .02
    congestion_overtaking: float = .35
    pursuit_lane_spacing: float = 16.
    # Only positioning orders settle; transient passages and attacks stay soft.
    settling_overlap: float = .25
    settling_delay: float = 2.
    settling_retry: float = 5.
    settling_timeout: float = 60.
    settling_radius: float = 110.
    settling_gap: float = 4.
    # Sparse screens attenuate rather than completely block musket frontage.
    friendly_loose_density: float = .35
    friendly_fire_clearance: float = .5
    cohesion_rest_recovery: float = .65
    cohesion_move_recovery: float = .1
    avoidance_enabled: bool = True
    avoidance_lookahead: float = 150.
    avoidance_margin: float = 6.
    avoidance_max_extra: float = 100.
    avoidance_max_ratio: float = 1.5
    avoidance_max_seconds: float = 120.
