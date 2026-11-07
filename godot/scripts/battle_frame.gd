class_name BattleFrame
extends RefCounted
## Presentation DTOs. No JSON, file access, scene nodes or battle rules here.

class RegimentInfo extends RefCounted:
    var id: int
    var army: int
    var name: String
    var archetype: String
    var category: String
    var commander: String
    var symbol: String
    var maximum: int
    var accent: Color
    var guns: int = 0
    var faction: String = ""
    var charge_max_speed: float = 0
    var weapon_range: float = 0

class UnitState extends RefCounted:
    var transport: bool=false
    var info: RegimentInfo
    var position: Vector2
    var facing: float
    var width: float
    var depth: float
    var formation: String
    var strength: int
    var morale: float
    var cohesion: float
    var state: String
    var combat_state: String
    var active: bool
    var withdrawn: bool
    var speed: float
    var order: String
    var target: int = -1
    var charge_state: String
    var momentum: float
    var pursuit: int = -1
    # Optional live-movement inspection fields; old recordings retain defaults.
    var observed: bool = true
    var environment_state: String=""
    var crossing: String=""
    var road: String=""
    var route_points: Array=[]
    var fatigue: float = 0
    var transition_left: float = 0
    var next_formation: String = ""
    var destination: Variant = null
    var arrival_facing: Variant = null
    var settling_goal: Variant = null
    var congestion: float = 0
    var congestion_speed: float = 1
    var terrain_speed: float = 1
    # Optional live-combat fields; old replay files retain their original UI.
    var morale_simulated: bool = true
    var combat_enabled: bool = false
    var combat_capable: bool = false
    var weapon_range: float = 0
    var reload_left: float = 0
    var fire_lane: float = 1
    var sight_state: String = "none"
    var sight_transmission: float = 1
    var forest_cover: float = 0
    var slope: float = 0
    var last_volley_shots: int = 0
    var last_volley_probability: float = 0
    var ranged_capable: bool = false
    var melee_capable: bool = false
    var effective: bool = true
    var cavalry_simulated: bool = false
    var movement_state: String = ""
    var safe_time: float = 0
    var state_reason: String = ""
    var cavalry_target: int = -1
    var last_momentum: float = 0
    var charge_cooldown: float = 0
    var charge_ready: bool = false
    var charge_result: String = "none"
    var ai_enabled: bool=false
    var personality: String=""
    var specialization: String=""
    var specialization_name: String=""
    var commander_effects: String=""
    var autonomy: String="ordered"
    var order_owner: String=""
    var intention: String=""
    var next_decision: float=0
    var threat_ratio: float=0
    var target_score: float=0
    var upgrades: Array=[]
    var upgrade_effects: String=""
    var infantry_charging: bool=false
    var charge_distance: float = 0
    var guns: int = 0
    var battery_state: String = "not ported"
    var setup_left: float = 0
    var limber_left: float = 0
    var hold_fire: bool = false
    var reload_seconds: float = 0
    var ability: String = ""
    var drill: float = 0
    var aimed: float = 1

class ShotState extends RefCounted:
    var id: int
    var position: Vector2
    var velocity: Vector2
    var height: float
    var ground: float
    var bounces: int
    var energy: float

class BattleEvent extends RefCounted:
    var sequence: int
    var time: float
    var kind: String
    var message: String
    var has_position: bool = false
    var position: Vector2
    var facing: float = 0.0
    var width: float = 0.0
    var duration: float = 3.0
    var unit_id: int = -1
    var target_id: int = -1
    var tick: int = -1
    var losses: int = 0

class TerrainData extends RefCounted:
    var size: Vector2
    var hills: Array = []
    var forests: Array = []
    var environment: Dictionary={}
    var canonical_grid: Dictionary={}

    func is_water(point: Vector2) -> bool:
        for piece in environment.get("water",[]):
            if Geometry2D.is_point_in_polygon(point,PackedVector2Array(piece.points)):return true
        return false
    func crossing_at(point: Vector2) -> Dictionary:
        for c in environment.get("crossings",[]):
            var d: Vector2=(point-c.position).rotated(-c.facing)
            if absf(d.x)<=c.length/2 and absf(d.y)<=c.width/2:return c
        return {}
    func grid_height(point: Vector2) -> float:
        var nx: int=canonical_grid.nx;var nz: int=canonical_grid.nz
        var cell: Vector2=(point/size*Vector2(nx,nz)).clamp(Vector2.ZERO,Vector2(nx,nz))
        var x:=mini(nx-1,int(floor(cell.x)));var z:=mini(nz-1,int(floor(cell.y)));var f:=cell-Vector2(x,z)
        var h: PackedFloat32Array=canonical_grid.heights
        var a:=h[z*(nx+1)+x];var b:=h[z*(nx+1)+x+1];var c:=h[(z+1)*(nx+1)+x];var d:=h[(z+1)*(nx+1)+x+1]
        return a+(b-a)*f.x+(c-a)*f.y if f.x+f.y<=1 else d+(c-d)*(1-f.x)+(b-d)*(1-f.y)
    func elevation(point: Vector2) -> float:
        if not canonical_grid.is_empty():return grid_height(point)
        var height := 0.0
        for h in hills:
            var delta: Vector2 = (point - h.center) / h.radius
            var squared: float = delta.length_squared()
            if h.compact:
                height += h.height * pow(maxf(0.0, 1.0 - squared / 9.0), 4)
            else:
                height += h.height * exp(-0.5 * squared)
        return height

    func forest_density(point: Vector2) -> float:
        var density := 0.0
        for f in forests:
            var delta: Vector2 = (point - f.center) / f.radius
            var t := clampf((1.0 - delta.length()) / 0.2, 0.0, 1.0)
            density = maxf(density, f.density * t * t * (3.0 - 2.0 * t))
        return density

var time: float = 0.0
var tick: int = 0
var result: String = ""
var units: Dictionary = {}
var shots: Dictionary = {}
