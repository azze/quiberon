using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class MoraleCavalryTests
{
    private static Regiment Unit(int id=0,int army=0,double x=500,double y=300,string type="infantry",double facing=0)
        =>new(id,army,$"Regiment {id}",Archetypes.Get(type),new(x,y),facing);
    private static BattleSimulation Battle(Regiment[] units,ISimulationRandom? random=null, TerrainMap? terrain=null,Rules? rules=null,long seed=17)
        =>new(units,rules??new(){Width=1600,Height=800,CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true},terrain,seed,random);
    private static void Steps(BattleSimulation b,int n){for(int i=0;i<n && b.Result is null;i++)b.Step();}
    [Fact] public void CasualtyShockAffectsMoraleSeparatelyFromCohesion()
    {
        var a=Unit();var target=Unit(1,1,600);var b=Battle([a,target]);
        b.Combat.Damage(target,24,a,4,"controlled fire");
        Assert.Equal(71.5,target.Morale,9);Assert.Equal(85.6,target.Cohesion,9);Assert.Equal(85.6,a.Morale,9);Assert.Equal(0,target.LastAttackerId);
    }
    [Theory]
    [InlineData(23,MoraleState.Steady,MoraleState.Routing)]
    [InlineData(39,MoraleState.Steady,MoraleState.Wavering)]
    [InlineData(59,MoraleState.Steady,MoraleState.Shaken)]
    [InlineData(62,MoraleState.Shaken,MoraleState.Shaken)]
    [InlineData(67,MoraleState.Shaken,MoraleState.Steady)]
    [InlineData(45,MoraleState.Wavering,MoraleState.Wavering)]
    [InlineData(47,MoraleState.Wavering,MoraleState.Shaken)]
    public void ThresholdsHaveTheCurrentPythonHysteresis(double morale,MoraleState initial,MoraleState expected)
    {var u=Unit();u.Morale=morale;u.State=initial;var b=Battle([u]);b.MoraleSystem.Update();Assert.Equal(expected,u.State);}
    [Theory]
    [InlineData(MoraleState.Steady,1)] [InlineData(MoraleState.Shaken,.7)] [InlineData(MoraleState.Wavering,.4)] [InlineData(MoraleState.Routing,.1)]
    public void MoraleStatesScaleBothMeleeDamageAndShock(MoraleState state,double factor)
    {
        var a=Unit();var t=Unit(1,1,512,facing:Math.PI);var b=Battle([a,t]);var original=b.Combat.CalculateMelee(a,t);
        a.State=state;var actual=b.Combat.CalculateMelee(a,t);
        Assert.Equal(original.Power*factor,actual.Power,9);Assert.Equal(original.Shock*factor,actual.Shock,9);
    }
    [Fact] public void RallyingMeleeRecoveryIsGradualAndCannotFire()
    {
        var a=Unit();var t=Unit(1,1,600);var b=Battle([a,t]);a.State=MoraleState.Rallying;a.Morale=28;a.Cohesion=20;
        Assert.Equal(.25,MoraleSystem.MeleeEffectiveness(a,b.Rules));Assert.False(b.Combat.Fire(a,t));
        a.Morale=48;a.Cohesion=45;Assert.Equal(.60,MoraleSystem.MeleeEffectiveness(a,b.Rules),9);
    }
    [Fact] public void BrokenMeleeHasNoGuaranteedCasualtyFloor()
    {
        var a=Unit();a.Strength=1;a.Cohesion=0;a.State=MoraleState.Routing;
        var t=Unit(1,1,512,facing:Math.PI);var b=Battle([a,t],new TapeRandom(Enumerable.Repeat(.999,100)));
        b.Combat.ResolveMelee(b.Units);Assert.Equal(t.MaximumStrength,t.Strength);
    }
    [Fact] public void RoutingLosesCohesionAndRejectsOrdinaryOrders()
    {
        var u=Unit();u.Morale=10;var b=Battle([u]);b.Step();Assert.Equal(MoraleState.Routing,u.State);
        double before=u.Cohesion;b.Issue(new(0,new(OrderKind.Move,new(1200,300))));b.Issue(new(0,Formation:Formation.Column));Steps(b,10);
        Assert.Equal(OrderKind.Hold,u.Order.Kind);Assert.Equal(0,u.TransitionLeft);Assert.True(u.Cohesion<before-.9);
    }
    [Fact] public void EscapePlanningRunsAwayFromAnEnemyBehindTheHomeEdge()
    {
        var u=Unit(x:500);u.State=MoraleState.Routing;u.Morale=10;var threat=Unit(1,1,430);
        var b=Battle([u,threat]);var goal=RoutingSystem.Destination(b,u);
        Assert.NotNull(goal);Assert.True(goal.Value.X>u.Position.X);Assert.True(goal.Value.Finite);
    }
    [Fact] public void FootprintExitPreservesSurvivorsAndClearsTargets()
    {
        var u=Unit(x:7,facing:Math.PI);u.State=MoraleState.Routing;u.Morale=10;
        var b=Battle([u]);b.Step();Assert.True(u.Withdrawn);Assert.False(u.Active);Assert.Equal(240,u.Strength);
        Assert.Null(u.TargetId);Assert.Equal(CombatState.Withdrawn,u.CombatState);Assert.Contains(b.Events,e=>e.Kind=="withdraw");
    }
    [Fact] public void SafeRegimentRalliesGraduallyAndRegainsControlOnlyOnDuty()
    {
        var u=Unit(facing:Math.PI);u.State=MoraleState.Routing;u.Morale=5;u.Cohesion=65;
        var b=Battle([u]);Steps(b,230);Assert.Equal(MoraleState.Rallying,u.State);Assert.InRange(u.Morale,28,31);Assert.False(u.Effective);
        Steps(b,250);Assert.True(u.Effective);Assert.Equal(MoraleState.Shaken,u.State);Assert.InRange(u.Morale,48,60);
        b.Issue(new(0,new(OrderKind.Move,new(600,400))));b.Step();Assert.Equal(OrderKind.Move,u.Order.Kind);
    }
    [Fact] public void NearbyEnemiesInterruptRallyingWithoutRepeatingInitialRoutShock()
    {
        var u=Unit();u.State=MoraleState.Rallying;u.Morale=30;
        var friend=Unit(1,0,530,500);var enemy=Unit(2,1,600);var b=Battle([u,friend,enemy]);b.MoraleSystem.Update();
        Assert.Equal(MoraleState.Routing,u.State);Assert.Equal(0,b.Metrics.CascadeShocks);Assert.Equal(0,u.SafeTime);
    }
    [Fact] public void CascadesAreOneShotSpatiallyAttenuatedAndDeferred()
    {
        var a=Unit(x:500,y:300);a.Morale=10;
        var near=Unit(1,0,520,300);near.Morale=24;var far=Unit(2,0,700,300);far.Morale=50;
        var b=Battle([a,near,far]);b.MoraleSystem.Update();
        Assert.Equal(1,b.Metrics.Routs);Assert.Equal(MoraleState.Wavering,near.State);Assert.True(near.Morale<23);
        Assert.True(far.Morale>=50);Assert.Equal(1,b.Metrics.CascadeShocks);
        b.MoraleSystem.Update();Assert.Equal(MoraleState.Routing,near.State);Assert.Equal(2,b.Metrics.Routs);
        long count=b.Metrics.CascadeShocks;b.MoraleSystem.Update();Assert.Equal(count,b.Metrics.CascadeShocks);
    }
    [Fact] public void ThreatenedRegimentsCannotUseSafeMoraleRecovery()
    {
        var u=Unit();u.Morale=60;var b=Battle([u,Unit(1,1,620)]);b.MoraleSystem.Update();Assert.Equal(60,u.Morale);
        var safe=Battle([u]);safe.MoraleSystem.Update();Assert.True(u.Morale>60);
    }
    [Fact] public void VictoryUsesFightingStrengthAndTwelveSecondGrace()
    {
        var a=Unit(x:200);var t=Unit(1,1,1300);t.State=MoraleState.Routing;t.Morale=10;var b=Battle([a,t]);
        Steps(b,120);Assert.Null(b.Result);Steps(b,2);Assert.Equal("army_0",b.Result?.Id);Assert.True(t.Strength>0);
    }
    [Fact] public void RecoveredFightingStrengthResetsTheDefeatTimer()
    {
        var a=Unit(x:200);var t=Unit(1,1,1200);t.State=MoraleState.Routing;t.Morale=10;var b=Battle([a,t]);Steps(b,100);
        t.State=MoraleState.Shaken;t.Morale=50;b.Step();Assert.False(b.DefeatSince.ContainsKey(1));
        t.State=MoraleState.Routing;t.Morale=10;Steps(b,100);Assert.Null(b.Result);
    }
    [Fact] public void ChargeAcceleratesAndCannotBuildInstantMomentum()
    {
        var a=Unit(type:"cavalry");var t=Unit(1,1,590,facing:Math.PI);var b=Battle([a,t]);b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();
        Assert.Equal(CavalryState.Charging,a.CavalryState);Assert.InRange(a.Speed,0,.200001);Assert.Equal(0,a.ChargeMomentum);
        Steps(b,30);Assert.True(a.Speed>5);Assert.True(a.ChargeMomentum>0);Assert.True(a.ChargeDistance>5);
    }
    [Fact] public void ShortApproachAndDisorganizationCannotGrantFullCharge()
    {
        var a=Unit(type:"cavalry");var t=Unit(1,1,520,facing:Math.PI);var b=Battle([a,t]);b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));Steps(b,20);
        Assert.Equal(0,b.Metrics.ChargeImpacts);Assert.Equal(0,b.Metrics.ChargeStarts);
    }
    [Fact] public void ChargeImpactIsConsumedOnceEvenIfAttackOrdersRepeat()
    {
        var a=Unit(type:"cavalry");var t=Unit(1,1,590,facing:Math.PI);var b=Battle([a,t]);b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));Steps(b,150);
        Assert.Equal(1,b.Metrics.ChargeImpacts);Assert.False(a.ChargeReady);
        for(int i=0;i<20;i++){b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();}
        Assert.Equal(1,b.Metrics.ChargeImpacts);
    }
    private static (BattleSimulation Battle,Regiment Cavalry,Regiment Target) ImpactCase(double facing= Math.PI,double cohesion=100, MoraleState state=MoraleState.Steady)
    {
        var a=Unit(type:"cavalry");var t=Unit(1,1,515,facing:facing);t.Cohesion=cohesion;t.State=state;
        var b=Battle([a,t],new TapeRandom(Enumerable.Repeat(.5,1000)));
        a.CavalryState=CavalryState.Charging;a.ChargeSequence=1;a.ChargeMomentum=.9;a.Velocity=new Vec2(12,0);return(b,a,t);
    }
    [Fact] public void PreparedFrontResistsAndRecoilIsARealOutcome()
    {
        var (b,a,t)=ImpactCase();b.Cavalry.Impact(a,t);
        Assert.Equal(CavalryState.Recoil,a.CavalryState);Assert.Equal("prepared front",a.ChargeResult);Assert.Equal(1,b.Metrics.FailedCharges);
        Assert.NotNull(a.RecoilGoal);Assert.True(a.RecoilGoal.Value.X<a.Position.X);
    }
    [Fact] public void FlankAndWaveringTargetsSufferMoreThanPreparedFronts()
    {
        var front=ImpactCase();front.Battle.Cavalry.Impact(front.Cavalry,front.Target);
        var flank=ImpactCase(Math.PI/2);flank.Battle.Cavalry.Impact(flank.Cavalry,flank.Target);
        var weak=ImpactCase(Math.PI,30,MoraleState.Wavering);weak.Battle.Cavalry.Impact(weak.Cavalry,weak.Target);
        Assert.True(flank.Battle.Metrics.ImpactCasualties>front.Battle.Metrics.ImpactCasualties*3);
        Assert.True(weak.Battle.Metrics.ImpactCasualties>front.Battle.Metrics.ImpactCasualties*3);
    }
    [Fact] public void ImpactDoesNotAlsoDealAFullOrdinaryCavalryHit()
    {
        var (b,a,t)=ImpactCase(Math.PI/2);a.Order=new(OrderKind.Charge,TargetId:1);a.TargetId=1;
        b.Combat.ResolveMelee(b.Units);Assert.Equal(1,b.Metrics.ChargeImpacts);
        Assert.Equal(t.MaximumStrength-b.Metrics.ImpactCasualties,t.Strength);
    }
    [Fact] public void DenseForestPreventsFullOpenGroundCharge()
    {
        var a=Unit(type:"cavalry");var t=Unit(1,1,590,facing:Math.PI);
        var b=Battle([a,t],terrain:new(forests:[new(550,300,200,150,1)]));b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));Steps(b,100);
        Assert.Equal(0,b.Metrics.ChargeStarts);Assert.True(a.Speed<6);Assert.True(a.Cohesion<100);
    }
    private static (BattleSimulation Battle,Regiment[] Riders,Regiment Target) PursuitCase(int count=1,int targetStrength=120,long seed=17)
    {
        var t=Unit(count,1,700);t.State=MoraleState.Routing;t.Morale=10;t.Cohesion=25;t.Strength=targetStrength;
        var riders=Enumerable.Range(0,count).Select(i=>Unit(i,0,630,295+i*10,"cavalry")).ToArray();
        var b=Battle(riders.Concat([t,Unit(count+1,1,1400,650),Unit(count+2,0,120,650)]).ToArray(),seed:seed);
        foreach(var a in riders)b.Issue(new(a.Id,new(OrderKind.Attack,TargetId:t.Id)));return(b,riders,t);
    }
    [Fact] public void CavalryCatchesRoutingInfantryAndInflictsMovingPursuitLosses()
    {
        var (b,riders,t)=PursuitCase();double start=riders[0].Position.X;Steps(b,300);
        Assert.True(b.Metrics.PursuitCasualties>20);Assert.True(b.Metrics.PursuitLosses<10);
        Assert.True(riders[0].Position.X>start+50);Assert.True(riders[0].Strength>85);Assert.True(t.Strength<90);
    }
    [Fact] public void MultiplePursuersMoveWithoutExcessiveCongestionAndDamageIsCapped()
    {
        var (b,riders,t)=PursuitCase(2);Steps(b,250);
        Assert.True(b.Metrics.PursuitCasualties>20);Assert.All(riders,u=>{Assert.True(u.Position.X>690);Assert.True(u.Cohesion>65);});
        Assert.True(b.Metrics.PursuitCasualties<=b.Metrics.PursuitPulses*(int)(t.MaximumStrength*b.Rules.PursuitMaxFraction));
        Assert.True(b.Metrics.ChargeImpacts<=2);
    }
    [Fact] public void PlayerHoldInterruptsPursuitAndCannotResetImpactLock()
    {
        var (b,riders,_)=PursuitCase();Steps(b,180);var a=riders[0];b.Issue(new(a.Id,new(OrderKind.Hold)));b.Step();
        Assert.NotEqual(CavalryState.Pursuit,a.CavalryState);Assert.NotEqual(CavalryState.Charging,a.CavalryState);Assert.Null(a.CavalryTargetId);Assert.Null(a.PursuitId);Assert.False(a.ChargeReady);
        Assert.Contains(b.Events,e=>e.Kind=="pursuit_end");
    }
    [Fact] public void DisappearingTargetCleansPursuitReferences()
    {
        var (b,riders,t)=PursuitCase();Steps(b,180);t.Withdrawn=true;b.Step();var a=riders[0];
        Assert.NotEqual(t.Id,a.CavalryTargetId);Assert.Null(a.PursuitId);Assert.NotEqual(t.Id,a.TargetId);
    }
    [Fact] public void DynamicsSnapshotsEventsAndCompleteRunsAreRepeatable()
    {
        string Run(){var (b,_,_)=PursuitCase(2);Steps(b,400);Assert.All(b.Events,e=>Assert.Equal(e.Tick*.1,e.Time));
            return JsonSerializer.Serialize(new{snapshot=b.Snapshot(),events=b.Events,draws=b.Random.Draws},ScenarioJson.Options);}
        Assert.Equal(Run(),Run());
    }
    [Fact] public void ARouteCanPassAStationaryFriendlyLineWithoutPermanentBlocking()
    {
        var fleeing=Unit();fleeing.State=MoraleState.Routing;fleeing.Morale=10;
        var friend=Unit(1,0,550);var enemy=Unit(2,1,430);var b=Battle([fleeing,friend,enemy]);Steps(b,500);
        Assert.True(fleeing.Position.X>friend.Position.X+15);Assert.True(fleeing.Cohesion<60);
    }
    [Fact] public void ExplicitPursuitEndsWhenItsTargetRallies()
    {
        var (b,riders,t)=PursuitCase();Steps(b,160);var u=riders[0];u.Order=new(OrderKind.Pursue,TargetId:t.Id);
        t.State=MoraleState.Rallying;t.Morale=30;b.Combat.PreparePhase(b.Units);
        b.Cavalry.Intent(u,b.Combat.Intent(u));
        Assert.Equal(OrderKind.Hold,u.Order.Kind);Assert.Null(u.CavalryTargetId);Assert.Null(u.PursuitId);
    }
    [Fact] public void ChargeRearmingRequiresRealClearanceTimeAndCooldown()
    {
        var (b,u,t)=ImpactCase();b.Cavalry.Impact(u,t);b.Issue(new(0,new(OrderKind.Move,new(300,300))));
        Steps(b,50);Assert.False(u.ChargeReady);
        Steps(b,250);Assert.True(u.ChargeReady);Assert.True(CavalrySystem.Gap(u,t)>b.Rules.ChargeClearance);
    }
    [Theory]
    [InlineData(12)] [InlineData(24)] [InlineData(36)] [InlineData(60)]
    public void DynamicsStressScenariosFightRouteChargeAndPursueWithinBounds(int count)
    {
        var definition=CombatScenarios.Get($"benchmark-dynamics-{count}");var b=definition.Create();
        for(int i=0;i<700;i++){definition.IssueScheduled(b);b.Step();}
        Assert.Null(b.Result);Assert.Equal(700,b.Tick);
        Assert.True(b.Metrics.Routs>0 && b.Metrics.ChargeImpacts>0 && b.Metrics.PursuitCasualties>0);
        Assert.All(b.Units,u=>
        {
            Assert.InRange(u.Strength,0,u.MaximumStrength);Assert.InRange(u.Morale,0,100);Assert.InRange(u.Cohesion,0,100);
            Assert.True(u.Position.Finite&&double.IsFinite(u.Facing+u.Speed));Assert.True(u.Speed>=0);
            Assert.True(u.CavalryTargetId is null||b.Unit(u.CavalryTargetId.Value)?.Active==true);
            Assert.True(u.PursuitId is null||b.Unit(u.PursuitId.Value)?.Active==true);
        });
    }
    [Fact] public void AllocationDiagnosticsDoNotChangeTheBattleOrRandomStream()
    {
        var definition=CombatScenarios.Get("benchmark-dynamics-12");var normal=definition.Create();var measured=definition.Create(true);
        for(int i=0;i<700;i++){definition.IssueScheduled(normal);definition.IssueScheduled(measured);normal.Step();measured.Step();}
        Assert.Equal(JsonSerializer.Serialize(normal.Snapshot(),ScenarioJson.Options),JsonSerializer.Serialize(measured.Snapshot(),ScenarioJson.Options));
        Assert.Equal(normal.Random.Draws,measured.Random.Draws);Assert.True(measured.Metrics.MoraleAllocatedBytes>0);
        Assert.Equal(0,normal.Metrics.MoraleAllocatedBytes);
    }
    [Fact] public void ExplicitPursuitDoesNotSwitchToAnotherRoutingTarget()
    {
        var (b,riders,t)=PursuitCase();Steps(b,150);var u=riders[0];u.Order=new(OrderKind.Pursue,TargetId:t.Id);
        t.Withdrawn=true;var other=b.Units.Last();other.State=MoraleState.Routing;other.Morale=10;b.Step();
        Assert.Equal(OrderKind.Hold,u.Order.Kind);Assert.Null(u.PursuitId);
    }
    [Fact] public void PhysicalContactCanIdentifyAPreviouslyConcealedFugitive()
    {
        var u=Unit(type:"cavalry");var t=Unit(1,1,515);t.State=MoraleState.Routing;t.Morale=10;
        var b=Battle([u,t],terrain:new([new(507.5,300,2,70,10)]));u.Order=new(OrderKind.Attack,TargetId:1);
        b.Combat.Intent(u);Assert.Null(u.TargetId);b.Cavalry.Intent(u,null);
        Assert.True(b.Cavalry.Contact(u,t));Assert.Equal(t.Id,u.CavalryTargetId);
        b.Cavalry.Pursuits(b.Units);Assert.Equal(CombatState.Pursuit,u.CombatState);
    }
    [Theory]
    [InlineData(1)] [InlineData(7)] [InlineData(31)]
    public void FreshGenericCavalryOverrunsEvenFullStrengthRoutingInfantry(long seed)
    {
        var(b,riders,t)=PursuitCase(targetStrength:240,seed:seed);t.Cohesion=100;
        for(int i=0;i<1500 && t.Active;i++){b.Step();Assert.True(riders[0].Effective);}
        Assert.False(t.Active);Assert.Equal(0,t.Strength);Assert.True(riders[0].Strength>=75);
        Assert.True(b.Metrics.PursuitCasualties>0);Assert.True(b.Metrics.PursuitLosses<25);
    }
}
