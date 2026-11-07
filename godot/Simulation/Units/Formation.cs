namespace Quiberon.Simulation;

public enum UnitCategory { Infantry, Cavalry, Artillery }
public enum Formation { Line, Column, Skirmish }
public readonly record struct FormationProfile(double Width, double Depth, double Speed, double Turn, double CongestionSpeed, double CongestionLoss);
public static class Formations
{
    public static FormationProfile Get(Formation value) => value switch
    {
        Formation.Line => new(64, 12, .75, .65, .45, 2.4),
        Formation.Column => new(22, 34, 1, 1, .25, .9),
        Formation.Skirmish => new(78, 28, .94, 1.15, .30, 1.1),
        _ => throw new ArgumentOutOfRangeException(nameof(value))
    };
}
