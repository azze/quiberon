using Quiberon.Simulation;
using Xunit;

public class MeleeRetentionTests
{
    static Regiment Unit(int id,int army,Vec2 p,string archetype="infantry")=>new(id,army,$"Unit {id}",Archetypes.Get(archetype),p,army==0?0:Math.PI);
    static BattleSimulation Pair(bool dynamics=false)=>new([Unit(0,0,new(300,300)),Unit(1,1,new(312,300))],new(){CombatEnabled=true,MoraleEnabled=dynamics,CavalryEnabled=dynamics});
    [Fact] public void NewFightsNeedContactButEstablishedFightsSurviveSmallGaps()
    {
        var b=Pair();var a=b.Units[0];var t=b.Units[1];t.Position=new(315,300);b.Combat.ResolveMelee(b.Units);Assert.Equal(0,b.Combat.EngagementCount);
        t.Position=new(312,300);b.Combat.ResolveMelee(b.Units);Assert.Equal(1,b.Combat.EngagementCount);
        int strength=t.Strength;
        foreach(double x in new[]{313.0,315.0,312.0,316.0,314.0}){t.Position=new(x,300);b.Combat.ResolveMelee(b.Units);Assert.True(b.Combat.IsEngaged(a,t));}
        Assert.Single(b.Events,e=>e.Kind=="melee_enter");Assert.DoesNotContain(b.Events,e=>e.Kind=="melee_leave");
        Assert.Equal(strength,t.Strength);Assert.Equal(1,b.Metrics.MeleePulses);
    }
    [Fact] public void LeavingTheBufferEndsMeleeAndDoesNotRetainGhostTargets()
    {
        var b=Pair();b.Combat.ResolveMelee(b.Units);b.Units[1].Position=new(318,300);b.Combat.ResolveMelee(b.Units);b.Combat.Cleanup();
        Assert.Equal(0,b.Combat.EngagementCount);Assert.Single(b.Events,e=>e.Kind=="melee_leave");Assert.NotEqual(CombatState.Melee,b.Units[0].CombatState);
    }
    [Fact] public void DestroyedOrEscapedRegimentsCannotRemainEngaged()
    {
        foreach(bool escape in new[]{false,true}){var b=Pair();b.Combat.ResolveMelee(b.Units);if(escape)b.Units[1].Withdrawn=true;else b.Units[1].Strength=0;b.Combat.Cleanup();Assert.Equal(0,b.Combat.EngagementCount);Assert.False(b.Combat.IsEngaged(b.Units[0],b.Units[1]));}
    }
    [Fact] public void FleeingAndExplicitDisengagementAreNotFrozenByRetention()
    {
        var b=Pair(true);b.Units[0].HoldFire=b.Units[1].HoldFire=true;b.Combat.ResolveMelee(b.Units);b.Units[1].State=MoraleState.Routing;b.Units[1].Morale=10;
        var before=b.Units[1].Position;for(int i=0;i<80;i++)b.Step();Assert.True((b.Units[1].Position-before).Length>4);Assert.Equal(0,b.Combat.EngagementCount);
        b=Pair();b.Issue(new(0,new(OrderKind.Move,new(250,300))));for(int i=0;i<160;i++)b.Step();Assert.True(b.Units[0].Position.X<290);Assert.Equal(0,b.Combat.EngagementCount);
    }
    [Fact] public void RetentionHaloCannotCreateAnotherChargeImpact()
    {
        var a=Unit(0,0,new(300,300),"cavalry");var t=Unit(1,1,new(315,300));var b=new BattleSimulation([a,t],new(){CombatEnabled=true,CavalryEnabled=true,MoraleEnabled=true});
        b.Combat.ResolveMelee(b.Units);t.Position=new(318,300);a.CavalryState=CavalryState.Charging;a.ChargeSequence=1;a.ChargeMomentum=1;a.Velocity=new(12,0);
        b.Combat.ResolveMelee(b.Units);Assert.Equal(1,b.Combat.EngagementCount);Assert.Equal(0,b.Metrics.ChargeImpacts);
    }
    [Fact] public void SpatialBroadPhaseRetainsTheSameBufferedContacts()
    {
        var units=new List<Regiment>{Unit(0,0,new(399,300)),Unit(1,1,new(411,300))};
        for(int i=2;i<14;i++)units.Add(Unit(i,0,new(600+(i%4)*150,500+(i/4)*120)));
        var b=new BattleSimulation(units,new(){CombatEnabled=true,Width=1600,Height=1200});b.Combat.ResolveMelee(b.Units);units[1].Position=new(414,300);b.Combat.ResolveMelee(b.Units);
        Assert.Equal(1,b.Combat.EngagementCount);Assert.Single(b.Events,e=>e.Kind=="melee_enter");
    }
    [Fact] public void CavalryTransitionsToMovingPursuitRatherThanBeingHeldInMelee()
    {
        var a=Unit(0,0,new(300,300),"cavalry");var t=Unit(1,1,new(315,300));var b=new BattleSimulation([a,t],new(){CombatEnabled=true,CavalryEnabled=true,MoraleEnabled=true});
        a.Order=new(OrderKind.Attack,TargetId:1);a.TargetId=1;b.Combat.ResolveMelee(b.Units);t.Position=new(318,300);t.State=MoraleState.Routing;
        b.Combat.ResolveMelee(b.Units);Assert.Equal(CavalryState.Pursuit,a.CavalryState);Assert.Equal(0,b.Combat.EngagementCount);
    }
}
