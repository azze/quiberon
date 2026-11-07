using System.Diagnostics;
namespace Quiberon.Simulation;

/// <summary>Retains overload debt; never skips ticks or alters their duration.</summary>
public sealed class SimulationClock
{
    public BattleSimulation Battle { get; }
    public bool Playing { get; set; } = true;
    public double Speed { get; set; } = 1;
    public double Accumulator { get; private set; }
    public int MaxTicksPerAdvance { get; set; } = 16;
    public double Alpha { get; private set; }
    public int StepsLastAdvance { get; private set; }
    public double LastTickMilliseconds { get; private set; }
    public BattleSnapshot Previous { get; private set; }
    public BattleSnapshot Current { get; private set; }
    private readonly Action<BattleSimulation>? beforeTick;
    public SimulationClock(BattleSimulation battle, Action<BattleSimulation>? beforeTick = null)
    { Battle = battle; this.beforeTick = beforeTick; Previous = Current = battle.Snapshot(); }
    public void RefreshState() { Previous=Current=Battle.Snapshot(); }
    public int Advance(double realSeconds)
    {
        if (!double.IsFinite(realSeconds) || realSeconds < 0 || !double.IsFinite(Speed) || Speed < 0 || Speed > 10 || MaxTicksPerAdvance < 1) throw new ArgumentOutOfRangeException(nameof(realSeconds));
        StepsLastAdvance = 0;
        if (!Playing || Battle.Result is not null) return 0;
        Accumulator += realSeconds * Speed;
        while (Accumulator + 1e-12 >= Rules.Dt && StepsLastAdvance < MaxTicksPerAdvance)
        {
            Step(); Accumulator = Math.Max(0, Accumulator - Rules.Dt); StepsLastAdvance++;
            if(Battle.Result is not null){Playing=false;Alpha=1;return StepsLastAdvance;}
        }
        Alpha = Math.Clamp(Accumulator / Rules.Dt, 0, 1);
        return StepsLastAdvance;
    }
    private void Step()
    {
        Previous = Current; long start = Stopwatch.GetTimestamp(); beforeTick?.Invoke(Battle); Battle.Step();
        LastTickMilliseconds = Stopwatch.GetElapsedTime(start).TotalMilliseconds;
        Current = Battle.Snapshot();
    }
    public bool SingleStep()
    {
        if (Playing || Battle.Result is not null) return false;
        Step(); Alpha = 1; return true;
    }
}
