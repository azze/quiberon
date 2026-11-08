namespace Quiberon.Simulation;

/// <summary>A shared purpose, independent of immediate combat orders. Optional mission JSON data.</summary>
public sealed record TacticalAssignmentDefinition(string Id,int Army,string Kind,Vec2 Position,double Radius=100,int[]? Units=null,string? ObjectiveId=null);
public readonly record struct LocalSupport(double Friendly,double Hostile);

public sealed partial class TacticalAi
{
    private readonly SortedDictionary<string,TacticalAssignmentDefinition> assignments=new(StringComparer.Ordinal);
    public IReadOnlyCollection<TacticalAssignmentDefinition> Assignments=>assignments.Values;
    public void Assign(TacticalAssignmentDefinition assignment)
    {
        if(string.IsNullOrWhiteSpace(assignment.Id) || assignment.Kind is not ("attack" or "defend" or "support" or "reserve") || !assignment.Position.Finite || !double.IsFinite(assignment.Radius) || assignment.Radius<20 || assignment.Radius>1000 || assignment.Position.X<0 || assignment.Position.Y<0 || assignment.Position.X>battle.Rules.Width || assignment.Position.Y>battle.Rules.Height || !battle.Units.Any(u=>u.Army==assignment.Army) || assignment.Units is {Length:0} || assignment.Units?.Any(id=>battle.Unit(id)?.Army!=assignment.Army)==true)
            throw new ArgumentException("Invalid tactical assignment");
        assignments[assignment.Id]=assignment with{Units=assignment.Units?.ToArray()};
    }
    public bool RemoveAssignment(string id)=>assignments.Remove(id);
    private TacticalAssignmentDefinition? Assignment(Regiment u)
    {
        bool Live(TacticalAssignmentDefinition a)=>a.ObjectiveId is null || battle.Mission?.Objectives.Any(o=>o.Id==a.ObjectiveId && o.Status=="active")==true;
        TacticalAssignmentDefinition? best=null;double distance=double.PositiveInfinity;
        foreach(var a in assignments.Values)
        {
            if(a.Army!=u.Army || a.Units is not null && !a.Units.Contains(u.Id) || !Live(a))continue;
            double score=(a.Position-Anchors[u.Id]).LengthSquared;
            // Explicit group membership takes precedence over army-wide defaults.
            if(a.Units is not null)score-=1e9;
            if(score<distance){best=a;distance=score;}
        }
        if(best is not null)return best;
        // Missions supply intent, not hidden enemy intelligence. Existing authored routes still execute first.
        if(battle.Mission is not { } mission)return null;
        foreach(var o in mission.Definition.Objectives)
        {
            if(o.Optional || mission.Objectives.First(s=>s.Id==o.Id).Status!="active" || o.Type is not ("capture" or "hold" or "delay" or "rescue" or "convoy"))continue;
            Vec2 position=o.Position;
            string kind=o.Type is "delay" or "hold"?(u.Army==o.Army?"defend":"attack"):(u.Army==o.Army?"attack":"defend");
            if(o.Type is "rescue" or "convoy")
            {
                Vec2 sum=Vec2.Zero;int count=0;
                foreach(int id in o.Units??[])
                {
                    var unit=battle.Unit(id);
                    if(unit is not {Active:true} || !mission.Arrived(id) || unit.Army!=u.Army && !battle.Perceives(u,unit))continue;
                    sum+=unit.Position;count++;
                }
                if(count==0)continue;position=sum/count;
                kind=o.Type=="rescue"?(u.Army==o.Army?"support":"attack"):(u.Army==o.Army?"attack":"support");
            }
            double score=(position-Anchors[u.Id]).LengthSquared;if(score>=distance)continue;
            best=new($"objective-{o.Id}-{u.Army}",u.Army,kind,position,o.Radius,ObjectiveId:o.Id);distance=score;
        }
        return best;
    }
    private void RefreshAssignment(Regiment u)
    {
        var a=Assignment(u);u.AiAssignment=a is null?"":$"{a.Kind} {a.Id}";
    }
    private Vec2 AssignmentSlot(Regiment u,TacticalAssignmentDefinition a)
    {
        // Preserve lateral spacing from deployment rather than pile every regiment onto the marker.
        var first=battle.Units.First(f=>f.Army==u.Army && (a.Units is null || a.Units.Contains(f.Id)));
        var offset=Anchors[u.Id]-Anchors[first.Id];
        double spread=Math.Max(1,offset.Length/Math.Max(10,a.Radius*.65));
        return Clamp(u,a.Position+offset/spread);
    }
    private Vec2 DefensiveAnchor(Regiment u)=>Assignment(u) is { } a?AssignmentSlot(u,a):Anchors[u.Id];
    private bool ExecuteAssignment(Regiment u,Regiment[] enemies)
    {
        var a=Assignment(u);if(a is null)return false;
        var slot=AssignmentSlot(u,a);double range=u.Archetype.Weapon?.Range??100;
        bool urgent=enemies.Any(e=>(e.Position-u.Position).Length<80);
        bool relevant=enemies.Any(e=>(e.Position-a.Position).Length<=a.Radius+range);
        bool outside=(u.Position-a.Position).Length>a.Radius+range*.5;
        if(!urgent && (outside && a.Kind!="attack" || !relevant && a.Kind=="attack" || enemies.Length==0))
        {Note(u,$"Move to shared {a.Kind} position",(slot-u.Position).Length>8?new(OrderKind.Move,slot):new());return true;}
        if(a.Kind=="reserve" && !urgent)
        {Note(u,"Maintain assigned reserve",(slot-u.Position).Length>8?new(OrderKind.Move,slot):new(OrderKind.Reserve));return true;}
        if(a.Kind is "defend" or "support" && !outside && !urgent && !relevant)
        {Note(u,"Maintain assigned defensive area",new());return true;}
        return false;
    }

