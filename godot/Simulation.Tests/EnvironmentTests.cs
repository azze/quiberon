using System.Text.Json;
using Quiberon.Simulation;
using Xunit;
public class EnvironmentTests
{
    static RiverDefinition River()=>new("river","Test river",[new(500,-100),new(500,900)],60);
    static CrossingDefinition Bridge(string id="bridge",double y=400,double width=26)=>new(id,"river",new(500,y),0,100,width);
    static CrossingDefinition Ford(bool guns=false)=>new("ford","river",new(500,600),0,100,36,CrossingKind.Ford,FordDepth:guns?FordDepth.Shallow:FordDepth.Moderate);
    static TerrainMap Map(CrossingDefinition[]? crossings=null,WeatherType weather=WeatherType.Clear)=>new(environment:new(Rivers:[River()],Crossings:crossings,Weather:new(weather)));
    static Regiment Unit(int id=0,string type="infantry",double x=250,double y=400,int army=0,double facing=0)=>new(id,army,$"Unit {id}",Archetypes.Get(type),new(x,y),facing);
    static BattleSimulation Battle(TerrainMap map,params Regiment[] units)=>new(units,new(){Width=1000,Height=800},map);
    static void Move(BattleSimulation b,int id,Vec2 goal,string? crossing=null)=>b.Issue(new(id,new(OrderKind.Move,goal,ViaCrossing:crossing)));
    static void Steps(BattleSimulation b,int n){for(int i=0;i<n && b.Result is null;i++){b.Step();Assert.All(b.Units.Where(u=>u.Active),u=>Assert.True(b.Terrain.Environment.Passable(u.Rect,u.Archetype.Category),$"Water violation tick {b.Tick}: {u.Id} {u.Position} {u.Facing} {u.Width}/{u.Depth} {u.Navigation.Status}"));}}
    [Fact] public void RiverGeometryHasActualBanksAndFootprintContainment()
    {
        var e=Map().Environment;Assert.True(e.InRiver(new(500,400)));Assert.False(e.InRiver(new(469,400)));Assert.True(e.InRiver(new(470.01,400)));
        Assert.False(e.Passable(new(new(465,400),0,64,12),UnitCategory.Infantry));Assert.True(e.Passable(new(new(460,400),0,64,12),UnitCategory.Infantry));
        Assert.False(e.Swept(new(new(400,400),0,22,34),new(new(600,400),0,22,34),UnitCategory.Infantry));
    }
    [Fact] public void CrossingsMustSpanTheirRiverAndIdsAreUnique()
    {
        Assert.Throws<ArgumentException>(()=>Map([Bridge() with{Length=20}]));Assert.Throws<ArgumentException>(()=>Map([Bridge(),Bridge()]));
        Assert.Throws<ArgumentException>(()=>Map([Bridge() with{RiverId="unknown"}]));Assert.Throws<ArgumentException>(()=>new BattleEnvironment(new(Version:2)));
    }
    [Fact] public void BridgeGeometryDoesNotPermitCrossingBesideItsVisibleDeck()
    {
        var e=Map([Bridge()]).Environment;Assert.True(e.Passable(new(new(500,400),0,22,34),UnitCategory.Infantry));Assert.False(e.Passable(new(new(500,414),0,22,34),UnitCategory.Infantry));Assert.False(e.Passable(new(new(500,400),0,64,12),UnitCategory.Infantry));
        Assert.False(e.Passable(new(new(500,400),Math.PI/2,22,34),UnitCategory.Infantry));
    }
    [Theory][InlineData("infantry")][InlineData("cavalry")][InlineData("artillery")]
    public void DeepWaterStopsEveryUnitCategoryWithoutTunnelling(string type)
    {var u=Unit(type:type);var b=Battle(Map(),u);Move(b,0,new(750,400));Steps(b,1000);Assert.True(u.Position.X<470);Assert.Contains("crossing",u.Navigation.Status);}
    [Fact] public void InitialFootprintsInDeepWaterAreRejected()=>Assert.Throws<ArgumentException>(()=>Battle(Map(),Unit(x:500)));
    [Theory][InlineData("infantry",2300)][InlineData("cavalry",1400)][InlineData("artillery",4000) ]
    public void TimedApproachAndCompactFormationsCanCrossNarrowBridge(string type,int ticks)
    {
        var u=Unit(type:type);var b=Battle(Map([Bridge()]),u);Move(b,0,new(750,400));Steps(b,ticks);
        Assert.True(u.Position.X>720,$"{type} stuck at {u.Position}; {u.Navigation.Status}; {u.Formation}; compact {u.TransitCompact}; transition {u.TransitionLeft}");
        if(type=="infantry")Assert.Equal(Formation.Column,u.Formation);
    }
    [Fact] public void ExplicitWideLineWaitsForARealFormationOrder()
    {
        var u=Unit();var b=Battle(Map([Bridge()]),u);u.PlayerFormationPinned=true;Move(b,0,new(750,400));Steps(b,900);Assert.True(u.Position.X<450);Assert.Contains("column",u.Navigation.Status);
        b.Issue(new(0,Formation:Formation.Column));b.Step();Assert.True(u.TransitionLeft>0);Steps(b,1700);Assert.True(u.Position.X>720);
    }
    [Fact] public void FriendlyOppositeTrafficDoesNotPermanentlyDeadlock()
    {
        var a=Unit();var z=Unit(1,x:750,facing:Math.PI);var b=Battle(Map([Bridge()]),a,z);Move(b,0,new(750,400));Move(b,1,new(250,400));Steps(b,4000);
        Assert.True(a.Position.X>700 && z.Position.X<300,$"Traffic stalled {a.Position}/{z.Position}: {a.Navigation.Status}; {z.Navigation.Status}");
    }
    [Fact] public void CancellingAWaitingOrderDoesNotLeaveAStaleQueue()
    {
        var a=Unit();var z=Unit(1,x:200);var b=Battle(Map([Bridge()]),a,z);Move(b,0,new(750,400));Move(b,1,new(750,400));Steps(b,700);Move(b,0,new(200,250));Steps(b,2500);Assert.True(z.Position.X>700,$"{z.Position}: {z.Navigation.Status}");
    }
    [Fact] public void ManualFordChoiceOverridesTheNearestBridge()
    {
        var u=Unit(type:"cavalry",y:570);var b=Battle(Map([Bridge(),Ford()]),u);Move(b,0,new(750,570),"ford");bool ford=false;for(int i=0;i<1800;i++){b.Step();ford|=u.Navigation.CrossingId=="ford";}Assert.True(ford);Assert.True(u.Position.X>700,$"{u.Position} {u.Navigation.Status}");
    }
    [Fact] public void FordPermissionsAndMovementDisorderAreMeaningful()
    {
        var e=Map([Ford()]).Environment;Assert.True(e.Crossings[0].Permits(UnitCategory.Infantry));Assert.True(e.Crossings[0].Permits(UnitCategory.Cavalry));Assert.False(e.Crossings[0].Permits(UnitCategory.Artillery));Assert.True(Map([Ford(true)]).Environment.Crossings[0].Permits(UnitCategory.Artillery));
        var u=Unit(type:"cavalry",x:500,y:600);var map=Map([Ford()]);u.TransitCompact=true;var b=Battle(map,u);var effect=map.MovementEffect(u,new(1,0));Assert.InRange(effect.Speed,.1,.5);Assert.True(effect.LossPerMetre>=.1);
    }
    [Fact] public void RainIsModestAndGoodRoadsProtectArtilleryMobility()
    {
        var road=new RoadDefinition("road","Main road",[new(100,400),new(900,400)],10);var u=Unit(type:"artillery");
        var rain=new TerrainMap(environment:new(Roads:[road],Weather:new(WeatherType.Rain)));var off=new TerrainMap(environment:new(Weather:new(WeatherType.Rain)));
        Assert.True(rain.MovementEffect(u,new(1,0)).Speed>off.MovementEffect(u,new(1,0)).Speed);Assert.Equal(.8,off.MovementEffect(u,new(1,0)).Speed,8);
        var b=Battle(rain,u);Assert.Equal(19*1.03,SpecialistSystem.Reload(u),8);Assert.Equal(1,new BattleEnvironment().Reload(UnitCategory.Infantry));
    }
    [Fact] public void RoadsFavourColumnsAndGunsNotWideFiringLines()
    {
        var map=new TerrainMap(environment:new(Roads:[new("r","Road",[new(100,400),new(900,400)],10)]));var line=Unit();var column=Unit();column.Formation=Formation.Column;
        Assert.Equal(1,map.MovementEffect(line,new(1,0)).Speed);Assert.Equal(1.08,map.MovementEffect(column,new(1,0)).Speed,8);Assert.Equal(1.2,map.MovementEffect(Unit(type:"artillery"),new(1,0)).Speed,8);Assert.Equal(1,map.MovementEffect(column,new(0,1)).Speed,8);
    }
    [Fact] public void DirectionalWorksProtectCorrectlyPositionedTroopsOnly()
    {
        var map=new TerrainMap(environment:new(Defences:[new("work",new(430,400),0)]));var u=Unit(x:415);Assert.Equal(.7,map.Environment.Defence(u,new(550,400)));Assert.Equal(1,map.Environment.Defence(u,new(300,400)));Assert.Equal(.65,map.Environment.Defence(u,new(550,400),true));
        u.Facing=Math.PI;Assert.Equal(1,map.Environment.Defence(u,new(550,400)));u.Facing=0;u.Position=new(429,400);Assert.Equal(1,map.Environment.Defence(u,new(550,400)));
    }
    [Fact] public void FogComposesWithForestAndRidgeVisibility()
    {
        var clear=new TerrainMap();var fog=new TerrainMap(environment:new(Weather:new(WeatherType.Fog,VisibilityLimit:180)));
        Assert.True(clear.Visibility(new(100,400),new(400,400)).Visible);Assert.False(fog.Visibility(new(100,400),new(400,400)).Visible);Assert.Equal("fog",fog.Visibility(new(100,400),new(400,400)).Reason);Assert.True(fog.Visibility(new(100,400),new(250,400)).Transmission<1);
        var ridge=new TerrainMap([new(200,400,15,100,20,true)],environment:new(Weather:new(WeatherType.Fog,VisibilityLimit:300)));Assert.False(ridge.Visibility(new(100,400),new(280,400)).Visible);
    }
    [Fact] public void FogRestrictsManualAndAiArtilleryAcquisitionButNotPhysicalFlight()
    {
        var map=new TerrainMap(environment:new(Weather:new(WeatherType.Fog,VisibilityLimit:180)));var gun=Unit(type:"artillery");var enemy=Unit(1,army:1,x:650);var b=new BattleSimulation([gun,enemy],new(){Width=1000,Height=800,CombatEnabled=true,ArtilleryEnabled=true},map);
        Assert.False(b.Perceives(gun,enemy));Assert.False(b.Combat.CanFire(gun,enemy));b.Artillery.Add(new(){OwnerId=0,Position=new(400,100),Height=25,Velocity=new(100,0),VerticalSpeed=5});for(int i=0;i<25;i++)b.Artillery.Update();Assert.Contains(b.Artillery.Projectiles,p=>p.Position.X>600);
    }
    [Fact] public void ClearWithoutFeaturesPreservesTheLegacyExactPaths()
    {
        var a=new ScenarioDefinition{Units=[new(){Id=0,Position=new(200,300),Order=new(OrderKind.Move,new(450,300))},new(){Id=1,Army=1,Position=new(800,600)}]};var first=a.Create();var second=(a with{Terrain=new([],[],new(Weather:new(WeatherType.Clear)))}).Create();for(int i=0;i<100;i++){a.IssueScheduled(first);a.IssueScheduled(second);first.Step();second.Step();}Assert.Equal(JsonSerializer.Serialize(first.Snapshot(),ScenarioJson.Options),JsonSerializer.Serialize(second.Snapshot(),ScenarioJson.Options));
    }

