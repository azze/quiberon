using Quiberon.Simulation;
using Xunit;

public class CombatTests
{
    private static Regiment Unit(int id=0,int army=0,Vec2? position=null,double facing=0,string archetype="infantry")=>new(id,army,$"Line {id}",Archetypes.Get(archetype),position??new(300,300),facing);
    private static BattleSimulation Battle(Regiment[] units,TerrainMap? terrain=null,ISimulationRandom? random=null,long seed=17)=>new(units,new(){CombatEnabled=true},terrain,seed,random);
    private static void Steps(BattleSimulation b,int n){for(int i=0;i<n;i++)b.Step();}
    [Fact] public void PortableRandomHasStableDrawsAndTapeIsFinite()
    {
        var a=new SimulationRandom(17);var b=new SimulationRandom(17);var c=new SimulationRandom(18);
        var first=a.NextDouble();Assert.NotEqual(first,c.NextDouble());Assert.Equal(first,b.NextDouble());
        for(int i=0;i<1000;i++){double x=a.NextDouble();Assert.InRange(x,0,1);Assert.Equal(x,b.NextDouble());}
        var tape=new TapeRandom([.1,.2]);Assert.Equal(.1,tape.NextDouble());Assert.Equal(.2,tape.NextDouble());Assert.Throws<InvalidOperationException>(()=>tape.NextDouble());
        Assert.Throws<ArgumentException>(()=>new TapeRandom([double.NaN]));
    }
    [Fact] public void FlatVisibilityIsClearAndCachingDoesNotRepeatRays()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b]);
        Assert.True(battle.Combat.Sight(a,b).Visible);Assert.Equal(1,battle.Metrics.VisibilityCalculations);
        battle.Combat.Sight(a,b);Assert.Equal(1,battle.Metrics.VisibilityCalculations);Assert.Equal(2,battle.Metrics.VisibilityQueries);
        b.Position+=new Vec2(1,0);battle.Combat.Sight(a,b);Assert.Equal(2,battle.Metrics.VisibilityCalculations);
    }
    [Fact] public void ARealRidgeBlocksDirectMusketFire()
    {
        var terrain=new TerrainMap([new(350,300,20,80,20)]);var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b],terrain);
        Assert.False(battle.Combat.Sight(a,b).Visible);Assert.Equal("ridge",battle.Combat.Sight(a,b).Reason);Assert.False(battle.Combat.CanFire(a,b));
        int strength=b.Strength;Steps(battle,150);Assert.Equal(strength,b.Strength);Assert.Equal(0,battle.Metrics.Volleys);
    }
    [Fact] public void ElevatedEndpointsCanSeeOverLowerGround()
    {
        var terrain=new TerrainMap([new(300,300,22,50,20),new(450,300,22,50,20),new(375,300,15,50,4)]);
        Assert.True(terrain.Visibility(new(300,300),new(450,300)).Visible);
    }
    [Fact] public void ForestDepthIsDeterministicAndCloseTroopsCanEngage()
    {
        var terrain=new TerrainMap(forests:[new(400,300,180,100,1)]);
        Assert.False(terrain.Visibility(new(300,300),new(450,300)).Visible);
        var close=terrain.Visibility(new(380,300),new(410,300));Assert.True(close.Visible);Assert.Equal("obscured",close.State);Assert.True(close.Transmission<1);
    }
    [Fact] public void RangeArcAndTargetValidityAreRequired()
    {
        var a=Unit();var b=Unit(1,1,new(455,300),Math.PI);var battle=Battle([a,b]);
        Assert.True(battle.Combat.CanFire(a,b));b.Position=new(455.01,300);Assert.False(battle.Combat.CanFire(a,b));
        b.Position=new(400,300);a.Facing=Math.PI;Assert.False(battle.Combat.CanFire(a,b));a.Facing=0;
        Assert.False(battle.Combat.CanFire(a,a));b.Strength=0;Assert.False(battle.Combat.CanFire(a,b));
    }
    [Fact] public void DenseFriendlyScreenBlocksAndAFlankingLaneRestoresFire()
    {
        var a=Unit();var friend=Unit(1,0,new(350,300));var b=Unit(2,1,new(430,300),Math.PI);var battle=Battle([a,friend,b]);
        Assert.False(battle.Combat.CanFire(a,b));Assert.Equal(0,battle.Combat.FriendlyFireFactor(a,b));
        friend.Position=new(350,390);battle.Combat.PreparePhase(battle.Units);
        Assert.True(battle.Combat.CanFire(a,b));Assert.Equal(1,battle.Combat.FriendlyFireFactor(a,b));
    }
    [Fact] public void CoincidentLinesShareOneFrontageAndOverlappingTargetsRemainHittable()
    {
        var a=Unit();var f=Unit(1);var f2=Unit(2);var b=Unit(3,1,new(430,300),Math.PI);var b2=Unit(4,1,b.Position,Math.PI);var battle=Battle([a,f,f2,b,b2]);
        Assert.True(battle.Combat.CanFire(a,b));Assert.Equal(1/3.0,battle.Combat.FriendlyFireFactor(a,b),8);
        Assert.InRange(battle.Combat.CalculateVolley(a,b).Shots,32,34);
    }
    [Fact] public void LooseScreensAllowMoreFireAndElevationCanClearFriendlyLines()
    {
        var a=Unit();var f=Unit(1,0,new(350,300));f.Formation=Formation.Skirmish;var b=Unit(2,1,new(430,300),Math.PI);var battle=Battle([a,f,b]);
        Assert.True(battle.Combat.CanFire(a,b));Assert.InRange(battle.Combat.FriendlyFireFactor(a,b),.6,.7);
        f.Formation=Formation.Line;
        var elevated=Battle([a,f,b],new([new(300,300,14,50,25),new(430,300,14,50,25)]));
        Assert.True(elevated.Combat.CanFire(a,b));
    }
    [Fact] public void ColumnAndDispersedFormationHaveDifferentFirepower()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b]);var line=battle.Combat.CalculateVolley(a,b);
        a.Formation=Formation.Column;Assert.True(battle.Combat.CalculateVolley(a,b).Shots<line.Shots/2);
        a.Formation=Formation.Line;b.Formation=Formation.Skirmish;Assert.Equal(line.Probability*.65,battle.Combat.CalculateVolley(a,b).Probability,10);
    }
    [Fact] public void MovementAndPoorCohesionReduceAccuracy()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b]);double ready=battle.Combat.CalculateVolley(a,b).Probability;
        a.Cohesion=20;Assert.True(battle.Combat.CalculateVolley(a,b).Probability<ready);a.Cohesion=100;
        MovementSystem.Move(a,new(500,300),battle.Rules,battle.Terrain,null);
        Assert.True(battle.Combat.CalculateVolley(a,b).Probability<ready*.5);
    }
    [Fact] public void VolleyUsesControlledDrawsAndReloadCannotBeBypassed()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b],random:new TapeRandom(Enumerable.Repeat(0.0,10000)));
        Assert.True(battle.Combat.Fire(a,b));Assert.Equal(130,b.Strength);Assert.Equal(12,a.ReloadLeft);Assert.True(b.Cohesion<100);Assert.Equal(85,b.Morale);
        Assert.False(battle.Combat.Fire(a,b));Assert.Equal(1,battle.Metrics.Volleys);
    }
    [Fact] public void ReloadAndFormationTransitionUseSimulationTicks()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b],random:new TapeRandom(Enumerable.Repeat(.999,100000)));
        battle.Step();Assert.Equal(2,battle.Metrics.Volleys);Steps(battle,119);Assert.Equal(2,battle.Metrics.Volleys);
        Steps(battle,2);Assert.Equal(4,battle.Metrics.Volleys);
        battle.Issue(new(0,Formation:Formation.Column));battle.Step();Assert.True(a.TransitionLeft>0);
    }
    [Fact] public void ExplicitAttackTargetIsBindingWhileBlocked()
    {
        var a=Unit();var designated=Unit(1,1,new(400,400),Math.PI);var other=Unit(2,1,new(400,300),Math.PI);var battle=Battle([a,designated,other]);
        battle.Issue(new(0,new(OrderKind.Attack,TargetId:1)));battle.Step();Assert.Equal(1,a.Order.TargetId);Assert.Equal(1,a.TargetId);
        Assert.Null(battle.Combat.SelectFireTarget(a));
    }
    [Fact] public void AttackAndAdvanceApproachThenFaceWithoutInstantRotation()
    {
        var a=Unit();var b=Unit(1,1,new(550,300),Math.PI);var battle=Battle([a,b]);battle.Issue(new(0,new(OrderKind.Attack,TargetId:1)));Steps(battle,600);
        Assert.True(a.Position.X>300);Assert.True(battle.Metrics.Volleys>0);Assert.True(a.Active);
    }
    [Fact] public void BasicMeleePulsesAtTwoSecondIntervalsWithoutCharges()
    {
        var a=Unit();var b=Unit(1,1,new(312,300),Math.PI);var battle=Battle([a,b]);battle.Step();int strength=b.Strength;
        Assert.Equal(CombatState.Melee,a.CombatState);Assert.Equal(1,battle.Metrics.MeleePulses);Steps(battle,19);Assert.Equal(strength,b.Strength);
        battle.Step();Assert.True(b.Strength<strength);Assert.Equal(0,battle.Metrics.Volleys);
    }
    [Fact] public void FlankAndRearMeleeAreStrongerThanPreparedFront()
    {
        var a=Unit();var b=Unit(1,1,new(312,300),Math.PI);var battle=Battle([a,b]);double front=battle.Combat.CalculateMelee(a,b).Power;
        b.Facing=Math.PI/2;Assert.Equal(front*1.6,battle.Combat.CalculateMelee(a,b).Power,8);
        b.Facing=0;Assert.Equal(front*2.2,battle.Combat.CalculateMelee(a,b).Power,8);
    }
    [Fact] public void MeleeInForestAndUphillHasExistingPenalties()
    {
        var a=Unit();var b=Unit(1,1,new(312,300),Math.PI);var open=Battle([a,b]);double power=open.Combat.CalculateMelee(a,b).Power;
        var woods=Battle([a,b],new(forests:[new(300,300,100,100)]));Assert.True(woods.Combat.CalculateMelee(a,b).Power<power);
        var hill=Battle([a,b],new([new(350,300,60,60,30)]));Assert.True(hill.Combat.CalculateMelee(a,b).Power<power);
    }
    [Fact] public void LeavingContactClearsEngagementAndDeadTargetsAreRemoved()
    {
        var a=Unit();var b=Unit(1,1,new(312,300),Math.PI);var battle=Battle([a,b]);battle.Step();Assert.Equal(1,battle.Combat.EngagementCount);
        b.Position=new(500,300);battle.Step();Assert.Equal(0,battle.Combat.EngagementCount);Assert.Contains(battle.Events,e=>e.Kind=="melee_leave");
        b.Strength=0;battle.Step();Assert.Null(a.TargetId);Assert.Equal(CombatState.Destroyed,b.CombatState);
    }
    [Fact] public void DestructionCompletesTemporaryBattleAndClockStopsSafely()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);b.Strength=1;var battle=Battle([a,b],random:new TapeRandom(Enumerable.Repeat(0.0,1000)));var clock=new SimulationClock(battle);
        clock.Advance(.2);Assert.Equal(0,b.Strength);Assert.Equal("army_0",battle.Result?.Id);Assert.Equal(1,battle.Tick);Assert.False(clock.Playing);
        clock.Advance(10);Assert.Equal(1,battle.Tick);Assert.False(clock.SingleStep());Assert.Equal(85,a.Morale);
        Assert.Contains(battle.Events,e=>e.Kind=="destroyed");Assert.Contains(battle.Events,e=>e.Kind=="battle_complete");Assert.Null(a.TargetId);
    }
    [Fact] public void EventsHaveStableSequenceSimulationTimesAndBoundedStorage()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b]);Steps(battle,200);
        long previous=-1;double time=-1;
        foreach(var e in battle.Events){Assert.Equal(previous+1,e.Sequence);Assert.True(e.Time>=time);Assert.Equal(e.Tick*.1,e.Time);previous=e.Sequence;time=e.Time;}
        Assert.True(battle.Events.Count<=4096);
    }
    [Fact] public void SeededCombatIsRepeatableAndOtherSeedsCanDiffer()
    {
        string Run(long seed){var b=Battle([Unit(),Unit(1,1,new(400,300),Math.PI)],seed:seed);Steps(b,300);return System.Text.Json.JsonSerializer.Serialize(b.Snapshot(),ScenarioJson.Options);}
        Assert.Equal(Run(17),Run(17));Assert.NotEqual(Run(17),Run(18));
    }
    [Fact] public void UnportedBatteriesAndCavalryDoNotDealCombatDamage()
    {
        var a=Unit(archetype:"artillery");var b=Unit(1,1,new(310,300),Math.PI,archetype:"cavalry");var battle=Battle([a,b]);Steps(battle,100);
        Assert.Equal(48,a.Strength);Assert.Equal(100,b.Strength);Assert.Equal(0,battle.Metrics.Volleys);Assert.Null(battle.Result);
    }
    [Fact] public void ExplicitMoveDisengagesThroughNormalTurningAndMovement()
    {
        var a=Unit();var b=Unit(1,1,new(312,300),Math.PI);var battle=Battle([a,b]);battle.Step();
        battle.Issue(new(0,new(OrderKind.Move,new(210,300))));Steps(battle,400);
        Assert.True(a.Position.X<280);Assert.Equal(0,battle.Combat.EngagementCount);
        Assert.NotEqual(CombatState.Melee,a.CombatState);Assert.Contains(battle.Events,e=>e.Kind=="melee_leave");
    }
    [Fact] public void FormationTransitionPreventsFiringEvenWithAReadyWeapon()
    {
        var a=Unit();var b=Unit(1,1,new(400,300),Math.PI);var battle=Battle([a,b]);
        battle.Issue(new(0,Formation:Formation.Column));Steps(battle,69);
        Assert.DoesNotContain(battle.Events,e=>e.Kind=="volley"&&e.UnitId==0);
        Steps(battle,3);Assert.Contains(battle.Events,e=>e.Kind=="volley"&&e.UnitId==0);
    }
    [Fact] public void BattleClockExecutesScenarioCommandsOnEveryAuthoritativeTick()
    {
        var definition=CombatScenarios.Get("infantry-duel") with {Commands=[new(0,0,new(OrderKind.Move,new(480,220))),new(3,0,new(OrderKind.Hold))]};
        var battle=definition.Create();var clock=new SimulationClock(battle,definition.IssueScheduled);clock.Advance(.5);
        Assert.Equal(5,battle.Tick);Assert.Equal(OrderKind.Hold,battle.Unit(0)!.Order.Kind);Assert.True(battle.Unit(0)!.Position.X>430);
    }
    [Theory]
    [InlineData(12)] [InlineData(24)] [InlineData(36)] [InlineData(60)]
    public void CrowdedCombatPreservesStateBoundsAndActuallyFights(int count)
    {
        var definition=CombatScenarios.Get($"benchmark-{count}");var battle=definition.Create();Steps(battle,700);
        Assert.True(battle.Metrics.Volleys>0&&battle.Metrics.MeleePulses>0&&battle.Metrics.Casualties>0);
        Assert.All(battle.Units,u=>
        {
            Assert.True(u.Position.Finite&&double.IsFinite(u.Facing+u.Speed));Assert.InRange(u.Cohesion,0,100);
            Assert.InRange(u.Strength,0,u.MaximumStrength);Assert.True(u.Speed>=0);
            Assert.True(u.TargetId is null||battle.Unit(u.TargetId.Value) is {Active:true});
            Assert.InRange(u.Position.X,0,battle.Rules.Width);Assert.InRange(u.Position.Y,0,battle.Rules.Height);
        });
    }
}
