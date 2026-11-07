namespace Quiberon.Simulation;

public enum MoraleState { Steady, Shaken, Wavering, Routing, Rallying }
public enum CavalryState { Approach, Charging, Melee, Pursuit, Recoil, Reforming }

/// <summary>Authoritative regiment state, including commander identity and transient ability timers. No scene nodes.</summary>
public sealed class Regiment
{
    public bool NonCombatant {get;internal set;}
    public int Id { get; }
    public int Army { get; }
    public string Name { get; }
    public RegimentArchetype Archetype { get; }
    public CommanderIdentity Commander { get; internal set; }
    public bool CommanderAssigned { get; internal set; }
    public bool CommandersEnabled { get; internal set; }
    public AutonomyMode Autonomy { get; internal set; }
    public string AiIntention { get; internal set; }="Manual orders";
    public double AiNextDecision { get; internal set; }
    public int? AiTarget { get; internal set; }
    public MoraleState AiObservedState;
    public double AiPositionUntil, AiCommitAt, AiRetreatUntil, AiNextRetreat, AiReformUntil, AiNextReform, AiTargetUntil, AiAvoidUntil, AiFormationUntil;
    public double? AiMeleeSince;
    public Vec2? AiWaypoint, AiRetreatGoal, AiPursuitOrigin;
    public int? AiAvoidTarget, AiPursuitTarget;
    public Vec2? AiCoverGoal;
    public double AiCoverUntil;
    public bool SkirmishRetreat;
    public double SkirmishUntil;
    public bool PlayerFormationPinned;
    public double AiThreatRatio { get; internal set; }
    public double AiTargetScore { get; internal set; }
    public int Decisions { get; internal set; }
    public int TargetChanges { get; internal set; }
    public int FormationChanges { get; internal set; }
    public int DamageInflicted { get; internal set; }
    public int ShotsFired { get; internal set; }
    public double MovingSeconds { get; internal set; }
    public double FiringSeconds { get; internal set; }
    public Vec2 Position { get; set; }
    public double Facing { get; set; }
    public Formation Formation { get; set; }
    public int Strength { get; set; }
    public int MaximumStrength => Archetype.Strength;
    public double Morale { get; set; }
    public double Cohesion { get; set; } = 100;
    public double Fatigue { get; set; }
    public NavigationState Navigation {get;}=new();
    public bool TransitCompact {get;internal set;}
    public bool? TransitTarget {get;internal set;}
    public double WeatherReload {get;internal set;}=1;
    public string RoadId {get;internal set;}="";
    public double CommandShock { get; internal set; } = 1;
    public double CommandRecovery { get; internal set; } = 1;
    public double CommandMovement { get; internal set; } = 1;
    public double CommandManoeuvre { get; internal set; } = 1;
    public double CommandMorale { get; internal set; }
    public bool CommandOutnumbered { get; internal set; }
    public string CommandSupport { get; internal set; } = "";
    public Order Order { get; internal set; } = new();
    public bool PlayerOrder { get; internal set; }
    public double Speed { get; internal set; }
    public Vec2? Velocity { get; set; }
    public double TransitionLeft { get; internal set; }
    public Formation? NextFormation { get; internal set; }
    public bool Withdrawn { get; internal set; }
    public bool Active => Strength > 0 && !Withdrawn;
    public MoraleState State { get; set; }
    public bool Effective => Active && State is not (MoraleState.Routing or MoraleState.Rallying);
    public bool SpecialistsEnabled { get; internal set; }
    public bool ArtilleryEnabled { get; internal set; }
    public bool HoldFire { get; internal set; }
    internal HashSet<string> ActivatedAbilities = new();
    public int AvailableGuns => Archetype.Category == UnitCategory.Artillery && Active ? Math.Min(Archetype.Guns,(int)Math.Ceiling(Archetype.Guns*Strength/(double)MaximumStrength)) : 0;
    public string BatteryState => !Active ? "unavailable" : LimberLeft>0 ? "limbering" : Speed>.1 || Limbered && SetupLeft<=0 ? "travelling" : SetupLeft>0 ? "deploying" : HoldFire ? "hold fire" : ReloadLeft>0 ? "reloading" : "deployed";
    public bool CombatCapable => Archetype.Weapon is not null && (Archetype.Category == UnitCategory.Artillery ? ArtilleryEnabled : Archetype.Id == "infantry" || SpecialistsEnabled);
    public CombatState CombatState { get; internal set; }
    public int? TargetId { get; internal set; }
    public double ReloadLeft { get; internal set; }
    public double FireLaneFactor { get; internal set; } = 1;
    public string SightState { get; internal set; } = "none";
    public double SightTransmission { get; internal set; } = 1;
    public double LastVolleyProbability { get; internal set; }
    public int LastVolleyShots { get; internal set; }
    public Vec2? LastSeenTargetPosition { get; internal set; }
    public double SafeTime { get; set; }
    public Vec2? RoutHeading { get; internal set; }
    internal double RoutNextPlan;
    public int? LastAttackerId { get; internal set; }
    public string StateReason { get; internal set; } = "Standing orders";
    public CavalryState CavalryState { get; internal set; }
    public int? CavalryTargetId { get; internal set; }
    public int? PursuitId { get; internal set; }
    public double? PursuitSpeedLimit { get; internal set; }
    public int ChargeSequence { get; internal set; }
    public int ChargeImpactedSequence { get; internal set; } = -1;
    public int ChargeImpactTick { get; internal set; } = -1;
    public int? ChargeImpactTargetId { get; internal set; }
    public bool ChargeReady { get; internal set; } = true;
    public double? ChargeClearSince { get; internal set; }
    public double ChargeCooldown { get; internal set; }
    public double ChargeStarted { get; internal set; }
    public double ChargeDistance { get; internal set; }
    public double ChargeMomentum { get; internal set; }
    public double ChargeLastMomentum { get; internal set; }
    public double ChargeContactAt { get; internal set; } = -1e9;
    public double ChargeMeleeSince { get; internal set; }
    public double CavalryRetreatUntil { get; internal set; }
    public Vec2? RecoilGoal { get; internal set; }
    public string ChargeResult { get; internal set; } = "none";
    public bool InfantryCharging { get; internal set; }
    public int? InfantryChargeTargetId { get; internal set; }
    public double UpgradeStationary { get; internal set; }
    internal Vec2? AmbushPosition;
    internal double LastUpgradeAttack = -1e9;
    internal readonly HashSet<int> PursuitRouts = new();
    public int Charges { get; internal set; }
    public int RoutEvents { get; internal set; }
    public int RallyEvents { get; internal set; }
    public double Width => TransitCompact?12:Archetype.Category == UnitCategory.Infantry ? Formations.Get(Formation).Width : Archetype.Category == UnitCategory.Cavalry ? 40 : 28;
    public double Depth => TransitCompact?(Archetype.Category==UnitCategory.Cavalry?60:42):Archetype.Category == UnitCategory.Infantry ? Formations.Get(Formation).Depth : 18;
    public double Congestion { get; internal set; }
    public double CongestionSpeed { get; internal set; } = 1;
    public double CongestionLoss { get; internal set; }
    internal double Impedance, Disruption;
    public bool Limbered { get; internal set; }
    public double LimberLeft { get; internal set; }
    public double SetupLeft { get; internal set; }
    public bool EnemyContact { get; internal set; }
    public double TerrainSpeed { get; internal set; } = 1;
    public double TerrainLoss { get; internal set; }
    public double ForestCover { get; internal set; }
    public double GroundSlope { get; internal set; }
    internal Vec2? AvoidanceGoal, AvoidanceDestination;
    internal double AvoidanceLeft;
    internal bool AvoidanceUsed;
    internal Vec2? TerrainWaypoint, TerrainDestination;
    internal bool TerrainRouteUsed;
    internal double TerrainRouteLeft;
    public Vec2? SettlingGoal { get; internal set; }
    public double? SettlingFacing { get; internal set; }
    public Vec2? PositionPreference { get; internal set; }
    internal (OrderKind Kind, Vec2? Destination, double? Facing)? PositionKey;
    public double RestTime { get; internal set; }
    public double StationaryOverlap { get; internal set; }
    internal double SettlingRetryAt, SettlingStarted;
    private OrientedRect cachedRect;
    private bool hasRect;
    public OrientedRect Rect
    {
        get
        {
            if (!hasRect || cachedRect.Position != Position || cachedRect.Facing != Facing || cachedRect.Width != Width || cachedRect.Depth != Depth)
            { cachedRect = new(Position, Facing, Width, Depth); hasRect = true; }
            return cachedRect;
        }
    }
    public string MovementState => TransitionLeft > 0 ? "changing formation" : LimberLeft > 0 ? "limbering" : SetupLeft > 0 && Speed < .1 ? "deploying" : EnemyContact ? "enemy contact" : Speed > .1 && (Velocity?.Length ?? 0) > .1 ? "moving" : SettlingGoal is not null && (SettlingGoal.Value - Position).Length > 1 ? "separating" : Order.Destination is { } goal && (goal - Position).Length < 1 && (Order.Facing is null || Math.Abs(Vec2.AngleDelta(Facing, Order.Facing.Value)) < .001) ? "arrived" : "holding";
    public Regiment(int id, int army, string name, RegimentArchetype archetype, Vec2 position, double facing = 0, Formation? formation = null, CommanderIdentity? commander = null)
    {
        Id = id; Army = army; Name = name; Archetype = archetype; Position = position; Facing = facing;
        Formation = formation ?? archetype.DefaultFormation; Strength = archetype.Strength; Morale = archetype.InitialMorale;
        CommanderAssigned=commander is not null;Commander = commander ?? new($"live-{id}", $"Commander {id + 1}");
        if (!archetype.Formations.Contains(Formation)) throw new ArgumentException("Unsupported initial formation");
    }
}
