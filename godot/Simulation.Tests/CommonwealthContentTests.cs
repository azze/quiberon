using System.Text.Json;
using Quiberon.Simulation;
using Xunit;

public class CommonwealthContentTests
{
    static Rules Rules()=>new(){Width=1200,Height=800,CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true,ArtilleryEnabled=true,SpecialistsEnabled=true,CommandersEnabled=true,AiEnabled=true};
    static Regiment U(string type="commonwealth_regulars",int id=0,int army=0,double x=400,double y=350,string? commander=null)=>
        new(id,army,type,Archetypes.Get(type),new(x,y),army==0?0:Math.PI,commander:commander is null?new("test-"+id,"Laboratory Officer "+id,Specialization:"inspirer"):HistoricalCommanders.Get(commander).Create());
    static BattleSimulation B(Regiment a,Regiment? enemy=null)=>new([a,enemy??U(id:1,army:1,x:620)],Rules(),seed:1796);
    static void Steps(BattleSimulation b,int n){for(int i=0;i<n && b.Result is null;i++)b.Step();}
    static readonly string[] Core=["commonwealth_regulars","commonwealth_militia","commonwealth_scythemen","commonwealth_national_cavalry","commonwealth_uhlans","commonwealth_field_artillery","revolutionary_line","revolutionary_rifles","haudenosaunee_skirmishers","prussian_line","prussian_grenadiers","prussian_cuirassiers","russian_musketeers","russian_grenadiers","russian_cossacks"];
    [Fact] public void ExactlyFifteenCoreTypesAndLegacySandboxRemainAvailable()
    {
        Assert.Equal(Core.Order(),Archetypes.All.Where(a=>a.CampaignCore).Select(a=>a.Id).Order());
        Assert.Equal(20,Archetypes.All.Count());
        foreach(var id in new[]{"infantry","cavalry","artillery","royal_grenadiers","french_horse_artillery"})Assert.NotNull(Archetypes.Get(id));
        foreach(var a in Archetypes.All){Assert.InRange(a.Strength,20,400);Assert.InRange(a.Speed,1,10);Assert.InRange(a.TurnRate,.1,2);Assert.Contains(a.DefaultFormation,a.Formations);Assert.False(string.IsNullOrWhiteSpace(a.Role));Assert.InRange(a.Impact,.5,1.5);if(a.Weapon is { } w){Assert.InRange(w.ReloadSeconds,.5,40);Assert.InRange(w.Range,100,500);Assert.InRange(w.Accuracy,.1,3);}}
    }
    [Fact] public void ReusedProfilesPreserveTheExistingBalanceAndIds()
    {
        Assert.Equal(140,Archetypes.Get("haudenosaunee_skirmishers").Strength);Assert.Equal(3.6,Archetypes.Get("haudenosaunee_skirmishers").Speed);
        Assert.Equal(235,Archetypes.Get("revolutionary_rifles").Weapon!.Range);Assert.Equal(22,Archetypes.Get("revolutionary_rifles").Weapon!.ReloadSeconds);
        Assert.Equal(80,Archetypes.Get("commonwealth_uhlans").Strength);Assert.Equal("exploit",Archetypes.Get("commonwealth_uhlans").Trait);
        Assert.Equal("drill",Archetypes.Get("prussian_line").Trait);Assert.Equal("prestige",Archetypes.Get("royal_grenadiers").Trait);
    }
    [Fact] public void HistoricalRegistryContainsOnlyTheFourteenRecommendedCharacters()
    {
        Assert.Equal(14,HistoricalCommanders.All.Count);Assert.Equal(14,HistoricalCommanders.All.Select(d=>d.Id).Distinct().Count());
        Assert.Equal(14,HistoricalCommanders.All.Select(d=>d.Specialization).Distinct().Count());Assert.Equal(2,HistoricalCommanders.All.Count(d=>d.ArmyLevel));
        Assert.Equal("Tadeusz Kościuszko",HistoricalCommanders.Get("tadeusz_kosciuszko").Name);
        Assert.Equal("Franciszek Ksawery Łaźniński",HistoricalCommanders.Get("franciszek_ksawery_lazninski").Name);
        var cook=HistoricalCommanders.Get("joseph_louis_cook");Assert.Contains("Akiatonharónkwen",cook.AlternativeNames);Assert.Equal("Mohawk",cook.Nation);
        var copy=JsonSerializer.Deserialize<HistoricalCommanderDefinition>(JsonSerializer.Serialize(cook,ScenarioJson.Options),ScenarioJson.Options)!;
        Assert.Equal(cook.AlternativeNames,copy.AlternativeNames);Assert.Equal(cook.CampaignRole,copy.CampaignRole);
        foreach(var d in HistoricalCommanders.All){Assert.Contains(d.Personality,CommanderSystem.Personalities);Assert.NotEmpty(d.Availability);Assert.NotEmpty(d.IntendedRoles??[]);if(!d.ArmyLevel)foreach(var category in d.Categories)CommanderSystem.Validate(d.Create(),Enum.Parse<UnitCategory>(category,true));}
    }
    [Fact] public void DuplicateHistoricalDefinitionsAreRejectedEvenWithDifferentInstanceIds()
    {
        var a=U(commander:"jan_henryk_dabrowski");var b=U(id:1,army:1,commander:"jan_henryk_dabrowski");b.Commander=b.Commander with{Id="different-instance"};
        Assert.Throws<ArgumentException>(()=>new BattleSimulation([a,b],Rules()));
        Assert.Throws<ArgumentException>(()=>CommanderSystem.Validate(HistoricalCommanders.Get("tadeusz_kosciuszko").Create(),UnitCategory.Infantry));
        var battle=B(U());Assert.Throws<ArgumentException>(()=>battle.SetArmyCommanders([new(0,"alexander_suvorov"),new(1,"alexander_suvorov")]));
    }
    [Fact] public void SignaturesCannotBeForgedOrEditedIntoGenericOfficers()
    {
        var c=HistoricalCommanders.Get("jan_henryk_dabrowski").Create();Assert.Throws<ArgumentException>(()=>CommanderSystem.Validate(c with{Specialization="inspirer"},UnitCategory.Infantry));
        Assert.Throws<ArgumentException>(()=>CommanderSystem.Validate(c with{DefinitionId=""},UnitCategory.Infantry));
        Assert.Throws<ArgumentException>(()=>CommanderSystem.Validate(c with{Name="Invented"},UnitCategory.Infantry));
    }
    [Fact] public void ScythemenHaveNoFirearmAndAutonomouslyReachMelee()
    {
        var u=U("commonwealth_scythemen");var enemy=U(id:1,army:1,x:470);var b=B(u,enemy);enemy.HoldFire=true;b.Ai.ConfigureArmy(0,"balanced");
        b.Ai.Plan(u,"balanced");Assert.Contains(u.Order.Kind,new[]{OrderKind.Attack,OrderKind.Charge});Assert.NotNull(b.Combat.Intent(u));Assert.False(b.Combat.CanFire(u,enemy));
        Steps(b,600);Assert.Equal(0,u.ShotsFired);Assert.True(u.DamageInflicted>0);Assert.Null(u.Archetype.Weapon);Assert.True(b.Combat.CanMelee(u));
    }
    [Fact] public void MilitiaDefenceIsConditionalAndManoeuvringIsWorseThanRegulars()
    {
        var a=U("commonwealth_militia");var b=B(a);double morale=a.Morale;b.Combat.Damage(a,0,b.Units[1],10,"test");double holding=morale-a.Morale;
        a.Morale=morale;a.Order=new(OrderKind.Attack,TargetId:1);b.Combat.Damage(a,0,b.Units[1],10,"test");Assert.True(morale-a.Morale>holding);
        var regular=U();B(regular);Assert.True(SpecialistSystem.FormationTime(a,7)>SpecialistSystem.FormationTime(regular,7));Assert.True(a.MaximumStrength>regular.MaximumStrength);
    }
    [Fact] public void RegularInfantryProfilesHaveTradeoffsRatherThanUniversalSuperiority()
    {
        var cw=Archetypes.Get("commonwealth_regulars");var brit=Archetypes.Get("revolutionary_line");var rus=Archetypes.Get("russian_musketeers");
        Assert.True(brit.Weapon!.ReloadSeconds<cw.Weapon!.ReloadSeconds);Assert.True(brit.Strength<cw.Strength);Assert.True(rus.InitialMorale>cw.InitialMorale);Assert.True(rus.TurnRate<cw.TurnRate);
        var pr=B(U("prussian_line")).Units[0];Assert.True(SpecialistSystem.Reload(pr)<SpecialistSystem.Reload(B(U()).Units[0]));
        pr.Cohesion=30;Assert.Equal(12,SpecialistSystem.Reload(pr));
    }
    [Fact] public void HeavyAndLightCavalryHaveDifferentMobilityImpactAndAiRisk()
    {
        var heavy=Archetypes.Get("prussian_cuirassiers");var light=Archetypes.Get("russian_cossacks");Assert.True(heavy.Impact>light.Impact && heavy.Melee>light.Melee && heavy.Speed<light.Speed && heavy.TurnRate<light.TurnRate && light.Pursuit>heavy.Pursuit);
        var u=U("russian_cossacks");var b=B(u,U(id:1,army:1,x:490));b.Ai.ConfigureArmy(0,"all_out_attack");b.Ai.Plan(u,"all_out_attack");Assert.NotEqual(OrderKind.Attack,u.Order.Kind);
        b.Units[1].State=MoraleState.Routing;b.Ai.Plan(u,"balanced");Assert.Equal(OrderKind.Attack,u.Order.Kind);
    }
    [Fact] public void WarPartiesCanHarassAndWithdrawOutsideForestsAndRiflesUseRange()
    {
        foreach(var type in new[]{"haudenosaunee_skirmishers","revolutionary_rifles"}){var u=U(type);var b=B(u,U(id:1,army:1,x:500));b.Ai.ConfigureArmy(0,"balanced");b.Ai.Plan(u,"balanced");Assert.Equal(OrderKind.Skirmish,u.Order.Kind);Assert.True(b.Combat.CalculateVolley(u,b.Units[1]).Probability>0);b.Units[1].Position=new(440,350);Assert.NotNull(b.Ai.Skirmish(u,b.Units[1]));Assert.True(u.SkirmishRetreat);}
    }
    [Fact] public void NiesiolowskiBenefitsOrganizedStationaryLinesOnly()
    {
        var u=U(commander:"franciszek_ksawery_niesiolowski");var b=B(u);Assert.Equal(1.18,CommanderSystem.Accuracy(u,1),8);
        u.Cohesion=40;Assert.Equal(1,CommanderSystem.Accuracy(u,1));u.Cohesion=100;u.Formation=Formation.Column;Assert.Equal(1,CommanderSystem.Accuracy(u,1));u.Formation=Formation.Line;u.Speed=1;Assert.Equal(1,CommanderSystem.Accuracy(u,1));
        var melee=U("commonwealth_scythemen",commander:"franciszek_ksawery_niesiolowski");B(melee);Assert.Equal(1,CommanderSystem.Accuracy(melee,1));Assert.Contains("inactive",CommanderSystem.Effects(melee));
    }
    [Theory][InlineData("jan_henryk_dabrowski")][InlineData("friedrich_wilhelm_von_bulow")]
    public void ManoeuvreSignaturesUseExistingFormationAndCohesionRules(string id)
    {var u=U(commander:id);B(u);Assert.True(CommanderSystem.Formation(u)<1);Assert.True(CommanderSystem.Manoeuvre(u)<1);Assert.InRange(CommanderSystem.Recovery(u),1.1,1.3);}
    [Fact] public void MadalinskiAndPlatovImproveMovingPursuitWithoutPreparedFrontDominance()
    {
        foreach(var id in new[]{"antoni_madalinski","matvei_platov"}){var u=U("russian_cossacks",commander:id);var b=B(u);Assert.True(CommanderSystem.Pursuit(u)>1);Assert.Equal(1,CommanderSystem.PursuitLoss(u));u.PursuitId=b.Units[1].Id;Assert.True(CommanderSystem.PursuitLoss(u)<1);Assert.True(CommanderSystem.FrontalPenalty(u,b.Units[1])<1);}
    }
    [Fact] public void JasinskiRequiresCitizenTroopsAndActualLocalOvermatch()
    {
        var a=U("commonwealth_militia",commander:"jakub_jasinski");var b=new BattleSimulation([a,U(id:1,army:1,x:480),U(id:2,army:1,x:500,y:410)],Rules());b.CommandSupport.Update();Assert.True(a.CommandOutnumbered);Assert.Equal(.82,HistoricalEffects.Shock(a));Assert.Equal(1.1,HistoricalEffects.Melee(a));Assert.Equal(.88,HistoricalEffects.CasualtyMorale(a));a.State=MoraleState.Wavering;b.CommandSupport.Update();Assert.Equal(.88,HistoricalEffects.CasualtyMorale(a));
        b.Units[2].Position=new(1000,700);b.CommandSupport.Update();Assert.False(a.CommandOutnumbered);Assert.Equal(1,HistoricalEffects.Shock(a));
    }
    [Fact] public void LazninskiRecoversButCannotResetChargeImpactLocks()
    {
        var u=U("commonwealth_national_cavalry",commander:"franciszek_ksawery_lazninski");B(u);u.Fatigue=40;u.ChargeReady=false;u.ChargeImpactedSequence=1;HistoricalEffects.RecoverFatigue(u);Assert.True(u.Fatigue<40);Assert.False(u.ChargeReady);Assert.Equal(1,u.ChargeImpactedSequence);Assert.Equal(.8,HistoricalEffects.Reform(u));Assert.Equal(.85,HistoricalEffects.Cooldown(u));
    }
    [Fact] public void DespardUsesDeploymentAndPreparedDefenceWithoutInventedFortifications()
    {
        var u=U("commonwealth_field_artillery",commander:"edward_marcus_despard");B(u);Assert.Equal(.85,CommanderSystem.Redeploy(u));Assert.Equal(.88,HistoricalEffects.Shock(u));u.Order=new(OrderKind.Attack,TargetId:1);Assert.Equal(1,HistoricalEffects.Shock(u));Assert.Contains("future-only",HistoricalCommanders.Get("edward_marcus_despard").Notes);
    }
    [Fact] public void CoalitionSupportRequiresRealNearbyMixedFactionsAndNeverStacks()
    {
        var source=U("revolutionary_line",commander:"lord_edward_fitzgerald");var a=U(id:1,x:450);var cook=U("haudenosaunee_skirmishers",2,x:400,y:410,commander:"joseph_louis_cook");var b=new BattleSimulation([source,a,cook,U(id:3,army:1,x:900)],Rules());b.CommandSupport.Update();Assert.InRange(a.CommandRecovery,1.12,1.15);Assert.Equal(.12,a.CommandMorale);Assert.Equal(.9,a.CommandManoeuvre);Assert.InRange(a.CommandRecovery,1,1.15);
        source.Position=new(50,50);cook.Position=new(50,700);b.CommandSupport.Update();Assert.Equal(1,a.CommandRecovery);Assert.Equal(0,a.CommandMorale);
        var same=new BattleSimulation([U(commander:"lord_edward_fitzgerald"),U(id:1,x:440),U(id:2,army:1,x:900)],Rules());same.CommandSupport.Update();Assert.Equal(1,same.Units[1].CommandRecovery);
    }
    [Fact] public void BlucherAndBagrationUseAggressiveDecisionsAndConditionalOffence()
    {
        var cavalry=U("prussian_cuirassiers",commander:"gebhard_leberecht_von_blucher");B(cavalry);Assert.True(CommanderSystem.Is(cavalry,"aggressive"));Assert.Equal(1.15,HistoricalEffects.ChargeShock(cavalry,.8,false));Assert.Equal(1,HistoricalEffects.ChargeShock(cavalry,.8,true));
        var infantry=U("russian_grenadiers",commander:"pyotr_bagration");B(infantry);Assert.Equal(1,HistoricalEffects.Move(infantry));infantry.Order=new(OrderKind.Attack,TargetId:1);Assert.Equal(1.08,HistoricalEffects.Move(infantry));Assert.True(HistoricalEffects.Manoeuvre(infantry)<1);
    }
    [Fact] public void ArmyCommandIsLocalConditionalAndDoesNotOccupyARegiment()
    {
        var u=U("commonwealth_militia");var b=B(u);b.SetArmyCommanders([new(0,"tadeusz_kosciuszko",new(400,350))]);b.CommandSupport.Update();Assert.Equal(2,b.Units.Count);Assert.Equal(.85,u.CommandShock);u.Order=new(OrderKind.Attack,TargetId:1);b.CommandSupport.Update();Assert.Equal(1,u.CommandShock);
        b.SetArmyCommanders([new(0,"alexander_suvorov",new(400,350))]);b.Ai.ConfigureArmy(0,"balanced");Assert.Equal("balanced",b.Ai.Armies[0]);b.CommandSupport.Update();Assert.Equal(1.06,u.CommandMovement);u.Position=new(50,50);b.CommandSupport.Update();Assert.Equal(1,u.CommandMovement);
    }
    [Fact] public void PursuitSpecialistsCanExploitNearbyRoutsWithoutCancellingPlayerOrders()
    {
        var u=U("commonwealth_uhlans",commander:"antoni_madalinski");var front=U(id:1,army:1,x:550);var routed=U(id:2,army:1,x:500,y:450);routed.State=MoraleState.Routing;
        var b=new BattleSimulation([u,front,routed],Rules());b.Ai.ConfigureArmy(0,"balanced");u.AiTarget=front.Id;u.Order=new(OrderKind.Attack,TargetId:front.Id);
        b.Ai.Plan(u,"balanced");Assert.Equal(routed.Id,u.Order.TargetId);Assert.Equal(OrderKind.Attack,u.Order.Kind);
        b.Issue(new(u.Id,new(OrderKind.Hold)));b.Step();Assert.Equal(OrderKind.Hold,u.Order.Kind);Assert.True(u.PlayerOrder);
    }
    [Fact] public void SuvorovsDefaultDoctrineDoesNotOverwriteExplicitArmyInstructions()
    {
        var d=CombatScenarios.Get("commonwealth-commander-alexander_suvorov") with{AiStrategies=new()};var b=d.Create();Assert.Equal("all_out_attack",b.Ai.Armies[0]);b.Ai.ConfigureArmy(0,"hold_the_line");Assert.Equal("hold_the_line",b.Ai.Armies[0]);b.Ai.ConfigureArmy(0,"balanced");Assert.Equal("balanced",b.Ai.Armies[0]);
    }
    [Fact] public void HistoricalCommanderRespectsExplicitPlayerHoldAndMove()
    {
        var u=U("prussian_cuirassiers",commander:"gebhard_leberecht_von_blucher");var b=B(u);b.Ai.ConfigureArmy(0,"all_out_attack");b.Issue(new(0,new(OrderKind.Hold)));Steps(b,80);Assert.True(u.PlayerOrder);Assert.Equal(OrderKind.Hold,u.Order.Kind);b.Issue(new(0,new(OrderKind.Move,new(320,350))));Steps(b,60);Assert.Equal(OrderKind.Move,u.Order.Kind);
    }
    [Fact] public void CanisterIsPhysicalSweptFriendlyFireCapableAndBounded()
    {
        var gun=U("commonwealth_field_artillery");var friend=U(id:1,x:440);var target=U(id:2,army:1,x:480);var b=new BattleSimulation([gun,friend,target],Rules());b.Artillery.Salvo(gun,target);Assert.Equal(48,b.Artillery.Projectiles.Count);Assert.All(b.Artillery.Projectiles,p=>Assert.Equal("canister",p.Type));
        for(int i=0;i<30;i++)b.Artillery.Update();Assert.True(friend.Strength<friend.MaximumStrength);Assert.True(b.Metrics.FriendlyFireHits>0);Assert.Empty(b.Artillery.Projectiles);
        var far=B(U("commonwealth_field_artillery"));far.Artillery.Salvo(far.Units[0],far.Units[1]);Assert.Equal(6,far.Artillery.Projectiles.Count);Assert.All(far.Artillery.Projectiles,p=>Assert.Equal("round_shot",p.Type));
    }
    [Fact] public void CanisterDoesNotPassThroughHillsOrHitBeyondItsPhysicalRange()
    {
        var gun=U("commonwealth_field_artillery");var target=U(id:1,army:1,x:480);var b=new BattleSimulation([gun,target],Rules(),new([new(440,350,8,50,20,true)]));b.Artillery.Salvo(gun,target);for(int i=0;i<30;i++)b.Artillery.Update();Assert.Equal(target.MaximumStrength,target.Strength);Assert.Empty(b.Artillery.Projectiles);
    }
    [Fact] public void CanisterCannotDamageAFormationBeyondItsMaximumSweptRange()
    {
        var gun=U("commonwealth_field_artillery");var target=U(id:1,army:1,x:515);var b=B(gun,target);
        b.Artillery.Add(new(){OwnerId=0,Type="canister",Position=new(400,350),Velocity=new(100,0),Height=2,VerticalSpeed=5});
        for(int i=0;i<15;i++)b.Artillery.Update();Assert.Equal(target.MaximumStrength,target.Strength);Assert.Empty(b.Artillery.Projectiles);
    }
    [Fact] public void HistoricalAlternativeNamesCannotBeDuplicatedByAProceduralOfficer()
    {
        var cook=U("haudenosaunee_skirmishers",commander:"joseph_louis_cook");var generic=U(id:1);generic.Commander=generic.Commander with{Name="Akiatonharónkwen"};
        Assert.Throws<ArgumentException>(()=>new BattleSimulation([cook,generic],Rules()));
        var auto=new Regiment(2,0,"Detachment",Archetypes.Get("haudenosaunee_skirmishers"),new(400,500));
        var b=new BattleSimulation([cook,auto,U(id:3,army:1,x:850)],Rules());Assert.NotEqual("Akiatonharónkwen",auto.Commander.Name);
    }
    [Fact] public void MixedFactionCustomRecipeAndHistoricalNamesRoundTrip()
    {
        var recipe=new BattleConfiguration{Symmetric=false,Blue=new(){["commonwealth_regulars"]=1,["revolutionary_line"]=1,["haudenosaunee_skirmishers"]=1},Red=new(){["prussian_line"]=1,["russian_musketeers"]=1},ArmyCommanders=[new(0,"tadeusz_kosciuszko"),new(1,"alexander_suvorov")]}.Prepare();
        var cook=recipe.Placements.Single(p=>p.Archetype=="haudenosaunee_skirmishers");recipe=recipe with{Placements=recipe.Placements.Select(p=>p.Id==cook.Id?p with{Commander=HistoricalCommanders.Get("joseph_louis_cook").Create()}:p).ToArray()};
        recipe.Validate();var copy=BattleConfiguration.Parse(recipe.ToJson()).Prepare();Assert.Equal(2,copy.ArmyCommanders.Length);Assert.Equal("joseph_louis_cook",copy.Placements.Single(p=>p.Id==cook.Id).Commander!.DefinitionId);Assert.Equal(3,copy.Scenario().Create().Units.Where(u=>u.Army==0).Select(u=>u.Archetype.Faction).Distinct().Count());
    }
    [Fact] public void EveryLaboratoryScenarioCreatesAndAdvancesWithValidState()
    {
        var scenarios=CombatScenarios.Available.Where(p=>p.Id.StartsWith("commonwealth-",StringComparison.Ordinal)).ToArray();Assert.Equal(54,scenarios.Length);
        foreach(var (id,_) in scenarios){var b=CombatScenarios.Get(id).Create();Steps(b,5);Assert.All(b.Units,u=>Assert.True(u.Position.Finite && double.IsFinite(u.Facing+u.Morale+u.Cohesion)));}
    }
    [Fact] public void MixedAutonomousBattleIsDeterministicAndAllSystemsContribute()
    {
        string Run(){var b=CombatScenarios.Get("commonwealth-battle-coalition").Create();Steps(b,1500);Assert.True(b.Metrics.Volleys>0 && b.Metrics.ArtilleryShots>0 && b.Metrics.Casualties>0);return JsonSerializer.Serialize(new{snapshot=b.Snapshot(),b.Random.Draws,events=b.Events},ScenarioJson.Options);}Assert.Equal(Run(),Run());
    }
}
