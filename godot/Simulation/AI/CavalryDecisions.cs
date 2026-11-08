namespace Quiberon.Simulation;

public sealed partial class TacticalAi
{
    public ArmyDirector Director {get;}=new(battle);
    private void DescribeRole(Regiment u,ArmyPlan plan)
    {
        u.AiArmyPlan=$"{plan.Intention}: {plan.Reason}";
        u.AiArmyRole=u.Archetype.Category switch{UnitCategory.Cavalry=>"Mounted reserve",UnitCategory.Artillery=>"Fire support",_=>u.Archetype.Skirmisher?"Screen / harassment":u.Id==plan.ReserveId?"Infantry reserve":"Battle line"};
        u.AiArmyGoal=ArmyPurpose(u)?.Position;
    }
    private TacticalAssignmentDefinition? ArmyPurpose(Regiment u)
    {
        if(!Autonomous(u) || !Director.Plans.TryGetValue(u.Army,out var plan) || !plan.HasLine)return null;
        string kind="attack";Vec2 position=plan.Focus;double radius=180;
        var side=new Vec2(-plan.Forward.Y,plan.Forward.X);
        var own=battle.Units.Where(f=>f.Army==u.Army && f.Archetype.Category==UnitCategory.Infantry && !f.Archetype.Skirmisher).ToArray();
        var origin=new Vec2(own.Average(f=>Anchors[f.Id].X),own.Average(f=>Anchors[f.Id].Y));
        double lateral=Math.Clamp((Anchors[u.Id]-origin).Dot(side),-250,250);
        if(u.Archetype.Category==UnitCategory.Cavalry){kind="support";position=Director.CavalryStation(u,plan);radius=180;}
        else if(u.Archetype.Category==UnitCategory.Artillery){kind="support";position=plan.Front-plan.Forward*125+side*lateral;radius=220;}
        else if(u.Id==plan.ReserveId && !plan.CommitReserve){kind="reserve";position=plan.Centre-plan.Forward*70;radius=90;}
        else if(u.Id==plan.ReserveId && plan.Reinforce is { } sector){kind="support";position=sector;radius=100;}
        else if(Armies[u.Army]=="hold_the_line"){kind="defend";position=Anchors[u.Id];radius=100;}
        else position+=side*lateral;
        position=Clamp(u,position);
        return new($"army-{u.Army}-{u.AiArmyRole}",u.Army,kind,position,radius,[u.Id]);
    }
    private bool InfantryReserve(Regiment u,ArmyPlan plan,Regiment target)
    {
        if(plan.ReserveId!=u.Id || plan.CommitReserve || (target.Position-u.Position).Length<=(u.Archetype.Weapon?.Range??100)*1.15)return false;
        var station=Clamp(u,plan.Centre-plan.Forward*70);
        Note(u,"Army reserve: accompany line until a threatened sector or opening requires support",(station-u.Position).Length>25?new(OrderKind.Move,station):new(OrderKind.Reserve));return true;
    }
    private bool MountedDecision(Regiment u,Regiment[] detected,string strategy,ArmyPlan plan)
    {
        if(u.Archetype.Category!=UnitCategory.Cavalry || !plan.HasLine)return false;
        if(u.Navigation.Route.Count>0)return true; // Finish the real crossing; do not replace its approach mid-transit.
        var candidates=new SortedDictionary<int,Regiment>();foreach(var e in detected)candidates[e.Id]=e;
        foreach(var e in battle.Combat.Nearby(u.Position,320))
            if(e.Army!=u.Army && e.Active && (e.Position-u.Position).Length<=320 && !(e.Id==u.AiAvoidTarget && battle.Time<u.AiAvoidUntil) && battle.Perceives(u,e))candidates.TryAdd(e.Id,e);
        Regiment? chosen=null;double score=double.PositiveInfinity;
        foreach(var enemy in candidates.Values)
        {
            if(!MountedOpportunity(u,enemy,plan))continue;
            double value=CavalryScore(u,enemy);
            if(enemy.Id==u.CavalryTargetId && battle.Time<u.AiMountedCommitUntil)value-=25;
            if(value<score){score=value;chosen=enemy;}
        }
        if(chosen is not null)
        {
            if(Preparation(u,chosen)){u.AiMountedIntent="Recover";return true;}
            RecordTarget(u,chosen);u.CavalryTargetId=chosen.Id;u.AiTargetScore=score;
            if(u.AiMountedIntent!="Exploit"){u.AiMountedCommitUntil=battle.Time+20;u.AiMountedIntent="Exploit";}
            Note(u,"Mounted exploitation: favourable target, nearby support and a valid run-up",new(OrderKind.Attack,TargetId:chosen.Id));return true;
        }
        // A failed opportunity returns to the friendly wing, not an enemy-relative flank waypoint.
        if(u.CavalryState==CavalryState.Melee && u.AiMeleeSince is { } since && battle.Time-since<CommanderSystem.Policy(u).DisengageSeconds)return true;
        var assigned=Assignment(u);
        var station=Clamp(u,assigned is not null && !assigned.Id.StartsWith("army-",StringComparison.Ordinal) && assigned.Kind is "support" or "reserve"
            ?assigned.Position-plan.Forward*(assigned.Kind=="reserve"?0:65):Director.CavalryStation(u,plan));
        if(u.AiEscortGoal is null || (station-u.AiEscortGoal.Value).Length>25)u.AiEscortGoal=station;
        var goal=u.AiEscortGoal.Value;
        bool recover=u.Cohesion<50 || u.Fatigue>battle.Rules.PursuitMaxFatigue-10;
        u.AiMountedIntent=recover?"Recover":(goal-u.Position).Length>20?"Accompany":"Reserve";
        Note(u,recover?"Mounted recovery behind friendly infantry":u.AiMountedIntent=="Accompany"?"Accompany friendly wing; do not advance unsupported":"Mounted reserve: watch for a supported opening",
            (goal-u.Position).Length>20?new(OrderKind.Move,goal):new(OrderKind.Reserve));
        return true;
    }
    private bool MountedOpportunity(Regiment u,Regiment enemy,ArmyPlan plan)
    {
        if(u.Cohesion<50 || u.Fatigue>battle.Rules.PursuitMaxFatigue-10)return false;
        double distance=(enemy.Position-u.Position).Length;
        double reach=CommanderSystem.Is(u,"aggressive")?250:CommanderSystem.Is(u,"cautious")?180:220;
        if((enemy.Position-plan.Front).Dot(plan.Forward)>reach || distance>350)return false;
        var assignment=Assignment(u);
        if(assignment is {Kind:"reserve"})return false;
        if(assignment is {Kind:"defend" or "support"} && (enemy.Position-assignment.Position).Length>assignment.Radius+100)return false;
        bool exposed=Vulnerable(enemy) || enemy.Archetype.Category==UnitCategory.Artillery ||
            enemy.Archetype.Category==UnitCategory.Cavalry && enemy.Strength*enemy.Archetype.Melee<u.Strength*u.Archetype.Melee*1.15 ||
            enemy.Archetype.Category==UnitCategory.Infantry && CavalrySystem.Readiness(u,enemy)<.25 && Math.Abs(Vec2.AngleDelta(enemy.Facing,Vec2.AngleTo(enemy.Position,u.Position)))>Math.PI/3;
        if(!exposed)return false;
        double overmatch=Math.Clamp(CommanderSystem.Policy(u).Overmatch,1.1,1.8);
        if(AssessEngagement(u,enemy)>overmatch)return false;
        var middle=(u.Position+enemy.Position)*.5;
        if(battle.Terrain.ForestDensity(middle)>.5 || battle.Terrain.Gradient(middle).Length>.16)return false;
        if(!battle.Terrain.Environment.Swept(u.Rect,new(enemy.Position,Vec2.AngleTo(u.Position,enemy.Position),u.Width,u.Depth),u.Archetype.Category,false))return false;
        return true;
    }
}
