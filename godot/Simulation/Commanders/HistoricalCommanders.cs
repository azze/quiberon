using System.Text.Json;
namespace Quiberon.Simulation;

public sealed record HistoricalCommanderDefinition(string Id, string Name, string Faction, string Personality,
    string Specialization, string SpecializationName, string CampaignRole, IReadOnlyList<string> Availability,
    IReadOnlyList<string> Categories, string Description, string Notes, IReadOnlyList<string> AlternativeNames,
    string Nation = "", bool ArmyLevel = false, IReadOnlyList<string>? IntendedRoles = null)
{
    public CommanderIdentity Create() => new("historical-" + Id, Name, Background: Faction, Personality: Personality,
        Specialization: Specialization, Biography: Description, Nation: Nation, DefinitionId: Id);
}
public sealed record ArmyCommanderAssignment(int Army, string CommanderId, Vec2? Position = null);

/// <summary>Authored definitions stay separate from fictional officer generation and acquired upgrades.</summary>
public static class HistoricalCommanders
{
    public static IReadOnlyList<HistoricalCommanderDefinition> All { get; } = Load();
    private static readonly Dictionary<string, HistoricalCommanderDefinition> byId = All.ToDictionary(d => d.Id, StringComparer.Ordinal);
    public static HistoricalCommanderDefinition Get(string id) => byId.TryGetValue(id, out var d) ? d : throw new ArgumentException("Unknown historical commander: " + id);
    public static bool Has(Regiment u, string signature) => u.CommandersEnabled && u.Commander.DefinitionId.Length > 0 && u.Commander.Specialization == signature;
    public static void Validate(CommanderIdentity c, UnitCategory category)
    {
        var d = Get(c.DefinitionId);
        if (d.ArmyLevel || !d.Categories.Contains(category.ToString().ToLowerInvariant()) || c.Name != d.Name || c.Background != d.Faction || c.Specialization != d.Specialization || c.Personality != d.Personality)
            throw new ArgumentException("Historical commander identity, role or signature is incompatible.");
    }
    public static void ValidateAssignments(IEnumerable<CommanderIdentity> officers, IEnumerable<ArmyCommanderAssignment> leaders, IEnumerable<int> armies)
    {
        var roster=officers.ToArray();
        var ids = new HashSet<string>(StringComparer.Ordinal); var sides = new HashSet<int>();
        foreach (var c in roster.Where(c => c.DefinitionId.Length > 0))
        {
            if (!ids.Add(c.DefinitionId)) throw new ArgumentException("A historical individual cannot appear twice in a battle.");
            var d=Get(c.DefinitionId);
            if(roster.Any(other=>other.DefinitionId.Length==0 && (other.Name==d.Name || d.AlternativeNames.Contains(other.Name))))
                throw new ArgumentException("A generated officer uses this historical name or alternative name; reroll that officer before assigning the historical individual.");
        }
        foreach (var a in leaders)
        {
            var d = Get(a.CommanderId);
            if (!d.ArmyLevel || !armies.Contains(a.Army) || !sides.Add(a.Army) || !ids.Add(d.Id) || a.Position is { Finite: false })
                throw new ArgumentException("Invalid or duplicate army commander assignment.");
        }
    }
    private static IReadOnlyList<HistoricalCommanderDefinition> Load()
    {
        using var stream = typeof(HistoricalCommanders).Assembly.GetManifestResourceStream("commonwealth_commanders.json")!;
        var definitions = JsonSerializer.Deserialize<HistoricalCommanderDefinition[]>(stream, ScenarioJson.Options)!;
        return Array.AsReadOnly(definitions.Select(d => d with {
            Availability = Array.AsReadOnly(d.Availability.ToArray()), Categories = Array.AsReadOnly(d.Categories.ToArray()),
            AlternativeNames = Array.AsReadOnly(d.AlternativeNames.ToArray()), IntendedRoles = Array.AsReadOnly((d.IntendedRoles??[]).ToArray()) }).ToArray());
    }
}