    // Support is a decision estimate, never a combat modifier. Spatial broad phase, exact radius,
    // and observer perception prevent hidden or distant regiments from affecting the assessment.
    private double SupportPower(Regiment other,Vec2 contact)
    {
        double morale=other.State switch{MoraleState.Shaken=>.7,MoraleState.Wavering=>.4,MoraleState.Routing=>.08,MoraleState.Rallying=>.15,_=>1};
        double readiness=other.TransitionLeft>0?.45:1;
        double facing=Math.Abs(Vec2.AngleDelta(other.Facing,Vec2.AngleTo(other.Position,contact)));
        double alignment=facing>Math.PI*.65?.45:1;
        double weapon=other.Archetype.Category==UnitCategory.Artillery?(other.Limbered?.15:1.3):1;
        return other.Strength*other.Archetype.Melee*(.3+other.Cohesion/100)*morale*readiness*alignment*weapon*ForestPower(other,battle.Combat.ForestCover(other));
    }
    public LocalSupport AssessSupport(Regiment u,Regiment target)
    {
        double friendly=0,hostile=0;
        for(int side=0;side<2;side++)
        {
            bool allied=side==0;var centre=allied?u.Position:target.Position;
            foreach(var other in battle.Combat.Nearby(centre,180))
            {
                if(!other.Effective || other.NonCombatant || other.Id==u.Id || other.Id==target.Id || (other.Army==u.Army)!=allied)continue;
                double distance=(other.Position-centre).Length;
                if(distance>=180 || !allied && !battle.Perceives(u,other))continue;
                double contribution=SupportPower(other,allied?target.Position:u.Position)*.65*(1-distance/180);
                if(allied)friendly+=contribution;else hostile+=contribution;
            }
        }
        return new(friendly,hostile);
    }
    public double AssessEngagement(Regiment u,Regiment target)
    {var s=AssessSupport(u,target);return (SupportPower(target,u.Position)+s.Hostile)/Math.Max(1,SupportPower(u,target.Position)+s.Friendly);}

    private Regiment SupportedTarget(Regiment u,Regiment[] enemies)
    {
        if(u.Archetype.Category!=UnitCategory.Infantry || CommanderSystem.Is(u,"opportunistic") || enemies.Length<2)return enemies[0];
        var a=Assignment(u);
        double Score(Regiment e)=>(e.Position-u.Position).Length*.12+30*Math.Clamp(AssessEngagement(u,e)-1,0,3)
            +(a is null?0:Math.Max(0,(e.Position-a.Position).Length-a.Radius)*.15);
        var current=enemies.FirstOrDefault(e=>e.Id==u.AiTarget);
        if(current is not null && battle.Time<u.AiTargetUntil)return current;
        var best=enemies[0];double score=Score(best);
        foreach(var e in enemies.Skip(1)){double next=Score(e);if(next<score){best=e;score=next;}}
        if(current is not null && score>Score(current)-15)return current;
        if(best.Id!=u.AiTarget)u.AiTargetUntil=battle.Time+10;
        return best;
    }

