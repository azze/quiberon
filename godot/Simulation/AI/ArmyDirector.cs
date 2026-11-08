namespace Quiberon.Simulation;

public sealed record ArmyPlan(int Army,string Intention,Vec2 Focus,Vec2 Centre,Vec2 Front,Vec2 Forward,
    bool HasLine,int? ReserveId,bool CommitReserve,Vec2? Reinforce,string Reason,double NextReview,double CommitUntil=0);

/// <summary>Small, persistent army plan. It assigns purposes; regiment AI owns combat orders.</summary>
public sealed class ArmyDirector(BattleSimulation battle)
{
    private readonly SortedDictionary<int,ArmyPlan> plans=new();
    public IReadOnlyDictionary<int,ArmyPlan> Plans=>plans;
    public void Invalidate(int army)=>plans.Remove(army);
    public ArmyPlan Get(int army,string strategy)
    {
        if(plans.TryGetValue(army,out var old) && battle.Time<old.NextReview &&
            (old.ReserveId is null || battle.Unit(old.ReserveId.Value)?.Effective==true))return old;
        var friends=battle.Units.Where(u=>u.Army==army && u.Effective && !u.NonCombatant).ToArray();
        var line=friends.Where(u=>u.Archetype.Category==UnitCategory.Infantry && !u.Archetype.Skirmisher && !u.InfantryCharging).ToArray();
        int? selectedReserve=line.Length>=4 && strategy=="balanced"?(old?.ReserveId is { } previous && line.Any(u=>u.Id==previous)?previous:line.OrderBy(u=>u.Id).Last().Id):null;
        var marching=line.Where(u=>u.Id!=selectedReserve || old?.CommitReserve==true).ToArray();
        var body=marching.Length>0?marching:friends;
        Vec2 centre=body.Length>0?new(body.Average(u=>u.Position.X),body.Average(u=>u.Position.Y)):new(battle.Rules.Width/2,battle.Rules.Height/2);
        var known=new SortedDictionary<int,Regiment>();
        foreach(var friend in friends)
        {
            foreach(int id in new[]{friend.AiTarget??-1,friend.TargetId??-1})
                if(battle.Unit(id)is {Active:true} target && target.Army!=army && battle.Perceives(friend,target))known.TryAdd(id,target);
            foreach(var target in battle.Combat.Nearby(friend.Position,420))
                if(target.Active && target.Army!=army && (target.Position-friend.Position).Length<=420 && !known.ContainsKey(target.Id) && battle.Perceives(friend,target))known.TryAdd(target.Id,target);
        }
        var observed=known.Values.Where(e=>e.Effective).ToArray();if(observed.Length==0)observed=known.Values.ToArray();
        var forward=observed.Length>0?(new Vec2(observed.Average(u=>u.Position.X),observed.Average(u=>u.Position.Y))-centre).Normalized:
            old?.Forward??(body.Length>0?new Vec2(body.Average(u=>Math.Cos(u.Facing)),body.Average(u=>Math.Sin(u.Facing))).Normalized:new(army==0?1:-1,0));
        if(forward.Length<.1)forward=new(army==0?1:-1,0);
        var progress=marching.Select(u=>(u.Position-centre).Dot(forward)).Order().ToArray();
        var front=centre+forward*(progress.Length>0?progress[(progress.Length-1)*3/4]:0);
        Vec2 focus=observed.Length>0?new(observed.Average(u=>u.Position.X),observed.Average(u=>u.Position.Y)):
            old?.Focus??new(battle.Rules.Width/2,centre.Y);
        string intent=strategy=="hold_the_line"?"Defend":"Advance",reason=known.Count>0?"Advance towards observed contact":"Advance towards last contact / battlefield centre";
        var mission=battle.Mission;
        if(strategy=="hold_the_line" && mission is null){focus=old?.Focus??centre;reason="Maintain deployment area; support threatened sectors";}
        if(mission is not null)
        {
            var objective=mission.Definition.Objectives.FirstOrDefault(o=>!o.Optional && o.Type is "capture" or "hold" or "delay" && mission.Objectives.First(s=>s.Id==o.Id).Status=="active");
            if(objective is not null)
            {focus=objective.Position;bool defend=objective.Type=="capture"?objective.Army!=army:objective.Army==army;intent=defend?"Defend":"Attack objective";reason=$"{intent}: {objective.Description}";}
        }
        var close=known.Values.Where(e=>e.Effective && (e.Position-front).Length<220).ToArray();
        if(intent=="Advance" && close.Length>0){intent="Engage";reason="Establish firing line; artillery supports; cavalry waits on the wings";}
        Vec2? reinforce=null;
        foreach(var u in line.OrderBy(u=>u.Cohesion).ThenBy(u=>u.Id))
        {
            var enemy=close.OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).FirstOrDefault();
            if(enemy is null || (enemy.Position-u.Position).Length>190 || !battle.Perceives(u,enemy))continue;
            if(u.State==MoraleState.Wavering || battle.Ai.AssessEngagement(u,enemy)>1.65){reinforce=u.Position-forward*30;break;}
        }
        bool opportunity=known.Values.Any(e=>e.State is MoraleState.Wavering or MoraleState.Routing && (e.Position-front).Length<240);
        if(intent=="Engage" && opportunity){intent="Exploit";reason="Maintain infantry pressure; release cavalry against local disruption";}
        if(reinforce is not null){intent="Reinforce";reason="Support a threatened section without abandoning the battle line";}
        int? reserve=selectedReserve;
        if(old is not null && intent!=old.Intention && battle.Time<old.CommitUntil && reinforce is null){intent=old.Intention;reason=old.Reason;}
        bool commit=old?.CommitReserve==true || reinforce is not null || opportunity || line.Any(u=>u.Strength<battle.InitialUnitStrength[u.Id]*.85);
        var result=new ArmyPlan(army,intent,focus,centre,front,forward,line.Length>0,reserve,commit,reinforce,reason,battle.Time+5,old is null || old.Intention!=intent?battle.Time+15:old.CommitUntil);
        plans[army]=result;
        if(friends.Length>0 && (old is null || old.Intention!=intent))battle.Emit("army_plan",friends[0],null,focus,3,0,reason);
        return result;
    }
    public Vec2 CavalryStation(Regiment u,ArmyPlan plan)
    {
        var side=new Vec2(-plan.Forward.Y,plan.Forward.X);
        var horses=battle.Units.Where(f=>f.Army==u.Army && f.Archetype.Category==UnitCategory.Cavalry).OrderBy(f=>battle.Ai.Anchors[f.Id].Dot(side)).ThenBy(f=>f.Id).ToArray();
        int index=Array.FindIndex(horses,f=>f.Id==u.Id),split=(horses.Length+1)/2;
        double sign=horses.Length>1?(index<split?-1:1):(battle.Ai.Anchors[u.Id]-plan.Centre).Dot(side)<0?-1:1;
        int lane=horses.Length>1?(index<split?index:index-split):0;
        var wing=battle.Units.Where(f=>f.Army==u.Army && f.Effective && (plan.CommitReserve || f.Id!=plan.ReserveId) && !f.InfantryCharging && f.Archetype.Category==UnitCategory.Infantry && !f.Archetype.Skirmisher)
            .OrderByDescending(f=>(f.Position-plan.Centre).Dot(side)*sign).ThenBy(f=>f.Id).FirstOrDefault();
        return (wing?.Position??plan.Centre)-plan.Forward*(75+lane*25)+side*(sign*(45+lane*45));
    }
}
