extends RefCounted
## Live adapter implements the replay clock's frame-pair contract, without files.
## Native Godot collections are copied into presentation DTOs only at tick changes.
const Frame=preload("res://scripts/battle_frame.gd")
class LiveMetadata extends RefCounted:
    var title: String="C# Movement Sandbox"
    var seed_text: String="17"
    var terrain: Frame.TerrainData
    var armies: Dictionary={0:Color("#508bd5"),1:Color("#d85950")}
    var times: Array=[0.,INF]
    var frame_cache: Dictionary={}
    var error: String=""
var source: LiveMetadata
var backend: Object
var time: float=0
var speed: float=1
var playing: bool=true
var current: Frame
var following: Frame
var alpha: float=0
var events: Array=[]
var tick: int=0
var backlog: float=0
var tick_ms: float=0
var error: String=""
var infos: Dictionary={}
var formations: Dictionary={}
var count: int=8
var with_terrain: bool=false
var preferred_crossing: String=""
var cached_tick: int=-1
var scenario: String="movement"
var combat_enabled: bool=false
var ai_enabled: bool=false
var result: String=""
var dynamics: bool=true
var morale_enabled: bool=false
var cavalry_enabled: bool=false
var choices: Array=[]
var rules: Dictionary={}
var completion_rule: String=""
var seed: int=17
func attach(unit_count: int=8, terrain: bool=false, march: bool=false, scenario_id: String="movement",enable_dynamics: bool=true,battle_seed: int=17,custom_json: String="") -> bool:
    if not ClassDB.class_exists("CSharpScript"):
        error="Live mode needs Godot 4.7.2 .NET. Launch with: bash tools/godot.sh";return false
    var assembly: String="res://.godot/mono/temp/bin/Debug/Quiberon.dll"
    if not FileAccess.file_exists(assembly):
        error="Build C# first: bash tools/dotnet.sh build godot/Quiberon.csproj";return false
    var script: Script=load("res://scripts/simulation_adapter/LiveSimulationBridge.cs")
    if script==null or not script.can_instantiate():error="C# bridge unavailable; build godot/Quiberon.csproj.";return false
    backend=script.new();count=unit_count;with_terrain=terrain;scenario=scenario_id;dynamics=enable_dynamics;seed=battle_seed
    if scenario=="campaign":
        if not backend.InitializeCampaign():error="No prepared campaign encounter.";return false
    elif scenario=="custom":
        if not backend.InitializeCustom(custom_json):error=backend.SetupError;return false
    elif scenario=="movement":backend.InitializeScenario(count,with_terrain,seed)
    elif not backend.InitializeCombatScenario(scenario,seed,dynamics):error="Unknown combat scenario: "+scenario;return false
    synchronize()
    if march and not combat_enabled:backend.StartBenchmarkMarch()
    return true
func synchronize() -> void:
    seed=backend.GetSeed()
    ai_enabled=backend.IsAiEnabled();playing=not ai_enabled
    combat_enabled=backend.IsCombatEnabled();result="";events.clear()
    morale_enabled=backend.IsMoraleEnabled();cavalry_enabled=backend.IsCavalryEnabled();rules=backend.GetRuleInfo();choices=backend.GetScenarioChoices()
    source=LiveMetadata.new();source.title="C# · "+backend.GetScenarioName()
    source.seed_text=str(seed)
    var data: Dictionary=backend.GetTerrainDefinition()
    source.terrain=Frame.TerrainData.new();source.terrain.size=data.size;source.terrain.hills=data.hills;source.terrain.forests=data.forests;source.terrain.environment=data.get("environment",{});source.terrain.canonical_grid=data.get("canonical_grid",{})
    infos.clear();formations.clear()
    for row in backend.GetRegimentDefinitions():
        var info:=Frame.RegimentInfo.new()
        info.id=row.id;info.army=row.army;info.name=row.name;info.archetype=row.archetype;info.category=row.category
        info.commander=row.commander;info.maximum=row.maximum;info.symbol=row.symbol;info.faction=row.faction;info.guns=row.guns;info.accent=Color.WHITE
        info.charge_max_speed=row.charge_max_speed
        infos[info.id]=info;formations[info.id]=row.formations
    cached_tick=-1;refresh()
