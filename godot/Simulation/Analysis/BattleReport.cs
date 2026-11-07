using System.Collections.ObjectModel;
namespace Quiberon.Simulation;

public sealed record RegimentReport(int Id,int Army,string Name,string Archetype,string ArchetypeName,string Category,
    CommanderIdentity Commander,int Initial,int Remaining,int Lost,int Inflicted,int Salvos,int Charges,int Routs,int Rallies,
    int Activations,string Status,bool Effective,double Morale,double Cohesion);
public sealed record ArmyReport(int Army,int Initial,int Remaining,int Lost,int Effective,int Destroyed,int Withdrawn,
    int Routing,int Salvos,int Charges,int Routs,int Rallies,int Inflicted);
public sealed record ArchetypeReport(int Army,string Archetype,string Name,int Regiments,int Initial,int Remaining,int Lost,
    int Inflicted,int Salvos,int Charges,int Routs,int Rallies);

/// <summary>Frozen read-only report; casualties exclude living routed/escaped troops.</summary>
public sealed record BattleReport(long Seed,string? Result,double Duration,double Width,double Height,
    ReadOnlyCollection<RegimentReport> Regiments,ReadOnlyCollection<ArmyReport> Armies,
    ReadOnlyCollection<ArchetypeReport> Archetypes,ReadOnlyDictionary<string,double> Metrics)
{
    public static BattleReport Capture(BattleSimulation b)
    {
        var rows=b.Units.Select(u=>new RegimentReport(u.Id,u.Army,u.Name,u.Archetype.Id,u.Archetype.Name,u.Archetype.Category.ToString().ToLowerInvariant(),UpgradeSystem.Freeze(u.Commander),
            b.InitialUnitStrength[u.Id],u.Strength,Math.Max(0,b.InitialUnitStrength[u.Id]-u.Strength),u.DamageInflicted,u.ShotsFired,u.Charges,u.RoutEvents,u.RallyEvents,u.ActivatedAbilities.Count,
            b.Mission is not null && !b.Mission.Arrived(u.Id)?"not-arrived":u.Strength<=0?"destroyed":u.Withdrawn?"withdrawn":u.State.ToString().ToLowerInvariant(),u.Effective,u.Morale,u.Cohesion)).ToArray();
        var armies=rows.GroupBy(r=>r.Army).OrderBy(g=>g.Key).Select(g=>new ArmyReport(g.Key,g.Sum(r=>r.Initial),g.Sum(r=>r.Remaining),g.Sum(r=>r.Lost),g.Where(r=>r.Effective).Sum(r=>r.Remaining),g.Count(r=>r.Status=="destroyed"),g.Count(r=>r.Status=="withdrawn"),g.Count(r=>r.Status=="routing"),g.Sum(r=>r.Salvos),g.Sum(r=>r.Charges),g.Sum(r=>r.Routs),g.Sum(r=>r.Rallies),g.Sum(r=>r.Inflicted))).ToArray();
        var groups=rows.GroupBy(r=>(r.Army,r.Archetype)).OrderBy(g=>g.Key.Army).ThenBy(g=>g.Key.Archetype).Select(g=>new ArchetypeReport(g.Key.Army,g.Key.Archetype,g.First().ArchetypeName,g.Count(),g.Sum(r=>r.Initial),g.Sum(r=>r.Remaining),g.Sum(r=>r.Lost),g.Sum(r=>r.Inflicted),g.Sum(r=>r.Salvos),g.Sum(r=>r.Charges),g.Sum(r=>r.Routs),g.Sum(r=>r.Rallies))).ToArray();
        var metrics=new Dictionary<string,double>{{"salvos",rows.Sum(r=>r.Salvos)},{"casualties",b.Metrics.Casualties},{"friendlyFire",b.Metrics.FriendlyFireHits},{"cascadeShocks",b.Metrics.CascadeShocks},{"routs",b.Metrics.Routs},{"rallies",b.Metrics.Rallies},{"artilleryShots",b.Metrics.ArtilleryShots},{"charges",b.Metrics.ChargeImpacts},{"pursuitCasualties",b.Metrics.PursuitCasualties}};
        return new(b.Seed,b.Result?.Id,b.Time,b.Rules.Width,b.Rules.Height,Array.AsReadOnly(rows),Array.AsReadOnly(armies),Array.AsReadOnly(groups),new(metrics));
    }
}
