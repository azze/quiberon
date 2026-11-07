using Quiberon.Simulation;
using Xunit;
using System.Text.Json;
public class CampaignTests
{
    static CampaignSession New()=>CampaignSession.New(1796);
    static BattleSimulation Begin(CampaignSession c){var d=c.PrepareBattle();var b=d.Create();c.Begin();return b;}
    static void Victory(CampaignSession c,int loss=0){var b=Begin(c);var u=b.Unit(c.State.Roster[0].Id)!;u.Strength=Math.Max(0,u.Strength-loss);b.FinishMission(0,"controlled progression fixture");c.Complete(b);}
    static void Reward(CampaignSession c){var r=c.State.Rewards.First();c.Claim(r.Id,r.Upgrades?.FirstOrDefault()??"");}
    [Fact] public void StartsWithCommonwealthRosterAndUniqueHistoricalLeader(){var c=New();Assert.Equal(5,c.State.Roster.Count);Assert.Equal(1,c.State.Stage);Assert.Equal("overview",c.State.Phase);Assert.Equal("franciszek_ksawery_niesiolowski",c.State.Commanders.Single(x=>x.Id==c.State.Roster[0].CommanderId).DefinitionId);Assert.Equal(5,c.State.Roster.Select(r=>r.CommanderId).Distinct().Count());Assert.Throws<ArgumentException>(()=>c.AddHistorical("franciszek_ksawery_niesiolowski"));}
    [Fact] public void StrengthRecoveryDestructionAndReserveCommandersPersist(){var c=New();var id=c.State.Roster[0].Id;string officer=c.State.Roster[0].CommanderId;var b=Begin(c);b.Unit(id)!.Strength=0;b.Unit(c.State.Roster[1].Id)!.Strength=140;b.FinishMission(0,"fixture");c.Complete(b);Assert.DoesNotContain(c.State.Roster,r=>r.Id==id);Assert.Contains(c.State.Commanders,r=>r.Id==officer);Assert.Equal(160,c.State.Roster[0].Strength);Assert.Throws<ArgumentException>(()=>c.Complete(b));}
    [Theory][InlineData("rescue")][InlineData("intercept")]
    public void SixBattleProgressionSaveReloadAndBothBranchesWork(string branch)
    {
        var c=New();for(int stage=1;stage<=6;stage++)
        {
            Assert.Equal(stage,c.State.Stage);var ids=c.State.Roster.Select(r=>r.Id).ToArray();Victory(c,20);
            if(stage==6)break;
            string offered=JsonSerializer.Serialize(c.State.Rewards);c=CampaignSession.Deserialize(c.Serialize());Assert.Equal(offered,JsonSerializer.Serialize(c.State.Rewards));Reward(c);Assert.Throws<ArgumentException>(()=>c.Claim("already claimed"));
            while(c.State.Phase=="event"){var e=CampaignContent.Events.Single(e=>e.Id==c.State.PendingEvent);c.ChooseEvent(e.Id=="dangerous_choice"?branch:e.Choices[0].Id);}c=CampaignSession.Deserialize(c.Serialize());
            Assert.All(ids.Where(id=>c.State.Roster.Any(r=>r.Id==id)),id=>Assert.Contains(c.State.Roster,r=>r.Id==id));
        }
        Assert.Equal("ended",c.State.Phase);Assert.Equal("decisive",c.State.Ending);Assert.Equal(6,c.State.History.Count);Assert.Equal(branch,c.State.Branch);Assert.Contains(branch=="rescue"?"allies_saved":"supplies_cut",c.State.Flags);
    }
    [Fact] public void DefeatAndNegotiatedVictoryAreExplicit(){var c=New();var b=Begin(c);b.FinishMission(1,"fixture");c.Complete(b);Assert.Equal("defeat",c.State.Ending);Assert.Throws<ArgumentException>(()=>c.PrepareBattle());var late=New();late.State.Stage=6;var last=Begin(late);foreach(var u in last.Units.Where(u=>u.Army==0))u.Strength=1;last.FinishMission(0,"fixture");late.Complete(last);Assert.Equal("negotiated",late.State.Ending);}
    [Fact] public void RewardUpgradeChoicesPersistAndApplyOnce(){var c=New();Victory(c);var r=c.State.Rewards.FirstOrDefault(r=>r.Kind=="upgrade");if(r is null){Assert.Equal(3,c.State.Rewards.Count);return;}c=CampaignSession.Deserialize(c.Serialize());c.Claim(r.Id,r.Upgrades![0]);Assert.Contains(r.Upgrades[0],c.State.Commanders.Single(x=>x.Id==r.CommanderId).Upgrades!);Assert.Throws<ArgumentException>(()=>c.Claim(r.Id,r.Upgrades[0]));}
    [Fact] public void AssignmentsPreserveDisplacedOfficersAndCompatibility(){var c=New();var officer=c.AddHistorical("jan_henryk_dabrowski");var old=c.State.Roster[0].CommanderId;c.Assign(c.State.Roster[0].Id,officer.Id);Assert.Contains(c.State.Commanders,x=>x.Id==old);Assert.Equal(officer.Id,c.State.Roster[0].CommanderId);Assert.Throws<ArgumentException>(()=>c.Assign(c.State.Roster.Last().Id,officer.Id));}
    [Theory][InlineData(1,"")][InlineData(2,"")][InlineData(3,"")][InlineData(4,"rescue")][InlineData(4,"intercept")][InlineData(5,"rescue")][InlineData(6,"rescue")]
    public void EveryAuthoredEncounterStartsAndRunsDeterministically(int stage,string branch)
    {
        string Run(){var c=New();c.State.Stage=stage;c.State.Branch=branch;var d=c.PrepareBattle(true);var b=d.Create();for(int i=0;i<800 && b.Result is null;i++)b.Step();Assert.All(b.Units,u=>{Assert.True(u.Position.Finite);Assert.InRange(u.Strength,0,u.MaximumStrength);Assert.True(b.Terrain.Environment.Passable(u.Rect,u.Archetype.Category));});return JsonSerializer.Serialize(new{snapshot=b.Snapshot(),events=b.Events,draws=b.Random.Draws},ScenarioJson.Options);}
        Assert.Equal(Run(),Run());
    }
    [Fact] public void CapacityAndUnavailableEnemiesAreEnforced(){var c=New();while(c.State.Roster.Count<c.State.Rules.Capacity)c.Recruit("commonwealth_militia");Assert.Throws<ArgumentException>(()=>c.Recruit("commonwealth_regulars"));Assert.Throws<ArgumentException>(()=>New().Recruit("prussian_line"));Victory(c);Assert.DoesNotContain(c.State.Rewards,r=>r.Kind=="unit");}
    [Fact] public void SavedChoicesDoNotRerollAndMalformedVersionsFail(){var c=New();Victory(c);var copy=CampaignSession.Deserialize(c.Serialize());Assert.Equal(c.Serialize(),copy.Serialize());Assert.Throws<ArgumentException>(()=>CampaignSession.Deserialize(c.Serialize().Replace("\"version\": 1","\"version\": 9")));}
    static BattleSimulation Mission(ObjectiveDefinition objective,params Regiment[] units){var b=new BattleSimulation(units,new(){Width=1000,Height=800});b.SetMission(new([objective],Timeout:100));return b;}
    static Regiment U(int id,int army,double x=400,double y=300)=>new(id,army,"Test",Archetypes.Get("infantry"),new(x,y),0);
    [Theory][InlineData("capture")][InlineData("hold")]
    public void CapturingAndHoldingNeedOrganizedUncontestedControl(string type){var a=U(0,0);var e=U(1,1,410);var b=Mission(new("point",type,"Control",new(400,300),100,2),a,e);for(int i=0;i<30;i++)b.Step();Assert.Null(b.Result);e.Position=new(800,600);a.State=MoraleState.Routing;for(int i=0;i<30;i++)b.Step();Assert.Null(b.Result);a.State=MoraleState.Steady;for(int i=0;i<30 && b.Result is null;i++)b.Step();Assert.Equal(0,b.Result!.WinnerArmy);}
    [Fact] public void DelayLosesWhenEnemyControlsPositionAndWinsAtDeadline(){var b=Mission(new("delay","delay","Defend",new(400,300),60,30),U(0,0,100),U(1,1));for(int i=0;i<110;i++)b.Step();Assert.Equal(1,b.Result!.WinnerArmy);var safe=Mission(new("delay","delay","Defend",new(400,300),60,2),U(0,0),U(1,1,800));for(int i=0;i<25;i++)safe.Step();Assert.Equal(0,safe.Result!.WinnerArmy);}
    [Fact] public void RescueAndConvoyUsePhysicalUnits(){var ally=U(0,0);var b=Mission(new("rescue","rescue","Safety",new(400,300),100,Units:[0]),ally,U(1,1,800));b.Step();Assert.Equal(0,b.Result!.WinnerArmy);var convoy=U(2,1,600);convoy.Strength=0;var intercept=Mission(new("convoy","convoy","Intercept",new(900,300),50,Units:[2]),U(0,0),convoy);intercept.Step();Assert.Equal(0,intercept.Result!.WinnerArmy);}
    [Fact] public void ReinforcementsWaitForClearEntryAndDoNotDuplicate(){var a=U(0,0);var reserve=U(1,0,400);var b=new BattleSimulation([a,reserve],new(){Width=1000,Height=800});b.SetMission(new([new("hold","hold","Hold",new(50,50),30,90)], [new(1,[],Arrival:1)]));for(int i=0;i<30;i++)b.Step();Assert.True(reserve.Withdrawn);a.Position=new(100,100);b.Step();Assert.False(reserve.Withdrawn);for(int i=0;i<20;i++)b.Step();Assert.Single(b.Events,e=>e.Kind=="reinforcement");}