    private bool ValidFiringPosition(Regiment u,Vec2 p,Regiment target)
    {
        double facing=Vec2.AngleTo(p,target.Position);
        var formation=Formations.Get(u.Archetype.Skirmisher?Formation.Skirmish:Formation.Line);
        var rect=new OrientedRect(p,facing,Math.Max(u.Width,formation.Width),Math.Max(u.Depth,formation.Depth));
        if(p.X<rect.Radius || p.Y<rect.Radius || p.X>battle.Rules.Width-rect.Radius || p.Y>battle.Rules.Height-rect.Radius || !battle.Terrain.Environment.Swept(u.Rect,rect,u.Archetype.Category,false))return false;
        foreach(var other in battle.Combat.Nearby(p,rect.Radius+80))
            if(other.Active && other.Id!=u.Id && (other.Army==u.Army || battle.Perceives(u,other)) && OrientedRect.Touching(rect,other.Rect,4))return false;
        return true;
    }
    private double FiringScore(Regiment u,Regiment target,Vec2 p,double desired)
    {
        battle.Metrics.AiPositionEvaluations++;
        double range=u.Archetype.Weapon!.Range,distance=(p-target.Position).Length;
        var sight=battle.Combat.SightFrom(u,target,p);
        double score=(sight.Visible?40*sight.Transmission:-65)-Math.Abs(distance-desired)*.22;
        if(distance>range)score-=35;
        if(battle.Combat.FiringBlocker(u,target,p) is not null)score-=65;
        score+=battle.Terrain.ForestDensity(p)*(u.Archetype.Skirmisher?15:4);
        score+=Math.Clamp(battle.Terrain.Elevation(p)-battle.Terrain.Elevation(target.Position),-5,5);
        score-=(p-u.Position).Length*.16;
        foreach(var other in battle.Combat.Nearby(p,150))
        {
            if(other.Id==u.Id || !other.Effective || other.NonCombatant)continue;
            double d=(other.Position-p).Length;if(d>150)continue;
            if(other.Army==u.Army)score+=4*(1-d/150);
            else if(other.Id!=target.Id && battle.Perceives(u,other))score-=12*(1-d/150);
        }
        var a=Assignment(u);
        if(a is not null && a.Kind!="attack" && (p-a.Position).Length>a.Radius+range*.5)return double.NegativeInfinity;
        return score;
    }
    private bool TryFiringPosition(Regiment u,Regiment target,string strategy)
    {
        if(u.Archetype.Category!=UnitCategory.Infantry || u.Archetype.MeleeOnly || u.Archetype.Weapon is null || u.CombatState==CombatState.Melee || u.Navigation.Route.Count>0 || u.TransitionLeft>0 || u.SkirmishRetreat || u.Archetype.Skirmisher && (target.Position-u.Position).Length<100)return false;
        double range=u.Archetype.Weapon.Range,distance=(target.Position-u.Position).Length;
        if(distance<Math.Min(75,range*.45) || distance>range*1.8)return false;
        if(u.AiFiringPosition is { } goal && battle.Time<u.AiFiringCommitUntil)
        {
            if((goal-u.Position).Length>6 && ValidFiringPosition(u,goal,target))
            {Note(u,u.AiPositionReason,new(OrderKind.Move,goal,Facing:Vec2.AngleTo(goal,target.Position)));return true;}
            u.AiFiringPosition=null;
        }
        if(battle.Time<u.AiFiringEvaluateAt)return MaintainFiringPosition(u,target,strategy);
        u.AiFiringEvaluateAt=battle.Time+8;
        double desired=range*(u.Archetype.Role=="rifles"?.82:CommanderSystem.Policy(u).FiringDistance);
        double current=FiringScore(u,target,u.Position,desired),best=current;Vec2 chosen=u.Position;
        if(!double.IsFinite(current))return false;
        var forward=(target.Position-u.Position).Normalized;var side=new Vec2(-forward.Y,forward.X);
        // Bounded local search: lateral clearance, range adjustments, and nearby slope/cover.
        foreach(var offset in new[]{side*35,side*(-35),side*65,side*(-65),forward*35,forward*(-35),(side+forward)*35,(forward-side)*35})
        {
            var p=Clamp(u,u.Position+offset);if(!ValidFiringPosition(u,p,target))continue;
            double score=FiringScore(u,target,p,desired);
            if(distance<=range && battle.Combat.Sight(u,target).Visible && battle.Combat.FiringBlocker(u,target)is null)
                score-=Math.Min(18,(p-u.Position).Length/Math.Max(.5,u.Archetype.Speed)*.65);
            score-=Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,p)))*1.5;
            if(score>best){best=score;chosen=p;}
        }
        if(best>current+14)
        {
            u.AiFiringPosition=chosen;u.AiFiringCommitUntil=battle.Time+18;u.AiFiringEvaluateAt=battle.Time+24;
            u.AiPositionReason=$"Firing position: clear lane/range/cover improves score by {best-current:F0}";
            Note(u,u.AiPositionReason,new(OrderKind.Move,chosen,Facing:Vec2.AngleTo(chosen,target.Position)));return true;
        }
        return MaintainFiringPosition(u,target,strategy);
    }
    private bool MaintainFiringPosition(Regiment u,Regiment target,string strategy)
    {
        if((target.Position-u.Position).Length<=u.Archetype.Weapon!.Range && battle.Combat.Sight(u,target).Visible && battle.Combat.FiringBlocker(u,target)is null && strategy!="all_out_attack")
        {ChooseFormation(u,u.Archetype.Skirmisher?Formation.Skirmish:Formation.Line);Note(u,"Hold useful firing position: visible target and clear lane",new(u.Archetype.Skirmisher?OrderKind.Skirmish:OrderKind.FireAt,TargetId:target.Id));return true;}
        return false;
    }
}
