using System.Collections.ObjectModel;
namespace Quiberon.Simulation;

public sealed class BattleSimulation
{
    public MissionSystem? Mission {get;private set;}
    public void SetMission(MissionDefinition definition){if(Tick!=0 || Mission is not null)throw new ArgumentException("Mission must be assigned once before tick one.");Mission=new(this,definition);}
    public void FinishMission(int army,string reason){if(Result is not null)return;Result=new(army,Tick,Time,reason);Artillery.Clear();Emit("battle_complete",Units[0],null,new(Rules.Width/2,Rules.Height/2),5,0,reason);}
    public Rules Rules { get; }
    public TerrainMap Terrain { get; }
    public CrossingNavigation Navigation {get;}
    public long Seed { get; }
    public int Tick { get; private set; }
    public double Time => Tick * global::Quiberon.Simulation.Rules.Dt;
    public IReadOnlyList<Regiment> Units { get; }
    public ISimulationRandom Random { get; }
    public CombatMetrics Metrics { get; } = new();
    public VisibilityService Visibility { get; }
    public CombatSystem Combat { get; }
    public MoraleSystem MoraleSystem { get; }
    public CavalrySystem Cavalry { get; }
    public InfantryChargeSystem InfantryCharges { get; }
    internal Dictionary<int,double> InspirationNext { get; } = new();
    public IReadOnlyDictionary<int,int> InitialUnitStrength { get; }
    public ArtillerySystem Artillery { get; }
    public TacticalAi Ai { get; }
    public IReadOnlyList<ArmyCommanderAssignment> ArmyCommanders { get; private set; } = Array.Empty<ArmyCommanderAssignment>();
    public CommandSupportSystem CommandSupport { get; private set; } = null!;
    public BattleResult? Result { get; private set; }
    private readonly int[] combatArmies;
    public IReadOnlyDictionary<int,int> InitialStrength { get; }
    public Dictionary<int,double> DefeatSince { get; } = new();
    private readonly Queue<SimulationEvent> events = new();
    private long nextEvent;
    public IReadOnlyCollection<SimulationEvent> Events => events;
    private readonly Dictionary<int, Regiment> byId;
    private readonly List<Regiment> active = new();
    private readonly List<Regiment> movementParticipants = new();
    private readonly List<Overlap> overlaps = new();
    private readonly Dictionary<int, Vec2?> intents = new(), destinations = new();
    private readonly Queue<Command> commands = new();
    public BattleSimulation(IEnumerable<Regiment> units, Rules? rules = null, TerrainMap? terrain = null, long seed = 1, ISimulationRandom? random = null)
    {
        Rules = rules ?? new(); Terrain = terrain ?? new(); Seed = seed;
        if(!double.IsFinite(Rules.MeleeDisengageDistance) || Rules.MeleeDisengageDistance<.75 || Rules.MeleeDisengageDistance>20)throw new ArgumentException("Melee disengagement distance must be .75–20 m");
        if(Rules.AiDecisionTicks<1)throw new ArgumentException("AI interval must be positive");
        if (!double.IsFinite(Rules.Width + Rules.Height) || Math.Min(Rules.Width, Rules.Height) < 100) throw new ArgumentException("Battlefield dimensions must be finite and at least 100 m");
        var list = units.OrderBy(u => u.Id).ToArray();
        if (list.Length == 0 || list.Length > 512 || list.Any(u => u.Id < 0 || !u.Position.Finite || !double.IsFinite(u.Facing + u.Cohesion + u.Fatigue + u.Morale + u.SafeTime))) throw new ArgumentException("Invalid regiment state");
        byId = list.ToDictionary(u => u.Id); Units = Array.AsReadOnly(list);
        Random = random ?? new SimulationRandom(seed); Visibility = new(Terrain,Metrics); Combat = new(this);MoraleSystem=new(this);Cavalry=new(this);InfantryCharges=new(this);Artillery=new(this);
        var officerRandom=new SimulationRandom(Rules.CommanderSeed);var names=new Dictionary<int,HashSet<string>>();var ids=new HashSet<string>();
        foreach(var u in Units.Where(u=>u.CommanderAssigned)){if(Rules.CommandersEnabled)CommanderSystem.Validate(u.Commander,u.Archetype.Category);if(!ids.Add(u.Commander.Id) && Rules.CommandersEnabled)throw new ArgumentException("Duplicate commander ID");if(!names.ContainsKey(u.Army))names[u.Army]=new();names[u.Army].Add(u.Commander.Name);}
        var reservedNames=Units.Where(u=>u.Commander.DefinitionId.Length>0).SelectMany(u=>HistoricalCommanders.Get(u.Commander.DefinitionId).AlternativeNames.Append(u.Commander.Name)).ToHashSet();
        foreach(var u in Units){u.SpecialistsEnabled=Rules.SpecialistsEnabled;u.ArtilleryEnabled=Rules.ArtilleryEnabled;u.CommandersEnabled=Rules.CommandersEnabled;
            if(Rules.CommandersEnabled && !u.CommanderAssigned){if(!names.ContainsKey(u.Army))names[u.Army]=new();names[u.Army].UnionWith(reservedNames);u.Commander=CommanderSystem.Generate(officerRandom,u.Archetype.Category,u.Archetype.Faction,names[u.Army],ids);u.CommanderAssigned=true;}}
        InitialStrength=new ReadOnlyDictionary<int,int>(list.GroupBy(u=>u.Army).OrderBy(g=>g.Key).ToDictionary(g=>g.Key,g=>g.Sum(u=>u.Strength)));
        combatArmies = list.Where(u=>u.CombatCapable || u.Archetype.MeleeOnly).Select(u=>u.Army).Distinct().Order().ToArray();
        InitialUnitStrength = new ReadOnlyDictionary<int,int>(list.ToDictionary(u=>u.Id,u=>u.Strength));
        foreach(var u in Units){UpgradeSystem.Validate(u.Commander,u.Archetype);u.Commander=UpgradeSystem.Freeze(u.Commander);}
        foreach (var u in Units){MovementSystem.ClampToField(u, Rules);u.WeatherReload=Terrain.Environment.Reload(u.Archetype.Category);if(!Terrain.Environment.Passable(u.Rect,u.Archetype.Category))throw new ArgumentException($"{u.Name}: initial footprint overlaps impassable water.");}
        Navigation=new(this);
        HistoricalCommanders.ValidateAssignments(Units.Select(u=>u.Commander),ArmyCommanders,InitialStrength.Keys);
        Ai=new(this);CommandSupport=new(this);
    }
    public void SetArmyCommanders(IEnumerable<ArmyCommanderAssignment> leaders)
    {
        if(Tick!=0)throw new ArgumentException("Army command may only change before the first tick.");
        var assignments=leaders.ToArray();
        HistoricalCommanders.ValidateAssignments(Units.Select(u=>u.Commander),assignments,InitialStrength.Keys);
        foreach(var a in assignments)if(a.Position is { } p && (p.X<0 || p.X>Rules.Width || p.Y<0 || p.Y>Rules.Height))throw new ArgumentException("Headquarters must be inside the battlefield.");
        ArmyCommanders=Array.AsReadOnly(assignments.Select(a=>a with{Position=a.Position??new Vec2(Units.Where(u=>u.Army==a.Army).Average(u=>u.Position.X),Units.Where(u=>u.Army==a.Army).Average(u=>u.Position.Y))}).ToArray());
        CommandSupport=new(this);
    }
    public bool AssignCommander(int id,CommanderIdentity commander)
    {if(Tick!=0 || !Rules.CommandersEnabled || Unit(id)is not { } unit || Units.Any(u=>u.Id!=id && u.Commander.Id==commander.Id))return false;CommanderSystem.Validate(commander,unit.Archetype.Category);UpgradeSystem.Validate(commander,unit.Archetype);HistoricalCommanders.ValidateAssignments(Units.Where(u=>u.Id!=id).Select(u=>u.Commander).Append(commander),ArmyCommanders,InitialStrength.Keys);unit.Commander=UpgradeSystem.Freeze(commander);CommandSupport=new(this);return true;}
    public Regiment? Unit(int id) => byId.GetValueOrDefault(id);
    public bool AssignSetupAutonomy(int id,bool autonomous)
    {
        if(Tick!=0 || !Rules.AiEnabled || Unit(id)is not {Effective:true} u)return false;
        if(autonomous)Ai.Release(u);
        else {u.Autonomy=AutonomyMode.Hold;u.PlayerOrder=true;u.Order=new();}
        return true;
    }
    public bool Perceives(Regiment observer,Regiment target)
    {
        if(!Terrain.Environment.InVisibility(observer.Position,target.Position))return false;
        if(Terrain.Empty || Combat.Sight(observer,target).Visible)return true;
        return observer.Archetype.Category==UnitCategory.Artillery && Units.Any(u=>u.Army==observer.Army && u.Effective && Combat.Sight(u,target).Visible);
    }
    public bool VisibleToArmy(Regiment unit,int army=0)=>unit.Army==army || Terrain.Environment.Weather.Type!=WeatherType.Fog || Units.Any(friend=>friend.Army==army && friend.Effective && Terrain.Environment.InVisibility(friend.Position,unit.Position) && Combat.Sight(friend,unit).Visible);
    internal void Emit(string kind,Regiment unit,Regiment? target,Vec2 position,double duration,int losses,string message)
    {
        events.Enqueue(new(nextEvent++,Tick,Time,kind,unit.Id,target?.Id,position,unit.Facing,unit.Width,duration,losses,message));
        while(events.Count>4096)events.Dequeue();
    }
    public void Issue(Command command)
    {
        if (command.Order?.Destination is { } p && !p.Finite || command.Order?.Facing is { } a && !double.IsFinite(a)) throw new ArgumentException("Order coordinates/facing must be finite");
        if(command.Order?.ViaCrossing is { } via && !Terrain.Environment.Crossings.Any(c=>c.Definition.Id==via))throw new ArgumentException("Unknown movement crossing.");
        commands.Enqueue(command);
    }
    private void ApplyCommands()
    {
        while (commands.TryDequeue(out var command))
        {
            var u = Unit(command.RegimentId);
            if (u is null || !u.Effective) continue;
            if(command.Autonomy is { } mode){if(mode==AutonomyMode.Autonomous){Ai.Release(u);continue;}u.Autonomy=mode;u.PlayerOrder=true;if(mode==AutonomyMode.Hold)u.Order=new();}
            if (command.Order is { } order)
            {
                if(order.Kind is OrderKind.HoldFire or OrderKind.ResumeFire){u.HoldFire=order.Kind==OrderKind.HoldFire;continue;}
                if(order.Kind==OrderKind.Charge && !(Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry || Rules.InfantryChargesEnabled && u.Archetype.Category==UnitCategory.Infantry))continue;
                if(order.Kind==OrderKind.Pursue && (!Rules.CavalryEnabled || u.Archetype.Category!=UnitCategory.Cavalry))continue;
                if(order.Kind==OrderKind.Pursue && Unit(order.TargetId??-1) is not {State:MoraleState.Routing,Active:true})continue;
                if(order.Kind==OrderKind.Disengage && order.Destination is null)
                {
                    var threat=Unit(u.TargetId??-1)??Units.Where(e=>e.Army!=u.Army && e.Active).OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).FirstOrDefault();
                    var away=threat is null?new Vec2(u.Army==0?-1:1,0):(u.Position-threat.Position).Normalized;
                    if(away.Length<.1)away=Vec2.Direction(u.Facing+Math.PI);
                    var p=u.Position+away*Rules.ChargeRecoilDistance;double radius=u.Rect.Radius+1;
                    order=order with {Destination=new Vec2(Math.Clamp(p.X,radius,Rules.Width-radius),Math.Clamp(p.Y,radius,Rules.Height-radius))};
                }
                if(Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry)Cavalry.Cancel(u,"New player order");
                if(u.Archetype.Category==UnitCategory.Infantry)InfantryCharges.Cancel(u);
                u.AiIntention=$"Executing player {order.Kind.ToString().ToLowerInvariant()} order";u.Order = order; u.PlayerOrder = true;u.Autonomy=order.Kind is OrderKind.Hold or OrderKind.Defend?AutonomyMode.Hold:AutonomyMode.Ordered; SeparationSystem.Reset(u); MovementSystem.ResetAvoidance(u);
                if(order.Kind==OrderKind.HoldFire)u.HoldFire=true;else if(order.Kind==OrderKind.ResumeFire)u.HoldFire=false;
                if(order.Kind==OrderKind.Skirmish)SpecialistSystem.Activate(this,u,"Skirmish: bounded withdrawal and re-engagement");
                if (order.TargetId is { } id && Unit(id) is { } target && target.Army!=u.Army && target.Active)u.LastSeenTargetPosition=target.Position;
            }
            if(command.Formation is { } requestedFormation && Terrain.Environment.Rivers.Count>0 && !Terrain.Environment.Passable(new(u.Position,u.Facing,Formations.Get(requestedFormation).Width,Formations.Get(requestedFormation).Depth),u.Archetype.Category)){u.Navigation.Status="Formation would overlap deep water";continue;}
            if (command.Formation is { } formation && u.Archetype.Category == UnitCategory.Infantry && u.Archetype.Formations.Contains(formation) && formation != u.Formation && u.TransitionLeft == 0)
            {
                u.PlayerFormationPinned=true;ChangeFormation(u,formation);
            }
        }
    }
    public void ChangeFormation(Regiment u,Formation formation)
    {u.NextFormation=formation;u.TransitionLeft=SpecialistSystem.FormationTime(u,Rules.FormationSeconds);u.Cohesion=Math.Max(0,u.Cohesion-6);u.FormationChanges++;Metrics.AiFormationChanges++;}
    public void Step()
    {
        if(Result is not null)return;
        Mission?.BeforeTick();ApplyCommands();Navigation.Begin(); active.Clear(); movementParticipants.Clear(); intents.Clear(); destinations.Clear();
        long allocationMark=Rules.MeasureAllocations?GC.GetAllocatedBytesForCurrentThread():0;
        foreach (var u in Units)
        {
            if (!u.Active) continue;
            active.Add(u); u.EnemyContact = false;
            if(Rules.MoraleEnabled)movementParticipants.Add(u);
            intents[u.Id] = u.Order.Kind is OrderKind.Move or OrderKind.Defend or OrderKind.Advance ? u.Order.Destination : null;
        }
        if(Rules.CombatEnabled)
        {
            Combat.PreparePhase(active);CommandSupport.Update();Ai.Update();
            foreach(var u in active)intents[u.Id]=Combat.Intent(u);
            if(Rules.CavalryEnabled)
            {
                foreach(var u in active)if(u.Archetype.Category==UnitCategory.Cavalry)intents[u.Id]=Cavalry.Intent(u,intents[u.Id]);
                CavalrySystem.PursuitLanes(this,active,intents);
            }
            if(Rules.InfantryChargesEnabled)foreach(var u in active)if(u.Archetype.Category==UnitCategory.Infantry && (u.Order.Kind==OrderKind.Charge || u.InfantryCharging || !u.ChargeReady))intents[u.Id]=InfantryCharges.Intent(u,intents[u.Id]);
        }
        if(Rules.MeasureAllocations){long now=GC.GetAllocatedBytesForCurrentThread();Metrics.IntentAllocatedBytes+=now-allocationMark;allocationMark=now;}
        CongestionSystem.Update(active, Rules, overlaps);
        SeparationSystem.Settle(this, active, intents, overlaps);
        foreach (var u in active) destinations[u.Id] = MovementSystem.AvoidFriends(u, intents[u.Id], active, Rules, intents);
        foreach (var u in active)
        {
            if(Rules.CombatEnabled){u.CombatState=CombatState.Idle;u.ReloadLeft=Math.Max(0,u.ReloadLeft-global::Quiberon.Simulation.Rules.Dt);u.ChargeCooldown=Math.Max(0,u.ChargeCooldown-global::Quiberon.Simulation.Rules.Dt);}
            var priorPose=Navigation.Before(u);
            var destination = MovementSystem.TerrainSteer(this, u, destinations[u.Id]);
            if(Terrain.Environment.Rivers.Count>0){var routed=Navigation.Destination(u,intents[u.Id]);if(Navigation.Active(u) || routed!=intents[u.Id] || destination is { } detour && !Terrain.Environment.Swept(u.Rect,new(detour,u.Facing,u.Width,u.Depth),u.Archetype.Category))destination=routed;}
            double? arrival = u.Effective && u.Order.Kind is OrderKind.Move or OrderKind.Advance && (destination == u.Order.Destination || destination == u.SettlingGoal) ? u.Order.Facing : null;
            if (u.SettlingFacing is not null && destination == u.SettlingGoal) arrival = u.SettlingFacing;
            var before=u.Position;string batteryBefore=u.BatteryState;
            if(Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry)
            {
                bool charging=u.CavalryState==CavalryState.Charging;
                MovementSystem.Move(u,destination,Rules,Terrain,arrival,charging?Rules.ChargeMaxSpeed*u.Archetype.ChargeSpeed:null,
                    charging?Rules.ChargeAcceleration:null,charging?Rules.ChargeTurnMultiplier*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_turn"):1):1,u.PursuitSpeedLimit);
                Cavalry.AfterMove(u,before);
            }
            else if(u.InfantryCharging){MovementSystem.Move(u,destination,Rules,Terrain,arrival,InfantryCharges.SpeedCap(u),Rules.InfantryChargeAcceleration,.85);InfantryCharges.AfterMove(u,before);}
            else MovementSystem.Move(u, destination, Rules, Terrain, arrival);
            if(Terrain.Environment.Rivers.Count>0){Navigation.Constrain(u,priorPose);if(Terrain.Environment.Fording(u)){u.ChargeMomentum=Math.Min(.15,u.ChargeMomentum);u.ChargeDistance=0;}}
            if(u.Commander.Upgrades is {Count:>0})UpgradeSystem.UpdateStationary(u);
            if(Rules.ArtilleryEnabled && u.Archetype.Category==UnitCategory.Artillery && batteryBefore!=u.BatteryState)
            {if(u.BatteryState=="limbering")Emit("battery_redeploy",u,null,u.Position,1,0,$"{u.Name}: limbering");else if(!u.Limbered && u.SetupLeft==0 && batteryBefore is "deploying" or "travelling")Emit("battery_deployed",u,null,u.Position,1,0,$"{u.Name}: deployed and ready");}
            if (u.SettlingGoal is { } goal && u.SettlingFacing is { } facing && (u.Position - goal).Length < 1 && Math.Abs(Vec2.AngleDelta(u.Facing, facing)) < .001) u.SettlingFacing = null;
        }
        CongestionSystem.Update(active, Rules, overlaps, global::Quiberon.Simulation.Rules.Dt);
        if(Rules.MeasureAllocations){long now=GC.GetAllocatedBytesForCurrentThread();Metrics.MovementAllocatedBytes+=now-allocationMark;allocationMark=now;}
        if(Rules.CombatEnabled)
        {
            Combat.PreparePhase(active);Combat.ResolveMelee(active);
            if(Rules.CavalryEnabled)Cavalry.Pursuits(active);
            foreach(var u in active)
            {
                if(!u.Effective || !u.CombatCapable || u.CombatState==CombatState.Melee)continue;
                var target=Combat.SelectFireTarget(u);
                if(target is not null){u.TargetId=target.Id;Combat.Fire(u,target);}
            }
            if(Rules.ArtilleryEnabled)Artillery.Update();
            if(Rules.AiEnabled)foreach(var u in active){if(u.Speed>.1)u.MovingSeconds+=global::Quiberon.Simulation.Rules.Dt;if(u.CombatState==CombatState.Firing)u.FiringSeconds+=global::Quiberon.Simulation.Rules.Dt;}
            Combat.Cleanup();
            // SpatialIndex keeps this list's stable ordinal positions. Removal
            // invalidates those ordinals before the new morale-query phase.
            if(active.RemoveAll(u=>!u.Active)>0 && Rules.MoraleEnabled)Combat.PreparePhase(active);
        }
        if(Rules.MeasureAllocations){long now=GC.GetAllocatedBytesForCurrentThread();Metrics.CombatAllocatedBytes+=now-allocationMark;allocationMark=now;}
        if(Rules.CombatEnabled && Rules.MoraleEnabled)MoraleSystem.Update();
        else foreach (var u in active)
        {
            if ((!Rules.CombatEnabled || u.CombatState==CombatState.Idle) && u.CongestionLoss < 1e-6 && u.TerrainLoss < 1e-6)
            {
                double rate = u.Speed < .1 ? Rules.CohesionRestRecovery : Rules.CohesionMoveRecovery;
                u.Cohesion = Math.Min(100, u.Cohesion + global::Quiberon.Simulation.Rules.Dt * rate * Math.Min(UpgradeSystem.Has(u,"swift_reform")?1.8:1.5, u.Archetype.Recovery*CommanderSystem.Recovery(u)));
            }
        }
        if(Rules.CavalryEnabled)Cavalry.Cleanup();
        foreach(var u in active)if(HistoricalCommanders.Has(u,"vorwarts") && u.CavalryState==CavalryState.Charging)u.Fatigue=Math.Min(100,u.Fatigue+global::Quiberon.Simulation.Rules.Dt*.1);
        if(Rules.CombatEnabled && Rules.MoraleEnabled)Combat.Cleanup();
        if(Rules.MeasureAllocations){long now=GC.GetAllocatedBytesForCurrentThread();Metrics.MoraleAllocatedBytes+=now-allocationMark;}
        int finalRemoved=active.RemoveAll(u=>!u.Active);
        MovementSystem.SeparateEnemies(Rules.MoraleEnabled?movementParticipants:active, Rules);Navigation.FinalGuard();
        if(Mission is not null && finalRemoved>0)Combat.PreparePhase(active); // Mission queries cannot use stale spatial ordinals.
        Tick++;
        if(Mission is not null)Mission.AfterTick();
        else if(Rules.CombatEnabled && Rules.MoraleEnabled)CheckVictory();
        else if(Rules.CombatEnabled && combatArmies.Length>=2)
        {
            var alive=combatArmies.Where(army=>Units.Any(u=>u.Army==army && u.Active && (u.CombatCapable || u.Archetype.MeleeOnly))).ToArray();
            if(alive.Length<=1)
            {
                Result=new(alive.Length==1?alive[0]:null,Tick,Time);
                Emit("battle_complete",Units[0],null,new(Rules.Width/2,Rules.Height/2),3,0,$"Battle complete: {Result.Id} (temporary infantry annihilation)");
            }
        }
    }
    public void CheckVictory()
    {
        if(Mission is not null || InitialStrength.Count<2 || Result is not null)return;
        var defeated=new List<int>();
        foreach(var (army,initial) in InitialStrength)
        {
            int effective=Units.Where(u=>u.Army==army && u.Effective).Sum(u=>u.Strength);
            if(effective<initial*Rules.DefeatFraction)
            {
                DefeatSince.TryAdd(army,Time);
                if(Time-DefeatSince[army]>=Rules.DefeatGraceSeconds)defeated.Add(army);
            }
            else DefeatSince.Remove(army);
        }
        if(defeated.Count==0)return;
        var survivors=InitialStrength.Keys.Where(a=>!defeated.Contains(a)).ToArray();
        Result=new(survivors.Length==1?survivors[0]:null,Tick,Time,"fighting strength below 18% for 12 seconds");
        Artillery.Clear();
        Emit("battle_complete",Units[0],null,new(Rules.Width/2,Rules.Height/2),3,0,$"Battle complete: {Result.Id}; opposing fighting strength collapsed");
    }
    public BattleSnapshot Snapshot() => new(Tick, Time, Array.AsReadOnly(Units.Select(u => new RegimentSnapshot(u.Id, u.Army, u.Position, u.Facing, u.Formation, u.Width, u.Depth, u.Strength, u.Morale, u.Cohesion, u.Fatigue, u.Speed, u.Velocity ?? Vec2.Zero, u.Order, u.MovementState, u.TransitionLeft, u.NextFormation, u.SettlingGoal, u.PositionPreference, u.Congestion, u.CongestionSpeed, u.CongestionLoss, u.TerrainSpeed, u.TerrainLoss, u.ForestCover, u.GroundSlope, u.LimberLeft, u.SetupLeft, u.EnemyContact,
        u.CombatState,u.TargetId,u.ReloadLeft,u.FireLaneFactor,u.SightState,u.SightTransmission,u.Archetype.Weapon?.Range??0,u.CombatCapable,u.LastVolleyShots,u.LastVolleyProbability,
        Rules.MoraleEnabled||Rules.CavalryEnabled?new RegimentDynamics(u.State,u.Withdrawn,u.Effective,u.SafeTime,u.StateReason,
            u.CavalryState,u.CavalryTargetId,u.PursuitId,u.ChargeMomentum,u.ChargeLastMomentum,u.ChargeCooldown,u.ChargeReady,u.ChargeSequence,u.ChargeImpactedSequence,u.ChargeResult,
            Rules.MoraleEnabled,Rules.CavalryEnabled,Combat.CanMelee(u),u.ChargeDistance,u.ChargeImpactTargetId,u.InfantryCharging):null,
        Rules.ArtilleryEnabled||Rules.SpecialistsEnabled?new RegimentAbilities(u.AvailableGuns,u.BatteryState,u.Limbered,u.LimberLeft,u.SetupLeft,u.HoldFire,SpecialistSystem.Reload(u),u.SpecialistsEnabled?u.Archetype.Ability:"",SpecialistSystem.Drill(u),SpecialistSystem.Aimed(u,u.SightTransmission)):null,
        Rules.AiEnabled||Rules.CommandersEnabled?new RegimentIntel(u.Commander,u.Autonomy,u.PlayerOrder,u.AiIntention,u.AiNextDecision,u.AiTarget,u.AiThreatRatio,u.AiTargetScore,CommanderSystem.Effects(u),Rules.AiEnabled,u.Decisions,u.TargetChanges,u.FormationChanges):null,Terrain.Environment.Legacy?null:new EnvironmentUnitState(u.Navigation.Status,u.Navigation.CrossingId,u.Navigation.Waiting,u.TransitCompact,u.RoadId,VisibleToArmy(u),u.Navigation.Waypoints))).ToArray()),Result?.Id,Rules.ArtilleryEnabled?Artillery.Snapshot():null);
}