func frame(data: Dictionary) -> Frame:
    var result:=Frame.new();result.tick=data.tick;result.time=data.time;result.result=data.result
    for row in data.units:
        var u:=Frame.UnitState.new();u.info=infos[row.id];u.position=row.position;u.facing=row.facing
        u.width=row.width;u.depth=row.depth;u.formation=row.formation;u.strength=row.strength;u.morale=row.morale;u.cohesion=row.cohesion
        u.state=row.morale_state if morale_enabled else row.movement_state;u.combat_state=row.combat_state if combat_enabled else "movement only";u.withdrawn=row.withdrawn;u.active=u.strength>0 and not u.withdrawn;u.speed=row.speed;u.order=row.order
        u.charge_state=row.cavalry_state;u.fatigue=row.fatigue;u.transition_left=row.transition_left;u.next_formation=row.next_formation
        u.destination=row.destination;u.arrival_facing=row.arrival_facing;u.settling_goal=row.settling_goal
        u.congestion=row.congestion;u.congestion_speed=row.congestion_speed;u.terrain_speed=row.terrain_speed
        u.morale_simulated=morale_enabled;u.combat_enabled=combat_enabled;u.ranged_capable=row.combat_capable;u.combat_capable=row.get("attack_capable",u.ranged_capable or cavalry_enabled and u.info.category=="cavalry")
        u.target=row.target;u.reload_left=row.reload_left;u.weapon_range=row.weapon_range
        u.fire_lane=row.fire_lane;u.sight_state=row.sight_state;u.sight_transmission=row.sight_transmission
        u.forest_cover=row.forest_cover;u.slope=row.slope;u.last_volley_shots=row.last_volley_shots;u.last_volley_probability=row.last_volley_probability
        u.effective=row.effective;u.cavalry_simulated=row.cavalry_simulated;u.melee_capable=row.melee_capable;u.movement_state=row.movement_state
        u.safe_time=row.safe_time;u.state_reason=row.state_reason;u.cavalry_target=row.cavalry_target;u.pursuit=row.pursuit;u.momentum=row.momentum
        u.last_momentum=row.last_momentum;u.charge_cooldown=row.charge_cooldown;u.charge_ready=row.charge_ready;u.charge_result=row.charge_result;u.charge_distance=row.charge_distance
        u.transport=row.get("transport",false);u.observed=row.get("observed",true);u.environment_state=row.get("environment_state","");u.crossing=row.get("crossing","");u.road=row.get("road","");u.route_points=row.get("route_points",[])
        u.upgrades=row.get("upgrades",[]);u.upgrade_effects=row.get("upgrade_effects","");u.infantry_charging=row.get("infantry_charging",false)
        u.guns=row.guns;u.battery_state=row.battery_state;u.setup_left=row.setup_left;u.limber_left=row.limber_left;u.hold_fire=row.hold_fire;u.reload_seconds=row.reload_seconds;u.ability=row.ability;u.drill=row.drill;u.aimed=row.aimed
        u.ai_enabled=row.ai_enabled;u.personality=row.personality;u.specialization=row.specialization;u.specialization_name=row.get("specialization_name",row.specialization);u.commander_effects=row.commander_effects;u.autonomy=row.autonomy;u.order_owner=row.order_owner;u.intention=row.intention;u.next_decision=row.next_decision;u.army_plan=row.get("army_plan","");u.army_role=row.get("army_role","");u.mounted_intent=row.get("mounted_intent","");u.tactical_assignment=row.get("tactical_assignment","");u.friendly_support=row.get("friendly_support",0);u.enemy_support=row.get("enemy_support",0);u.position_reason=row.get("position_reason","");u.threat_ratio=row.threat_ratio;u.target_score=row.target_score
        if row.commander_name!="":u.info.commander=row.commander_name
        result.units[u.info.id]=u
    for row in data.get("projectiles",[]):
        var p:=Frame.ShotState.new();p.id=row.id;p.position=row.position;p.velocity=row.velocity;p.height=row.height;p.ground=source.terrain.elevation(p.position);p.energy=row.energy;p.bounces=row.bounces;result.shots[p.id]=p
    return result
