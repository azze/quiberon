using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using Quiberon.Simulation;

if(args.Length!=2)throw new ArgumentException("Usage: tournament CASES_JSON OUTPUT_JSONL");
var cases=JsonSerializer.Deserialize<Case[]>(File.ReadAllText(args[0]),ScenarioJson.Options)!;
using var output=new StreamWriter(args[1],append:false){AutoFlush=true};
foreach(var c in cases)
{
    var b=c.Scenario.Create();
    foreach(int army in c.LegacyArmies)b.Ai.EvaluationLegacyArmies.Add(army);
    foreach(int army in c.DisablePositioningArmies??[])b.Ai.EvaluationDisablePositions.Add(army);
    var lastSalvos=b.Units.ToDictionary(u=>u.Id,u=>u.ShotsFired);
    double[] distanceTotals=new double[2],probabilityTotals=new double[2];int[] volleyCounts=new int[2],columnVolleys=new int[2],movingVolleys=new int[2],totalShots=new int[2];
    var firstVolleys=new List<object>();var observedFirst=new HashSet<int>();
    var blocked=new Dictionary<int,double>{{0,0},{1,0}};
    double[] unsupportedCavalry=new double[2],aheadCavalry=new double[2];
    while(b.Result is null && b.Time<c.Scenario.Duration)
    {
        c.Scenario.IssueScheduled(b);b.Step();
        foreach(var u in b.Units)
        {
            if(u.ShotsFired>lastSalvos[u.Id] && u.Archetype.Category==UnitCategory.Infantry && u.Archetype.Weapon is { } weapon)
            {
                var volley=b.Events.LastOrDefault(e=>e.UnitId==u.Id && e.Kind=="volley");
                if(volley?.TargetId is { } id && b.Unit(id)is { } target)
                {
                    volleyCounts[u.Army]++;distanceTotals[u.Army]+=(u.Position-target.Position).Length/weapon.Range;probabilityTotals[u.Army]+=u.LastVolleyProbability;totalShots[u.Army]+=u.LastVolleyShots;
                    if(u.Formation==Formation.Column)columnVolleys[u.Army]++;if(u.Speed>.1)movingVolleys[u.Army]++;
                    if(observedFirst.Add(u.Id))firstVolleys.Add(new{u.Id,u.Army,time=b.Time,u.Formation,u.Strength,shots=u.LastVolleyShots,probability=u.LastVolleyProbability,u.TransitionLeft,order=u.Order.Kind});
                }
            }
            lastSalvos[u.Id]=u.ShotsFired;
        }
        if(b.Tick%10!=0)continue;
        foreach(var horse in b.Units.Where(u=>u.Effective && u.Archetype.Category==UnitCategory.Cavalry))
        {
            var friends=b.Units.Where(u=>u.Army==horse.Army && u.Effective && u.Archetype.Category==UnitCategory.Infantry && !u.Archetype.Skirmisher).ToArray();
            if(friends.Length==0)continue;
            var enemies=b.Units.Where(u=>u.Army!=horse.Army && u.Effective && b.Perceives(horse,u)).ToArray();
            int threats=enemies.Count(e=>(e.Position-horse.Position).Length<180);
            if(threats>=2 && friends.All(f=>(f.Position-horse.Position).Length>160))unsupportedCavalry[horse.Army]++;
            if(enemies.Length>0)
            {
                var centre=new Vec2(friends.Average(f=>f.Position.X),friends.Average(f=>f.Position.Y));
                var axis=(new Vec2(enemies.Average(e=>e.Position.X),enemies.Average(e=>e.Position.Y))-centre).Normalized;
                var front=friends.Select(f=>(f.Position-centre).Dot(axis)).Order().ToArray();
                if((horse.Position-centre).Dot(axis)>front[(front.Length-1)*3/4]+60)aheadCavalry[horse.Army]++;
            }
        }
        foreach(var u in b.Units)
        {
            if(!u.Effective || u.Archetype.Category!=UnitCategory.Infantry || u.Archetype.Weapon is not { } w || b.Unit(u.TargetId??-1)is not {Active:true} target)continue;
            if((u.Position-target.Position).Length<=w.Range && b.Combat.Sight(u,target).Visible && b.Combat.FiringBlocker(u,target)is not null)blocked[u.Army]+=1;
        }
    }
    var state=b.Units.Select(u=>new{u.Id,u.Army,u.Position,u.Facing,u.Strength,u.Morale,u.Cohesion,u.State,u.Withdrawn}).ToArray();
    string checksum=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new{state,b.Random.Draws},ScenarioJson.Options))));
    var row=new{c.Name,c.Seed,c.Cohort,c.NewArmy,c.LegacyArmies,c.DisablePositioningArmies,c.Scenario.Duration,seconds=b.Time,winner=b.Result?.WinnerArmy,timedOut=b.Result is null,rule=b.Result?.Rule,objectives=b.Mission?.Objectives,checksum,state,intentions=b.Units.Select(u=>new{u.Id,u.Order,u.AiIntention,u.Cohesion,u.AiMountedIntent}),firstVolleys,randomDraws=b.Random.Draws,
        armies=b.Units.GroupBy(u=>u.Army).OrderBy(g=>g.Key).Select(g=>new{army=g.Key,initial=g.Sum(u=>b.InitialUnitStrength[u.Id]),remaining=g.Sum(u=>u.Strength),effective=g.Where(u=>u.Effective).Sum(u=>u.Strength),lost=g.Sum(u=>b.InitialUnitStrength[u.Id]-u.Strength),inflicted=g.Sum(u=>u.DamageInflicted),salvos=g.Sum(u=>u.ShotsFired),charges=g.Sum(u=>u.Charges),targetChanges=g.Sum(u=>u.TargetChanges),formationChanges=g.Sum(u=>u.FormationChanges),movingSeconds=g.Sum(u=>u.MovingSeconds),firingSeconds=g.Sum(u=>u.FiringSeconds),unsupportedCavalrySeconds=unsupportedCavalry[g.Key],cavalryAheadSeconds=aheadCavalry[g.Key],blockedFiringRegimentSeconds=blocked[g.Key],columnVolleys=columnVolleys[g.Key],movingVolleys=movingVolleys[g.Key],totalMusketShots=totalShots[g.Key],meanVolleyRangeFraction=volleyCounts[g.Key]>0?distanceTotals[g.Key]/volleyCounts[g.Key]:0,meanVolleyProbability=volleyCounts[g.Key]>0?probabilityTotals[g.Key]/volleyCounts[g.Key]:0}),b.Metrics};
    output.WriteLine(JsonSerializer.Serialize(row,new JsonSerializerOptions(ScenarioJson.Options){WriteIndented=false}));
    Console.WriteLine($"{c.Cohort} {c.Name} seed={c.Seed} newSide={c.NewArmy} winner={b.Result?.WinnerArmy.ToString()??"TIMEOUT"} time={b.Time:F1}");
}
record Case(string Name,long Seed,string Cohort,int? NewArmy,int[] LegacyArmies,ScenarioDefinition Scenario,int[]? DisablePositioningArmies=null);
