using System.Text.Json;
using System.Text.Json.Serialization;
namespace Quiberon.Simulation;

public sealed record UnitDefinition
{
    public bool NonCombatant {get;init;}
    public int Id { get; init; }
    public int Army { get; init; }
    public string Archetype { get; init; } = "infantry";
    public string Name { get; init; } = "Regiment";
    public Vec2 Position { get; init; }
    public double Facing { get; init; }
    public Formation? Formation { get; init; }
    public double Cohesion { get; init; } = 100;
    public double Fatigue { get; init; }
    public int? Strength { get; init; }
    public double? Morale { get; init; }
    public MoraleState State { get; init; }
    public double SafeTime { get; init; }
    public CommanderIdentity? Commander { get; init; }
    public AutonomyMode? Autonomy { get; init; }
    public Order? Order { get; init; }
}
public sealed record ScheduledCommand(int Tick, int RegimentId, Order? Order = null, Formation? Formation = null)
{
    public Command Command => new(RegimentId, Order, Formation);
}
public sealed record TerrainDefinition
{
    public Hill[] Hills {get;init;}=[];
    public Forest[] Forests {get;init;}=[];
    public EnvironmentDefinition? Environment {get;init;}
    [JsonConstructor] public TerrainDefinition() { }
    public TerrainDefinition(Hill[] hills,Forest[] forests,EnvironmentDefinition? environment=null){Hills=hills;Forests=forests;Environment=environment;}
}
public sealed record ScenarioDefinition
{
    public string Name { get; init; } = "movement";
    public int Version { get; init; } = 1;
    public long Seed { get; init; } = 17;
    public double Width { get; init; } = 1000;
    public double Height { get; init; } = 600;
    public double Duration { get; init; } = 60;
    public int[] SampleTicks { get; init; } = [0, 10, 100, 600];
    public UnitDefinition[] Units { get; init; } = [];
    public ArmyCommanderAssignment[] ArmyCommanders { get; init; } = [];
    public ScheduledCommand[] Commands { get; init; } = [];
    public TerrainDefinition? Terrain { get; init; }
    public bool AiEnabled { get; init; }
    public int AiDecisionTicks { get; init; } = 50;
    public bool CommandersEnabled { get; init; }
    public long CommanderSeed { get; init; } = 1729;
    public int[] AiArmies { get; init; } = [];
    public Dictionary<int,string> AiStrategies { get; init; } = new();
    public bool CombatEnabled { get; init; }
    public bool ArtilleryEnabled { get; init; }
    public bool SpecialistsEnabled { get; init; }
    public bool MoraleEnabled { get; init; }
    public bool CavalryEnabled { get; init; }
    public double MeleeDisengageDistance { get; init; } = 4;
    public double[]? RandomDraws { get; init; }
    public MissionDefinition? Mission {get;init;}
    public BattleSimulation Create(bool measureAllocations=false)
    {
        if (Version != 1 || !double.IsFinite(Duration) || Duration < 0 || Duration > 100000 || Commands.Any(c => c.Tick < 0)) throw new ArgumentException("Invalid simulation scenario");
        var battle=new BattleSimulation(Units.Select(u => new Regiment(u.Id, u.Army, u.Name, u.NonCombatant ? Archetypes.Get(u.Archetype) with{Weapon=null,Melee=0,Speed=1.5,Guns=0,Role="transport"}:Archetypes.Get(u.Archetype), u.Position, u.Facing, u.Formation, u.Commander) { NonCombatant=u.NonCombatant,Cohesion = Math.Clamp(u.Cohesion, 0, 100), Fatigue = Math.Clamp(u.Fatigue, 0, 100),Strength=Math.Clamp(u.Strength??Archetypes.Get(u.Archetype).Strength,0,Archetypes.Get(u.Archetype).Strength),Morale=Math.Clamp(u.Morale??Archetypes.Get(u.Archetype).InitialMorale,0,100),State=u.State,SafeTime=Math.Max(0,u.SafeTime) }), new() { Width = Width, Height = Height,AiEnabled=AiEnabled,AiDecisionTicks=AiDecisionTicks,CommandersEnabled=CommandersEnabled,CommanderSeed=CommanderSeed,CombatEnabled=CombatEnabled,MeleeDisengageDistance=MeleeDisengageDistance,MoraleEnabled=MoraleEnabled,CavalryEnabled=CavalryEnabled,ArtilleryEnabled=ArtilleryEnabled,SpecialistsEnabled=SpecialistsEnabled,MeasureAllocations=measureAllocations }, new TerrainMap(Terrain?.Hills, Terrain?.Forests,Terrain?.Environment), Seed,RandomDraws is null?null:new TapeRandom(RandomDraws));
        battle.SetArmyCommanders(ArmyCommanders);
        foreach(int army in AiArmies.Order())battle.Ai.ConfigureArmy(army,AiStrategies.GetValueOrDefault(army,battle.ArmyCommanders.Any(a=>a.Army==army && HistoricalCommanders.Get(a.CommanderId).Specialization=="speed_and_shock")?"all_out_attack":"balanced"));
        foreach(var u in Units)if(u.Autonomy is { } mode){var actual=battle.Unit(u.Id)!;actual.Autonomy=mode;actual.PlayerOrder=mode!=AutonomyMode.Autonomous;}
        foreach(var u in Units)if(u.Order is { } order){if(order.ViaCrossing is { } via && !battle.Terrain.Environment.Crossings.Any(c=>c.Definition.Id==via))throw new ArgumentException("Unknown movement crossing.");battle.Unit(u.Id)!.Order=order;}
        if(Mission is not null)battle.SetMission(Mission);
        return battle;
    }
    public void IssueScheduled(BattleSimulation battle)
    { foreach (var c in Commands) if (c.Tick == battle.Tick) battle.Issue(c.Command); }
    public static ScenarioDefinition Load(string path) => JsonSerializer.Deserialize<ScenarioDefinition>(File.ReadAllText(path), ScenarioJson.Options) ?? throw new InvalidDataException("Empty scenario");
    public static ScenarioDefinition Sandbox(int count = 8, bool terrain = false)
    {
        if (count < 2 || count > 256) throw new ArgumentOutOfRangeException(nameof(count));
        var units = new List<UnitDefinition>();
        if (count == 8)
        {
            for (int i = 0; i < 4; i++) units.Add(new() { Id = i, Army = 0, Name = $"Blue Line Infantry {i + 1}", Position = new(260, 130 + i * 100) });
            units.Add(new() { Id = 4, Army = 0, Name = "Blue Cavalry", Archetype = "cavalry", Position = new(160, 70) });
            units.Add(new() { Id = 5, Army = 0, Name = "Blue Battery", Archetype = "artillery", Position = new(160, 470) });
            for (int i = 0; i < 2; i++) units.Add(new() { Id = 6 + i, Army = 1, Name = $"Red Line Infantry {i + 1}", Position = new(760, 230 + i * 150), Facing = Math.PI });
        }
        else
        {
            string[] roster = ["infantry", "infantry", "cavalry", "artillery", "haudenosaunee_skirmishers"];
            for (int i = 0; i < count; i++) units.Add(new() { Id = i, Army = i < Math.Max(1, count - 2) ? 0 : 1, Archetype = roster[i % roster.Length], Name = $"Movement Regiment {i + 1}", Position = new(180 + i % 6 * 100, 75 + i / 6 * 75) });
        }
        return new() { Name = terrain ? "Terrain March" : "Live Movement Sandbox", Width = 1000, Height = Math.Max(600, Math.Ceiling(count / 6.0) * 75 + 100), Units = units.ToArray(), Terrain = terrain ? new([new(500, 300, 95, 110, 30, true)], [new(450, 150, 95, 95, .9), new(620, 430, 105, 90, .6)]) : null };
    }
}
public static class ScenarioJson
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase, PropertyNameCaseInsensitive = true,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) }, WriteIndented = true
    };
}