    [Fact] public void UpgradeRewardActuallyPersistsAcrossNextBattleAndRejectsBadChoices()
    {
        CampaignSession? found=null;CampaignReward? offer=null;
        for(int seed=1;seed<=30;seed++){var c=CampaignSession.New(seed);Victory(c);var r=c.State.Rewards.FirstOrDefault(r=>r.Kind=="upgrade");if(r is not null){found=c;offer=r;break;}}
        Assert.NotNull(found);Assert.NotNull(offer);Assert.Throws<ArgumentException>(()=>found.Claim(offer.Id,"invalid"));found.Claim(offer.Id,offer.Upgrades![0]);while(found.State.Phase=="event")found.ChooseEvent(CampaignContent.Events.Single(e=>e.Id==found.State.PendingEvent).Choices[0].Id);
        var loaded=CampaignSession.Deserialize(found.Serialize());var b=Begin(loaded);Assert.Contains(b.Units,u=>u.Commander.Id==offer.CommanderId && u.Commander.Upgrades!.Contains(offer.Upgrades[0]));
    }
    [Fact] public void AtomicSaveAndPendingEventsReloadWithoutRepeatingReinforcements()
    {
        var c=New();Victory(c);Reward(c);string path=Path.Combine(Path.GetTempPath(),"campaign-"+Guid.NewGuid()+".json");
        try{c.Save(path);c=CampaignSession.Deserialize(File.ReadAllText(path));c.ChooseEvent("accept");Assert.Throws<ArgumentException>(()=>c.ChooseEvent("accept"));Assert.Single(c.State.Commanders,x=>x.DefinitionId=="joseph_louis_cook");c.Save(path);var copy=CampaignSession.Deserialize(File.ReadAllText(path));Assert.Equal(c.Serialize(),copy.Serialize());var b=Begin(copy);Assert.Throws<ArgumentException>(()=>copy.Save(path));}finally{File.Delete(path);File.Delete(path+".tmp");}
    }
    [Fact] public void CampaignGenerationReservesHistoricalAlternativeNames()
    {
        for(int seed=1;seed<30;seed++){var c=CampaignSession.New(seed);c.State.Flags.Add("haudenosaunee");c.Recruit("haudenosaunee_skirmishers");var cook=c.AddHistorical("joseph_louis_cook");c.Assign(c.State.Roster.Last().Id,cook.Id);_ =c.PrepareBattle().Create();}
    }
    [Fact] public void BranchAndDiplomaticConsequencesChangeOnlyAuthoredForces()
    {
        var c=New();c.State.Stage=5;c.State.Branch="intercept";var baseline=c.PrepareBattle();c.State.Flags.Add("supplies_cut");c.State.Flags.Add("enemy_delay");var cut=c.PrepareBattle();Assert.Equal(baseline.Units.Count(u=>u.Army==1)-1,cut.Units.Count(u=>u.Army==1));Assert.True(cut.Mission!.Directives!.First(p=>p.Arrival>0).Arrival>baseline.Mission!.Directives!.First(p=>p.Arrival>0).Arrival);
        c.State.Flags.Add("allies_saved");Assert.Contains(c.PrepareBattle().Units,u=>u.Id==850 && u.Army==0);
    }
    [Fact] public void SimultaneousFailureTakesPriorityAndSubstantialEnemiesContest()
    {
        var b=Mission(new("capture","capture","Point",new(400,300),60,1),U(0,0),U(1,1,800));for(int i=0;i<15;i++)b.Step();Assert.Equal(0,b.Result!.WinnerArmy);
        var minimal=U(1,1,410);minimal.Strength=1;var notContested=Mission(new("capture","capture","Point",new(400,300),60,1),U(0,0),minimal);for(int i=0;i<15;i++)notContested.Step();Assert.Equal(0,notContested.Result!.WinnerArmy);
    }

