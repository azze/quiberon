using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class DynamicsReferenceTests
{
    private static IEnumerable<object[]> Rows(string name)
    {
        using var doc=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"dynamics_fixtures",name+".json")));
        return doc.RootElement.EnumerateArray().Select(r=>new object[]{r.GetProperty("input").GetProperty("name").GetString()!,r.GetRawText()}).ToArray();
    }
    public static IEnumerable<object[]> Calculations=>Rows("calculations");
    public static IEnumerable<object[]> Traces=>Rows("traces");
    private static object Describe(Regiment u)=>new
    {
        id=u.Id,position=u.Position,facing=u.Facing,strength=u.Strength,morale=u.Morale,cohesion=u.Cohesion,fatigue=u.Fatigue,speed=u.Speed,
        state=u.State.ToString().ToLowerInvariant(),withdrawn=u.Withdrawn,effective=u.Effective,safeTime=u.SafeTime,reloadLeft=u.ReloadLeft,
        chargeState=u.CavalryState.ToString().ToLowerInvariant(),momentum=u.ChargeMomentum,lastMomentum=u.ChargeLastMomentum,chargeDistance=u.ChargeDistance,
        chargeReady=u.ChargeReady,cooldown=u.ChargeCooldown,chargeSequence=u.ChargeSequence,impactedSequence=u.ChargeImpactedSequence,
        impactTarget=u.ChargeImpactTargetId,chargeResult=u.ChargeResult
    };
    [Theory,MemberData(nameof(Calculations))]
    public void CurrentPythonDynamicsCalculationsMatchControlledDraws(string name,string json)
    {
        using var doc=JsonDocument.Parse(json);var row=doc.RootElement;
        var data=JsonSerializer.Deserialize<ScenarioDefinition>(row.GetProperty("input").GetRawText(),ScenarioJson.Options)!;
        var b=data.Create();var u=b.Units[0];var target=b.Units.Count>1?b.Units[1]:null;
        var control=row.GetProperty("control");var extra=new Dictionary<string,object?>();
        switch(row.GetProperty("action").GetString())
        {
            case "damage":b.Combat.Damage(target!,control.GetProperty("losses").GetInt32(),u,control.GetProperty("shock").GetDouble(),"probe");break;
            case "morale":b.MoraleSystem.Update();break;
            case "routing":extra["goal"]=RoutingSystem.Destination(b,u);break;
            case "impact":
                u.CavalryState=CavalryState.Charging;u.ChargeSequence=1;u.ChargeMomentum=control.GetProperty("momentum").GetDouble();u.Velocity=new(12,0);
                extra["readiness"]=CavalrySystem.Readiness(u,target!);b.Cavalry.Impact(u,target!);break;
            case "melee":b.Combat.ResolveMelee(b.Units);break;
            case "fire":b.Combat.Fire(u,target!);break;
            case "momentum":
                u.CavalryState=CavalryState.Charging;u.ChargeDistance=control.GetProperty("distance").GetDouble();u.Velocity=new(control.GetProperty("speed").GetDouble(),0);
                b.Cavalry.AfterMove(u,u.Position);break;
            default:throw new InvalidDataException(name);
        }
        using var actual=JsonDocument.Parse(JsonSerializer.Serialize(new{units=b.Units.Select(Describe),draws=b.Random.Draws,extra},ScenarioJson.Options));
        CombatReferenceTests.Compare(row.GetProperty("expected"),actual.RootElement,name);
    }
    [Theory,MemberData(nameof(Traces))]
    public void ActualPythonBattleStepsAndPortableRandomOrderMatch(string name,string json)
    {
        using var doc=JsonDocument.Parse(json);var row=doc.RootElement;
        var data=JsonSerializer.Deserialize<ScenarioDefinition>(row.GetProperty("input").GetRawText(),ScenarioJson.Options)!;
        string Run()
        {
            // The unchanged Python oracle uses strict footprint contact.
            var b=(data with {MeleeDisengageDistance=.75}).Create();var samples=data.SampleTicks.ToHashSet();var frames=new List<object>();
            while(true)
            {
                if(samples.Contains(b.Tick)||b.Result is not null)frames.Add(new{tick=b.Tick,units=b.Units.Select(Describe).ToArray()});
                if(b.Tick>=Math.Round(data.Duration/Rules.Dt)||b.Result is not null)break;
                data.IssueScheduled(b);b.Step();
            }
            return JsonSerializer.Serialize(new{name=data.Name,frames,draws=b.Random.Draws,result=b.Result?.Id,routs=b.Metrics.Routs,rallies=b.Metrics.Rallies,
                cascadeShocks=b.Metrics.CascadeShocks,chargeStarts=b.Metrics.ChargeStarts,impacts=b.Metrics.ChargeImpacts,
                pursuitCasualties=b.Metrics.PursuitCasualties,pursuitLosses=b.Metrics.PursuitLosses},ScenarioJson.Options);
        }
        string one=Run();Assert.Equal(one,Run());using var actual=JsonDocument.Parse(one);
        CombatReferenceTests.Compare(row.GetProperty("expected"),actual.RootElement,name);
    }
}
