namespace Quiberon.Simulation;

/// <summary>Bounded, scenario-level command support. Queries the existing spatial index, every 0.5 s.
/// Headquarters are fixed battlefield coordinates, not dummy combat regiments or campaign entities.</summary>
public sealed class CommandSupportSystem(BattleSimulation battle)
{
    private readonly bool enabled = battle.Rules.CommandersEnabled && (battle.ArmyCommanders.Count > 0 || battle.Units.Any(u => u.Commander.DefinitionId.Length > 0));
    public void Update()
    {
        if (!enabled || battle.Tick % 5 != 0) return;
        foreach (var u in battle.Units)
        {
            u.CommandShock = u.CommandRecovery = u.CommandMovement = u.CommandManoeuvre = 1;
            u.CommandMorale = 0; u.CommandOutnumbered = false; u.CommandSupport = "";
        }
        foreach (var source in battle.Units)
        {
            if (!source.Effective) continue;
            bool brotherhood = source.State==MoraleState.Steady && HistoricalCommanders.Has(source, "brotherhood_of_nations");
            bool veteran = source.State==MoraleState.Steady && HistoricalCommanders.Has(source, "veteran_of_two_worlds");
            if (brotherhood || veteran)
            foreach (var friend in battle.Combat.Nearby(source.Position, 110))
            {
                if (friend.Id == source.Id || friend.Army != source.Army || !friend.Effective || friend.State != MoraleState.Steady ||
                    friend.Archetype.Faction == source.Archetype.Faction || (friend.Position-source.Position).Length > 110 || !battle.Combat.Sight(source,friend).Visible) continue;
                bool haud = source.Archetype.Faction == "Haudenosaunee Confederacy" || friend.Archetype.Faction == "Haudenosaunee Confederacy";
                bool conventional = !source.Archetype.Skirmisher || !friend.Archetype.Skirmisher;
                if (veteran && !(haud && conventional)) continue;
                Apply(source, veteran); Apply(friend, veteran);
            }
            if (HistoricalCommanders.Has(source, "revolutionary_fervour") && source.Archetype.Citizen)
            {
                int own=source.Strength, enemy=0;
                foreach(var other in battle.Combat.Nearby(source.Position,130))
                    if(other.Id!=source.Id && other.Effective && (other.Position-source.Position).Length<=130 && battle.Combat.Sight(source,other).Visible)
                    { if(other.Army==source.Army)own+=other.Strength;else enemy+=other.Strength; }
                source.CommandOutnumbered=enemy>own;
            }
        }
        foreach(var assignment in battle.ArmyCommanders)
        {
            var d=HistoricalCommanders.Get(assignment.CommanderId);var centre=assignment.Position!.Value;
            double radius=d.Specialization=="citizens_defence"?180:220;
            foreach(var u in battle.Combat.Nearby(centre,radius))
            {
                if(!u.Effective || u.Army!=assignment.Army || (u.Position-centre).Length>radius)continue;
                if(d.Specialization=="citizens_defence" && u.Archetype.Citizen && u.Cohesion>=45 && CommanderSystem.Defending(u))
                {u.CommandShock=Math.Min(u.CommandShock,.85);u.CommandMorale=Math.Max(u.CommandMorale,.15);u.CommandSupport="Citizen’s Defence: within headquarters support radius";}
                else if(d.Specialization=="speed_and_shock" && u.Archetype.Category==UnitCategory.Infantry && HistoricalEffects.Attacking(u))
                {u.CommandShock=Math.Min(u.CommandShock,.92);u.CommandMovement=Math.Max(u.CommandMovement,1.06);u.CommandRecovery=Math.Max(u.CommandRecovery,1.08);u.CommandSupport="Speed and Shock: local offensive coordination";}
            }
        }
    }
    private static void Apply(Regiment u,bool veteran)
    {
        u.CommandRecovery=Math.Max(u.CommandRecovery,veteran?1.15:1.12);
        u.CommandManoeuvre=Math.Min(u.CommandManoeuvre,veteran?.9:1);
        u.CommandMorale=Math.Max(u.CommandMorale,.12);
        u.CommandSupport=veteran?"Veteran of Two Worlds: mixed detachment coordination":"Brotherhood of Nations: mixed-faction coordination";
    }
}

