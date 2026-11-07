using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class CombatReferenceTests
{
    private static string Fixture(string name)=>Path.Combine(AppContext.BaseDirectory,"combat_fixtures",name+".json");
    private static IEnumerable<object[]> Rows(string file)
    {
        using var document=JsonDocument.Parse(File.ReadAllText(Fixture(file)));
        return document.RootElement.EnumerateArray().Select(row=>new object[]{row.GetProperty("input").GetProperty("name").GetString()!,row.GetRawText()}).ToArray();
    }
    public static IEnumerable<object[]> Calculations=>Rows("calculations");
    public static IEnumerable<object[]> Traces=>Rows("traces");
    [Fact] public void PortableRngMatchesPythonGoldenDoublesExactly()
    {
        var expected=JsonSerializer.Deserialize<double[]>(File.ReadAllText(Fixture("rng")))!;var random=new SimulationRandom(17);
        foreach(var value in expected)Assert.Equal(value,random.NextDouble());
    }
    [Theory,MemberData(nameof(Calculations))]
    public void CurrentPythonCombatCalculationsAndControlledCasualtiesMatch(string name,string json)
    {
        using var document=JsonDocument.Parse(json);var root=document.RootElement;
        var data=JsonSerializer.Deserialize<ScenarioDefinition>(root.GetProperty("input").GetRawText(),ScenarioJson.Options)!;
        var units=data.Units.Select(d=>new Regiment(d.Id,d.Army,d.Name,Archetypes.Get(d.Archetype),d.Position,d.Facing)
            {Formation=d.Formation??Formation.Line,Cohesion=d.Cohesion,Strength=d.Strength??Archetypes.Get(d.Archetype).Strength}).ToArray();
        var battle=new BattleSimulation(units,new(){Width=data.Width,Height=data.Height,CombatEnabled=true},new(data.Terrain?.Hills,data.Terrain?.Forests),data.Seed,new TapeRandom(data.RandomDraws!));
        var a=battle.Unit(0)!;var target=battle.Unit(1)!;
        if(root.GetProperty("moving").GetBoolean())MovementSystem.Move(a,a.Position+new Vec2(100,0),battle.Rules,battle.Terrain,null);
        var sight=battle.Combat.Sight(a,target);var volley=battle.Combat.CalculateVolley(a,target);var melee=battle.Combat.CalculateMelee(a,target);
        bool canFire=battle.Combat.CanFire(a,target),touching=OrientedRect.Touching(a.Rect,target.Rect);
        double elevation=battle.Terrain.Elevation(a.Position),forest=battle.Terrain.ForestDensity(a.Position),slope=battle.Terrain.Gradient(a.Position).Length;
        if(name.StartsWith("melee-",StringComparison.Ordinal))battle.Combat.ResolveMelee(battle.Units);else battle.Combat.Fire(a,target);
        var result=new{elevation,forest,slope,visible=sight.Visible,transmission=sight.Transmission,vegetation=sight.Vegetation,reason=sight.Reason,
            canFire,laneFactor=volley.LaneFactor,shots=volley.Shots,probability=volley.Probability,touching,meleePower=melee.Power,meleeShock=melee.Shock,
            after=units.Select(u=>new{id=u.Id,strength=u.Strength,cohesion=u.Cohesion,reloadLeft=u.ReloadLeft}),draws=battle.Random.Draws};
        using var actual=JsonDocument.Parse(JsonSerializer.Serialize(result,ScenarioJson.Options));Compare(root.GetProperty("expected"),actual.RootElement,name);
    }
    [Theory,MemberData(nameof(Traces))]
    public void SimplifiedBattleTraceMatchesPythonAndIsReproducible(string name,string json)
    {
        using var document=JsonDocument.Parse(json);var root=document.RootElement;
        var data=JsonSerializer.Deserialize<ScenarioDefinition>(root.GetProperty("input").GetRawText(),ScenarioJson.Options)!;
        string Run()
        {
            var battle=data.Create();var samples=data.SampleTicks.ToHashSet();var frames=new List<object>();
            while(true)
            {
                if(samples.Contains(battle.Tick))frames.Add(new{tick=battle.Tick,units=battle.Units.Select(u=>new{id=u.Id,position=u.Position,facing=u.Facing,strength=u.Strength,cohesion=u.Cohesion,reloadLeft=u.ReloadLeft,combatState=u.CombatState.ToString().ToLowerInvariant()}).ToArray()});
                if(battle.Time>=data.Duration||battle.Result is not null)break;
                data.IssueScheduled(battle);battle.Step();
            }
            return JsonSerializer.Serialize(new{name=data.Name,frames,draws=battle.Random.Draws},ScenarioJson.Options);
        }
        string one=Run();Assert.Equal(one,Run());using var actual=JsonDocument.Parse(one);Compare(root.GetProperty("expected"),actual.RootElement,name);
    }
    internal static void Compare(JsonElement a,JsonElement b,string path)
    {
        switch(a.ValueKind)
        {
            case JsonValueKind.Object:foreach(var property in a.EnumerateObject())Compare(property.Value,b.GetProperty(property.Name),path+"."+property.Name);break;
            case JsonValueKind.Array:
                Assert.Equal(a.GetArrayLength(),b.GetArrayLength());int i=0;foreach(var value in a.EnumerateArray()){Compare(value,b[i],path+$"[{i}]");i++;}break;
            case JsonValueKind.Number:Assert.True(double.IsFinite(b.GetDouble())&&Math.Abs(a.GetDouble()-b.GetDouble())<1e-5,$"{path}: {a} vs {b}");break;
            default:Assert.Equal(a.ToString(),b.ToString());break;
        }
    }
    [Fact] public void AllPublishedCombatScenariosLoadAndRemainValid()
    {
        Assert.Equal(103,CombatScenarios.Available.Count());
        foreach(var(id,_) in CombatScenarios.Available)
        {
            var definition=CombatScenarios.Get(id);var battle=definition.Create();Assert.True(battle.Rules.CombatEnabled);
            for(int tick=0;tick<20;tick++){definition.IssueScheduled(battle);battle.Step();}
            Assert.All(battle.Units,u=>{Assert.InRange(u.Strength,0,u.MaximumStrength);Assert.InRange(u.Cohesion,0,100);Assert.True(u.Position.Finite);});
        }
    }
}
