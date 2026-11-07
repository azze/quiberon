namespace Quiberon.Simulation;

/// <summary>Ported movement, combat, morale, cavalry and bayonet-charge tuning.</summary>
public sealed record Rules
{
    public const double Dt = .1;
    public bool AiEnabled { get; init; }
    public bool CommandersEnabled { get; init; }
    public long CommanderSeed { get; init; } = 1729;
    public int AiDecisionTicks { get; init; } = 50;
    public bool AiDebug { get; init; }
    public bool CombatEnabled { get; init; }
    public bool ArtilleryEnabled { get; init; }
    public bool SpecialistsEnabled { get; init; }
    public double Gravity { get; init; } = 9.81;
    public double ProjectileLifetime { get; init; } = 14;
    public double ArtilleryScatter { get; init; } = 45;
    public double ArtilleryVerticalScatter { get; init; } = 3;
    public double ProjectileStep { get; init; } = 2;
    public double ProjectileForestDrag { get; init; } = .008;
    // False only for preserved M1/M2 movement/frozen-morale reference fixtures.
    public bool MoraleEnabled { get; init; }
    public bool CavalryEnabled { get; init; }
    public bool InfantryChargesEnabled { get; init; } = true;
    public double InfantryChargeRange { get; init; } = 55;
    public double InfantryChargeSpeed { get; init; } = 1.20;
    public double InfantryChargeAcceleration { get; init; } = .8;
    public double InfantryChargeMinCohesion { get; init; } = 35;
    public double InfantryChargeMinRun { get; init; } = 4;
    public double InfantryChargeCooldown { get; init; } = 20;
    public double InfantryChargeClearance { get; init; } = 18;
    public double InfantryChargeReform { get; init; } = 3;
    public double InfantryChargeDamage { get; init; } = .035;
    public double InfantryChargeShock { get; init; } = 6;
    public bool MeasureAllocations { get; init; }
    public double CasualtyMorale { get; init; } = 95;
    public double RoutThreshold { get; init; } = 23;
    public double RoutingCohesionLoss { get; init; } = 1;
    public double RoutRadius { get; init; } = 145;
    public double RoutShock { get; init; } = 15;
    public double RallySafeSeconds { get; init; } = 22;
    public double ThreatRadius { get; init; } = 160;
    public double RoutThreatRadius { get; init; } = 240;
    public double RoutPlanSeconds { get; init; } = 1;
    public double RoutLookahead { get; init; } = 60;
    public double RoutExitMargin { get; init; } = 2;
    public double RoutingMeleeFactor { get; init; } = .10;
    public double RallyingMeleeFactor { get; init; } = .25;
    public double RallyingMeleeMax { get; init; } = .60;
    public double ShakenMeleeFactor { get; init; } = .70;
    public double WaveringMeleeFactor { get; init; } = .40;
    public double ShakenAccuracyFactor { get; init; } = .80;
    public double WaveringAccuracyFactor { get; init; } = .55;
    public double ChargeRange { get; init; } = 100;
    public double ChargeMinRun { get; init; } = 12;
    public double ChargeMaxSpeed { get; init; } = 12;
    public double ChargeAcceleration { get; init; } = 2;
    public double ChargeTurnMultiplier { get; init; } = .5;
    public double ChargeMinCohesion { get; init; } = 50;
    public double ChargeMinSpeed { get; init; } = 3;
    public double ChargeMaxForest { get; init; } = .45;
    public double ChargeMaxSlope { get; init; } = .25;
    public double ChargeMaxSeconds { get; init; } = 16;
    public double ChargeCooldownSeconds { get; init; } = 20;
    public double ChargeReformSeconds { get; init; } = 4;
    public double ChargeClearance { get; init; } = 30;
    public double ChargeDamage { get; init; } = .20;
    public double ChargeShock { get; init; } = 24;
    public double ChargeCohesionDamage { get; init; } = 18;
    public double ChargeRecoilDistance { get; init; } = 40;
    public double CavalryMeleeFactor { get; init; } = .80;
    public double PursuitInterval { get; init; } = 2;
    public double PursuitContactGap { get; init; } = 6;
    public double PursuitMinCohesion { get; init; } = 25;
    public double PursuitMaxFatigue { get; init; } = 85;
    public double PursuitDamage { get; init; } = .12;
    public double PursuitMaxFraction { get; init; } = .12;
    public double PursuitResistance { get; init; } = .03;
    public double CongestionSharedPursuit { get; init; } = .02;
    public double PursuitLaneSpacing { get; init; } = 16;
    public double DefeatFraction { get; init; } = .18;
    public double DefeatGraceSeconds { get; init; } = 12;
    public double FiringHalfArc { get; init; } = .65;
    public double MusketAccuracy { get; init; } = .14;
    public double InfantryVolleyDamage { get; init; } = 1.10;
    public double MeleeInterval { get; init; } = 2;
    // New engagements still need .75 m contact. Existing fights release at 4 m.
    public double MeleeDisengageDistance { get; init; } = 4;
    public double FriendlyLooseDensity { get; init; } = .35;
    public double FriendlyFireClearance { get; init; } = .5;
    public double ArtilleryMeleeVulnerability { get; init; } = 1.25;
    public double Width { get; init; } = 1000;
    public double Height { get; init; } = 600;
    public double FormationSeconds { get; init; } = 7;
    public double CongestionMinSpeed { get; init; } = .5;
    public double CongestionStationaryLoss { get; init; } = .35;
    public double CongestionSameDirection { get; init; } = .20;
    public double CongestionCavalrySameDirection { get; init; } = .06;
    public double CongestionOvertaking { get; init; } = .35;
    public double SettlingOverlap { get; init; } = .25;
    public double SettlingDelay { get; init; } = 2;
    public double SettlingRetry { get; init; } = 5;
    public double SettlingTimeout { get; init; } = 60;
    public double SettlingRadius { get; init; } = 110;
    public double SettlingGap { get; init; } = 4;
    public bool AvoidanceEnabled { get; init; } = true;
    public double AvoidanceLookahead { get; init; } = 150;
    public double AvoidanceMargin { get; init; } = 6;
    public double AvoidanceMaxExtra { get; init; } = 100;
    public double AvoidanceMaxRatio { get; init; } = 1.5;
    public double AvoidanceMaxSeconds { get; init; } = 120;
    public double CohesionRestRecovery { get; init; } = .65;
    public double CohesionMoveRecovery { get; init; } = .1;
}