func refresh() -> void:
    tick=backend.GetTick();alpha=backend.GetAlpha();backlog=backend.GetBacklogSeconds();tick_ms=backend.GetTickMilliseconds()
    if tick!=cached_tick:
        current=frame(backend.GetFrame(true));following=frame(backend.GetFrame(false));cached_tick=tick
        events.clear()
        for row in backend.GetRecentEvents():
            var e:=Frame.BattleEvent.new();e.sequence=row.sequence;e.time=row.time;e.tick=row.tick;e.kind=row.kind;e.message=row.message
            e.has_position=true;e.position=row.position;e.facing=row.facing;e.width=row.width;e.duration=row.duration
            e.unit_id=row.unit_id;e.target_id=row.target_id;e.losses=row.losses;events.append(e)
    result=backend.GetResult();completion_rule=backend.GetCompletionRule()
    if result!="":playing=false;current=following;alpha=0
    time=lerpf(current.time,following.time,alpha)
func advance(delta: float) -> bool:
    backend.Advance(maxf(0,delta),speed,playing);refresh();return true
func single_step() -> void:
    playing=false;backend.SingleStep();refresh()
    # Debug stepping displays the completed tick, including discrete orders and
    # formations, rather than leaving the inspector one interpolation tick back.
    current=following;alpha=0;time=current.time
func warm_start(ticks: int) -> void:
    backend.WarmStart(ticks);cached_tick=-1;refresh();current=following;alpha=0;time=current.time
func restart() -> bool:
    var was_playing: bool=playing or result!=""
    backend.ResetBattle();cached_tick=-1;refresh();playing=was_playing;return true
func issue_move(id: int, point: Vector2, facing: Variant=null) -> bool:
    return backend.IssueMoveVia(id,point,0.0 if facing==null else facing,facing!=null,preferred_crossing)
func issue_hold(id: int) -> bool:return backend.IssueHold(id)
func issue_advance(id: int) -> bool:return backend.IssueAdvance(id)
func issue_attack(id: int,target: int) -> bool:return backend.IssueAttack(id,target)
func issue_charge(id: int,target: int=-1) -> bool:return backend.IssueCavalryOrder(id,target,false)
func issue_pursue(id: int,target: int=-1) -> bool:return backend.IssueCavalryOrder(id,target,true)
func issue_disengage(id: int) -> bool:return backend.IssueRecoveryOrder(id,true)
func issue_reform(id: int) -> bool:return backend.IssueRecoveryOrder(id,false)
func issue_formation(id: int, formation: String) -> bool:return backend.IssueFormation(id,formation)

func issue_fire_control(id: int,hold: bool) -> bool:return backend.IssueFireControl(id,hold)
func issue_skirmish(id: int) -> bool:return backend.IssueSkirmish(id)

func configure_army(army: int,strategy: String) -> bool:
    var ok: bool=backend.ConfigureArmy(army,strategy);cached_tick=-1;refresh();return ok
func issue_autonomy(id: int,enabled: bool) -> bool:
    var ok: bool=backend.IssueAutonomy(id,enabled)
    if ok and backend.IsDeployment():cached_tick=-1;refresh()
    return ok
func edit_commander(id: int,personality: String="",specialization: String="") -> bool:
    var ok: bool=backend.RerollCommander(id) if personality=="" else backend.AssignCommander(id,personality,specialization)
    cached_tick=-1;refresh();return ok

func edit_deployment(id: int,point: Vector2,facing: float,formation: String) -> bool:
    var ok: bool=backend.EditDeployment(id,point,facing,formation)
    if ok:synchronize();playing=false
    return ok
func set_upgrades(id: int,keys: Array) -> bool:
    var ok: bool=backend.SetCommanderUpgrades(id,keys)
    cached_tick=-1;refresh();return ok