    [Fact] public void RainReloadUsesExistingWeaponTimingAndDoesNotDisorderStationaryTroops()
    {
        BattleSimulation Shoot(WeatherType weather){var a=Unit(x:250);var z=Unit(1,x:390,army:1,facing:Math.PI);return new([a,z],new(){Width=1000,Height=800,CombatEnabled=true},new(environment:new(Weather:new(weather))));}
        var clear=Shoot(WeatherType.Clear);var rain=Shoot(WeatherType.Rain);
        Assert.True(clear.Combat.Fire(clear.Units[0],clear.Units[1]));Assert.True(rain.Combat.Fire(rain.Units[0],rain.Units[1]));
        Assert.Equal(clear.Units[0].ReloadLeft*1.08,rain.Units[0].ReloadLeft,10);
        var resting=Unit();resting.Cohesion=60;var b=Battle(new(environment:new(Weather:new(WeatherType.Rain))),resting);Steps(b,100);
        Assert.True(resting.Cohesion>=60);Assert.Equal(0,resting.TerrainLoss);
    }
    [Fact] public void FireCrossesWaterAndCoverModifiesActualVolleyProbability()
    {
        var a=Unit(x:430);var z=Unit(1,x:580,army:1,facing:Math.PI);var b=new BattleSimulation([a,z],new(){Width=1000,Height=800,CombatEnabled=true},Map());
        Assert.True(b.Combat.CanFire(a,z));Assert.True(b.Combat.Fire(a,z));
        var work=new DefenceDefinition("wall",new(560,400),Math.PI,100,ProtectionDepth:36);
        var defended=new BattleSimulation([Unit(x:430),Unit(1,x:580,army:1,facing:Math.PI)],new(){Width=1000,Height=800,CombatEnabled=true},new(environment:new(Defences:[work])));
        Assert.True(defended.Combat.Fire(defended.Units[0],defended.Units[1]));
        Assert.Equal(a.LastVolleyProbability*.7,defended.Units[0].LastVolleyProbability,10);
        Assert.Equal(.65,defended.Terrain.Environment.Defence(defended.Units[1],new(420,400),true));
        Assert.Equal(1,defended.Terrain.Environment.Defence(defended.Units[1],new(800,400),true));
    }
    [Fact] public void WaterTerminatesLowCannonballsButDoesNotStopAirborneFlight()
    {
        var gun=Unit(type:"artillery");var b=new BattleSimulation([gun],new(){Width=1000,Height=800,CombatEnabled=true,ArtilleryEnabled=true},Map());
        var p=b.Artillery.Add(new(){OwnerId=0,Position=new(480,300),Velocity=new(100,0),Height=.2,VerticalSpeed=-5});
        b.Artillery.AdvancePiece(p,.2,true);Assert.Equal(0,p.Energy);Assert.Contains(b.Events,e=>e.Kind=="projectile_water");
        var high=b.Artillery.Add(new(){OwnerId=0,Position=new(450,300),Velocity=new(1000,0),Height=30});
        b.Artillery.AdvancePiece(high,.1,true);Assert.True(high.Position.X>540 && high.Energy>0);
    }
    [Fact] public void FordPreventsStoredChargeMomentumAndArtilleryCannotUseModerateFord()
    {
        var u=Unit(type:"cavalry",x:500,y:600);u.TransitCompact=true;u.ChargeMomentum=1;u.ChargeDistance=130;
        var b=new BattleSimulation([u],new(){Width=1000,Height=800,CavalryEnabled=true},Map([Ford()]));b.Step();Assert.True(u.ChargeMomentum<=.15);Assert.Equal(0,u.ChargeDistance);
        var gun=Unit(type:"artillery",y:600);var blocked=Battle(Map([Ford()]),gun);Move(blocked,0,new(750,600));Steps(blocked,1000);Assert.True(gun.Position.X<470);Assert.True(blocked.Navigation.Plans<40);
    }
    [Fact] public void RoutingFindsARealBankEscapeAndCannotOverrideWaterWithOrdinaryOrders()
    {
        var fleeing=Unit(x:430);fleeing.State=MoraleState.Routing;fleeing.Morale=5;fleeing.LastAttackerId=1;
        var enemy=Unit(1,x:150,army:1);enemy.HoldFire=true;var support=Unit(2,x:150,y:740);support.HoldFire=true;
        var b=new BattleSimulation([fleeing,enemy,support],new(){Width=1000,Height=800,CombatEnabled=true,MoraleEnabled=true},Map());
        var start=fleeing.Position;Move(b,0,new(700,400));Steps(b,300);
        Assert.True(fleeing.Position.X<470);Assert.True((fleeing.Position-start).Length>15,$"Fleeing unit stuck at {fleeing.Position}");
    }
    [Fact] public void EnvironmentCustomRecipesRoundTripAndOldScenariosDefaultToClear()
    {
        var c=BattleConfiguration.Parse("{\"version\":1,\"name\":\"Old test\",\"blue\":{\"infantry\":1},\"red\":{\"infantry\":1}}").Prepare();
        Assert.True(c.Scenario().Create().Terrain.Environment.Legacy);
        var environmental=c with{Terrain=new([],[],new(Rivers:[River()],Crossings:[Bridge()],Roads:[new("road","Road",[new(100,400),new(900,400)])],Weather:new(WeatherType.Rain)))};
        var loaded=BattleConfiguration.Parse(environmental.ToJson());Assert.Equal(WeatherType.Rain,loaded.Terrain!.Environment!.Weather!.Type);Assert.Single(loaded.Terrain.Environment.Crossings!);
    }
    [Fact] public void TwoRiversAndAPreferredCrossingRemainConnected()
    {
        var r1=River() with{Points=[new(350,-100),new(350,900)]};var r2=River() with{Id="second",Points=[new(650,-100),new(650,900)]};
        var c1=Bridge() with{Position=new(350,400)};var c2=Bridge("second-bridge") with{RiverId="second",Position=new(650,400)};
        var u=Unit(x:180);var b=Battle(new(environment:new(Rivers:[r1,r2],Crossings:[c1,c2])),u);Move(b,0,new(820,400),"bridge");Steps(b,3800);Assert.True(u.Position.X>790,$"{u.Position}: {u.Navigation.Status}");
        Assert.Throws<ArgumentException>(()=>Move(b,0,new(100,400),"missing"));
    }
    [Theory][InlineData("river")][InlineData("bridge")][InlineData("ford")][InlineData("roads")][InlineData("defences")][InlineData("rain")][InlineData("fog")][InlineData("vistula")]
    public void EveryEnvironmentLaboratoryIsDeterministicAndFootprintSafe(string name)
    {
        string Run(){var d=CombatScenarios.Get("environment-"+name);var b=d.Create();for(int n=0;n<1200 && b.Result is null;n++){d.IssueScheduled(b);Steps(b,1);}return JsonSerializer.Serialize(new{snapshot=b.Snapshot(),events=b.Events,draws=b.Random.Draws},ScenarioJson.Options);}
        Assert.Equal(Run(),Run());
    }

