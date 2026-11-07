namespace Quiberon.Simulation;

/// <summary>Morale.py with shared commander, specialist and acquired-ability support.</summary>
public sealed class MoraleSystem(BattleSimulation battle)
{
    private readonly List<Regiment> newlyRouted = new();
    public static double MeleeEffectiveness(Regiment u, Rules rules) => u.State switch
    {
        MoraleState.Routing => rules.RoutingMeleeFactor,
        MoraleState.Rallying => rules.RallyingMeleeFactor + (rules.RallyingMeleeMax - rules.RallyingMeleeFactor) *
            Math.Clamp(Math.Min((u.Morale - 28) / 20, u.Cohesion / 45), 0, 1),
        MoraleState.Shaken => rules.ShakenMeleeFactor,
        MoraleState.Wavering => rules.WaveringMeleeFactor,
        _ => 1
    };
    public static void RecoverCohesion(Regiment u, Rules rules)
    {
        if (u.State == MoraleState.Routing)
        { u.Cohesion = Math.Max(0, u.Cohesion - rules.RoutingCohesionLoss * Rules.Dt); return; }
        if (u.CombatState == CombatState.Idle && u.CongestionLoss < 1e-6 && u.TerrainLoss < 1e-6)
        {
            double rate = u.Speed < .1 ? rules.CohesionRestRecovery : rules.CohesionMoveRecovery;
            u.Cohesion = Math.Min(100, u.Cohesion + Rules.Dt * rate * Math.Min(UpgradeSystem.Has(u,"swift_reform")?1.8:1.5, u.Archetype.Recovery*CommanderSystem.Recovery(u)));
        }
    }
    public void Update()
    {
        var r = battle.Rules; newlyRouted.Clear();
        foreach (var u in battle.Units)
        {
            if (!u.Active) continue;
            bool threatened = false; double hostile = 0, support = u.Strength; int friends = 0;
            foreach (var other in battle.Combat.Nearby(u.Position, Math.Max(130, r.ThreatRadius)))
            {
                if (!other.Active || other.Id == u.Id) continue;
                double distanceSquared = (other.Position - u.Position).LengthSquared;
                if (other.Army == u.Army)
                {
                    if (other.Effective && distanceSquared < 130 * 130) { support += other.Strength; friends++; }
                }
                else if (distanceSquared < r.ThreatRadius * r.ThreatRadius && battle.Perceives(u, other))
                { threatened = true; if (other.Effective) hostile += other.Strength; }
            }
            var anchor=u.Morale<100 && u.State!=MoraleState.Routing?SpecialistSystem.Support(battle,u):null;
            if(anchor is not null){u.Morale=Math.Min(100,u.Morale+Rules.Dt*Math.Min(.45,CommanderSystem.Aura(anchor,u.State==MoraleState.Rallying)));SpecialistSystem.Activate(battle,anchor,(UpgradeSystem.Has(anchor,"rallying_presence")?"Rallying Presence":SpecialistSystem.Has(anchor,"prestige")?"Royal Prestige":"Inspirer")+": visible friends supported within 125 m (non-stacking)");}
            var previous = u.State;
            if (u.State == MoraleState.Routing)
            {
                u.SafeTime = threatened ? 0 : u.SafeTime + Rules.Dt;
                if (u.SafeTime >= r.RallySafeSeconds && u.Strength > u.MaximumStrength * .15)
                {
                    u.State = MoraleState.Rallying; u.Morale = Math.Max(28, u.Morale); u.SafeTime = 0;
                    battle.Metrics.Rallies++;u.RallyEvents++;
                    Emit(u, "rally", "Rallying away from danger");
                }
            }
            else if (u.State == MoraleState.Rallying)
            {
                if (threatened)
                { StartRoute(u); Emit(u, "rout", "Rally interrupted by nearby enemies"); }
                else
                {
                    u.Morale = Math.Min(60, u.Morale + Rules.Dt * .9 * u.Archetype.Recovery);
                    if (u.CongestionLoss < 1e-6 && u.TerrainLoss < 1e-6) u.Cohesion = Math.Min(100, u.Cohesion + Rules.Dt * 1.2);
                    if (u.Morale >= 48 && u.Cohesion >= 45)
                    { u.State = MoraleState.Shaken; Emit(u, "rally", "Returned to duty, still shaken"); }
                }
            }
            else
            {
                if (u.Morale <= r.RoutThreshold)
                {
                    StartRoute(u); newlyRouted.Add(u); battle.Metrics.Routs++;u.RoutEvents++;UpgradeSystem.OnRout(battle,u);
                    Emit(u, "rout", $"Broke: morale {u.Morale:F0}, cohesion {u.Cohesion:F0}");
                }
                else if (u.Morale < 40) u.State = MoraleState.Wavering;
                else if (u.Morale < 60 && u.State == MoraleState.Steady) u.State = MoraleState.Shaken;
                else if (u.Morale > 66) u.State = MoraleState.Steady;
                else if (u.Morale > 46 && u.State == MoraleState.Wavering) u.State = MoraleState.Shaken;
                if (threatened)
                { if (hostile > support * 1.6) {double pressure=1;
                    if(SpecialistSystem.Has(u,"woodland") && u.ForestCover>0 && !battle.Combat.Nearby(u.Position,100).Any(e=>e.Effective && e.Army!=u.Army && e.Archetype.Category==UnitCategory.Cavalry && (e.Position-u.Position).Length<100))pressure=1-.95*SpecialistSystem.WoodlandSkill(u.ForestCover);
                    u.Morale -= Rules.Dt * .35*Math.Max(.1,pressure);} }
                else
                {
                    u.Morale += Rules.Dt * (.35 + .08 * friends) * u.Archetype.Discipline * u.Archetype.Recovery;
                    u.Fatigue = Math.Max(0, u.Fatigue - Rules.Dt * .1);
                }
            }
            RecoverCohesion(u, r);HistoricalEffects.RecoverFatigue(u);
            if(u.Effective && u.State!=MoraleState.Routing)u.Morale=Math.Min(100,u.Morale+Rules.Dt*Math.Min(.15,u.CommandMorale));
            if(CommanderSystem.Is(u,"stalwart") && CommanderSystem.Defending(u) && u.State is MoraleState.Shaken or MoraleState.Wavering)u.Morale=Math.Min(66,u.Morale+Rules.Dt*.04);
            u.Morale = Math.Clamp(u.Morale, 0, 100); u.Cohesion = Math.Clamp(u.Cohesion, 0, 100);
            if (previous != u.State)
                battle.Emit("morale_state", u, battle.Unit(u.LastAttackerId ?? -1), u.Position, 2, 0,
                    $"{u.Name}: {previous.ToString().ToLowerInvariant()} → {u.State.ToString().ToLowerInvariant()}");
        }
        // Deferred, one shock per actual transition; secondary routs wait a tick.
        foreach (var source in newlyRouted)
        foreach (var u in battle.Combat.Nearby(source.Position, r.RoutRadius))
        {
            double distance = (u.Position - source.Position).Length;
            if (u.Id == source.Id || !u.Effective || distance >= r.RoutRadius || !battle.Combat.Sight(u, source).Visible) continue;
            if (u.Army == source.Army)
            {
                double shock = r.RoutShock * (1 - distance / r.RoutRadius) / u.Archetype.Discipline * Math.Max(.6, u.Archetype.ShockResistance*CommanderSystem.Shock(u)*(SpecialistSystem.Support(battle,u)is { } supporter?(UpgradeSystem.Has(supporter,"rallying_presence")?.8:SpecialistSystem.Has(supporter,"prestige")?.85:.9):1));
                u.Morale = Math.Max(0, u.Morale - shock); battle.Metrics.CascadeShocks++;
                battle.Emit("morale_shock", u, source, u.Position, 2, 0, $"{u.Name}: −{shock:F1} morale as {source.Name} routed nearby");
            }
            else u.Morale = Math.Min(100, u.Morale + 3);
        }
    }
    private static void StartRoute(Regiment u)
    {
        u.State = MoraleState.Routing; u.SafeTime = 0; u.RoutHeading = null; u.RoutNextPlan = 0;
        u.TransitionLeft = 0; u.NextFormation = null;
    }
    private void Emit(Regiment u, string kind, string reason)
    { u.StateReason = reason; battle.Emit(kind, u, battle.Unit(u.LastAttackerId ?? -1), u.Position, 3, 0, $"{u.Name}: {reason}"); }
}
