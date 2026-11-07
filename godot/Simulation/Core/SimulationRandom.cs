namespace Quiberon.Simulation;

public interface ISimulationRandom
{
    double NextDouble();
    long Draws { get; }
}

/// <summary>SplitMix64-v1: specified unsigned wraparound and top-53-bit doubles.
/// This does not claim compatibility with Python random.Random or System.Random.</summary>
public sealed class SimulationRandom(long seed) : ISimulationRandom
{
    private ulong state = unchecked((ulong)seed);
    public long Draws { get; private set; }
    public double NextDouble()
    {
        unchecked
        {
            state += 0x9E3779B97F4A7C15UL;
            ulong z = state;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            z ^= z >> 31; Draws++;
            return (z >> 11) * (1.0 / 9007199254740992.0);
        }
    }
}

/// <summary>Finite controlled test draws; exhaustion fails instead of recycling.</summary>
public sealed class TapeRandom : ISimulationRandom
{
    private readonly double[] values;
    public long Draws { get; private set; }
    public TapeRandom(IEnumerable<double> values)
    {
        this.values = values.ToArray();
        if (this.values.Any(x => !double.IsFinite(x) || x < 0 || x >= 1)) throw new ArgumentException("Random draws must be in [0,1)");
    }
    public double NextDouble() => Draws < values.Length ? values[Draws++] : throw new InvalidOperationException("Controlled random tape exhausted");
}
