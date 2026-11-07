using System.Text.Json.Serialization;
namespace Quiberon.Simulation;

/// <summary>Metres, X right/Y down, clockwise radians, double precision.</summary>
public readonly record struct Vec2(double X, double Y)
{
    public override string ToString() => FormattableString.Invariant($"({X}, {Y})");
    public static Vec2 Zero => new(0, 0);
    [JsonIgnore] public double Length => Math.Sqrt(X * X + Y * Y);
    [JsonIgnore] public double LengthSquared => X * X + Y * Y;
    [JsonIgnore] public bool Finite => double.IsFinite(X) && double.IsFinite(Y);
    [JsonIgnore] public Vec2 Normalized => Length > 0 ? this / Length : Zero;
    public double Dot(Vec2 b) => X * b.X + Y * b.Y;
    public static double Cross(Vec2 a, Vec2 b) => a.X * b.Y - a.Y * b.X;
    public static Vec2 operator +(Vec2 a, Vec2 b) => new(a.X + b.X, a.Y + b.Y);
    public static Vec2 operator -(Vec2 a, Vec2 b) => new(a.X - b.X, a.Y - b.Y);
    public static Vec2 operator *(Vec2 a, double b) => new(a.X * b, a.Y * b);
    public static Vec2 operator /(Vec2 a, double b) => a * (1 / b);
    public static Vec2 Direction(double angle) => new(Math.Cos(angle), Math.Sin(angle));
    public static double AngleTo(Vec2 a, Vec2 b) => Math.Atan2(b.Y - a.Y, b.X - a.X);
    public static double AngleDelta(double a, double b)
    {
        double value = (b - a + Math.PI) % Math.Tau;
        return (value < 0 ? value + Math.Tau : value) - Math.PI;
    }
}
