using System.Text.Json;
namespace Quiberon.Simulation;

public sealed record WeaponProfile(string Id = "musket", double Range = 155, double ReloadSeconds = 12, double Accuracy = 1);
public sealed record RegimentArchetype(string Id, string Name, string Faction, string Symbol, UnitCategory Category,
    int Strength, double Speed, double TurnRate, IReadOnlyList<Formation> Formations, Formation DefaultFormation,
    double InitialMorale = 85, double ForestSlow = 1, double ForestLoss = 1, double SlopeLoss = 1,
    double Recovery = 1, double LimberSeconds = 0, double SetupSeconds = 0, int Guns = 0,
    WeaponProfile? Weapon = null, double Discipline = 1, double Melee = 1,
    double ShockResistance = 1, double ChargeSpeed = 1, double Pursuit = 1,
    double MeleeDamage = 1, double MeleeShock = 1, string Trait = "", string Ability = "",
    double Concealment = 1, double ForestFire = 1, double ForestVision = 1, double ForestAim = 1,
    double ForestAccuracy = 1, double ForestMeleeDamage = 1, double ForestMeleeShock = 1, double ProjectilePower = 1,
    string Role = "", bool CampaignCore = false, string CampaignName = "", IReadOnlyList<string>? Tags = null,
    double ManoeuvreLoss = 1, double FormationTime = 1, double DefensiveResolve = 1,
    double Impact = 1, double CanisterRange = 0)
{
    public bool MeleeOnly => Category == UnitCategory.Infantry && Weapon is null && Role == "assault";
    public bool Citizen => Tags?.Contains("citizen") == true;
    public bool Skirmisher => Role is "skirmisher" or "rifles";
    public string DisplayName => CampaignName.Length > 0 ? CampaignName : Name;
}

public static class Archetypes
{
    private static readonly Dictionary<string, RegimentArchetype> definitions = Load();
    public static IEnumerable<RegimentArchetype> All => definitions.Values;
    public static RegimentArchetype Get(string id) => definitions.TryGetValue(id, out var value) ? value : throw new ArgumentException($"Unknown movement archetype: {id}");
    private static Dictionary<string, RegimentArchetype> Load()
    {
        using var stream = typeof(Archetypes).Assembly.GetManifestResourceStream("movement_archetypes.json")!;
        var list = JsonSerializer.Deserialize<RegimentArchetype[]>(stream, ScenarioJson.Options) ?? throw new InvalidDataException("Missing archetypes");
        return list.Select(a => a with { Formations = Array.AsReadOnly(a.Formations.ToArray()), Tags = Array.AsReadOnly((a.Tags??[]).ToArray()) }).ToDictionary(a => a.Id, StringComparer.Ordinal);
    }
}