public sealed record BattleSnapshot(int Tick, double Time, ReadOnlyCollection<RegimentSnapshot> Units,string? Result=null,ProjectileSnapshot[]? Projectiles=null);
public readonly record struct RegimentSnapshot(int Id, int Army, Vec2 Position, double Facing, Formation Formation, double Width, double Depth, int Strength, double Morale, double Cohesion, double Fatigue, double Speed, Vec2 Velocity, Order Order, string MovementState, double TransitionLeft, Formation? NextFormation, Vec2? SettlingGoal, Vec2? PositionPreference, double Congestion, double CongestionSpeed, double CongestionLoss, double TerrainSpeed, double TerrainLoss, double ForestCover, double GroundSlope, double LimberLeft, double SetupLeft, bool EnemyContact,
    CombatState CombatState=CombatState.Idle,int? TargetId=null,double ReloadLeft=0,double FireLaneFactor=1,string SightState="none",double SightTransmission=1,double WeaponRange=0,bool CombatCapable=false,int LastVolleyShots=0,double LastVolleyProbability=0,RegimentDynamics? Dynamics=null,RegimentAbilities? Abilities=null,RegimentIntel? Intel=null,EnvironmentUnitState? Environment=null);
public sealed record EnvironmentUnitState(string Status,string Crossing,bool Waiting,bool Compact,string Road,bool Observed,IReadOnlyList<Vec2> Waypoints);
public sealed record RegimentIntel(CommanderIdentity Commander,AutonomyMode Autonomy,bool PlayerOrder,string Intention,double NextDecision,int? AiTarget,double ThreatRatio,double TargetScore,string Effects,bool AiEnabled,int Decisions,int TargetChanges,int FormationChanges);
public sealed record RegimentAbilities(int Guns,string BatteryState,bool Limbered,double LimberLeft,double SetupLeft,bool HoldFire,double ReloadSeconds,string Ability,double Drill,double Aimed);
public sealed record RegimentDynamics(MoraleState State,bool Withdrawn,bool Effective,double SafeTime,string Reason,CavalryState CavalryState,
    int? CavalryTargetId,int? PursuitId,double Momentum,double LastMomentum,double ChargeCooldown,bool ChargeReady,int ChargeSequence,int ImpactedSequence,
    string ChargeResult,bool MoraleEnabled,bool CavalryEnabled,bool MeleeCapable,double ChargeDistance,int? LastImpactTargetId,bool InfantryCharging=false);
