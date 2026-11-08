using Godot;
using Quiberon.Simulation;
using System;
using System.Linq;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using GArray = Godot.Collections.Array;
using GDictionary = Godot.Collections.Dictionary;

/// <summary>Godot-only adapter. The referenced Simulation assembly has no Godot dependency.</summary>
public partial class LiveSimulationBridge : RefCounted
{
    private bool campaignMode;
    private bool campaignCommitted;
    public bool IsCampaign()=>campaignMode;
    public bool InitializeCampaign()
    {
        if(CampaignBridge.Current?.State.Encounter is not { } encounter)return false;
        Initialize(encounter);campaignMode=true;custom=null;Deployment=true;return true;
    }
    public bool CompleteCampaign()
    {
        if(!campaignMode || battle.Result is null)return false;
        try{if(!campaignCommitted){CampaignBridge.Current!.Complete(battle);campaignCommitted=true;}if(!CampaignBridge.Laboratory)CampaignBridge.Current!.Save(ProjectSettings.GlobalizePath("user://commonwealth-campaign-v1.json"));return true;}catch(Exception e) when(e is ArgumentException or System.IO.IOException or UnauthorizedAccessException){SetupError=e.Message;return false;}
    }
    public string GetMissionJson()=>battle.Mission is null?"":JsonSerializer.Serialize(new{definitions=battle.Mission.Definition.Objectives,states=battle.Mission.Objectives,pending=(battle.Mission.Definition.Directives??[]).Where(d=>!battle.Mission.Arrived(d.UnitId)).Select(d=>d.UnitId),time=battle.Time,result=battle.Result},ScenarioJson.Options);
    private BattleSimulation battle = null!;
    private SimulationClock clock = null!;
    private GDictionary previous = new(), current = new();
    private ScenarioDefinition definition = null!;
    private int rerolls;
    private BattleConfiguration? custom;
    public string SetupError { get; private set; } = "";
    public bool Deployment { get; private set; }
    public bool InitializeCustom(string json)
    {
        try { var next=BattleConfiguration.Parse(json).Prepare();Initialize(next.Scenario());custom=next;Deployment=true;SetupError="";return true; }
        catch(Exception e) when(e is ArgumentException or InvalidDataException or JsonException){SetupError=e.Message;return false;}
    }
    public string ConfigurationWeather(string json,string type)
    {
        try{if(!Enum.TryParse<WeatherType>(type,true,out var weather))throw new ArgumentException("Unknown weather preset.");var c=BattleConfiguration.Parse(json).Prepare();var terrain=c.Terrain!;c=c with{Terrain=terrain with{Environment=(terrain.Environment??new()) with{Weather=new(weather)}}};c.Validate();SetupError="";return c.ToJson();}
        catch(ArgumentException e){SetupError=e.Message;return "";}
    }
    public string GetDefaultConfiguration()=>new BattleConfiguration().ToJson();
    public string NormalizeConfiguration(string json)
    {try{SetupError="";return BattleConfiguration.Parse(json).Prepare().ToJson();}catch(Exception e) when(e is ArgumentException or InvalidDataException or JsonException){SetupError=e.Message;return "";}}
    public GArray GetBattlePresets()=>new(typeof(BattleSimulation).Assembly.GetManifestResourceNames().Where(n=>n.StartsWith("battle_presets.",StringComparison.Ordinal)).Order().Select(n=>Variant.From(n["battle_presets.".Length..^5])).ToArray());
    public string GetBattlePreset(string id)
    {using var stream=typeof(BattleSimulation).Assembly.GetManifestResourceStream($"battle_presets.{id}.json");return stream is null?"":new StreamReader(stream).ReadToEnd();}
    public string GetConfiguration()=>custom?.ToJson()??new BattleConfiguration().ToJson();
    public GDictionary GetConfigurationSeeds(string json)
    {try{var c=BattleConfiguration.Parse(json);return new(){["battle"]=c.Seed.ToString(System.Globalization.CultureInfo.InvariantCulture),["commander"]=c.CommanderSeed.ToString(System.Globalization.CultureInfo.InvariantCulture),["terrain"]=c.TerrainSeed.ToString(System.Globalization.CultureInfo.InvariantCulture)};}catch(ArgumentException){return new(){["battle"]="17",["commander"]="1729",["terrain"]="17"};}}
    public bool IsDeployment()=>Deployment;
    public bool IsCustom()=>custom is not null;
    public bool StartDeployedBattle(){if(campaignMode && Deployment){CampaignBridge.Current!.Begin();Deployment=false;return true;}if(!Deployment || custom is null)return false;try{custom.Validate();Deployment=false;return true;}catch(ArgumentException e){SetupError=e.Message;return false;}}
    private Rect2 CampaignZone()=>definition.Mission?.PlayerZone=="east"?new(800,20,(float)battle.Rules.Width-820,(float)battle.Rules.Height-40):new(20,20,530,(float)battle.Rules.Height-40);
    public GArray GetDeploymentZones()=>campaignMode?new(){CampaignZone()}:new();
    private string CampaignPlacementError(int id,Vector2 position,double facing,string formation)
    {
        if(!Deployment || battle.Unit(id)is not {Army:0,Active:true} unit || id>=800 || !Enum.TryParse<Formation>(formation,true,out var f))return "Only your persistent active regiments can be deployed; scenario allies have fixed starting positions.";
        if(!float.IsFinite(position.X) || !float.IsFinite(position.Y) || !double.IsFinite(facing) || !unit.Archetype.Formations.Contains(f))return "Invalid formation or facing.";
        var candidate=new Regiment(id,0,unit.Name,unit.Archetype,new(position.X,position.Y),facing,f);var zone=CampaignZone();
        for(int i=0;i<4;i++){var point=candidate.Rect.Corner(i);if(!zone.HasPoint(new((float)point.X,(float)point.Y)))return "Whole formation must fit the blue deployment area.";}
        if(!battle.Terrain.Environment.Passable(candidate.Rect,unit.Archetype.Category) || battle.Units.Any(other=>other.Id!=id && other.Active && OrientedRect.Touching(candidate.Rect,other.Rect,3)))return "Formation overlaps water or another regiment.";
        return "";
    }
    public bool EditDeployment(int id,Vector2 position,double facing,string formation)
    {
        if(campaignMode){
            SetupError=CampaignPlacementError(id,position,facing,formation);if(SetupError!="")return false;
            var pos=new Vec2(position.X,position.Y);var shape=Enum.Parse<Formation>(formation,true);
            definition=definition with{Units=definition.Units.Select(d=>d.Id==id?d with{Position=pos,Facing=facing,Formation=shape}:d).ToArray()};Initialize(definition);return true;
        }
        if(!Deployment || custom is null || !Enum.TryParse<Formation>(formation,true,out var f))return false;
        try {var next=custom.EditPlacement(id,new(position.X,position.Y),facing,f);Initialize(next.Scenario());custom=next;SetupError="";return true;}
        catch(ArgumentException e){SetupError=e.Message;return false;}
    }
    public bool ResetDeployment()
    {if(campaignMode && Deployment){Initialize(CampaignBridge.Current!.State.Encounter!);return true;}if(!Deployment || custom is null)return false;try{var next=custom.ResetDeployment();Initialize(next.Scenario());custom=next;SetupError="";return true;}catch(ArgumentException e){SetupError=e.Message;return false;}}
    public bool LoadConfiguration(string path)
    {try{return InitializeCustom(BattleConfiguration.Load(path).ToJson());}catch(Exception e) when(e is IOException or UnauthorizedAccessException or ArgumentException){SetupError=e.Message;return false;}}
    public bool SaveConfiguration(string path)
    {if(custom is null)return false;try{custom.Save(path);SetupError="";return true;}catch(Exception e) when(e is IOException or UnauthorizedAccessException or ArgumentException){SetupError=e.Message;return false;}}
    public string GetBattleReportJson(){var node=JsonSerializer.SerializeToNode(BattleReport.Capture(battle),ScenarioJson.Options)!;node["seedText"]=battle.Seed.ToString(System.Globalization.CultureInfo.InvariantCulture);return node.ToJsonString(ScenarioJson.Options);}
    public bool Rematch(long seed)
    {if(campaignMode)return false;if(custom is not null)custom=custom with{Seed=seed};definition=definition with{Seed=seed};Deployment=false;Initialize(definition);return true;}
    public GArray GetArchetypes()
    {var result=new GArray();foreach(var a in Archetypes.All)result.Add(new GDictionary{["id"]=a.Id,["name"]=a.DisplayName,["category"]=Text(a.Category),["maximum"]=a.Strength,["faction"]=a.Faction,["role"]=a.Role,["campaign_core"]=a.CampaignCore,["speed"]=a.Speed,["range"]=a.Weapon?.Range??0,["reload"]=a.Weapon?.ReloadSeconds??0,["formations"]=new GArray(a.Formations.Select(f=>Variant.From(Text(f))).ToArray()),["ability"]=a.Ability});return result;}
    public GArray GetHistoricalCommanders(int id)
    {
        var result=new GArray();if(battle.Unit(id)is not { } u)return result;
        foreach(var d in HistoricalCommanders.All.Where(d=>!d.ArmyLevel && d.Categories.Contains(Text(u.Archetype.Category))))result.Add(new GDictionary{
            ["id"]=d.Id,["name"]=d.Name,["faction"]=d.Faction,["personality"]=d.Personality,["specialization"]=d.SpecializationName,
            ["description"]=d.Description,["role"]=d.CampaignRole,["alternative_names"]=string.Join(", ",d.AlternativeNames),
            ["assigned"]=battle.Units.Any(v=>v.Id!=id && v.Commander.DefinitionId==d.Id) || battle.ArmyCommanders.Any(a=>a.CommanderId==d.Id)});
        return result;
    }
    public string GetCommanderRosterKey()=>string.Join("|",battle.Units.Select(u=>u.Commander.Id+":"+u.Commander.DefinitionId))+string.Join("|",battle.ArmyCommanders.Select(a=>a.Army+":"+a.CommanderId));
    public string GetHistoricalDefinition(int id)=>battle.Unit(id)?.Commander.DefinitionId??"";
    public GArray GetArmyCommanders()=>new(HistoricalCommanders.All.Where(d=>d.ArmyLevel).Select(d=>Variant.From(new GDictionary{["id"]=d.Id,["name"]=d.Name,["description"]=d.Description})).ToArray());
    public string GetArmyCommander(int army)=>battle.ArmyCommanders.FirstOrDefault(a=>a.Army==army)?.CommanderId??"";
    public bool AssignHistoricalCommander(int id,string definitionId)
    {
        try{if(campaignMode || !battle.AssignCommander(id,HistoricalCommanders.Get(definitionId).Create())){SetupError="Historical officer is already assigned, incompatible, or setup has ended.";return false;}SaveOfficers();SetupError="";return true;}
        catch(ArgumentException e){SetupError=e.Message;return false;}
    }
    public bool AssignArmyCommander(int army,string definitionId)
    {
        if(campaignMode || battle.Tick!=0 || !battle.Rules.CommandersEnabled)return false;
        try{
            var leaders=battle.ArmyCommanders.Where(a=>a.Army!=army).ToList();
            if(definitionId!="")leaders.Add(new(army,definitionId));
            battle.SetArmyCommanders(leaders);definition=definition with{ArmyCommanders=battle.ArmyCommanders.ToArray()};
            if(custom is not null)custom=custom with{ArmyCommanders=definition.ArmyCommanders};
            if(battle.Ai.Armies.TryGetValue(army,out var strategy))battle.Ai.ConfigureArmy(army,definitionId!="" && HistoricalCommanders.Get(definitionId).Specialization=="speed_and_shock" && strategy=="balanced"?"all_out_attack":strategy);
            definition=definition with{AiStrategies=new(battle.Ai.Armies)};if(custom is not null)custom=custom with{AiStrategies=[definition.AiStrategies.GetValueOrDefault(0,"balanced"),definition.AiStrategies.GetValueOrDefault(1,"balanced")]};
            SaveOfficers();SetupError="";return true;
        }catch(ArgumentException e){SetupError=e.Message;return false;}
    }
    public GArray GetUpgrades(int id)
    {var result=new GArray();if(battle.Unit(id)is not { } u)return result;foreach(var d in UpgradeSystem.Definitions.Where(d=>UpgradeSystem.Eligible(u.Archetype,d.Id)))result.Add(new GDictionary{["id"]=d.Id,["name"]=d.Name,["description"]=d.Description,["selected"]=u.Commander.Upgrades?.Contains(d.Id)==true});return result;}
    public bool SetCommanderUpgrades(int id,GArray upgrades)
    {
        if(campaignMode || battle.Tick!=0 || battle.Unit(id)is not { } u)return false;
        try{if(!battle.AssignCommander(id,u.Commander with{Upgrades=upgrades.Select(v=>v.AsString()).ToArray()}))return false;SaveOfficers();SetupError="";return true;}
        catch(ArgumentException e){SetupError=e.Message;return false;}
    }
    public bool InitializeCombatScenario(string id, long seed, bool dynamics=true)
    {
        custom=null;Deployment=false;
        try { Initialize(CombatScenarios.Get(id) with { Seed = seed,MoraleEnabled=dynamics,CavalryEnabled=dynamics,ArtilleryEnabled=dynamics,SpecialistsEnabled=dynamics });return true; }
        catch(ArgumentException){return false;}
    }
    public void InitializeScenario(int count, bool withTerrain, long seed)
    { custom=null;Deployment=false;Initialize(ScenarioDefinition.Sandbox(count, withTerrain) with { Seed = seed }); }
    private void Initialize(ScenarioDefinition scenario)
    { definition=scenario; battle=definition.Create();if(battle.Rules.CommandersEnabled)definition=definition with { Units=definition.Units.Select(d=>d with {Commander=battle.Unit(d.Id)!.Commander}).ToArray() };clock=new(battle,definition.IssueScheduled);RefreshFrames(); }
    public bool IsAiEnabled()=>battle.Rules.AiEnabled;
    public void ResetBattle(){if(!campaignMode)Initialize(definition);}
    public bool ConfigureArmy(int army,string strategy)
    {if(campaignMode && army!=0)return false;if(!battle.Rules.AiEnabled || battle.Result is not null || !battle.Units.Any(u=>u.Army==army) || strategy!="manual" && !TacticalAi.Strategies.Contains(strategy))return false;battle.Ai.ConfigureArmy(army,strategy=="manual"?null:strategy);definition=definition with{AiArmies=battle.Ai.Armies.Keys.ToArray(),AiStrategies=new(battle.Ai.Armies)};if(custom is not null){definition=definition with{Units=definition.Units.Select(d=>d with{Autonomy=battle.Unit(d.Id)!.Autonomy}).ToArray()};custom=custom with{Placements=definition.Units,AiArmies=definition.AiArmies,AiStrategies=[definition.AiStrategies.GetValueOrDefault(0,"balanced"),definition.AiStrategies.GetValueOrDefault(1,"balanced")]};}clock.RefreshState();RefreshFrames();return true;}
    public string GetArmyStrategy(int army)=>battle.Ai.Armies.TryGetValue(army,out var strategy)?strategy:"manual";
    public bool IssueAutonomy(int id,bool enabled)
    {
        if(Deployment && custom is not null && battle.Unit(id)is {Army:0,Effective:true} u) {
            if(!battle.AssignSetupAutonomy(id,enabled))return false;
            definition=definition with {Units=definition.Units.Select(d=>d with{Autonomy=battle.Unit(d.Id)!.Autonomy}).ToArray(),AiArmies=battle.Ai.Armies.Keys.ToArray(),AiStrategies=new(battle.Ai.Armies)};
            custom=custom with{Placements=definition.Units,AiArmies=definition.AiArmies,AiStrategies=[definition.AiStrategies.GetValueOrDefault(0,"balanced"),definition.AiStrategies.GetValueOrDefault(1,"balanced")]};clock.RefreshState();RefreshFrames();return true;
        }
        if(!battle.Rules.AiEnabled || Controlled(id)is null)return false;battle.Issue(new(id,Autonomy:enabled?AutonomyMode.Autonomous:AutonomyMode.Hold));return true;
    }
    public string GetCommanderDescription(string personality,string specialization)=>CommanderSystem.Description(personality,specialization);
    public GArray GetPersonalities()=>new(CommanderSystem.Personalities.Select(p=>Variant.From(p)).ToArray());
    public GArray GetSpecializations(int id)=>battle.Unit(id)is { } u?new(CommanderSystem.Usable(u.Archetype.Category).Append(u.Commander.Specialization).Distinct().Select(p=>Variant.From(p)).ToArray()):new();
    public bool AssignCommander(int id,string personality,string specialization)
    {if(campaignMode || battle.Tick!=0 || !battle.Rules.CommandersEnabled || battle.Unit(id)is not { } u)return false;var next=u.Commander with {Personality=personality,Specialization=specialization};try{CommanderSystem.Validate(next,u.Archetype.Category);}catch(ArgumentException){return false;}if(!battle.AssignCommander(id,next))return false;SaveOfficers();return true;}
    public bool RerollCommander(int id)
    {if(campaignMode || battle.Tick!=0 || !battle.Rules.CommandersEnabled || battle.Unit(id)is not { } u)return false;var rng=new SimulationRandom(definition.CommanderSeed+(++rerolls)*49999);var names=battle.Units.Where(v=>v.Army==u.Army && v.Id!=id).Select(v=>v.Commander.Name).ToHashSet();var ids=battle.Units.Select(v=>v.Commander.Id).ToHashSet();battle.AssignCommander(id,CommanderSystem.Generate(rng,u.Archetype.Category,u.Archetype.Faction,names,ids));SaveOfficers();return true;}
    private void SaveOfficers(){definition=definition with{Units=definition.Units.Select(d=>d with{Commander=battle.Unit(d.Id)!.Commander}).ToArray()};if(custom is not null)custom=custom with{Placements=definition.Units};clock.RefreshState();RefreshFrames();}
    public string GetScenarioName() => definition.Name;
    public long GetSeed() => battle.Seed;
    public bool IsCombatEnabled() => battle.Rules.CombatEnabled;
    public bool IsMoraleEnabled() => battle.Rules.MoraleEnabled;
    public bool IsCavalryEnabled() => battle.Rules.CavalryEnabled;
    public string GetCompletionRule() => battle.Result?.Rule ?? (battle.Rules.MoraleEnabled?"Fighting-strength collapse":"Temporary infantry annihilation");
    public GArray GetScenarioChoices()
    {var choices=new GArray();foreach(var(id,name) in CombatScenarios.Available)choices.Add(new GDictionary{["id"]=id,["name"]=name});return choices;}
    public GDictionary GetRuleInfo()=>new(){["rally_safe_seconds"]=battle.Rules.RallySafeSeconds,["rout_threshold"]=battle.Rules.RoutThreshold,
        ["charge_min_cohesion"]=battle.Rules.ChargeMinCohesion,["charge_range"]=battle.Rules.ChargeRange,["charge_max_speed"]=battle.Rules.ChargeMaxSpeed};
    public string GetResult() => battle.Result?.Id ?? "";
    public int Advance(double seconds, double speed, bool playing)
    {
        if(Deployment)return 0;
        clock.Playing = playing; clock.Speed = speed;
        int steps = clock.Advance(seconds);
        if (steps > 0) RefreshFrames();
        return steps;
    }
    public bool SingleStep()
    {
        if(Deployment)return false;
        clock.Playing = false;
        bool changed = clock.SingleStep();
        if (changed) RefreshFrames();
        return changed;
    }
    public int WarmStart(int ticks)
    {
        if(Deployment)return 0;
        if(ticks<0 || ticks>100000)throw new ArgumentOutOfRangeException(nameof(ticks));
        clock.Playing=false;int before=battle.Tick;
        for(int i=0;i<ticks && battle.Result is null;i++)clock.SingleStep();
        RefreshFrames();return battle.Tick-before;
    }
    public int GetTick() => battle.Tick;
    public double GetTime() => battle.Time;
    public double GetAlpha() => clock.Alpha;
    public double GetBacklogSeconds() => clock.Accumulator;
    public double GetTickMilliseconds() => clock.LastTickMilliseconds;
    public GDictionary GetFrame(bool before) => before ? previous : current;
    private void RefreshFrames() { previous = Frame(clock.Previous); current = Frame(clock.Current); }
    private GDictionary Frame(BattleSnapshot snapshot)
    {
        var units = new GArray();var projectiles=new GArray();
        foreach (var u in snapshot.Units)
        {
            var row = new GDictionary
            {
                ["id"] = u.Id, ["army"] = u.Army, ["position"] = Position(u.Position), ["facing"] = u.Facing,
                ["formation"] = Text(u.Formation), ["width"] = u.Width, ["depth"] = u.Depth,
                ["strength"] = u.Strength, ["morale"] = u.Morale, ["cohesion"] = u.Cohesion,
                ["fatigue"] = u.Fatigue, ["speed"] = u.Speed, ["order"] = Text(u.Order.Kind),
                ["movement_state"] = u.MovementState, ["transition_left"] = u.TransitionLeft,
                ["next_formation"] = u.NextFormation is { } formation ? Text(formation) : "",
                ["congestion"] = u.Congestion, ["congestion_speed"] = u.CongestionSpeed,
                ["terrain_speed"] = u.TerrainSpeed, ["forest_cover"] = u.ForestCover, ["slope"] = u.GroundSlope
            };
            row["transport"]=battle.Unit(u.Id)!.NonCombatant;row["attack_capable"]=CanAttack(battle.Unit(u.Id)!);row["combat_state"]=Text(u.CombatState);row["target"]=u.TargetId??-1;
            row["reload_left"]=u.ReloadLeft;row["weapon_range"]=u.WeaponRange;row["combat_capable"]=u.CombatCapable;
            row["fire_lane"]=u.FireLaneFactor;row["sight_state"]=u.SightState;row["sight_transmission"]=u.SightTransmission;
            row["last_volley_shots"]=u.LastVolleyShots;row["last_volley_probability"]=u.LastVolleyProbability;
            var d=u.Dynamics;
            row["morale_simulated"]=d?.MoraleEnabled??false;row["cavalry_simulated"]=d?.CavalryEnabled??false;
            row["morale_state"]=d is null?"":Text(d.State);row["withdrawn"]=d?.Withdrawn??false;row["effective"]=d?.Effective??u.Strength>0;
            row["safe_time"]=d?.SafeTime??0;row["state_reason"]=d?.Reason??"";
            row["cavalry_state"]=d?.InfantryCharging==true?"bayonet charge":d?.CavalryEnabled==true?Text(d.CavalryState):"not ported";
            row["infantry_charging"]=d?.InfantryCharging??false;
            row["cavalry_target"]=d?.CavalryTargetId??-1;row["pursuit"]=d?.PursuitId??-1;
            row["momentum"]=d?.Momentum??0;row["last_momentum"]=d?.LastMomentum??0;row["charge_cooldown"]=d?.ChargeCooldown??0;
            row["charge_ready"]=d?.ChargeReady??false;row["charge_result"]=d?.ChargeResult??"none";row["charge_distance"]=d?.ChargeDistance??0;
            row["melee_capable"]=d?.MeleeCapable??u.CombatCapable;
            row["destination"] = u.Order.Destination is { } goal ? Variant.From(Position(goal)) : default;
            row["arrival_facing"] = u.Order.Facing is { } facing ? Variant.From(facing) : default;
            row["settling_goal"] = u.SettlingGoal is { } adjusted ? Variant.From(Position(adjusted)) : default;
            var a=u.Abilities;row["guns"]=a?.Guns??0;row["battery_state"]=a?.BatteryState??"not ported";row["setup_left"]=a?.SetupLeft??0;row["limber_left"]=a?.LimberLeft??0;row["hold_fire"]=a?.HoldFire??false;row["reload_seconds"]=a?.ReloadSeconds??0;row["ability"]=a?.Ability??"";row["drill"]=a?.Drill??0;row["aimed"]=a?.Aimed??1;
            var intel=u.Intel;row["ai_enabled"]=intel?.AiEnabled??false;row["commander_name"]=intel?.Commander.DisplayName??"";row["personality"]=intel?.Commander.Personality??"";row["specialization"]=intel?.Commander.Specialization??"";row["commander_effects"]=intel?.Effects??"";row["autonomy"]=intel is null?"ordered":Text(intel.Autonomy);row["order_owner"]=intel?.PlayerOrder==true?"player":"army/standing orders";row["intention"]=intel?.Intention??"";row["next_decision"]=intel?.NextDecision??0;row["ai_target"]=intel?.AiTarget??-1;row["army_plan"]=intel?.ArmyPlan??"";row["army_role"]=intel?.ArmyRole??"";row["mounted_intent"]=intel?.MountedIntent??"";row["tactical_assignment"]=intel?.Assignment??"";row["friendly_support"]=intel?.FriendlySupport??0;row["enemy_support"]=intel?.EnemySupport??0;row["position_reason"]=intel?.PositionReason??"";row["threat_ratio"]=intel?.ThreatRatio??0;row["target_score"]=intel?.TargetScore??0;
            row["specialization_name"]=intel?.Commander.DefinitionId is {Length:>0} historicalId?HistoricalCommanders.Get(historicalId).SpecializationName:(intel?.Commander.Specialization??"").Replace("_"," ");
            row["upgrades"]=new GArray((intel?.Commander.Upgrades??[]).Select(v=>Variant.From(v)).ToArray());
            row["upgrade_effects"]=UpgradeSystem.Describe(battle.Unit(u.Id)!);
            var environment=u.Environment;
            row["observed"]=environment?.Observed??true;row["environment_state"]=environment?.Status??"";row["crossing"]=environment?.Crossing??"";row["crossing_waiting"]=environment?.Waiting??false;row["transit_compact"]=environment?.Compact??false;row["road"]=environment?.Road??"";
            row["route_points"]=new GArray((environment?.Waypoints??[]).Select(p=>Variant.From(Position(p))).ToArray());
            units.Add(row);
        }
        foreach(var p in snapshot.Projectiles??[])projectiles.Add(new GDictionary{["id"]=p.Id,["owner"]=p.OwnerId,["army"]=p.Army,["position"]=Position(p.Position),["velocity"]=Position(p.Velocity),["height"]=p.Height,["type"]=p.Type,["bounces"]=p.Bounces,["energy"]=p.Energy});
        return new() { ["projectiles"]=projectiles,["tick"] = snapshot.Tick, ["time"] = snapshot.Time, ["units"] = units, ["result"] = snapshot.Result??"" };
    }
    public GArray GetRecentEvents()
    {
        var result=new GArray();
        foreach(var e in battle.Events)
            if(e.Time+Math.Max(3,e.Duration)>=clock.Previous.Time && (battle.Unit(e.UnitId) is not { } eventUnit || battle.VisibleToArmy(eventUnit)))
                result.Add(new GDictionary { ["sequence"]=e.Sequence,["time"]=e.Time,["tick"]=e.Tick,["kind"]=e.Kind,
                    ["unit_id"]=e.UnitId,["target_id"]=e.TargetId??-1,["position"]=Position(e.Position),
                    ["facing"]=e.Facing,["width"]=e.Width,["duration"]=e.Duration,["losses"]=e.Losses,["message"]=e.Message });
        return result;
    }
    public GDictionary GetMetrics() => new() { ["ai_decisions"]=battle.Metrics.AiDecisions,["ai_milliseconds"]=battle.Metrics.AiMilliseconds,["ai_target_evaluations"]=battle.Metrics.AiTargetEvaluations,["target_changes"]=battle.Metrics.AiTargetChanges,["formation_changes"]=battle.Metrics.AiFormationChanges,["artillery_shots"]=battle.Metrics.ArtilleryShots,["projectile_collision_checks"]=battle.Metrics.ProjectileCollisionChecks,["projectile_hits"]=battle.Metrics.ProjectileHits,["projectile_bounces"]=battle.Metrics.ProjectileBounces,["peak_projectiles"]=battle.Metrics.PeakProjectiles,["friendly_fire"]=battle.Metrics.FriendlyFireHits,["active_projectiles"]=battle.Artillery.Projectiles.Count,["volleys"]=battle.Metrics.Volleys,["casualties"]=battle.Metrics.Casualties,
        ["melee_pulses"]=battle.Metrics.MeleePulses,["visibility_queries"]=battle.Metrics.VisibilityQueries,
        ["visibility_calculations"]=battle.Metrics.VisibilityCalculations,["visibility_samples"]=battle.Metrics.VisibilitySamples,
        ["firing_blocker_checks"]=battle.Metrics.FiringBlockerChecks,["random_draws"]=battle.Random.Draws,
        ["routs"]=battle.Metrics.Routs,["rallies"]=battle.Metrics.Rallies,["cascade_shocks"]=battle.Metrics.CascadeShocks,["escapes"]=battle.Metrics.Escapes,
        ["charge_starts"]=battle.Metrics.ChargeStarts,["charge_impacts"]=battle.Metrics.ChargeImpacts,["failed_charges"]=battle.Metrics.FailedCharges,
        ["aborted_charges"]=battle.Metrics.AbortedCharges,["impact_casualties"]=battle.Metrics.ImpactCasualties,["impact_momentum"]=battle.Metrics.ImpactMomentum,
        ["pursuit_seconds"]=battle.Metrics.PursuitSeconds,["pursuit_casualties"]=battle.Metrics.PursuitCasualties,["pursuit_losses"]=battle.Metrics.PursuitLosses };
    public GArray GetRegimentDefinitions()
    {
        var result = new GArray();
        foreach (var u in battle.Units)
        {
            result.Add(new GDictionary
            {
                ["id"] = u.Id, ["army"] = u.Army, ["name"] = u.Name, ["archetype"] = u.Archetype.Id,
                ["category"] = Text(u.Archetype.Category), ["commander"] = u.Commander.DisplayName+(u.Commander.DefinitionId.Length>0 && HistoricalCommanders.Get(u.Commander.DefinitionId).AlternativeNames.Count>0?" ("+string.Join(", ",HistoricalCommanders.Get(u.Commander.DefinitionId).AlternativeNames)+")":""),
                ["commander_id"] = u.Commander.Id, ["maximum"] = u.MaximumStrength,
                ["symbol"] = u.Archetype.Symbol, ["faction"] = u.Archetype.Faction,
                ["guns"] = u.Archetype.Guns,
                ["charge_max_speed"]=u.Archetype.Category==UnitCategory.Cavalry?battle.Rules.ChargeMaxSpeed*u.Archetype.ChargeSpeed:0,
                ["formations"] = new GArray(u.Archetype.Formations.Select(f => Variant.From(Text(f))).ToArray())
            });
        }
        return result;
    }
    public GDictionary GetTerrainDefinition()
    {
        var hills = new GArray(); var forests = new GArray();
        foreach (var h in battle.Terrain.Hills) hills.Add(new GDictionary { ["center"] = new Vector2((float)h.X, (float)h.Y), ["radius"] = new Vector2((float)h.RadiusX, (float)h.RadiusY), ["height"] = h.Height, ["compact"] = h.Compact });
        foreach (var f in battle.Terrain.Forests) forests.Add(new GDictionary { ["center"] = new Vector2((float)f.X, (float)f.Y), ["radius"] = new Vector2((float)f.RadiusX, (float)f.RadiusY), ["density"] = f.Density });
        return new() { ["size"] = new Vector2((float)battle.Rules.Width, (float)battle.Rules.Height), ["hills"] = hills, ["forests"] = forests,["environment"]=EnvironmentData(),["canonical_grid"]=CanonicalGrid() };
    }
    private GDictionary CanonicalGrid()
    {
        if(battle.Terrain.Environment.Rivers.Count==0)return new();
        double spacing=Math.Max(5,Math.Sqrt(battle.Rules.Width*battle.Rules.Height/196000));int nx=(int)Math.Ceiling(battle.Rules.Width/spacing),nz=(int)Math.Ceiling(battle.Rules.Height/spacing);var heights=new float[(nx+1)*(nz+1)];
        for(int z=0;z<=nz;z++)for(int x=0;x<=nx;x++)heights[z*(nx+1)+x]=(float)battle.Terrain.Elevation(new(x*battle.Rules.Width/nx,z*battle.Rules.Height/nz));
        return new(){["nx"]=nx,["nz"]=nz,["heights"]=heights};
    }
    private GDictionary EnvironmentData()
    {
        var e=battle.Terrain.Environment;var water=new GArray();var crossings=new GArray();var roads=new GArray();var defences=new GArray();
        GArray Points(System.Collections.Generic.IEnumerable<Vec2> points)=>new(points.Select(p=>Variant.From(Position(p))).ToArray());
        var bounds=new Vec2[]{new(0,0),new(battle.Rules.Width,0),new(battle.Rules.Width,battle.Rules.Height),new(0,battle.Rules.Height)};
        foreach(var p in e.Water){var clipped=EnvironmentGeometry.Clip(p.Points,bounds);if(clipped.Length>=3)water.Add(new GDictionary{["id"]=p.RiverId,["points"]=Points(clipped),["height"]=p.Height});}
        foreach(var c in e.Crossings)crossings.Add(new GDictionary{["id"]=c.Definition.Id,["kind"]=Text(c.Definition.Kind),["position"]=Position(c.Definition.Position),["facing"]=c.Definition.Facing,["length"]=c.Definition.Length,["width"]=c.Definition.Width,["entry"]=Position(c.Entry),["exit"]=Position(c.Exit),["height"]=c.SurfaceHeight,["speed"]=c.Speed});
        foreach(var r in e.Roads)roads.Add(new GDictionary{["id"]=r.Id,["points"]=Points(r.Points),["width"]=r.Width,["surface"]=Text(r.Surface)});
        foreach(var f in e.Defences)defences.Add(new GDictionary{["id"]=f.Id,["position"]=Position(f.Position),["facing"]=f.Facing,["width"]=f.Width,["depth"]=f.Depth,["kind"]=Text(f.Kind),["cover"]=f.MusketExposure,["charge"]=f.ChargeResistance});
        return new(){["version"]=1,["water"]=water,["crossings"]=crossings,["roads"]=roads,["defences"]=defences,["weather"]=Text(e.Weather.Type),["visibility_limit"]=e.Weather.VisibilityLimit};
    }
    public GArray GetCrossings()=>new(battle.Terrain.Environment.Crossings.Select(c=>Variant.From(new GDictionary{["id"]=c.Definition.Id,["kind"]=Text(c.Definition.Kind)})).ToArray());
    public GDictionary GetEnvironmentMetrics()
    {var owners=new GDictionary();foreach(var pair in battle.Navigation.Owners)owners[pair.Key]=pair.Value;return new(){["geometry_queries"]=battle.Terrain.Environment.GeometryQueries,["route_plans"]=battle.Navigation.Plans,["owners"]=owners};}
    public bool IssueMoveVia(int id,Vector2 point,double facing,bool oriented,string via)=>MoveOrder(id,point,oriented?facing:null,via==""?null:via);
    private Regiment? Controlled(int id) => !Deployment && battle.Result is null && battle.Unit(id) is { Army: 0, Effective: true } unit ? unit : null;
    private bool CanAttack(Regiment u)=>u.CombatCapable || u.Archetype.MeleeOnly || battle.Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry;
    public Vector2 GetMoveDestination(int id,Vector2 destination)
    {
        var u=battle.Unit(id);if(u is null)return destination;
        double radius=u.Rect.Radius;
        if(u.Archetype.Category==UnitCategory.Infantry)foreach(var f in Enum.GetValues<Formation>()){var p=Formations.Get(f);radius=Math.Max(radius,Math.Sqrt(p.Width*p.Width+p.Depth*p.Depth)/2);}
        radius+=1;return new((float)Math.Clamp(destination.X,radius,battle.Rules.Width-radius),(float)Math.Clamp(destination.Y,radius,battle.Rules.Height-radius));
    }
    public bool IssueMove(int id, Vector2 destination)=>MoveOrder(id,destination,null);
    public bool IssueMoveOriented(int id,Vector2 destination,double facing)=>double.IsFinite(facing) && MoveOrder(id,destination,facing);
    private bool MoveOrder(int id,Vector2 destination,double? facing,string? via=null)
    {
        if(Controlled(id)is null || !float.IsFinite(destination.X) || !float.IsFinite(destination.Y))return false;
        var p=GetMoveDestination(id,destination);var point=new Vec2(p.X,p.Y);var e=battle.Terrain.Environment;
        if(via is not null && !e.Crossings.Any(c=>c.Definition.Id==via)){SetupError="Unknown crossing.";return false;}
        if(e.InRiver(point) && e.CrossingAt(point) is null){SetupError="Destination is deep water; choose a crossing or dry ground.";return false;}
        battle.Issue(new(id,new(OrderKind.Move,point,facing,ViaCrossing:via)));SetupError="";return true;
    }
    public string CheckMoveDestination(int id,Vector2 destination)
    {
        if(battle.Unit(id)is not { } u)return "Unknown regiment.";
        var e=battle.Terrain.Environment;var p=new Vec2(destination.X,destination.Y);
        if(e.InRiver(p) && e.CrossingAt(p) is null)return "Deep water is impassable.";
        if(e.CrossingAt(p) is { } crossing && !crossing.Permits(u.Archetype.Category))return "This crossing does not permit this unit category.";
        return "";
    }
    public string CheckDeployment(int id,Vector2 position,double facing,string formation)
    {
        if(campaignMode)return CampaignPlacementError(id,position,facing,formation);
        if(!Deployment || custom is null || !Enum.TryParse<Formation>(formation,true,out var f))return "Deployment is unavailable.";
        try{_ = custom.EditPlacement(id,new(position.X,position.Y),facing,f);return "";}catch(ArgumentException e){return e.Message;}
    }
    public bool IssueFireControl(int id,bool hold)
    {if(Controlled(id)is null)return false;battle.Issue(new(id,new(hold?OrderKind.HoldFire:OrderKind.ResumeFire)));return true;}
    public bool IssueSkirmish(int id)
    {if(Controlled(id)is not { } u || !u.Archetype.Formations.Contains(Formation.Skirmish))return false;battle.Issue(new(id,new(OrderKind.Skirmish),Formation.Skirmish));return true;}
    public bool IssueHold(int id)
    { if (Controlled(id) is null) return false; battle.Issue(new(id, new(OrderKind.Hold))); return true; }
    public bool IssueAdvance(int id)
    { if(!battle.Rules.CombatEnabled || Controlled(id) is not { } u || !CanAttack(u))return false; battle.Issue(new(id,new(OrderKind.Advance)));return true; }
    public bool IssueAttack(int id,int targetId)
    {
        if(!battle.Rules.CombatEnabled || Controlled(id) is not { } unit || !CanAttack(unit) || battle.Unit(targetId) is not { Active:true } target || target.Army==unit.Army)return false;
        if(!battle.Terrain.Environment.InVisibility(unit.Position,target.Position))return false;
        battle.Issue(new(id,new(OrderKind.Attack,TargetId:targetId)));return true;
    }
    public bool IssueCavalryOrder(int id,int targetId,bool pursue)
    {
        if(!battle.Rules.CombatEnabled || Controlled(id) is not { } u || (pursue ? !battle.Rules.CavalryEnabled || u.Archetype.Category!=UnitCategory.Cavalry : !(battle.Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry || battle.Rules.InfantryChargesEnabled && u.Archetype.Category==UnitCategory.Infantry)))return false;
        var target=battle.Unit(targetId>=0?targetId:u.TargetId??u.Order.TargetId??-1);
        target??=battle.Units.Where(t=>t.Active && t.Army!=u.Army && battle.Perceives(u,t)).OrderBy(t=>(t.Position-u.Position).LengthSquared).ThenBy(t=>t.Id).FirstOrDefault();
        if(target is null || !target.Active || target.Army==u.Army || !battle.Terrain.Environment.InVisibility(u.Position,target.Position) || pursue && target.State!=MoraleState.Routing)return false;
        battle.Issue(new(id,new(pursue?OrderKind.Pursue:OrderKind.Charge,TargetId:target.Id)));return true;
    }
    public bool IssueRecoveryOrder(int id,bool disengage)
    {if(Controlled(id) is null || !battle.Rules.MoraleEnabled)return false;battle.Issue(new(id,new(disengage?OrderKind.Disengage:OrderKind.Reform)));return true;}
    public bool IssueFormation(int id, string formation)
    {
        var unit = Controlled(id);
        if (unit is null || unit.TransitionLeft > 0 || !Enum.TryParse<Formation>(formation, true, out var value) || !unit.Archetype.Formations.Contains(value)) return false;
        battle.Issue(new(id, Formation: value)); return true;
    }
    public void StartBenchmarkMarch()
    {
        foreach (var u in battle.Units.Where(u => u.Army == 0))
            battle.Issue(new(u.Id, new(OrderKind.Move, new(800, 75 + u.Id / 6 * 75))));
    }
    private static Vector2 Position(Vec2 p) => new((float)p.X, (float)p.Y);
    private static string Text<T>(T value) where T : Enum => value.ToString().ToLowerInvariant();
}