    [Fact] public void TimedBritishArrivalMergesWithAuthoredDefensiveAssignment()
    {
        var c=New();c.State.Flags.UnionWith(["british","haudenosaunee"]);c.Recruit("revolutionary_line","edward_marcus_despard");c.State.Roster[^1]=c.State.Roster[^1] with{ArrivalStage=3};int waveId=c.State.Roster[^1].Id;c.Assign(c.State.Roster[0].Id,c.State.Roster[^1].CommanderId);c.State.Stage=3;
        var d=c.PrepareBattle(true);Assert.Equal(d.Mission!.Directives!.Length,d.Mission.Directives.Select(p=>p.UnitId).Distinct().Count());var b=d.Create();Assert.Contains(d.Mission.Directives,p=>p.Arrival==60);for(int i=0;i<650;i++)b.Step();Assert.Contains(b.Events,e=>e.Kind=="reinforcement" && e.UnitId==waveId);
    }

    [Fact] public void InvalidRecruitmentIsTransactionalAndForeignSavesAreRejected()
    {var c=New();var saved=c.Serialize();Assert.Throws<ArgumentException>(()=>c.Recruit("commonwealth_national_cavalry","jan_henryk_dabrowski"));Assert.Equal(saved,c.Serialize());Assert.Throws<ArgumentException>(()=>CampaignSession.Deserialize("{\"version\":1}"));}
    [Fact] public void AuthoredFriendlyMovementNeverOverridesAnExplicitHold()
    {var a=U(0,0);var b=new BattleSimulation([a],new(){Width=1000,Height=800});b.SetMission(new([new("wait","delay","Wait",new(50,50),20,90)],[new(0,[new(700,300)])]));b.Step();b.Issue(new(0,new(OrderKind.Hold)));b.Step();var p=a.Position;for(int i=0;i<20;i++)b.Step();Assert.Equal(OrderKind.Hold,a.Order.Kind);Assert.Equal(p,a.Position);}

