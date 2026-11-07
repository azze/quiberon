namespace Quiberon.Simulation;

public enum OrderKind { Hold, Move, Defend, Reserve, Advance, Attack, Charge, Pursue, Disengage, Reform, Withdraw, Skirmish, FireAt, HoldFire, ResumeFire }
public sealed record Order(OrderKind Kind = OrderKind.Hold, Vec2? Destination = null, double? Facing = null, int? TargetId = null,string? ViaCrossing=null);
public sealed record Command(int RegimentId, Order? Order = null, Formation? Formation = null, AutonomyMode? Autonomy = null);
public enum AutonomyMode { Ordered, Autonomous, Hold }
public sealed record CommanderIdentity(string Id, string Name, string Rank = "", string Background = "Generic",
    string Personality = "methodical", string Specialization = "inspirer", string Biography = "", string Nation = "",
    IReadOnlyList<string>? Upgrades = null, string DefinitionId = "")
{
    [System.Text.Json.Serialization.JsonIgnore]
    public string DisplayName => $"{Rank} {Name}".Trim();
}
