using System.Text.Json;
namespace Quiberon.Simulation;

public sealed record CommanderPolicy(double Commitment=1,double PursuitDistance=200,double DisengageSeconds=10,double Overmatch=1.5,double FiringDistance=.85);
public static class CommanderSystem
{
    private static readonly JsonDocument data=JsonDocument.Parse(typeof(CommanderSystem).Assembly.GetManifestResourceStream("commander_definitions.json")!);
    private static readonly Dictionary<string,double> tuning=data.RootElement.GetProperty("tuning").EnumerateObject().ToDictionary(p=>p.Name,p=>p.Value.GetDouble());
    public static readonly string[] Personalities=data.RootElement.GetProperty("personalities").EnumerateObject().Select(p=>p.Name).ToArray();
    public static IEnumerable<string> Compatible(UnitCategory kind)=>data.RootElement.GetProperty("specializations").EnumerateObject().Where(p=>p.Value.GetProperty("categories").EnumerateArray().Any(v=>v.GetString()==kind.ToString().ToLowerInvariant())).Select(p=>p.Name);
    public static IEnumerable<string> Usable(UnitCategory kind)=>Compatible(kind);
    public static string Description(string personality,string specialization)
    {if(HistoricalCommanders.All.FirstOrDefault(d=>d.Specialization==specialization) is { } historical)return historical.SpecializationName+": "+historical.Description+"\n"+historical.Notes;var p=data.RootElement.GetProperty("personalities").GetProperty(personality);var s=data.RootElement.GetProperty("specializations").GetProperty(specialization);return $"{p.GetProperty("name").GetString()}: {p.GetProperty("benefit").GetString()} Limitation: {p.GetProperty("drawback").GetString()}\n{s.GetProperty("name").GetString()}: {s.GetProperty("benefit").GetString()} Limitation: {s.GetProperty("drawback").GetString()}";}
    private static readonly Dictionary<string,CommanderPolicy> policies=data.RootElement.GetProperty("personalities").EnumerateObject().ToDictionary(p=>p.Name,p=>p.Value.GetProperty("policy").Deserialize<CommanderPolicy>(new JsonSerializerOptions(){PropertyNamingPolicy=JsonNamingPolicy.SnakeCaseLower})!);
    public static double T(string key)=>tuning[key];
    public static void Validate(CommanderIdentity c,UnitCategory kind)
    {
        if(string.IsNullOrWhiteSpace(c.Id) || c.Id.Length>96 || string.IsNullOrWhiteSpace(c.Name) || c.Name.Length>100 || string.IsNullOrWhiteSpace(c.Background) || c.Background.Length>80 || c.Rank.Length>60 || c.Biography.Length>300 || c.Nation.Length>80 || new[]{c.Id,c.Name,c.Background,c.Rank,c.Biography,c.Nation}.Any(s=>s.Any(char.IsControl)) || !Personalities.Contains(c.Personality) || c.DefinitionId.Length==0 && !Compatible(kind).Contains(c.Specialization))throw new ArgumentException("Invalid or incompatible commander");
        if(c.DefinitionId.Length>0)HistoricalCommanders.Validate(c,kind);
    }
    public static CommanderIdentity Generate(ISimulationRandom rng,UnitCategory kind,string background,HashSet<string> names,HashSet<string> ids)
    {
        string Pick(string[] values)=>values[Math.Min(values.Length-1,(int)(rng.NextDouble()*values.Length))];
        var pools=data.RootElement.GetProperty("names");var pool=pools.TryGetProperty(background,out var match)?match:pools.GetProperty("Generic");
        string[] first=pool[0].EnumerateArray().Select(v=>v.GetString()!).ToArray(),last=pool[1].EnumerateArray().Select(v=>v.GetString()!).ToArray();
        string name="",rank="Major",bio="Fictional regimental officer; no claim of historical identity.";
        if(background=="Haudenosaunee Confederacy") {var available=first.Where(n=>!names.Contains(n)).ToArray();name=Pick(available.Length>0?available:first);rank="";bio="Sandbox commander using a user-supplied Haudenosaunee name.";}
        else {for(int i=0;i<20;i++){name=$"{Pick(first)} {Pick(last)}";if(!names.Contains(name))break;}rank=background=="Bourbon France"?"Colonel":background=="Polish-Lithuanian Commonwealth" && kind==UnitCategory.Cavalry?"Rotmistrz":"Major";}
        if(names.Contains(name)){string basis=name;for(int i=1;i<=names.Count+1;i++){name=$"{basis} ({i})";if(!names.Contains(name))break;}}
        string id="";for(int attempt=0;attempt<64;attempt++){id=$"cmd-{(ulong)(rng.NextDouble()*(1UL<<48)):x12}{(ulong)(rng.NextDouble()*(1UL<<48)):x12}";if(!ids.Contains(id))break;}if(ids.Contains(id)){string basis=id;for(int suffix=0;suffix<=ids.Count;suffix++){id=$"{basis}-{ids.Count+suffix}";if(!ids.Contains(id))break;}}
        var result=new CommanderIdentity(id,name,rank,background,Pick(Personalities),Pick(Usable(kind).ToArray()),bio);Validate(result,kind);names.Add(name);ids.Add(id);return result;
    }
    public static bool Has(Regiment u,string s)=>u.CommandersEnabled && u.Commander.Specialization==s;
    public static bool Is(Regiment u,string p)=>u.CommandersEnabled && u.Commander.Personality==p;
    private static readonly CommanderPolicy neutralPolicy=new();
    public static CommanderPolicy Policy(Regiment u)=>u.CommandersEnabled?policies[u.Commander.Personality]:neutralPolicy;
    public static double Drill(Regiment u)=>Has(u,"drillmaster")?Math.Clamp((u.Cohesion-40)/50,0,1):0;
    public static bool Defending(Regiment u)=>u.Speed<.1 && u.TransitionLeft<=0 && u.Order.Kind is OrderKind.Hold or OrderKind.Defend or OrderKind.Reserve;
    public static double Formation(Regiment u)=>HistoricalEffects.Formation(u)*(1-T("drill_formation")*Drill(u))*(UpgradeSystem.Has(u,"swift_reform")?UpgradeSystem.T("swift_formation"):1);
    public static double Manoeuvre(Regiment u)=>HistoricalEffects.Manoeuvre(u)*(1-T("drill_manoeuvre")*Drill(u))*(Is(u,"methodical")?1-T("methodical_manoeuvre"):1)*(UpgradeSystem.Has(u,"swift_reform")?UpgradeSystem.T("swift_manoeuvre"):1);
    public static double Recovery(Regiment u)=>Math.Min(1.8,Math.Min(1.5,HistoricalEffects.Recovery(u)*Math.Min(1.25,1+T("drill_recovery")*Drill(u)+(Has(u,"defensive_tactician") && Defending(u)?.10:0)))*(UpgradeSystem.Has(u,"swift_reform")?UpgradeSystem.T("swift_recovery"):1));
    public static double Shock(Regiment u)=>HistoricalEffects.Shock(u)*(u.Archetype.DefensiveResolve<1 && UpgradeSystem.Prepared(u)?u.Archetype.DefensiveResolve:1)*(Is(u,"stalwart")?1-T("stalwart_shock"):1)*(UpgradeSystem.Has(u,"steadfast_defence") && UpgradeSystem.Prepared(u)?UpgradeSystem.T("defence"):1);
    public static double Advance(Regiment u)=>HistoricalEffects.Move(u)*(Has(u,"defensive_tactician") && u.Order.Kind is OrderKind.Attack or OrderKind.Advance or OrderKind.Charge?1-T("defensive_advance"):1);
    public static double Reload(Regiment u)=>Has(u,"sharpshooter")?1+T("sharpshooter_reload"):1;
    public static double Redeploy(Regiment u)=>(HistoricalCommanders.Has(u,"improvised_defences")?.85:1)*(Has(u,"artillerist")?1+T("artillerist_redeploy"):1)*(UpgradeSystem.Has(u,"mobile_battery")?UpgradeSystem.T("mobile"):1);
    public static double Accuracy(Regiment u,double sight)=>HistoricalEffects.Accuracy(u)*(Has(u,"sharpshooter") && u.Speed<=.1 && u.Cohesion>=50 && u.CombatState!=CombatState.Melee?1+T("sharpshooter_accuracy")*Math.Clamp((sight-.2)/.8,0,1):1);
    public static double Defence(Regiment u,Regiment? attacker=null)=>Defending(u) && u.State==MoraleState.Steady && u.Cohesion>=60 && (attacker is null || Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,attacker.Position)))<=1.0472)?Math.Max(.65,(Has(u,"defensive_tactician")?1-T("defensive_resistance"):1)*(UpgradeSystem.Has(u,"steadfast_defence") && UpgradeSystem.Prepared(u)?UpgradeSystem.T("defence"):1)):1;
    public static double FrontalPenalty(Regiment u,Regiment target)=>HistoricalEffects.Frontal(u,target)*(Has(u,"pursuit_specialist") && target.State==MoraleState.Steady && Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,u.Position)))<1.0472?.9:1);
    public static double ChargeShock(Regiment u,Regiment target,double momentum,bool prepared)=>Math.Min(1.8,(Has(u,"firebrand") && momentum>.25 && !prepared && (target.State!=MoraleState.Steady || target.Cohesion<60 || Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,u.Position)))>1.0472)?1+T("firebrand_shock"):1)*UpgradeSystem.ChargeShock(u,target,momentum,prepared)*HistoricalEffects.ChargeShock(u,momentum,prepared));
    public static double Pursuit(Regiment u)=>HistoricalEffects.Pursuit(u)*(Has(u,"pursuit_specialist")?1+T("pursuit_power"):1)*(UpgradeSystem.Has(u,"relentless_pursuit")?UpgradeSystem.T("pursuit_power"):1);
    public static double PursuitLoss(Regiment u)=>HistoricalEffects.PursuitLoss(u)*(Has(u,"pursuit_specialist") && u.PursuitId is not null?1-T("pursuit_disruption"):1);
    public static double PursuitGap(Regiment u,double gap)=>gap*HistoricalEffects.PursuitGap(u)*(Has(u,"pursuit_specialist")?1.1:1);
    public static double Scatter(Regiment u)=>u.Speed<.1 && !u.Limbered && u.SetupLeft<=0?Math.Max(.45,(Has(u,"artillerist")?1-T("artillerist_scatter"):1)*(UpgradeSystem.Has(u,"calculated_fire") && u.UpgradeStationary>=UpgradeSystem.T("calculated_seconds")?UpgradeSystem.T("calculated"):1)):1;
    public static double Aura(Regiment u,bool rally=false)=>Math.Max(Math.Max(SpecialistSystem.Has(u,"prestige")?(rally?.35:.22):0,Has(u,"inspirer")?(rally?T("inspirer_rally"):T("inspirer_morale")):0),UpgradeSystem.Has(u,"rallying_presence")?UpgradeSystem.T(rally?"aura_rally":"aura_morale"):0);
    public static string Effects(Regiment u)=>StartingEffects(u)+(u.Commander.DefinitionId.Length==0 && u.CommandSupport.Length>0?"\n"+u.CommandSupport:"");
    private static string StartingEffects(Regiment u)=>u.CommandersEnabled && u.Commander.DefinitionId.Length>0?HistoricalEffects.Effects(u):u.CommandersEnabled?u.Commander.Specialization switch
    {
        "drillmaster"=>$"High-cohesion drill {Drill(u):P0}: formation/turning/recovery",
        "pathfinder"=>u.ForestCover>.05 || u.GroundSlope>.05?"Terrain benefits active":"Terrain benefits inactive on level open ground",
        "sharpshooter"=>$"Aim factor {Accuracy(u,u.SightTransmission):F2}; reload +8%",
        "artillerist"=>$"Scatter factor {Scatter(u):F2}; setup/limber +10%",
        "inspirer"=>u.Effective && u.State==MoraleState.Steady && u.Morale>60?"Morale aura active; strongest source only":"Aura inactive while unsteady",
        "defensive_tactician"=>Defence(u)<1?"Prepared defensive benefits active":"Defence inactive: requires steady, cohesive holding",
        "firebrand"=>"Exposed charge shock +12%; impact disorder up to 3",
        _=>"Pursuit +12%; contact gap +10%; steady frontal combat -10%"
    }:"Commander effects disabled (legacy fixture)";
}
