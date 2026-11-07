namespace Quiberon.Simulation;

public sealed record ObjectiveDefinition(string Id,string Type,string Description,Vec2 Position=default,double Radius=70,double Duration=30,int Army=0,int[]? Units=null,double RequiredFraction=.5,string[]? Dependencies=null,bool Optional=false);
public sealed record DirectiveDefinition(int UnitId,Vec2[] Waypoints,string? Crossing=null,Formation? Formation=null,string After="attack",double Arrival=0,string? Condition=null,bool Convoy=false);
public sealed record MissionDefinition(ObjectiveDefinition[] Objectives,DirectiveDefinition[]? Directives=null,double Timeout=900,string PlayerZone="west");
public sealed class ObjectiveState
{
    public string Id {get;set;}="";
    public string Status {get;set;}="active";
    public double Progress {get;set;}
    public int Owner {get;set;}=-1;
}
/// <summary>Optional authored mission rules. No campaign persistence or strategic planner.</summary>
public sealed class MissionSystem
{
    readonly BattleSimulation battle;
    public MissionDefinition Definition {get;}
    public IReadOnlyList<ObjectiveState> Objectives {get;}
    readonly Dictionary<int,int> waypoint=new();
    readonly HashSet<int> pending=new();
    readonly Dictionary<int,double> blocked=new();
    readonly Dictionary<int,int> original=new();
    public bool Arrived(int id)=>!pending.Contains(id);
    public MissionSystem(BattleSimulation b,MissionDefinition d)
    {
        battle=b;Definition=d;
        if(d.Objectives.Length==0 || d.Objectives.Select(o=>o.Id).Distinct().Count()!=d.Objectives.Length || d.Timeout<=0 || !double.IsFinite(d.Timeout))throw new ArgumentException("Invalid mission objectives/timeout.");
        foreach(var o in d.Objectives)if(!new[]{"defeat","capture","hold","delay","rescue","convoy"}.Contains(o.Type) || !o.Position.Finite || o.Radius<=0 || o.Duration<0 || !double.IsFinite(o.Radius+o.Duration+o.RequiredFraction) || o.RequiredFraction is <=0 or >1 || o.Dependencies?.Any(id=>!d.Objectives.Any(x=>x.Id==id))==true)throw new ArgumentException("Invalid objective.");
        if(d.Objectives.Any(o=>o.Type is "rescue" or "convoy" && (o.Units is not {Length:>0} || o.Units.Any(id=>b.Unit(id)is null))) || (d.Directives??[]).Select(p=>p.UnitId).Distinct().Count()!=(d.Directives?.Length??0))throw new ArgumentException("Invalid objective units or duplicate directives.");
        Objectives=d.Objectives.Select(o=>new ObjectiveState{Id=o.Id}).ToArray();
        foreach(var plan in d.Directives??[])
        {
            var u=b.Unit(plan.UnitId)??throw new ArgumentException("Directive references unknown unit.");
            if(plan.Waypoints.Length>64 || plan.Condition is { } condition && !d.Objectives.Any(o=>o.Id==condition) || plan.Waypoints.Any(p=>!p.Finite) || plan.Arrival<0 || !double.IsFinite(plan.Arrival))throw new ArgumentException("Invalid directive.");
            original[u.Id]=u.Strength;waypoint[u.Id]=0;
            if(plan.Arrival>0 || plan.Condition is not null){pending.Add(u.Id);u.Withdrawn=true;}
            if(plan.Convoy){u.NonCombatant=true;u.HoldFire=true;}
        }
    }
    public void BeforeTick()
    {
        foreach(var p in Definition.Directives??[])
        {
            var u=battle.Unit(p.UnitId)!;
            if(pending.Contains(u.Id))
            {
                if(battle.Time<p.Arrival || p.Condition is { } condition && Objectives.First(o=>o.Id==condition).Status!="success")continue;
                if(battle.Units.Any(other=>other.Id!=u.Id && other.Active && OrientedRect.Touching(u.Rect,other.Rect,8)) || !battle.Terrain.Environment.Passable(u.Rect,u.Archetype.Category))
                {blocked.TryAdd(u.Id,battle.Time);continue;}
                pending.Remove(u.Id);u.Withdrawn=false;
                battle.Emit("reinforcement",u,null,u.Position,5,0,$"{u.Name} has arrived");
            }
            if(!u.Active || !u.Effective)continue;
            int i=waypoint[u.Id];
            if(i>=p.Waypoints.Length)continue;
            // Player instructions override allied authored movement; mandatory routing also wins.
            if(u.Army==0 && u.PlayerOrder) {waypoint[u.Id]=p.Waypoints.Length;continue;}
            if((u.Army!=0 || !u.PlayerFormationPinned) && p.Formation is { } f && u.Formation!=f && u.TransitionLeft<=0 && battle.Terrain.Environment.Passable(new(u.Position,u.Facing,Formations.Get(f).Width,Formations.Get(f).Depth),u.Archetype.Category))battle.ChangeFormation(u,f);
            if((u.Position-p.Waypoints[i]).Length<8){waypoint[u.Id]=++i;}
            if(i>=p.Waypoints.Length)
            {
                if(p.After=="hold" || p.Convoy){u.Order=new();u.Autonomy=AutonomyMode.Hold;}
                else {u.Order=new();u.PlayerOrder=false;battle.Ai.Release(u);}
                continue;
            }
            u.AiIntention="Authored scenario approach/escort";u.Autonomy=AutonomyMode.Ordered;u.Order=new(OrderKind.Move,p.Waypoints[i],ViaCrossing:p.Crossing);
        }
    }
    bool Collapsed(int army)
    {
        if(pending.Any(id=>battle.Unit(id)!.Army==army))return false;
        double initial=battle.InitialStrength.GetValueOrDefault(army);
        double effective=battle.Units.Where(u=>u.Army==army && u.Effective && !u.NonCombatant).Sum(u=>u.Strength);
        if(effective<initial*battle.Rules.DefeatFraction)
        {battle.DefeatSince.TryAdd(army,battle.Time);return battle.Time-battle.DefeatSince[army]>=battle.Rules.DefeatGraceSeconds;}
        battle.DefeatSince.Remove(army);return false;
    }
    public void AfterTick()
    {
        bool playerCollapsed=Collapsed(0),enemyCollapsed=Collapsed(1);
        foreach(var o in Definition.Objectives)
        {
            var state=Objectives.First(s=>s.Id==o.Id);if(state.Status!="active")continue;
            if(o.Dependencies?.Any(id=>Objectives.First(s=>s.Id==id).Status!="success")==true)continue;
            var near=battle.Combat.Nearby(o.Position,o.Radius+50).Where(u=>u.Effective && u.Strength>=Math.Max(5,u.MaximumStrength*.05) && !u.NonCombatant && !pending.Contains(u.Id) && (u.Position-o.Position).Length<=o.Radius).ToArray();
            bool friendly=near.Any(u=>u.Army==o.Army),enemy=near.Any(u=>u.Army!=o.Army);
            bool uncontested=friendly&&!enemy;
            if(o.Type=="defeat"){if(enemyCollapsed)state.Status="success";}
            else if(o.Type=="capture")
            {if(uncontested)state.Progress+=Rules.Dt;else if(enemy)state.Progress=0;if(state.Progress>=o.Duration){state.Owner=o.Army;state.Status="success";}}
            else if(o.Type=="hold")
            {if(uncontested)state.Progress+=Rules.Dt;else state.Progress=0;if(state.Progress>=o.Duration)state.Status="success";}
            else if(o.Type=="delay")
            {if(enemy&&!friendly)state.Progress+=Rules.Dt;else state.Progress=0;if(state.Progress>=10)state.Status="failure";else if(battle.Time>=o.Duration || enemyCollapsed)state.Status="success";}
            else if(o.Type=="rescue")
            {
                var group=(o.Units??[]).Select(id=>battle.Unit(id)??throw new ArgumentException("Missing rescue regiment")).ToArray();
                int initial=group.Sum(u=>battle.InitialUnitStrength[u.Id]);int safe=group.Where(u=>u.Active && !pending.Contains(u.Id) && (u.Position-o.Position).Length<=o.Radius).Sum(u=>u.Strength);
                if(!enemy && safe>=initial*o.RequiredFraction)state.Status="success";
                else if(group.Sum(u=>u.Strength)<initial*o.RequiredFraction || group.All(u=>u.Withdrawn && !pending.Contains(u.Id)))state.Status="failure";
            }
            else if(o.Type=="convoy")
            {
                var convoy=(o.Units??[]).Select(id=>battle.Unit(id)??throw new ArgumentException("Missing convoy")).ToArray();
                int disabled=convoy.Count(u=>u.Strength<=0 || u.State==MoraleState.Routing);
                if(disabled>=Math.Ceiling(convoy.Length*o.RequiredFraction))state.Status="success";
                else if(convoy.Any(u=>u.Active && (u.Position-o.Position).Length<=o.Radius))state.Status="failure";
            }
        }
        // Failure (including simultaneous collapse) wins ties; optional objectives never block victory.
        if(playerCollapsed || Objectives.Any(s=>s.Status=="failure" && !Definition.Objectives.First(o=>o.Id==s.Id).Optional))battle.FinishMission(1,"Mission failed: position lost, convoy escaped or army collapsed");
        else if(Objectives.Where(s=>!Definition.Objectives.First(o=>o.Id==s.Id).Optional).All(s=>s.Status=="success"))battle.FinishMission(0,"Mission objectives achieved");
        else if(battle.Time>=Definition.Timeout)battle.FinishMission(1,"Mission deadline expired");
    }
}
