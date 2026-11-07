using System.Text.Json;
namespace Quiberon.Simulation;

public sealed record UpgradeDefinition(string Id, string Name, string Description, string[] Categories,
    string[] Roles, bool LineRequired, int MaxRank, string[] Prerequisites);

/// <summary>Commander-owned sandbox abilities. No campaign state or reward machinery.</summary>
public static class UpgradeSystem
{
    private static readonly JsonDocument data = JsonDocument.Parse(typeof(UpgradeSystem).Assembly.GetManifestResourceStream("commander_upgrades.json")!);
    public static int Limit => data.RootElement.GetProperty("limit").GetInt32();
    public static IReadOnlyList<UpgradeDefinition> Definitions { get; } = Array.AsReadOnly(data.RootElement.GetProperty("definitions").Deserialize<UpgradeDefinition[]>(ScenarioJson.Options)!);
    private static readonly Dictionary<string, UpgradeDefinition> registry = Definitions.ToDictionary(d => d.Id);
    private static readonly Dictionary<string, double> tuning = data.RootElement.GetProperty("tuning").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetDouble());
    public static double T(string id) => tuning[id];
    public static bool Has(Regiment u, string id) => u.CommandersEnabled && u.Commander.Upgrades?.Contains(id) == true;
    public static string Role(RegimentArchetype a) => a.Id switch
    {
        "haudenosaunee_skirmishers" => "skirmisher", "revolutionary_rifles" => "rifles",
        "royal_grenadiers" => "anchor", "commonwealth_uhlans" => "flanker",
        _ => a.Category.ToString().ToLowerInvariant()
    };
    public static bool Eligible(RegimentArchetype a, string id) => registry.TryGetValue(id, out var d) &&
        d.Categories.Contains(a.Category.ToString().ToLowerInvariant()) &&
        (d.Roles.Length == 0 || d.Roles.Contains(Role(a))) && (!d.LineRequired || a.Formations.Contains(Formation.Line));
    public static IEnumerable<UpgradeDefinition> Available(RegimentArchetype a, CommanderIdentity c) =>
        (c.Upgrades?.Count ?? 0) >= Limit ? [] : Definitions.Where(d => Eligible(a, d.Id) &&
            c.Upgrades?.Contains(d.Id) != true && d.Prerequisites.All(p => c.Upgrades?.Contains(p) == true));
    public static void Validate(CommanderIdentity c, RegimentArchetype a)
    {
        var keys = c.Upgrades ?? [];
        if (keys.Count > Limit || keys.Distinct().Count() != keys.Count || keys.Any(k => k is null || !Eligible(a, k) || !registry[k].Prerequisites.All(keys.Contains)))
            throw new ArgumentException($"Commander upgrades must be unique, compatible and limited to {Limit}.");
    }
    public static CommanderIdentity Freeze(CommanderIdentity c) => c with { Upgrades = c.Upgrades is null ? null : Array.AsReadOnly(c.Upgrades.ToArray()) };
    public static bool Prepared(Regiment u) => u.Speed < .1 && u.State == MoraleState.Steady && u.Cohesion >= 60 &&
        u.TransitionLeft <= 0 && u.Formation == Formation.Line && CommanderSystem.Defending(u);
    public static void UpdateStationary(Regiment u) => u.UpgradeStationary = u.Speed < .1 && !u.Limbered && u.SetupLeft <= 0 && u.TransitionLeft <= 0 ? u.UpgradeStationary + Rules.Dt : 0;
    public static double VolleyReload(BattleSimulation b, Regiment u)
    {
        if (!Has(u, "rolling_volley") || u.Formation != Formation.Line || u.Cohesion < 70 || u.Speed > .1) return 1;
        foreach (var f in b.Combat.Nearby(u.Position, 90))
            if (f.Id != u.Id && f.Army == u.Army && f.Effective && f.State == MoraleState.Steady && f.Archetype.Category == UnitCategory.Infantry &&
                (f.Position - u.Position).Length <= 90 && b.Combat.Sight(u, f).Visible)
            { SpecialistSystem.Activate(b, u, "Rolling Volley: supporting infantry fire"); return T("rolling_reload"); }
        return 1;
    }
    public static void OnVolley(BattleSimulation b, Regiment u, Regiment target, int losses)
    {
        if (Has(u, "woodland_ambush"))
        {
            bool reset = u.AmbushPosition is null || b.Time - u.LastUpgradeAttack >= T("ambush_reset") && (u.Position - u.AmbushPosition.Value).Length >= T("ambush_move");
            if (reset && b.Combat.ForestCover(u) >= .4 && u.Speed < .1 && b.Combat.Sight(target, u).Transmission < .7)
            {
                u.AmbushPosition = u.Position;
                b.Combat.Damage(target, 0, u, T("ambush_shock"), "woodland ambush");
                target.Cohesion = Math.Max(0, target.Cohesion - T("ambush_cohesion"));
                b.Emit("upgrade", u, target, u.Position, 2, 0, "Woodland Ambush: concealed opening volley");
            }
        }
        if (losses > 0 && Has(u, "harassing_fire"))
        { target.Cohesion = Math.Max(0, target.Cohesion - T("harassing_cohesion")); SpecialistSystem.Activate(b, u, "Harassing Fire: formation disrupted"); }
        u.LastUpgradeAttack = b.Time;
    }
    public static void Inspired(BattleSimulation b, Regiment u, Regiment target, int losses)
    {
        if (losses <= 0 || !Has(u, "inspired_attack") || target.State is not (MoraleState.Wavering or MoraleState.Routing) || b.Time < b.InspirationNext.GetValueOrDefault(u.Army)) return;
        b.InspirationNext[u.Army] = b.Time + T("inspired_cooldown");
        foreach (var f in b.Combat.Nearby(u.Position, 100))
            if (f.Id != u.Id && f.Army == u.Army && f.Active && f.State != MoraleState.Routing && (f.Position - u.Position).Length < 100 && b.Combat.Sight(u, f).Visible)
                f.Morale = Math.Min(100, f.Morale + T("inspired_morale"));
        b.Emit("upgrade", u, target, u.Position, 2, 0, "Inspired Attack: nearby allies encouraged");
    }
    public static void OnRout(BattleSimulation b, Regiment target)
    {
        var u = b.Unit(target.LastAttackerId ?? -1);
        if (u is null || !u.Effective || u.Army == target.Army || !Has(u, "relentless_pursuit") || !u.PursuitRouts.Add(target.Id)) return;
        u.Cohesion = Math.Min(100, u.Cohesion + T("pursuit_recovery"));
        b.Emit("upgrade", u, target, u.Position, 2, 0, "Relentless Pursuit: exploiting an enemy rout");
    }
    public static double ChargeShock(Regiment u, Regiment target, double momentum, bool prepared) => Has(u, "shock_commander") && !prepared && momentum > .25 &&
        (target.State != MoraleState.Steady || target.Cohesion < 60 || Math.Abs(Vec2.AngleDelta(target.Facing, Vec2.AngleTo(target.Position, u.Position))) > 1.0472) ? T("shock") : 1;
    public static string Describe(Regiment u) => string.Join("\n", (u.Commander.Upgrades ?? []).Select(id => registry[id].Name + (id switch
    {
        "calculated_fire" => u.UpgradeStationary >= T("calculated_seconds") ? " (prepared)" : $" (preparing {u.UpgradeStationary:F1}/6 s)",
        "steadfast_defence" => Prepared(u) ? " (active)" : " (requires steady defensive line)",
        "woodland_ambush" => u.AmbushPosition is null ? " (opening volley available)" : " (requires disengagement and relocation)",
        _ => ""
    })));
}
