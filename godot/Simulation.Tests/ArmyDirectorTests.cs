using Quiberon.Simulation;
using Xunit;
using System.Text.Json;

public class ArmyDirectorTests
{
    static Regiment U(int id,int army,double x,double y=300,string type="infantry",string personality="aggressive")=>new(id,army,$"Unit {id}",Archetypes.Get(type),new(x,y),army*Math.PI,commander:new($"officer-{id}",$"Officer {id}",Personality:personality,Specialization:type.Contains("artillery")?"artillerist":type.Contains("cavalry")?"firebrand":"drillmaster"));
    static BattleSimulation B(params Regiment[] units){var b=new BattleSimulation(units,new(){Width=1400,Height=900,CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true,ArtilleryEnabled=true,SpecialistsEnabled=true,AiEnabled=true,CommandersEnabled=true});b.Ai.ConfigureArmy(0,"balanced");return b;}
    [Fact] public void FiringPositionCannotSuppressPreparingLineFormation()
    {
        var u=U(0,0,300);u.Formation=Formation.Column;var b=B(u,U(1,1,465));b.Ai.Plan(u,"balanced");
        Assert.Equal(Formation.Line,u.NextFormation);Assert.True(u.TransitionLeft>0);Assert.Null(u.AiFiringPosition);
    }
    [Fact] public void RiflePositionPreparesSkirmishAndHonoursExplicitFormationPins()
    {
        var u=U(0,0,300,type:"revolutionary_rifles");u.Formation=Formation.Column;var b=B(u,U(1,1,510));b.Ai.Plan(u,"balanced");Assert.Equal(Formation.Skirmish,u.NextFormation);
        var pinned=U(0,0,300);pinned.Formation=Formation.Column;pinned.PlayerFormationPinned=true;var b2=B(pinned,U(1,1,465));b2.Ai.Plan(pinned,"balanced");Assert.Null(pinned.NextFormation);
    }
    [Fact] public void MountedReserveStaysBehindFriendlyWingInsteadOfWalkingAtEnemy()
    {
        var horse=U(0,0,350,450,"cavalry");var b=B(horse,U(1,0,350,250),U(2,0,350,350),U(3,1,800,250),U(4,1,800,350));b.Ai.Plan(horse,"balanced");
        Assert.Equal(OrderKind.Move,horse.Order.Kind);Assert.NotNull(horse.AiEscortGoal);Assert.True(horse.AiEscortGoal!.Value.X<350);Assert.Equal("Accompany",horse.AiMountedIntent);
        Assert.Equal("Mounted reserve",horse.AiArmyRole);Assert.Contains("friendly wing",horse.AiIntention);
    }
    [Fact] public void CavalryFollowsTheAdvancingInfantryAndDoesNotChurnItsStation()
    {
        var horse=U(0,0,350,450,"cavalry");var b=B(horse,U(1,0,350,250),U(2,0,350,350),U(3,1,950));b.Ai.Plan(horse,"balanced");var first=horse.AiEscortGoal;
        b.Units[1].Position+=new Vec2(5,0);b.Units[2].Position+=new Vec2(5,0);b.Ai.Plan(horse,"balanced");Assert.Equal(first,horse.AiEscortGoal);
        b.Units[1].Position+=new Vec2(90,0);b.Units[2].Position+=new Vec2(90,0);b.Ai.Plan(horse,"balanced");Assert.True(horse.AiEscortGoal!.Value.X>first!.Value.X+50);
    }
    [Fact] public void MountedReserveExploitsAnIsolatedBrokenEnemyButRejectsAMassedSteadyFront()
    {
        var horse=U(0,0,350,400,"cavalry");var target=U(3,1,490,400);var b=B(horse,U(1,0,400,250),U(2,0,400,350),target);b.Ai.Plan(horse,"balanced");Assert.NotEqual(OrderKind.Attack,horse.Order.Kind);
        target.State=MoraleState.Wavering;target.Cohesion=25;b.Ai.Plan(horse,"balanced");Assert.Equal(OrderKind.Attack,horse.Order.Kind);Assert.Equal(target.Id,horse.Order.TargetId);Assert.Equal("Exploit",horse.AiMountedIntent);
    }
    [Fact] public void SupportedCavalryReturnsWhenItsOpportunityDisappears()
    {
        var horse=U(0,0,500,400,"cavalry");var target=U(3,1,580,400);target.State=MoraleState.Wavering;target.Cohesion=25;var b=B(horse,U(1,0,450,250),U(2,0,450,350),target);
        b.Ai.Plan(horse,"balanced");Assert.Equal(OrderKind.Attack,horse.Order.Kind);target.Strength=0;b.Ai.Plan(horse,"balanced");Assert.Equal(OrderKind.Move,horse.Order.Kind);Assert.True(horse.Order.Destination!.Value.X<450);
    }
    [Fact] public void ActiveChargesAndExplicitOrdersRemainAuthoritative()
    {
        var horse=U(0,0,350,450,"cavalry");var b=B(horse,U(1,0,350,250),U(2,1,700));horse.CavalryState=CavalryState.Charging;horse.Order=new(OrderKind.Attack,TargetId:2);var order=horse.Order;
        b.Ai.Plan(horse,"balanced");Assert.Equal(order,horse.Order);
        b.Issue(new(0,new(OrderKind.Move,new(600,700))));b.Step();Assert.True(horse.PlayerOrder);Assert.Equal(new Vec2(600,700),horse.Order.Destination);
    }
    [Fact] public void ArmyReserveCommitsToThreatenedSectorAndRetainsItsPlanBetweenReviews()
    {
        var units=new[]{U(0,0,350,200),U(1,0,350,320),U(2,0,350,440),U(3,0,280,560),U(4,1,800,320)};
        var b=B(units);var plan=b.Ai.Director.Get(0,"balanced");Assert.Equal(3,plan.ReserveId);Assert.False(plan.CommitReserve);
        units[0].Position+=new Vec2(5,0);Assert.Same(plan,b.Ai.Director.Get(0,"balanced"));units[0].Strength=100;b.Ai.Director.Invalidate(0);
        var committed=b.Ai.Director.Get(0,"balanced");Assert.True(committed.CommitReserve);
    }
    [Fact] public void FogDoesNotLeakHiddenEnemiesIntoArmyPlan()
    {
        var units=new[]{U(0,0,350),U(1,1,1000)};var b=new BattleSimulation(units,new(){Width=1400,Height=900,AiEnabled=true},new(environment:new(Weather:new(WeatherType.Fog,150))));b.Ai.ConfigureArmy(0,"balanced");
        var plan=b.Ai.Director.Get(0,"balanced");Assert.Equal(new Vec2(700,300),plan.Focus);Assert.Contains("last contact",plan.Reason);
    }
    [Fact] public void StrategicApproachUsesARealFormationTransition()
    {
        var u=U(0,0,300);var b=B(u,U(1,1,1100));b.Ai.Assign(new("crossing",0,"defend",new(800,300),80));b.Ai.Plan(u,"balanced");
        Assert.Equal(OrderKind.Move,u.Order.Kind);Assert.Equal(Formation.Column,u.NextFormation);Assert.True(u.TransitionLeft>0);
    }
    [Fact] public void FireSupportPurposeDoesNotLimberAnEffectiveBattery()
    {
        var gun=U(0,0,350,600,"artillery");var b=B(gun,U(1,0,400,250),U(2,0,400,350),U(3,1,550,600));b.Ai.Plan(gun,"balanced");
        Assert.Equal(OrderKind.FireAt,gun.Order.Kind);Assert.Equal("Fire support",gun.AiArmyRole);
    }
    [Fact] public void MultipleMountedReservesHaveSeparateStations()
    {
        var b=B(U(0,0,350,500,"cavalry"),U(1,0,350,600,"cavalry"),U(2,0,400,250),U(3,0,400,350),U(4,1,950));
        b.Ai.Plan(b.Units[0],"balanced");b.Ai.Plan(b.Units[1],"balanced");Assert.NotEqual(b.Units[0].AiEscortGoal,b.Units[1].AiEscortGoal);
    }
    [Fact] public void DistantDefensiveObjectiveDoesNotPullCavalryAheadOfItsArmy()
    {
        var horse=U(0,0,300,500,"cavalry");var b=B(horse,U(1,0,350,250),U(2,0,350,350),U(3,1,1100));
        b.Ai.Assign(new("defend-crossing",0,"defend",new(800,450),100,[0]));b.Ai.Plan(horse,"balanced");
        Assert.True(horse.Order.Destination!.Value.X<350);
    }
    [Fact] public void DetachedSupportAssignmentMovesCavalryToTheAssignedFormation()
    {
        var horse=U(0,0,300,500,"cavalry");var b=B(horse,U(1,0,350,250),U(2,0,350,350),U(3,1,1100));
        b.Ai.Assign(new("detached-support",0,"support",new(650,450),100,[0]));b.Ai.Plan(horse,"balanced");
        Assert.Equal(OrderKind.Move,horse.Order.Kind);Assert.True((horse.Order.Destination!.Value-new Vec2(650,450)).Length<100);
    }
    [Fact] public void MountedLaboratoryKeepsHorseBehindTheArmyDuringItsOpeningMarch()
    {
        var b=CombatScenarios.Get("ai-mounted-reserve").Create();
        for(int i=0;i<300;i++)
        {
            b.Step();
            foreach(var horse in b.Units.Where(u=>u.Archetype.Category==UnitCategory.Cavalry))
            {
                var plan=b.Ai.Director.Plans[horse.Army];Assert.True((horse.Position-plan.Front).Dot(plan.Forward)<60);
            }
        }
        Assert.Equal(0,b.Metrics.ChargeStarts);
    }
    [Theory][InlineData(17)][InlineData(31)]public void DirectorAndMountedDecisionsAreDeterministic(int seed)
    {
        string Run(){var b=(CombatScenarios.Get("ai-combined") with{Seed=seed}).Create();for(int i=0;i<2000 && b.Result is null;i++)b.Step();Assert.NotEmpty(b.Ai.Director.Plans);return JsonSerializer.Serialize(new{state=b.Snapshot(),events=b.Events,plans=b.Ai.Director.Plans,draws=b.Random.Draws},ScenarioJson.Options);}
        Assert.Equal(Run(),Run());
    }
}
