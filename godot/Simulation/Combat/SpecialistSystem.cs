namespace Quiberon.Simulation;

/// <summary>Shared archetype, commander and acquired-ability modifiers for existing rules.</summary>
public static class SpecialistSystem
{
    public static bool Has(Regiment u,string trait)=>u.SpecialistsEnabled && u.Archetype.Trait==trait;
    public static double Drill(Regiment u)=>Has(u,"drill")?Math.Clamp((u.Cohesion-40)/50,0,1):0;
    public static double Reload(Regiment u)=>Math.Max(.5,(u.Archetype.Weapon?.ReloadSeconds??5)*(1-.25*Drill(u))*(1+u.Fatigue*.003)*CommanderSystem.Reload(u)*u.WeatherReload);
    public static double FormationTime(Regiment u,double seconds)=>Math.Max(seconds*(UpgradeSystem.Has(u,"swift_reform")?.4:.5),seconds*(1-.4*Drill(u))*CommanderSystem.Formation(u)*u.Archetype.FormationTime);
    public static double Manoeuvre(Regiment u)=>Math.Max(.4,(1-.5*Drill(u))*CommanderSystem.Manoeuvre(u)*u.Archetype.ManoeuvreLoss);
    public static double WoodlandSkill(double cover)=>Math.Clamp(cover/.4,0,1);
    public static double Aimed(Regiment u,double transmission)=>Has(u,"aimed") && u.Speed<=.1 && u.CombatState!=CombatState.Melee?
        1+.35*Math.Clamp((u.Cohesion-40)/40,0,1)*Math.Clamp((transmission-.35)/.55,0,1):1;
    public static double Exploit(Regiment u,Regiment target,bool prepared)=>Has(u,"exploit") && !prepared && u.Speed>3 && (target.State is MoraleState.Wavering or MoraleState.Routing || target.Cohesion<40)?1.65:1;
    public static Regiment? Support(BattleSimulation b,Regiment u)
    {Regiment? best=null;double strength=0;foreach(var a in b.Combat.Nearby(u.Position,125)){double aura=CommanderSystem.Aura(a);if(a.Id==u.Id || a.Army!=u.Army || !a.Effective || a.State!=MoraleState.Steady || a.Morale<=60 || aura<=0 || (a.Position-u.Position).Length>=125 || aura<strength || aura==strength && best is not null && a.Id>best.Id)continue;if(!b.Combat.Sight(u,a).Visible)continue;best=a;strength=aura;}return best;}
    public static void Activate(BattleSimulation b,Regiment u,string effect)
    {if(u.ActivatedAbilities.Add(effect))b.Emit("specialist",u,null,u.Position,2,0,$"{u.Name}: {effect}");}
}
