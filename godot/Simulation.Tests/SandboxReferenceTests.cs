using System.Globalization;
using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class SandboxReferenceTests
{
    public static IEnumerable<object[]> Probes=>JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"sandbox_fixtures/probes.json"))).RootElement.EnumerateArray().Select(r=>new object[]{r.GetProperty("input").GetProperty("name").GetString()!,r.GetRawText()});
    [Theory][MemberData(nameof(Probes))]
    public void CurrentPythonUpgradeAndBayonetCalculations(string name,string json)
    {
        using var doc=JsonDocument.Parse(json);var root=doc.RootElement;var b=root.GetProperty("input").Deserialize<ScenarioDefinition>(ScenarioJson.Options)!.Create();var u=b.Units[0];var target=b.Units[1];object actual;
        if(root.GetProperty("action").GetString()=="impact") {
            u.InfantryCharging=true;u.ChargeMomentum=root.GetProperty("momentum").GetDouble();u.ChargeSequence=1;b.InfantryCharges.Impact(u,target);
            actual=new {strength=target.Strength,morale=target.Morale,cohesion=target.Cohesion,attackerCohesion=u.Cohesion,cooldown=u.ChargeCooldown,lastMomentum=u.ChargeLastMomentum};
        } else {
            u.Cohesion=root.GetProperty("cohesion").GetDouble();u.UpgradeStationary=6.1;
            actual=new {formation=SpecialistSystem.FormationTime(u,7),manoeuvre=SpecialistSystem.Manoeuvre(u),recovery=CommanderSystem.Recovery(u),shock=CommanderSystem.Shock(u),defence=CommanderSystem.Defence(u,target),redeploy=CommanderSystem.Redeploy(u),scatter=CommanderSystem.Scatter(u),pursuit=CommanderSystem.Pursuit(u),chargeShock=CommanderSystem.ChargeShock(u,target,.7,false),aura=UpgradeSystem.Has(u,"rallying_presence")?CommanderSystem.Aura(u):0};
        }
        using var parsed=JsonDocument.Parse(JsonSerializer.Serialize(actual,ScenarioJson.Options));CombatReferenceTests.Compare(root.GetProperty("expected"),parsed.RootElement,name);
    }
    [Fact] public void LegacyTerrainSeedsMatchPythonForAllPresetsAndSignedIntegerExtremes()
    {
        using var doc=JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"sandbox_fixtures/terrain.json")));
        foreach(var row in doc.RootElement.EnumerateArray()) {
            var actual=BattleConfiguration.GenerateTerrain(row.GetProperty("preset").GetString()!,row.GetProperty("width").GetDouble(),row.GetProperty("height").GetDouble(),long.Parse(row.GetProperty("seed").GetString()!,CultureInfo.InvariantCulture));
            var expectedHills=row.GetProperty("hills").EnumerateArray().ToArray();var expectedForests=row.GetProperty("forests").EnumerateArray().ToArray();Assert.Equal(expectedHills.Length,actual.Hills.Length);Assert.Equal(expectedForests.Length,actual.Forests.Length);
            for(int i=0;i<actual.Hills.Length;i++){var h=actual.Hills[i];var e=expectedHills[i];Assert.Equal(e.GetProperty("x").GetDouble(),h.X,10);Assert.Equal(e.GetProperty("y").GetDouble(),h.Y,10);Assert.Equal(e.GetProperty("radius_x").GetDouble(),h.RadiusX,10);Assert.Equal(e.GetProperty("radius_y").GetDouble(),h.RadiusY,10);Assert.Equal(e.GetProperty("height").GetDouble(),h.Height,10);}
            for(int i=0;i<actual.Forests.Length;i++){var f=actual.Forests[i];var e=expectedForests[i];Assert.Equal(e.GetProperty("x").GetDouble(),f.X,10);Assert.Equal(e.GetProperty("y").GetDouble(),f.Y,10);Assert.Equal(e.GetProperty("density").GetDouble(),f.Density,10);}
        }
    }
    [Fact] public void EveryExistingPythonCustomPresetLoadsAndPreparesWithoutPythonRuntime()
    {
        var assembly=typeof(BattleSimulation).Assembly;
        foreach(var name in assembly.GetManifestResourceNames().Where(n=>n.StartsWith("battle_presets.",StringComparison.Ordinal))) {
            using var stream=assembly.GetManifestResourceStream(name)!;var c=BattleConfiguration.Parse(new StreamReader(stream).ReadToEnd()).Prepare();c.Validate();Assert.NotEmpty(c.Placements);Assert.All(c.Scenario().Create().Units,u=>Assert.True(u.CommanderAssigned));
        }
    }
}