    [Fact] public void NextEncounterCopiesStrengthAndAbilitiesButResetsTransientCombatState()
    {
        var c=New();var b=Begin(c);var u=b.Unit(c.State.Roster[0].Id)!;u.Strength=180;u.State=MoraleState.Routing;u.Cohesion=12;u.Morale=8;u.Fatigue=50;u.ReloadLeft=90;u.ChargeCooldown=100;u.TargetId=100;
        b.FinishMission(0,"controlled boundary fixture");c.Complete(b);Reward(c);while(c.State.Phase=="event")c.ChooseEvent(CampaignContent.Events.Single(e=>e.Id==c.State.PendingEvent).Choices[0].Id);var next=c.PrepareBattle().Create();var fresh=next.Unit(u.Id)!;
        Assert.NotSame(u,fresh);Assert.Equal(c.State.Roster.Single(r=>r.Id==u.Id).Strength,fresh.Strength);Assert.Equal(MoraleState.Steady,fresh.State);Assert.Equal(100,fresh.Cohesion);Assert.Equal(0,fresh.Fatigue);Assert.Equal(0,fresh.ReloadLeft);Assert.Equal(0,fresh.ChargeCooldown);Assert.Null(fresh.TargetId);Assert.Empty(next.Artillery.Projectiles);
    }
}