    [Fact] public void EarthworksReduceRealChargeImpactWithoutBecomingProjectileShields()
    {
        BattleSimulation Encounter(bool works){var a=Unit(type:"cavalry",x:540);var target=Unit(1,x:580,army:1,facing:Math.PI);var map=new TerrainMap(environment:works?new(Defences:[new("work",new(560,400),Math.PI,100,ProtectionDepth:36)]):null);var b=new BattleSimulation([a,target],new(){Width=1000,Height=800,CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true,ArtilleryEnabled=true},map);a.CavalryState=CavalryState.Charging;a.ChargeMomentum=1;a.Velocity=new(12,0);b.Cavalry.Impact(a,target);return b;}
        var open=Encounter(false);var behind=Encounter(true);Assert.True(behind.Metrics.ImpactMoraleShock<open.Metrics.ImpactMoraleShock);Assert.True(behind.Metrics.ImpactCasualties<=open.Metrics.ImpactCasualties);
        var old=behind.Units[1].Strength;var p=behind.Artillery.Add(new(){OwnerId=0,Position=new(550,400),Velocity=new(1000,0),Height=1});behind.Artillery.AdvancePiece(p,.05,true);Assert.True(behind.Units[1].Strength<old);
        behind.Units[1].State=MoraleState.Shaken;behind.Units[1].Cohesion=80;Assert.Equal(.7,behind.Terrain.Environment.Defence(behind.Units[1],new(400,400)));Assert.Equal(1,behind.Terrain.Environment.Defence(behind.Units[1],new(400,400),true));
    }
    [Fact] public void OpposingCrossingTrafficRemainsOrdinaryCombat()
    {
        var a=Unit(x:250);var enemy=Unit(1,x:750,army:1,facing:Math.PI);var b=new BattleSimulation([a,enemy],new(){Width=1000,Height=800,CombatEnabled=true},Map([Bridge()]));Move(b,0,new(750,400));Move(b,1,new(250,400));Steps(b,2200);
        Assert.True(b.Metrics.Casualties>0);Assert.True(b.Metrics.MeleePulses>0 || !a.Active || !enemy.Active,"Enemy formations must fight or be destroyed; crossing access never makes them harmless.");
    }
    [Fact] public void FogAcquisitionUsesTheSameRestrictionsForAutonomousRegiments()
    {
        var def=new ScenarioDefinition{Width=1000,Height=800,CombatEnabled=true,AiEnabled=true,AiArmies=[0,1],Terrain=new([],[],new(Weather:new(WeatherType.Fog,VisibilityLimit:180))),Units=[new(){Id=0,Position=new(200,300)},new(){Id=1,Army=1,Position=new(800,300),Facing=Math.PI}]};var b=def.Create();Steps(b,30);
        Assert.All(b.Units,u=>Assert.Null(u.AiTarget));Assert.Equal(0,b.Metrics.Volleys);Assert.All(b.Units,u=>Assert.Contains("No detected enemy",u.AiIntention));
    }
}
