namespace Quiberon.Simulation;

public sealed class NavigationState
{
    internal readonly List<(Vec2 Point,string Crossing)> Route=new();
    internal Vec2? Goal;
    internal double ReplanAt;
    internal long QueueTick;
    internal Vec2? BankGoal;
    public string CrossingId { get; internal set; }="";
    public string Status { get; internal set; }="";
    public bool Waiting { get; internal set; }
    public IReadOnlyList<Vec2> Waypoints=>Route.Select(p=>p.Point).ToArray();
}
public readonly record struct EnvironmentalPose(Vec2 Position,double Facing,Formation Formation,bool Compact,double Cohesion);
/// <summary>Distance-only crossing graph and FIFO passage access. No tactical bridge planner.</summary>
public sealed class CrossingNavigation(BattleSimulation battle)
{
    private BattleEnvironment Environment=>battle.Terrain.Environment;
    private readonly Dictionary<string,int> owners=new(StringComparer.Ordinal);
    private readonly Dictionary<(string,int),long> queue=new();
    private readonly Dictionary<int,EnvironmentalPose> safe=new();
    private readonly Dictionary<(int,int),bool> links=new();
    private readonly (Vec2 Point,string Crossing)[] nodes=battle.Terrain.Environment.Crossings.SelectMany(c=>new[]{(c.Entry-c.Direction*46,""),(c.Exit+c.Direction*46,c.Definition.Id)}).ToArray();
    public IReadOnlyDictionary<string,int> Owners=>owners;
    public long Plans { get; private set; }
    public void Begin()
    {
        if(Environment.Rivers.Count==0)return;
        foreach(var u in battle.Units)if(u.Active)safe[u.Id]=Pose(u);
        foreach(var (key,id) in owners.ToArray())
        {
            var u=battle.Unit(id);var c=Environment.Crossings.First(x=>x.Definition.Id==key);
            if(u?.Active!=true || !OrientedRect.Touching(c.Rect,u.Rect,2) && u.Navigation.Route.All(p=>p.Crossing!=key))owners.Remove(key);
        }
        foreach(var key in queue.Keys.ToArray())if(battle.Unit(key.Item2) is not {Active:true} waiter || waiter.Navigation.CrossingId!=key.Item1)queue.Remove(key);
    }
    public EnvironmentalPose Before(Regiment u)=>safe.TryGetValue(u.Id,out var value)?value:Pose(u);
    public static EnvironmentalPose Pose(Regiment u)=>new(u.Position,u.Facing,u.Formation,u.TransitCompact,u.Cohesion);
    public bool Active(Regiment u)=>u.Navigation.Route.Count>0 || u.Navigation.CrossingId!="";
    private static double CompactWidth(Regiment u)=>u.Archetype.Category==UnitCategory.Infantry?Formations.Get(Formation.Column).Width:12;
    private bool Fits(Regiment u,CrossingGeometry c)=>c.Permits(u.Archetype.Category) && CompactWidth(u)+.5<=c.Definition.Width && (u.Archetype.Category!=UnitCategory.Infantry || u.Archetype.Formations.Contains(Formation.Column));
    // A preferred crossing constrains only its own river, allowing other rivers
    // on a multi-river route to retain their ordinary compatible connections.
    private bool Preferred(Regiment u,CrossingGeometry c)=>u.Order.ViaCrossing is null ||
        Environment.Crossings.FirstOrDefault(x=>x.Definition.Id==u.Order.ViaCrossing) is not { } preferred ||
        preferred.Definition.RiverId!=c.Definition.RiverId || preferred.Definition.Id==c.Definition.Id;
    private bool DryLink(Regiment u,Vec2 a,Vec2 b)
    {
        if((a-b).Length<.1)return true;double angle=Vec2.AngleTo(a,b);
        return Environment.Swept(new(a,angle,u.Width,u.Depth),new(b,angle,u.Width,u.Depth),u.Archetype.Category,false);
    }
    private bool StaticLink(int i,int j)
    {
        var key=(Math.Min(i,j),Math.Max(i,j));if(links.TryGetValue(key,out bool clear))return clear;
        var a=nodes[i].Point;var b=nodes[j].Point;double heading=Vec2.AngleTo(a,b);
        clear=Environment.Swept(new(a,heading,90,90),new(b,heading,90,90),UnitCategory.Infantry,false);links[key]=clear;return clear;
    }
    private bool Inside(Vec2 p)=>p.X>=1 && p.Y>=1 && p.X<=battle.Rules.Width-1 && p.Y<=battle.Rules.Height-1;
    private bool Plan(Regiment u,Vec2 goal)
    {
        Plans++;var nav=u.Navigation;nav.Route.Clear();nav.Goal=goal;nav.ReplanAt=battle.Time+3;
        int count=nodes.Length+2,start=count-2,end=count-1;var points=nodes.Select(n=>n.Point).Append(u.Position).Append(goal).ToArray();
        var costs=Enumerable.Repeat(double.PositiveInfinity,count).ToArray();var previous=Enumerable.Repeat(-1,count).ToArray();var via=new string[count];var visited=new bool[count];costs[start]=0;
        for(int pass=0;pass<count;pass++)
        {
            int current=-1;for(int i=0;i<count;i++)if(!visited[i] && (current<0 || costs[i]<costs[current]))current=i;
            if(current<0 || double.IsPositiveInfinity(costs[current]))break;if(current==end)break;visited[current]=true;
            for(int next=0;next<count;next++)
            {
                if(next==current || visited[next] || !Inside(points[next]))continue;
                string crossing="";bool permitted;
                if(current<nodes.Length && next<nodes.Length && current/2==next/2 && current%2!=next%2)
                {
                    var c=Environment.Crossings[current/2];crossing=c.Definition.Id;
                    permitted=Fits(u,c) && Preferred(u,c);
                }
                else if(next==end && Environment.CrossingAt(goal) is { } targetCross && current<nodes.Length && current/2==Environment.Crossings.ToList().IndexOf(targetCross))
                {crossing=targetCross.Definition.Id;permitted=Fits(u,targetCross) && Preferred(u,targetCross);}
                else permitted=current<nodes.Length && next<nodes.Length?StaticLink(current,next):DryLink(u,points[current],points[next]);
                if(!permitted)continue;
                double distance=(points[next]-points[current]).Length;
                double cost=costs[current]+distance*(crossing.Length>0 && Environment.Crossings.First(c=>c.Definition.Id==crossing).Definition.Kind==CrossingKind.Ford?2:1);
                if(cost+1e-8<costs[next]){costs[next]=cost;previous[next]=current;via[next]=crossing;}
            }
        }
        if(previous[end]<0)return false;
        var route=new List<int>();for(int n=end;n!=start;n=previous[n])route.Add(n);route.Reverse();
        foreach(int n in route)nav.Route.Add((points[n],via[n]??""));nav.Status="Route through usable crossing";return true;
    }
    private Vec2 BankEscape(Regiment u)
    {
        var nav=u.Navigation;if(nav.BankGoal is { } goal && (goal-u.Position).Length>4)return goal;
        var away=Environment.ClosestBankAway(u.Position)??new(1,0);var along=new Vec2(-away.Y,away.X);
        Vec2 best=u.Position;double score=double.NegativeInfinity;
        foreach(int sign in new[]{1,-1})
        {
            var p=u.Position+along*(sign*90);p=new(Math.Clamp(p.X,2,battle.Rules.Width-2),Math.Clamp(p.Y,2,battle.Rules.Height-2));
            if(!DryLink(u,u.Position,p))continue;var threat=battle.Unit(u.LastAttackerId??-1);double value=threat is null?-Math.Min(p.Y,battle.Rules.Height-p.Y):(p-threat.Position).Length;
            if(value>score){score=value;best=p;}
        }
        nav.BankGoal=best;u.RoutHeading=(best-u.Position).Normalized;return best;
    }
    public Vec2? Destination(Regiment u,Vec2? requested)
    {
        if(Environment.Rivers.Count==0)return requested;
        var nav=u.Navigation;nav.Waiting=false;
        if(requested is null && nav.CrossingId.Length>0 && owners.GetValueOrDefault(nav.CrossingId,-1)==u.Id && nav.Route.Count>0 && u.CombatState!=CombatState.Melee)
            requested=nav.Goal; // Clear the single-lane surface before stopping.
        if(requested is null)
        {nav.Route.Clear();nav.CrossingId="";nav.Status="";TryRestore(u);return null;}
        var goal=new Vec2(Math.Clamp(requested.Value.X,1,battle.Rules.Width-1),Math.Clamp(requested.Value.Y,1,battle.Rules.Height-1));
        if(nav.Route.Count>0 && nav.Goal is { } old && (old-goal).Length>25 && !Environment.InRiver(u.Position))nav.Route.Clear();
        if(nav.Route.Count==0)
        {
            double angle=Vec2.AngleTo(u.Position,goal);
            if(Environment.Swept(u.Rect,new(goal,angle,u.Width,u.Depth),u.Archetype.Category,false))
            {nav.CrossingId="";nav.Status="";TryRestore(u);return goal;}
            if(nav.Goal is { } last && (last-goal).Length<20 && battle.Time<nav.ReplanAt)
            {nav.Status="No reachable compatible crossing";return u.State==MoraleState.Routing?BankEscape(u):null;}
            if(!Plan(u,goal)){nav.Status="No reachable compatible crossing";return u.State==MoraleState.Routing?BankEscape(u):null;}
        }
        while(nav.Route.Count>0 && (nav.Route[0].Point-u.Position).Length<2.5)
        {
            var reached=nav.Route[0];nav.Route.RemoveAt(0);
            if(reached.Crossing.Length>0){owners.Remove(reached.Crossing);queue.Remove((reached.Crossing,u.Id));nav.CrossingId="";}
        }
        if(nav.Route.Count==0){nav.Goal=null;nav.CrossingId="";TryRestore(u);return goal;}
        var step=nav.Route[0];nav.CrossingId=step.Crossing;
        if(step.Crossing.Length==0){nav.Status="Approaching crossing entry";return step.Point;}
        var crossing=Environment.Crossings.First(c=>c.Definition.Id==step.Crossing);
        if(!Prepare(u,crossing)){nav.Waiting=true;return null;}
        double facing=Vec2.AngleTo(u.Position,step.Point);
        if(Math.Abs(Vec2.AngleDelta(u.Facing,facing))>.06 && !Environment.InRiver(u.Position))
        {nav.Status="Aligning crossing column";MovementSystem.TurnTo(u,facing);return null;}
        if(!queue.ContainsKey((step.Crossing,u.Id)))queue[(step.Crossing,u.Id)]=battle.Tick;
        if(!owners.TryGetValue(step.Crossing,out int owner))
        {
            var first=queue.Where(p=>p.Key.Item1==step.Crossing).OrderBy(p=>p.Value).ThenBy(p=>p.Key.Item2).First();
            if(first.Key.Item2==u.Id)owners[step.Crossing]=owner=u.Id;else owner=first.Key.Item2;
        }
        if(owner!=u.Id && battle.Unit(owner)?.Army==u.Army){nav.Waiting=true;nav.Status=$"Waiting for {owner} to clear {crossing.Definition.Id}";return null;}
        nav.Status=crossing.Definition.Kind==CrossingKind.Ford?"Fording: reduced speed and cohesion":"Crossing: exclusive friendly passage";
        if(u.Archetype.Category==UnitCategory.Cavalry && u.CavalryState==CavalryState.Charging)battle.Cavalry.Cancel(u,"Crossing requires a compact marching formation");
        if(u.InfantryCharging)battle.InfantryCharges.Cancel(u);
        return step.Point;
    }
    private bool Prepare(Regiment u,CrossingGeometry c)
    {
        if(u.TransitionLeft>0){u.Navigation.Status="Forming crossing column";return false;}
        if(u.Width+.5<=c.Definition.Width)return true;
        if(u.Archetype.Category==UnitCategory.Infantry)
        {
            if(u.PlayerFormationPinned && u.Formation!=Formation.Column){u.Navigation.Status="Crossing too narrow: order column formation";return false;}
            if(!u.Archetype.Formations.Contains(Formation.Column)){u.Navigation.Status="Formation cannot use crossing";return false;}
            battle.ChangeFormation(u,Formation.Column);u.Navigation.Status="Reforming into column before crossing";return false;
        }
        u.TransitTarget=true;u.TransitionLeft=4;u.Cohesion=Math.Max(0,u.Cohesion-6);u.Navigation.Status="Forming compact travelling column";return false;
    }
    private void TryRestore(Regiment u)
    {
        if(!u.TransitCompact || u.TransitTarget is not null || u.TransitionLeft>0 || Environment.InRiver(u.Position))return;
        double width=u.Archetype.Category==UnitCategory.Cavalry?40:28,depth=18;
        if(Environment.Passable(new(u.Position,u.Facing,width,depth),u.Archetype.Category,false))
        {u.TransitTarget=false;u.TransitionLeft=4;u.Navigation.Status="Reforming after crossing";}
    }
    public void Constrain(Regiment u,EnvironmentalPose before)
    {
        if(Environment.Rivers.Count==0)return;
        var from=new OrientedRect(before.Position,before.Facing,Width(u,before),Depth(u,before));
        if(Environment.Swept(from,u.Rect,u.Archetype.Category)){safe[u.Id]=Pose(u);return;}
        u.Position=before.Position;u.Facing=before.Facing;u.Formation=before.Formation;u.TransitCompact=before.Compact;u.Cohesion=before.Cohesion;u.Speed=0;u.Velocity=Vec2.Zero;u.ChargeMomentum=0;u.ChargeDistance=0;
        u.Navigation.Status="Bank/bridge edge blocks footprint; backing for clearance";
        // A bounded backwards/sideways clearance step avoids turn-in-place locks
        // at a bank. It is a real swept displacement, never a teleport.
        if(Environment.ClosestBankAway(u.Position) is { } away)
        {
            var p=u.Position+away*(u.Archetype.Speed*.35*Rules.Dt);var rect=new OrientedRect(p,u.Facing,u.Width,u.Depth);
            if(Inside(p) && Environment.Swept(u.Rect,rect,u.Archetype.Category,false))
            {u.Velocity=(p-u.Position)/Rules.Dt;u.Position=p;u.Speed=u.Velocity.Value.Length;}
        }
        safe[u.Id]=Pose(u);
    }
    private static double Width(Regiment u,EnvironmentalPose p)=>p.Compact?12:u.Archetype.Category==UnitCategory.Infantry?Formations.Get(p.Formation).Width:u.Archetype.Category==UnitCategory.Cavalry?40:28;
    private static double Depth(Regiment u,EnvironmentalPose p)=>p.Compact?(u.Archetype.Category==UnitCategory.Cavalry?60:42):u.Archetype.Category==UnitCategory.Infantry?Formations.Get(p.Formation).Depth:18;
    public void FinalGuard()
    {
        if(Environment.Rivers.Count==0)return;
        foreach(var u in battle.Units)if(u.Active && safe.TryGetValue(u.Id,out var pose))Constrain(u,pose);
    }
}