/// <summary>Starting signatures feed existing modifier hooks; no acquired-upgrade or campaign machinery.</summary>
public static class HistoricalEffects
{
    private static bool Has(Regiment u,string key)=>HistoricalCommanders.Has(u,key);
    public static bool Attacking(Regiment u)=>u.Order.Kind is OrderKind.Attack or OrderKind.Advance or OrderKind.Charge;
    public static double Formation(Regiment u)=>Has(u,"flexible_manoeuvres")?.85:Has(u,"disciplined_skirmishers")?.8:1;
    public static double Manoeuvre(Regiment u)=>(Has(u,"flexible_manoeuvres")?.78:Has(u,"disciplined_skirmishers")?.82:Has(u,"vanguard_assault") && Attacking(u)?.88:1)*u.CommandManoeuvre;
    public static double Recovery(Regiment u)=>(Has(u,"flexible_manoeuvres")?1.18:Has(u,"disciplined_skirmishers")?1.12:Has(u,"cavalry_reserve") && (u.Speed<=.1 || u.CavalryState==CavalryState.Reforming) && u.CavalryState!=CavalryState.Charging && u.PursuitId is null?1.25:1)*u.CommandRecovery;
    public static double Shock(Regiment u)=>(Has(u,"revolutionary_fervour") && u.Archetype.Citizen && u.CommandOutnumbered?.82:Has(u,"improvised_defences") && UpgradeSystem.Prepared(u)?.88:1)*u.CommandShock;
    public static double CasualtyMorale(Regiment u)=>Has(u,"revolutionary_fervour") && u.Archetype.Citizen && u.CommandOutnumbered?.88:1;
    public static double Move(Regiment u)=>(Has(u,"vanguard_assault") && Attacking(u)?1.08:Has(u,"cossack_screen") && u.Archetype.Role=="light_cavalry"?1.06:1)*u.CommandMovement;
    public static double Accuracy(Regiment u)=>Has(u,"steady_volley") && u.Archetype.Weapon is not null && u.Formation==global::Quiberon.Simulation.Formation.Line && u.Speed<=.1 && u.TransitionLeft<=0?1+.18*Math.Clamp((u.Cohesion-60)/30,0,1):1;
    public static double Pursuit(Regiment u)=>Has(u,"relentless_pursuit_signature")?1.22:Has(u,"cossack_screen")?1.15:1;
    public static double PursuitLoss(Regiment u)=>u.PursuitId is null?1:Has(u,"relentless_pursuit_signature")?.8:Has(u,"cossack_screen")?.9:1;
    public static double PursuitGap(Regiment u)=>Has(u,"relentless_pursuit_signature")?1.12:1;
    public static double Frontal(Regiment u,Regiment target)=>(Has(u,"relentless_pursuit_signature") || Has(u,"cossack_screen")) && target.State==MoraleState.Steady && CavalrySystem.Readiness(u,target)>.5?.9:1;
    public static double Melee(Regiment u)=>Has(u,"revolutionary_fervour") && u.Archetype.Citizen && u.CommandOutnumbered?1.1:1;
    public static double ChargeShock(Regiment u,double momentum,bool prepared)=>momentum>.25 && !prepared?(Has(u,"vorwarts")?1.15:Has(u,"vanguard_assault")?1.08:1):1;
    public static double Reform(Regiment u)=>Has(u,"cavalry_reserve")?.8:1;
    public static double Cooldown(Regiment u)=>Has(u,"cavalry_reserve")?.85:1;
    public static void RecoverFatigue(Regiment u)
    {if(Has(u,"cavalry_reserve") && u.Effective && u.Speed<=.1 && u.CombatState!=CombatState.Melee && u.PursuitId is null)u.Fatigue=Math.Max(0,u.Fatigue-Rules.Dt*.25);}
    public static string Effects(Regiment u)
    {
        var d=HistoricalCommanders.Get(u.Commander.DefinitionId);
        bool active=d.Specialization switch {
            "steady_volley"=>Accuracy(u)>1,
            "revolutionary_fervour"=>u.Archetype.Citizen && u.CommandOutnumbered,
            "brotherhood_of_nations" or "veteran_of_two_worlds"=>u.CommandSupport.Length>0,
            "improvised_defences"=>UpgradeSystem.Prepared(u) || u.Archetype.Category==UnitCategory.Artillery,
            "vanguard_assault"=>Attacking(u),
            "vorwarts"=>u.CavalryState==CavalryState.Charging,
            "relentless_pursuit_signature" or "cossack_screen"=>u.CavalryState==CavalryState.Pursuit,
            "cavalry_reserve"=>u.Speed<=.1 && u.CombatState!=CombatState.Melee,
            _=>true };
        return $"{d.SpecializationName}: {(active?"conditions active":"conditional benefits inactive")}. {d.Description}"+(u.CommandSupport.Length>0?"\n"+u.CommandSupport:"");
    }
}
