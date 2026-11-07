using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class MovementTests
{
    private static Regiment Unit(int id = 0, string kind = "infantry", Vec2? position = null, int army = 0) => new(id, army, $"Regiment {id}", Archetypes.Get(kind), position ?? new(300, 300));
    private static void Steps(BattleSimulation battle, int count) { for (int i = 0; i < count; i++) battle.Step(); }
    [Fact] public void GeometryAndFacingUsePythonConvention()
    {
        Assert.True((Vec2.Direction(Math.PI / 2) - new Vec2(0, 1)).Length < 1e-12);
        Assert.Equal(-Math.PI, Vec2.AngleDelta(0, Math.PI));
        var rect = new OrientedRect(new(10, 20), 0, 64, 12);
        Assert.True(rect.Contains(new(15, 50))); Assert.False(rect.Contains(new(17, 20)));
        Assert.Equal(768, OrientedRect.IntersectionArea(rect, rect), 8);
        Assert.Null(OrientedRect.Separation(rect, new(new(200, 20), 0, 64, 12)));
        Assert.NotNull(OrientedRect.Segment(new(-10, 20), new(100, 20), rect));
    }
    [Theory] [InlineData("infantry",64,12)] [InlineData("cavalry",40,18)] [InlineData("artillery",28,18)] [InlineData("haudenosaunee_skirmishers",78,28)]
    public void ArchetypesHaveFaithfulFootprints(string id, double width, double depth)
    { var u = Unit(kind:id); Assert.Equal(width,u.Width); Assert.Equal(depth,u.Depth); Assert.True(u.Strength>0); Assert.Contains(u.Formation,u.Archetype.Formations); }
    [Fact] public void StraightMovementMatchesLineSpeedAndRetainsOrder()
    {
        var u=Unit();var battle=new BattleSimulation([u]);battle.Issue(new(0,new(OrderKind.Move,new(310,300))));battle.Step();
        Assert.Equal(300.21,u.Position.X,8);Assert.Equal(2.1,u.Speed,8);Assert.Equal(.1,battle.Time);
        Steps(battle,150);Assert.True((u.Position-new Vec2(310,300)).Length<1);Assert.Equal(OrderKind.Move,u.Order.Kind);Assert.Equal("arrived",u.MovementState);
    }
    [Fact] public void TurningIsRateLimitedAndCostsCohesion()
    {
        var u=Unit();MovementSystem.TurnTo(u,-Math.PI/2);
        Assert.Equal(-.65*.65*.1,u.Facing,10);Assert.InRange(u.Cohesion,99,100);Assert.True(u.Cohesion<100);
    }
    [Fact] public void FormationChangeTakesTimeAndStopsMovement()
    {
        var u=Unit();var battle=new BattleSimulation([u]);battle.Issue(new(0,new(OrderKind.Move,new(700,300)),Formation.Column));battle.Step();
        Assert.Equal(Formation.Line,u.Formation);Assert.Equal(new Vec2(300,300),u.Position);Assert.InRange(u.Cohesion,94,95);
        Steps(battle,75);Assert.Equal(Formation.Column,u.Formation);Assert.Null(u.NextFormation);Assert.Equal(22,u.Width);Assert.True(u.Position.X>300);
    }
    [Fact] public void ArrivalFacingStillTurnsGradually()
    {
        var u=Unit();var battle=new BattleSimulation([u]);battle.Issue(new(0,new(OrderKind.Move,u.Position,Math.PI/2)));battle.Step();
        Assert.True(u.Facing>0 && u.Facing<Math.PI/2);Steps(battle,100);Assert.True(Math.Abs(Vec2.AngleDelta(u.Facing,Math.PI/2))<1e-8);
    }
    [Fact] public void DirectionAndCategoryAffectCongestion()
    {
        double Cost(string kind,Vec2 a,Vec2 b)
        { var x=Unit(0,kind);var y=Unit(1,kind);x.Velocity=a;y.Velocity=b;CongestionSystem.Update([x,y],new(),new());return x.CongestionSpeed; }
        Assert.True(Cost("infantry",new(2,0),new(2,0))>Cost("infantry",new(2,0),new(-2,0)));
        Assert.True(Cost("cavalry",new(5,0),new(5,0))>Cost("infantry",new(2,0),new(2,0)));
        Assert.True(Cost("cavalry",new(5,0),new(5,0))>Cost("cavalry",new(5,0),new(2,0)));
    }
    [Fact] public void StationaryOverlapDoesNotContinuouslyDamageCohesion()
    {
        var u=Unit();var v=Unit(1);u.Cohesion=80;CongestionSystem.Update([u,v],new(),new(),.1);
        Assert.Equal(80,u.Cohesion);Assert.Equal(0,u.CongestionLoss);Assert.Equal(1,u.Congestion);
    }
    [Fact] public void StationarySeparationIsGradualStableAndRespectsHoldPriority()
    {
        var a=Unit();var b=Unit(1);var battle=new BattleSimulation([a,b]);battle.Issue(new(0,new(OrderKind.Hold)));var anchor=a.Position;
        Steps(battle,15);Assert.Equal(anchor,b.Position);Steps(battle,300);
        Assert.Equal(anchor,a.Position);Assert.Equal(OrderKind.Hold,b.Order.Kind);Assert.True(OrientedRect.IntersectionArea(a.Rect,b.Rect)<.01);
        var final=b.Position;Steps(battle,200);Assert.True((b.Position-final).Length<.05);
    }
    [Fact] public void ConflictingMoveOrdersKeepTheirPreferredDestination()
    {
        var a=Unit(position:new(220,300));var b=Unit(1,position:new(220,390));var battle=new BattleSimulation([a,b]);var goal=new Vec2(420,340);
        battle.Issue(new(0,new(OrderKind.Move,goal,0)));battle.Issue(new(1,new(OrderKind.Move,goal,0)));Steps(battle,1800);
        Assert.Equal(goal,a.Order.Destination);Assert.Equal(goal,b.Order.Destination);Assert.True(OrientedRect.IntersectionArea(a.Rect,b.Rect)<.01);
    }
    [Fact] public void FriendlyCrossingsAreSoftAndCanComplete()
    {
        var a=Unit(position:new(350,300));var b=Unit(1,position:new(530,300));b.Facing=Math.PI;var battle=new BattleSimulation([a,b]);
        battle.Issue(new(0,new(OrderKind.Move,new(650,300))));battle.Issue(new(1,new(OrderKind.Move,new(200,300))));
        double maximum=0;for(int i=0;i<1800;i++){battle.Step();maximum=Math.Max(maximum,a.Congestion);}
        Assert.True(maximum>.5);Assert.True(a.Position.X>640);Assert.True(b.Position.X<210);
    }
    [Fact] public void EnemyContactDoesNotAllowPassingThrough()
    {
        var a=Unit(position:new(400,300));var b=Unit(1,position:new(480,300),army:1);var battle=new BattleSimulation([a,b]);battle.Issue(new(0,new(OrderKind.Move,new(900,300))));
        Steps(battle,1200);Assert.True(a.Position.X<b.Position.X);Assert.True(OrientedRect.IntersectionArea(a.Rect,b.Rect)<.1);Assert.Equal(240,a.Strength);Assert.Equal(240,b.Strength);
    }
    [Fact] public void BattlefieldBoundsAccountForOrientedFootprints()
    {
        var u=Unit();var battle=new BattleSimulation([u]);battle.Issue(new(0,new(OrderKind.Move,new(2000,-2000))));Steps(battle,2000);
        for(int i=0;i<4;i++){var p=u.Rect.Corner(i);Assert.InRange(p.X,-1e-8,1000+1e-8);Assert.InRange(p.Y,-1e-8,600+1e-8);}
        Assert.True(double.IsFinite(u.Facing));Assert.InRange(u.Cohesion,0,100);Assert.InRange(u.Fatigue,0,100);
    }
    [Fact] public void ArtilleryHasLimberAndSetupDelay()
    {
        var u=Unit(kind:"artillery");var battle=new BattleSimulation([u]);battle.Issue(new(0,new(OrderKind.Move,new(320,300))));Steps(battle,20);
        Assert.Equal(300,u.Position.X);Assert.True(u.Limbered);Steps(battle,500);Assert.True(u.Position.X>319);Assert.False(u.Limbered);
    }
    [Fact] public void TerrainMovementUsesForestFormationAndCategory()
    {
        var terrain=new TerrainMap(forests:[new(300,300,100,100)]);var infantry=Unit();var cavalry=Unit(1,"cavalry");
        double line=terrain.MovementEffect(infantry,new(1,0)).Speed;
        infantry.Formation=Formation.Column;Assert.True(terrain.MovementEffect(infantry,new(1,0)).Speed>line);
        Assert.True(terrain.MovementEffect(cavalry,new(1,0)).Speed<line);
        var light=Unit(2,"haudenosaunee_skirmishers");Assert.True(terrain.MovementEffect(light,new(1,0)).Speed>line);
    }
    [Fact] public void UphillMovementSlowsAndDownhillIsBounded()
    {
        var terrain=new TerrainMap([new(400,300,100,100,40)]);var u=Unit();
        Assert.True(terrain.MovementEffect(u,new(1,0)).Speed<1);Assert.InRange(terrain.MovementEffect(u,new(-1,0)).Speed,.2,1.12);
    }
    [Fact] public void SnapshotsAreSafeCopies()
    { var u=Unit();var b=new BattleSimulation([u]);var snapshot=b.Snapshot();u.Position=new(800,500);u.Cohesion=1;Assert.Equal(new Vec2(300,300),snapshot.Units[0].Position);Assert.Equal(100,snapshot.Units[0].Cohesion); }
    [Fact] public void RegimentIterationIsSortedAndStaticTerrainCannotBeMutated()
    {
        var battle=new BattleSimulation([Unit(5),Unit(2)]);Assert.Equal(2,battle.Units[0].Id);
        Hill[] hills=[new(300,300,80,80,20)];var terrain=new TerrainMap(hills);hills[0]=new(300,300,80,80,90);
        Assert.Equal(20,terrain.Elevation(new(300,300)),8);
        Assert.IsAssignableFrom<System.Collections.ObjectModel.ReadOnlyCollection<Formation>>(Archetypes.Get("infantry").Formations);
    }
    [Fact] public void InvalidCommandsCannotIntroduceNaN()
    { var b=new BattleSimulation([Unit()]);Assert.Throws<ArgumentException>(()=>b.Issue(new(0,new(OrderKind.Move,new(double.NaN,0))))); }
    [Fact] public void ClockRetainsDebtAndPauseDoesNotAccumulateTime()
    {
        var clock=new SimulationClock(new([Unit()])){Speed=10};clock.Advance(1);Assert.Equal(16,clock.Battle.Tick);Assert.True(clock.Accumulator>8);
        while(clock.Accumulator>Rules.Dt-1e-10)clock.Advance(0);Assert.Equal(100,clock.Battle.Tick);
        clock.Playing=false;clock.Advance(10);Assert.Equal(100,clock.Battle.Tick);Assert.True(clock.SingleStep());Assert.Equal(101,clock.Battle.Tick);
        clock.Playing=true;Assert.False(clock.SingleStep());
    }
    [Theory] [InlineData(1)] [InlineData(2)] [InlineData(4)] [InlineData(10)]
    public void ClockIsIndependentOfFrameGrouping(int speed)
    {
        int Run(int fps){var clock=new SimulationClock(new([Unit()])){Speed=speed};for(int i=0;i<fps*2;i++)clock.Advance(1.0/fps);return clock.Battle.Tick;}
        Assert.Equal(20*speed,Run(20));Assert.Equal(Run(20),Run(144));
    }
    [Theory]
    [InlineData("straight")] [InlineData("turning")] [InlineData("formation")] [InlineData("friendly-crossing")]
    [InlineData("cavalry-overtaking")] [InlineData("stationary-separation")] [InlineData("destination-conflict")]
    [InlineData("congested")] [InlineData("boundaries")] [InlineData("artillery-march")] [InlineData("woodland-march")]
    public void PythonReferencesMatchAndCSharpIsDeterministic(string name)
    {
        string folder=Path.Combine(AppContext.BaseDirectory,"fixtures");var definition=ScenarioDefinition.Load(Path.Combine(folder,name+".json"));
        string Run()
        {
            var battle=definition.Create();var frames=new List<BattleSnapshot>();var ticks=definition.SampleTicks.ToHashSet();ticks.Add((int)Math.Round(definition.Duration*10));
            for(;;){if(ticks.Contains(battle.Tick))frames.Add(battle.Snapshot());if(battle.Time>=definition.Duration)break;definition.IssueScheduled(battle);battle.Step();}
            return JsonSerializer.Serialize(new{name=definition.Name,snapshots=frames},ScenarioJson.Options);
        }
        string actual=Run();Assert.Equal(actual,Run());
        using var expected=JsonDocument.Parse(File.ReadAllText(Path.Combine(folder,"references",name+".json")));
        using var result=JsonDocument.Parse(actual);Compare(expected.RootElement,result.RootElement,name);
    }
    private static void Compare(JsonElement expected,JsonElement actual,string path)
    {
        switch(expected.ValueKind)
        {
            case JsonValueKind.Object:foreach(var p in expected.EnumerateObject())Compare(p.Value,actual.GetProperty(p.Name),path+"."+p.Name);break;
            case JsonValueKind.Array:
                Assert.Equal(expected.GetArrayLength(),actual.GetArrayLength());int i=0;foreach(var item in expected.EnumerateArray()){Compare(item,actual[i],path+$"[{i}]");i++;}break;
            case JsonValueKind.Number:Assert.True(double.IsFinite(actual.GetDouble())&&Math.Abs(expected.GetDouble()-actual.GetDouble())<=1e-5,$"{path}: {expected} != {actual}");break;
            default:Assert.Equal(expected.ToString(),actual.ToString());break;
        }
    }
}
