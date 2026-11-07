namespace Quiberon.Simulation;

public enum CombatState { Idle, Firing, Melee, Destroyed, Pursuit, Withdrawn }
public sealed record SimulationEvent(long Sequence, int Tick, double Time, string Kind,
    int UnitId, int? TargetId, Vec2 Position, double Facing, double Width,
    double Duration, int Losses, string Message);
public sealed record BattleResult(int? WinnerArmy, int Tick, double Time, string Rule = "temporary infantry annihilation")
{
    public string Id => WinnerArmy is { } army ? $"army_{army}" : "draw";
}
public sealed class CombatMetrics
{
    public long AiDecisions { get; internal set; }
    public long AiTargetEvaluations { get; internal set; }
    public double AiMilliseconds { get; internal set; }
    public long AiOrders { get; internal set; }
    public long AiTargetChanges { get; internal set; }
    public long AiFormationChanges { get; internal set; }
    public double? FirstEngagement { get; internal set; }
    public long ArtilleryShots { get; internal set; }
    public long ProjectileCollisionChecks { get; internal set; }
    public long ProjectileHits { get; internal set; }
    public long ProjectileBounces { get; internal set; }
    public long FriendlyFireHits { get; internal set; }
    public int PeakProjectiles { get; internal set; }
    public long Volleys { get; internal set; }
    public long Casualties { get; internal set; }
    public long MeleePulses { get; internal set; }
    public long VisibilityQueries { get; internal set; }
    public long VisibilityCalculations { get; internal set; }
    public long VisibilitySamples { get; internal set; }
    public long FiringBlockerChecks { get; internal set; }
    public long Routs { get; internal set; }
    public long Rallies { get; internal set; }
    public long CascadeShocks { get; internal set; }
    public long Escapes { get; internal set; }
    public long ChargeStarts { get; internal set; }
    public long ChargeImpacts { get; internal set; }
    public long FailedCharges { get; internal set; }
    public long AbortedCharges { get; internal set; }
    public long ImpactCasualties { get; internal set; }
    public double ImpactMomentum { get; internal set; }
    public double ImpactMoraleShock { get; internal set; }
    public long ChargeSuccesses { get; internal set; }
    public long PursuitPulses { get; internal set; }
    public long PursuitCasualties { get; internal set; }
    public long PursuitLosses { get; internal set; }
    public double PursuitSeconds { get; internal set; }
    // Optional diagnostic pass only; normal benchmark timings leave it off.
    public long IntentAllocatedBytes { get; internal set; }
    public long MovementAllocatedBytes { get; internal set; }
    public long CombatAllocatedBytes { get; internal set; }
    public long MoraleAllocatedBytes { get; internal set; }
}
