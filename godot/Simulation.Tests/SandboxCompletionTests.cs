using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class SandboxCompletionTests
{
    static CommanderIdentity Officer(int id,string type="infantry",params string[] upgrades)=>new($"officer-{id}","Test Officer",Specialization:type=="artillery"?"artillerist":type=="cavalry"?"pursuit_specialist":"drillmaster",Upgrades:upgrades);
    static Regiment Unit(int id=0,int army=0,string type="infantry",Vec2? pos=null,params string[] upgrades)=>new(id,army,$"Regiment {id}",Archetypes.Get(type),pos??new(300,300),army==0?0:Math.PI,commander:Officer(id,type,upgrades));
    static BattleSimulation Battle(params Regiment[] units)=>new(units,new(){CombatEnabled=true,CommandersEnabled=true,MoraleEnabled=true,CavalryEnabled=true,SpecialistsEnabled=true,ArtilleryEnabled=true,Width=1600,Height=800},seed:17);
    static void Steps(BattleSimulation b,int n){for(int i=0;i<n && b.Result is null;i++)b.Step();}

    [Fact] public void BayonetRushAcceleratesAndImpactsOnlyOnceWithoutFirstTickMeleeDoubleHit()
    {
        var a=Unit(pos:new(300,300));var t=Unit(1,1,pos:new(345,300));var b=Battle(a,t);a.HoldFire=t.HoldFire=true;
        b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));Steps(b,200);
        Assert.Equal(1,b.Metrics.ChargeStarts);Assert.Equal(1,b.Metrics.ChargeImpacts);Assert.Equal(1,a.Charges);
        Assert.True(a.ChargeLastMomentum>0);Assert.Equal("bayonet impact",a.ChargeResult);Assert.False(a.ChargeReady);
        b.InfantryCharges.Impact(a,t);Assert.Equal(1,b.Metrics.ChargeImpacts);Assert.True(t.Strength<t.MaximumStrength);
    }
    [Fact] public void BayonetChargeCannotGenerateStandingImpactOrBypassReformWithRepeatedOrders()
    {
        var a=Unit();var t=Unit(1,1,pos:new(310,300));var b=Battle(a,t);a.HoldFire=t.HoldFire=true;
        for(int i=0;i<30;i++){b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();}
        Assert.Equal(0,b.Metrics.ChargeImpacts);
        a.ChargeReady=false;a.ChargeCooldown=20;a.ChargeImpactTargetId=1;
        b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();Assert.False(a.ChargeReady);
    }
    [Fact] public void BayonetCancelAndRoutClearTransientState()
    {
        var a=Unit();var t=Unit(1,1,pos:new(345,300));var b=Battle(a,t);a.HoldFire=t.HoldFire=true;
        b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();Assert.True(a.InfantryCharging);
        b.Issue(new(0,new(OrderKind.Hold)));b.Step();Assert.False(a.InfantryCharging);
        b.Issue(new(0,new(OrderKind.Charge,TargetId:1)));b.Step();a.Morale=1;Steps(b,2);Assert.False(a.InfantryCharging);
    }
    [Fact] public void RegistryAllTwelveUpgradesHaveCompatibleArchetypesAndSerialize()
    {
        Assert.Equal(12,UpgradeSystem.Definitions.Count);
        foreach(var d in UpgradeSystem.Definitions){var a=Archetypes.All.First(a=>UpgradeSystem.Eligible(a,d.Id));var c=Officer(0) with{Upgrades=new[]{d.Id}};UpgradeSystem.Validate(c,a);var copy=JsonSerializer.Deserialize<CommanderIdentity>(JsonSerializer.Serialize(c,ScenarioJson.Options),ScenarioJson.Options)!;Assert.Equal(d.Id,Assert.Single(copy.Upgrades!));}
    }
    [Theory][InlineData("unknown")][InlineData("mobile_battery")][InlineData("woodland_ambush")]
    public void InvalidUpgradeAssignmentRejected(string key)=>Assert.Throws<ArgumentException>(()=>Battle(Unit(upgrades:[key])));
    [Fact] public void LimitsDuplicatesAndSnapshotOwnershipAreEnforced()
    {
        Assert.Throws<ArgumentException>(()=>Battle(Unit(upgrades:["swift_reform","swift_reform"])));
        Assert.Throws<ArgumentException>(()=>Battle(Unit(upgrades:["swift_reform","rolling_volley","rallying_presence","inspired_attack"])));
        var list=new[]{"swift_reform"};var b=Battle(Unit(upgrades:list));list[0]="mobile_battery";
        Assert.Equal("swift_reform",b.Snapshot().Units[0].Intel!.Commander.Upgrades![0]);
    }
    [Fact] public void RollingVolleyNeedsCloseVisibleSteadyInfantryAndChangesActualReload()
    {
        var a=Unit(upgrades:["rolling_volley"]);var friend=Unit(1,pos:new(300,375));var enemy=Unit(2,1,pos:new(420,300));var b=Battle(a,friend,enemy);
        Assert.Equal(.8,UpgradeSystem.VolleyReload(b,a));Assert.True(b.Combat.Fire(a,enemy));Assert.Equal(SpecialistSystem.Reload(a)*.8,a.ReloadLeft,8);
        friend.State=MoraleState.Wavering;Assert.Equal(1,UpgradeSystem.VolleyReload(b,a));friend.State=MoraleState.Steady;friend.Position=new(300,410);Assert.Equal(1,UpgradeSystem.VolleyReload(b,a));
        friend.Position=new(300,375);a.Formation=Formation.Column;Assert.Equal(1,UpgradeSystem.VolleyReload(b,a));
    }
    [Fact] public void SwiftReformUsesSharedFormationTurningAndRecoveryCaps()
    {
        var a=Unit(type:"prussian_line",upgrades:["swift_reform"]);var c=Unit(1,type:"prussian_line");var b=Battle(a,c);
        Assert.True(SpecialistSystem.FormationTime(a,7)<SpecialistSystem.FormationTime(c,7));Assert.True(SpecialistSystem.FormationTime(a,7)>=2.8);
        MovementSystem.TurnTo(a,.5);MovementSystem.TurnTo(c,.5);Assert.True(a.Cohesion>c.Cohesion);
        a.Cohesion=c.Cohesion=70;MoraleSystem.RecoverCohesion(a,b.Rules);MoraleSystem.RecoverCohesion(c,b.Rules);Assert.True(a.Cohesion>c.Cohesion);
    }
    [Fact] public void RallyingPresenceIsStrongestAuraOnlyAndCannotSupportWhileRouting()
    {
        var a=Unit(type:"royal_grenadiers",upgrades:["rallying_presence"]);var f=Unit(1,pos:new(300,370),upgrades:["rallying_presence"]);var t=Unit(2,pos:new(300,335));var b=Battle(a,f,t);t.Morale=50;
        Assert.Equal(.3,CommanderSystem.Aura(a));Assert.Equal(.45,CommanderSystem.Aura(a,true));Assert.NotNull(SpecialistSystem.Support(b,t));
        double before=t.Morale;b.MoraleSystem.Update();Assert.InRange(t.Morale-before,0,.2);
        a.State=f.State=MoraleState.Routing;Assert.Null(SpecialistSystem.Support(b,t));
    }
    [Fact] public void ControlledChargeModifiesCooldownAlignmentAndRecoilDisorder()
    {
        (BattleSimulation,Regiment) Make(string[] keys){var u=Unit(type:"cavalry",upgrades:keys);var t=Unit(1,1,pos:new(330,300));var b=Battle(u,t);u.CavalryState=CavalryState.Charging;u.ChargeMomentum=.8;u.Velocity=new(10,0);u.Speed=10;b.Cavalry.Impact(u,t);return(b,u);}
        var (b,u)=Make(["controlled_charge"]);var (_,v)=Make([]);Assert.Equal(16,u.ChargeCooldown);Assert.Equal(20,v.ChargeCooldown);Assert.True(u.Cohesion>v.Cohesion);Assert.Equal(1,b.Metrics.ChargeImpacts);
    }
    [Fact] public void RelentlessPursuitRecoversOncePerEnemyAcrossRepeatedRouts()
    {
        var a=Unit(type:"cavalry",upgrades:["relentless_pursuit"]);var t=Unit(1,1,pos:new(350,300));var b=Battle(a,t);a.Cohesion=50;t.LastAttackerId=0;
        UpgradeSystem.OnRout(b,t);Assert.Equal(58,a.Cohesion);UpgradeSystem.OnRout(b,t);Assert.Equal(58,a.Cohesion);Assert.True(CommanderSystem.Pursuit(a)>1.2);
    }
    [Fact] public void ShockCommanderOnlyBoostsExposedChargeAndStacksBoundedly()
    {
        var a=Unit(type:"royal_grenadiers",upgrades:["shock_commander"]);var t=Unit(1,1,pos:new(340,300));Battle(a,t);
        Assert.Equal(1,CommanderSystem.ChargeShock(a,t,.8,true));t.Cohesion=40;Assert.Equal(1.35,CommanderSystem.ChargeShock(a,t,.8,false));Assert.Equal(1,CommanderSystem.ChargeShock(a,t,.1,false));
    }
    [Fact] public void AmbushAndHarassmentNeedCoverAndGenuineReset()
    {
        var a=Unit(type:"haudenosaunee_skirmishers",upgrades:["woodland_ambush","harassing_fire"]);var t=Unit(1,1,pos:new(320,300));
        var b=new BattleSimulation([a,t],new(){CombatEnabled=true,CommandersEnabled=true,MoraleEnabled=true,SpecialistsEnabled=true},new(forests:[new(300,300,150,150,1)]));
        double before=t.Cohesion;UpgradeSystem.OnVolley(b,a,t,1);Assert.True(t.Cohesion<=before-11);Assert.Single(b.Events,e=>e.Kind=="upgrade");
        UpgradeSystem.OnVolley(b,a,t,1);Assert.Single(b.Events,e=>e.Kind=="upgrade");
        a.Position=new(350,300);UpgradeSystem.OnVolley(b,a,t,0);Assert.Single(b.Events,e=>e.Kind=="upgrade");
        a.HoldFire=t.HoldFire=true;Steps(b,310);UpgradeSystem.OnVolley(b,a,t,0);Assert.Equal(2,b.Events.Count(e=>e.Kind=="upgrade"));
    }
    [Fact] public void SteadfastDefenceRequiresStationarySteadyDefensiveLine()
    {
        var a=Unit(upgrades:["steadfast_defence"]);var t=Unit(1,1,pos:new(400,300));Battle(a,t);Assert.Equal(.8,CommanderSystem.Defence(a,t));
        a.Speed=1;Assert.Equal(1,CommanderSystem.Defence(a,t));a.Speed=0;a.Formation=Formation.Column;Assert.Equal(1,CommanderSystem.Shock(a));
    }
    [Fact] public void MobileBatteryAndCalculatedFireUseSharedDeploymentAndScatter()
    {
        var a=Unit(type:"artillery",upgrades:["mobile_battery","calculated_fire"]);var b=Battle(a);Assert.Equal(1.1*.6,CommanderSystem.Redeploy(a),8);
        Steps(b,61);Assert.Equal(.88*.65,CommanderSystem.Scatter(a),8);a.Speed=1;UpgradeSystem.UpdateStationary(a);Assert.Equal(0,a.UpgradeStationary);Assert.Equal(1,CommanderSystem.Scatter(a));
    }
    [Fact] public void InspiredAttackSharesArmyCooldownAcrossOfficers()
    {
        var a=Unit(upgrades:["inspired_attack"]);var f=Unit(1,pos:new(300,370),upgrades:["inspired_attack"]);var t=Unit(2,1,pos:new(400,300));var b=Battle(a,f,t);f.Morale=50;t.State=MoraleState.Wavering;
        UpgradeSystem.Inspired(b,a,t,1);Assert.Equal(53,f.Morale);UpgradeSystem.Inspired(b,a,t,1);UpgradeSystem.Inspired(b,f,t,1);Assert.Equal(53,f.Morale);Assert.Single(b.Events,e=>e.Kind=="upgrade");
    }
    [Fact] public void FreshBattlesResetAbilityTimersAndKeepCommanderOwnership()
    {
        var c=new BattleConfiguration().Prepare();var unit=c.Placements[0];c=c with{Placements=c.Placements.Select(p=>p.Id==unit.Id?p with{Commander=p.Commander! with{Upgrades=new[]{"swift_reform"}}}:p).ToArray()};
        var b=c.Scenario().Create();Steps(b,5);var fresh=c.Scenario().Create();Assert.Equal(0,fresh.Units[0].UpgradeStationary);Assert.Equal("swift_reform",Assert.Single(fresh.Units[0].Commander.Upgrades!));
    }
    [Theory][InlineData(600,400)][InlineData(1000,600)][InlineData(1600,1000)][InlineData(3200,2000)]
    public void DeploymentFitsDifferentMapSizesAndKeepsPlayerArmyUnordered(int width,int height)
    {
        var c=(new BattleConfiguration(){Width=width,Height=height}).Prepare();c.Validate();var b=c.Scenario().Create();Assert.All(b.Units.Where(u=>u.Army==0),u=>Assert.Equal(OrderKind.Hold,u.Order.Kind));Assert.Equal(0,b.Tick);Assert.Equal(12,c.Placements.Length);
    }
    [Fact] public void DeploymentEditIsTransactionalAndResetPreservesIdentities()
    {
        var c=new BattleConfiguration().Prepare();string json=c.ToJson();Assert.Throws<ArgumentException>(()=>c.EditPlacement(0,new(500,300)));Assert.Equal(json,c.ToJson());
        var p=c.Placements[0];var moved=c.EditPlacement(0,p.Position+new Vec2(-8,0));var reset=moved.ResetDeployment();Assert.Equal(p.Position,reset.Placements[0].Position);Assert.Equal(p.Commander,reset.Placements[0].Commander);
        Assert.Throws<ArgumentException>(()=>c.EditPlacement(0,c.Placements[1].Position));
    }
    [Fact] public void RecipesRoundTripRosterTerrainOfficersUpgradesAndInitialOrders()
    {
        var c=(new BattleConfiguration(){TerrainPreset="Mixed Terrain"}).Prepare();c=c with {Placements=c.Placements.Select(p=>p.Id==0?p with{Commander=p.Commander! with{Upgrades=new[]{"swift_reform"}},Order=new(OrderKind.Move,new(500,300))}:p).ToArray()};
        var copy=BattleConfiguration.Parse(c.ToJson()).Prepare();Assert.Equal(c.ToJson(),copy.ToJson());Assert.Equal(OrderKind.Move,copy.Scenario().Create().Units[0].Order.Kind);
    }
    [Theory][InlineData("{}")] [InlineData("{\"version\":99}")] [InlineData("[]")] [InlineData("not json")]
    public void InvalidFilesGiveActionableErrors(string json)=>Assert.Throws<ArgumentException>(()=>BattleConfiguration.Parse(json));
    [Fact] public void ReportsDistinguishCasualtiesEscapesAndRemainFrozen()
    {
        var a=Unit();var t=Unit(1,1,pos:new(500,300));var b=Battle(a,t);b.Combat.Damage(t,20,a,0,"test");t.Withdrawn=true;
        var report=BattleReport.Capture(b);Assert.Equal(20,report.Armies[1].Lost);Assert.Equal(220,report.Armies[1].Remaining);Assert.Equal(1,report.Armies[1].Withdrawn);
        a.Strength=1;Assert.Equal(240,report.Regiments[0].Remaining);Assert.Equal(20,report.Regiments[0].Inflicted);
    }
    [Fact] public void SetupAutonomyIsAuthoritativeAndLocksAfterTheFirstTick()
    {
        var b=new BattleConfiguration().Prepare().Scenario().Create();
        Assert.True(b.AssignSetupAutonomy(0,true));Assert.True(b.Ai.Autonomous(b.Unit(0)!));Assert.False(b.Ai.Autonomous(b.Unit(1)!));
        Assert.True(b.AssignSetupAutonomy(0,false));Assert.Equal(AutonomyMode.Hold,b.Unit(0)!.Autonomy);b.Step();Assert.False(b.AssignSetupAutonomy(0,true));
    }
}
