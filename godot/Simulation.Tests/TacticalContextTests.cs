using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class TacticalContextTests
{
    static Regiment U(int id,int army,double x,double y=300,string type="infantry",string personality="aggressive")=>
        new(id,army,$"Unit {id}",Archetypes.Get(type),new(x,y),army==0?0:Math.PI,commander:new($"officer-{id}",$"Officer {id}",Personality:personality,Specialization:"inspirer"));
    static BattleSimulation B(params Regiment[] units)
    {var b=new BattleSimulation(units,new(){Width=1400,Height=900,CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true,ArtilleryEnabled=true,SpecialistsEnabled=true,CommandersEnabled=true,AiEnabled=true});b.Ai.ConfigureArmy(0,"balanced");return b;}

    [Fact] public void SharedAssignmentKeepsItsPurposeAcrossDecisionsAndSpacesRegiments()
    {
        var b=B(U(0,0,200,250),U(1,0,200,350),U(2,1,1200));
        b.Ai.Assign(new("road-exit",0,"attack",new(700,300),100));
        foreach(var u in b.Units.Take(2)){b.Ai.Plan(u,"balanced");Assert.Equal(OrderKind.Move,u.Order.Kind);Assert.Contains("road-exit",u.AiIntention);}
        Assert.NotEqual(b.Units[0].Order.Destination,b.Units[1].Order.Destination);
        var first=b.Units[0].Order;b.Ai.Plan(b.Units[0],"balanced");Assert.Equal(first,b.Units[0].Order);
    }
    [Fact] public void DefendersReturnToTheirAssignedAreaInsteadOfFollowingDistantEnemies()
    {
        var u=U(0,0,800);var b=B(u,U(1,1,1200));b.Ai.Assign(new("bridge",0,"defend",new(300,300),90));b.Ai.Plan(u,"balanced");
        Assert.Equal(new Vec2(300,300),u.Order.Destination);Assert.Equal(OrderKind.Move,u.Order.Kind);
    }
    [Fact] public void ImmediateThreatCanInterruptAnAssignmentButDoesNotEraseIt()
    {
        var u=U(0,0,800);var b=B(u,U(1,1,850));b.Ai.Assign(new("bridge",0,"defend",new(300,300),90));b.Ai.Plan(u,"balanced");
        Assert.NotEqual(new Vec2(300,300),u.Order.Destination);Assert.Contains("bridge",u.AiAssignment);
    }
    [Fact] public void PlayerOrdersOverrideAssignmentsAndReleaseRestoresTheirPurpose()
    {
        var b=B(U(0,0,200),U(1,1,1200));b.Ai.Assign(new("exit",0,"attack",new(700,300)));
        b.Issue(new(0,new(OrderKind.Move,new(150,500))));b.Step();Assert.True(b.Units[0].PlayerOrder);Assert.Equal(new Vec2(150,500),b.Units[0].Order.Destination);
        b.Issue(new(0,Autonomy:AutonomyMode.Autonomous));b.Step();Assert.Contains("exit",b.Units[0].AiAssignment);
    }
    [Fact] public void MissionObjectivesSupplyIntentAndExplicitGroupAssignmentsTakePrecedence()
    {
        var b=B(U(0,0,200),U(1,0,200,450),U(2,1,1200));
        var d=new MissionDefinition([new("crossing","delay","Hold crossing",new(600,300),90,400)],Assignments:[new("reserve",0,"reserve",new(250,450),70,[1])]);
        b.SetMission(JsonSerializer.Deserialize<MissionDefinition>(JsonSerializer.Serialize(d,ScenarioJson.Options),ScenarioJson.Options)!);
        b.Ai.Plan(b.Units[0],"balanced");b.Ai.Plan(b.Units[1],"balanced");
        Assert.Contains("defend objective-crossing",b.Units[0].AiAssignment);Assert.Contains("reserve",b.Units[1].AiAssignment);
        Assert.Equal(new Vec2(250,450),b.Units[1].Order.Destination);b.Units[1].Position=new(250,450);b.Ai.Plan(b.Units[1],"balanced");Assert.Equal(OrderKind.Reserve,b.Units[1].Order.Kind);
    }
    [Fact] public void CompletedObjectiveAssignmentsAreReleased()
    {
        var b=B(U(0,0,200),U(1,1,1200));b.SetMission(new([new("place","capture","Take position",new(700,300))]));
        b.Ai.Plan(b.Units[0],"balanced");Assert.NotEmpty(b.Units[0].AiAssignment);b.Mission!.Objectives[0].Status="success";
        b.Ai.Plan(b.Units[0],"balanced");Assert.Empty(b.Units[0].AiAssignment);
    }
    [Fact] public void InvalidAssignmentsAreRejected()
    {var b=B(U(0,0,200),U(1,1,1200));Assert.Throws<ArgumentException>(()=>b.Ai.Assign(new("bad",0,"teleport",new(300,300))));Assert.Throws<ArgumentException>(()=>b.Ai.Assign(new("bad",0,"attack",new(300,300),Units:[1])));}
    [Fact] public void SupportIncludesNearbyAlliesAndEnemiesButNotRoutedOrDistantUnits()
    {
        var b=B(U(0,0,300),U(1,1,430),U(2,0,300,360),U(3,1,430,360),U(4,1,1100));
        var s=b.Ai.AssessSupport(b.Units[0],b.Units[1]);Assert.True(s.Friendly>0 && s.Hostile>0);
        b.Units[3].State=MoraleState.Routing;Assert.Equal(0,b.Ai.AssessSupport(b.Units[0],b.Units[1]).Hostile);
    }
    [Fact] public void FogDoesNotGiveTheSupportAssessmentHiddenEnemyKnowledge()
    {
        var units=new[]{U(0,0,300),U(1,1,400),U(2,1,490)};
        var b=new BattleSimulation(units,new(){Width=1400,Height=900,AiEnabled=true},new(environment:new(Weather:new(WeatherType.Fog,150))));
        Assert.True(b.Perceives(units[0],units[1]));Assert.False(b.Perceives(units[0],units[2]));Assert.Equal(0,b.Ai.AssessSupport(units[0],units[1]).Hostile);
    }
    [Fact] public void SupportChangesCautiousDisengagementWithoutChangingCombatStats()
    {
        var u=U(0,0,300,personality:"cautious");var b=B(u,U(1,1,375),U(2,1,380,345),U(3,1,390,270));
        Assert.True(b.Ai.Preparation(u,b.Units[1]));Assert.Contains("threat ratio",u.AiIntention);
        var friendly=B(U(0,0,300,personality:"cautious"),U(1,1,375),U(2,0,300,345),U(3,0,290,270));
        Assert.False(friendly.Ai.Preparation(friendly.Units[0],friendly.Units[1]));Assert.True(friendly.Units[0].AiFriendlySupport>0);
    }
    [Fact] public void InfantryCanPreferAnIsolatedWeakerEnemyAndKeepThatTarget()
    {
        var u=U(0,0,300);u.Strength=70;var isolated=U(2,1,430,500);isolated.Strength=25;
        var b=B(u,U(1,1,430),isolated);b.Ai.Plan(u,"balanced");Assert.Equal(2,u.AiTarget);
        b.Units[1].Strength=1;b.Ai.Plan(u,"balanced");Assert.Equal(2,u.AiTarget);
        isolated.Position=new(900,500);b.Ai.Plan(u,"balanced");Assert.Equal(2,u.AiTarget);
    }
    [Fact] public void ABlockedLineChoosesAClearLateralPositionAndCommitsToIt()
    {
        var u=U(0,0,300);var target=U(1,1,450);var b=B(u,target,U(2,0,375));
        Assert.NotNull(b.Combat.FiringBlocker(u,target));b.Ai.Plan(u,"balanced");
        Assert.NotNull(u.AiFiringPosition);Assert.Equal(OrderKind.Move,u.Order.Kind);
        Assert.Null(b.Combat.FiringBlocker(u,target,u.AiFiringPosition));
        var order=u.Order;b.Ai.Plan(u,"balanced");Assert.Equal(order,u.Order);Assert.True(u.AiFiringCommitUntil>0);
    }
    [Fact] public void GoodFiringPositionStaysPutAndRetainsFormationCooldown()
    {
        var u=U(0,0,300);var b=B(u,U(1,1,420));b.Ai.Plan(u,"balanced");var changes=u.FormationChanges;
        for(int i=0;i<20;i++)b.Ai.Plan(u,"balanced");Assert.Equal(OrderKind.FireAt,u.Order.Kind);Assert.Null(u.AiFiringPosition);Assert.Equal(changes,u.FormationChanges);
    }
    [Fact] public void RiflePositionKeepsItsRangeAndSkirmishBehaviour()
    {var u=U(0,0,300,type:"revolutionary_rifles");var b=B(u,U(1,1,490));b.Ai.Plan(u,"balanced");Assert.Equal(OrderKind.Skirmish,u.Order.Kind);Assert.Null(u.AiFiringPosition);}
    [Fact] public void PositionSearchNeverMovesAcrossAnUnbridgedRiver()
    {
        var u=U(0,0,300);var target=U(1,1,450);var env=new EnvironmentDefinition(Rivers:[new("river","River",[new(350,0),new(350,900)],35)]);
        var b=new BattleSimulation([u,target],new(){Width=1400,Height=900,CombatEnabled=true,AiEnabled=true,SpecialistsEnabled=true},new(environment:env));b.Ai.ConfigureArmy(0,"balanced");b.Ai.Plan(u,"balanced");
        if(u.AiFiringPosition is { } p)Assert.True(b.Terrain.Environment.Swept(u.Rect,new(p,Vec2.AngleTo(p,target.Position),u.Width,u.Depth),UnitCategory.Infantry,false));
        Assert.Equal(OrderKind.FireAt,u.Order.Kind);
    }
    [Fact] public void AuthoredRoutesAreNotOverwrittenByTacticalAssignments()
    {
        var b=B(U(0,0,200),U(1,1,1200));b.SetMission(new([new("place","capture","Take position",new(700,300))],[new(0,[new(250,500)])]));b.Step();
        Assert.Equal(AutonomyMode.Ordered,b.Units[0].Autonomy);Assert.Equal(new Vec2(250,500),b.Units[0].Order.Destination);
    }
    [Theory][InlineData("ai-shared-objective")][InlineData("ai-local-support")][InlineData("ai-firing-positions")]
    public void TacticalLaboratoriesRunWithParticipationAndValidStates(string name)
    {
        var b=CombatScenarios.Get(name).Create();for(int i=0;i<6000 && b.Result is null;i++)b.Step();
        Assert.True(b.Metrics.Volleys>0);Assert.True(b.Metrics.AiDecisions>0);
        Assert.All(b.Units,u=>Assert.True(u.Position.Finite && double.IsFinite(u.Morale+u.Cohesion)));
    }
    [Fact] public void RescueSupportTracksFriendlyDetachmentWithoutRevealingHiddenEnemies()
    {
        var b=B(U(0,0,200),U(1,0,650),U(2,1,1200));
        b.SetMission(new([new("rescue","rescue","Protect detachment",new(150,300),Units:[1])]));
        b.Ai.Plan(b.Units[0],"balanced");Assert.Contains("support objective-rescue",b.Units[0].AiAssignment);
        Assert.Equal(new Vec2(650,300),b.Units[0].Order.Destination);
    }
    [Theory][InlineData(17)][InlineData(31)]public void CombinedBattleWithAssignmentsIsDeterministic(int seed)
    {
        string Run(){var b=(CombatScenarios.Get("ai-combined") with{Seed=seed}).Create();b.Ai.Assign(new("support-centre",0,"support",new(500,400),180));for(int i=0;i<1600 && b.Result is null;i++)b.Step();Assert.True(b.Metrics.Volleys>0);Assert.True(b.Metrics.AiPositionEvaluations>0);return JsonSerializer.Serialize(new{snapshot=b.Snapshot(),b.Random.Draws,events=b.Events},ScenarioJson.Options);}
        Assert.Equal(Run(),Run());
    }
}
