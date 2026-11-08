using System.Diagnostics;
namespace Quiberon.Simulation;

/// <summary>Python army_plan/commander_ai/skirmish_destination, no scene-tree input.</summary>
public sealed partial class TacticalAi(BattleSimulation battle)
{
    public SortedDictionary<int,string> Armies { get; }=new();
    public Dictionary<int,Vec2> Anchors { get; }=battle.Units.ToDictionary(u=>u.Id,u=>u.Position);
    public static readonly string[] Strategies=["balanced","all_out_attack","hold_the_line","skirmish"];
    public bool Autonomous(Regiment u)=>battle.Rules.AiEnabled && u.Autonomy==AutonomyMode.Autonomous && !u.PlayerOrder && Armies.ContainsKey(u.Army);
    public static bool Vulnerable(Regiment u)=>u.State is MoraleState.Wavering or MoraleState.Routing || u.Cohesion<40;
    private Vec2 Clamp(Regiment u,Vec2 point){double r=u.Rect.Radius+1;return new(Math.Clamp(point.X,r,battle.Rules.Width-r),Math.Clamp(point.Y,r,battle.Rules.Height-r));}
    public void ConfigureArmy(int army,string? strategy)
    {
        Director.Invalidate(army);
        if(strategy is null){Armies.Remove(army);foreach(var u in battle.Units.Where(u=>u.Army==army && !u.PlayerOrder))u.Autonomy=AutonomyMode.Ordered;return;}
        if(!Strategies.Contains(strategy))throw new ArgumentException("Unknown army strategy");Armies[army]=strategy;
        foreach(var u in battle.Units.Where(u=>u.Army==army && !u.PlayerOrder))u.Autonomy=AutonomyMode.Autonomous;
    }
    public void Release(Regiment u)
    {u.PlayerOrder=false;u.PlayerFormationPinned=false;u.Autonomy=AutonomyMode.Autonomous;u.AiNextDecision=0;if(!Armies.ContainsKey(u.Army))Armies[u.Army]="balanced";}
    public void Update()
    {
        if(!battle.Rules.AiEnabled)return;
        foreach(var u in battle.Units)
        {
            if(u.CombatState==CombatState.Melee)u.AiMeleeSince??=battle.Time;else u.AiMeleeSince=null;
            if(!u.Effective)continue;
            if(u.PlayerOrder && u.Order.Kind is OrderKind.Attack or OrderKind.Charge or OrderKind.Pursue && battle.Unit(u.Order.TargetId??-1)?.Active!=true)
            {u.PlayerOrder=false;if(Armies.ContainsKey(u.Army))u.Autonomy=AutonomyMode.Autonomous;}
            if(!Autonomous(u))continue;
            var target=battle.Unit(u.AiTarget??-1);
            bool invalid=u.AiTarget is not null && (target?.Active!=true || target.State==MoraleState.Routing && u.AiObservedState!=MoraleState.Routing);
            if(battle.Time+1e-8<u.AiNextDecision && !invalid)continue;
            Plan(u,Armies[u.Army]);u.AiObservedState=battle.Unit(u.AiTarget??-1)?.State??MoraleState.Steady;
            // First plan is immediate for both armies; subsequent phases spread work.
            int phase=(u.Id*7)%battle.Rules.AiDecisionTicks;
            int next=battle.Tick+1;next+=(phase-next%battle.Rules.AiDecisionTicks+battle.Rules.AiDecisionTicks)%battle.Rules.AiDecisionTicks;
            u.AiNextDecision=next*Rules.Dt;
        }
    }
    private void Note(Regiment u,string text,Order order)
    {
        bool changed=u.Order!=order;u.Order=order;
        if(changed){battle.Metrics.AiOrders++;if(u.AiIntention!=text)battle.Emit("ai_decision",u,battle.Unit(order.TargetId??u.AiTarget??-1),u.Position,2,0,$"{u.Commander.DisplayName}: {text}");}
        u.AiIntention=(u.AiArmyRole.Length>0?$"{u.AiArmyRole}: ":"")+(u.AiAssignment.Length>0?$"{u.AiAssignment}: ":"")+text;
    }
    public void Retreat(Regiment u,Regiment enemy,string why)
    {
        var away=(u.Position-enemy.Position).Normalized;if(away.Length<.1)away=new(u.Army==0?-1:1,0);
        u.AiRetreatGoal=Clamp(u,u.Position+away*40);u.AiRetreatUntil=battle.Time+10;u.AiNextRetreat=battle.Time+40;
        Note(u,why,new(OrderKind.Move,u.AiRetreatGoal));
    }
    public bool Preparation(Regiment u,Regiment nearest)
    {
        if(battle.Time<u.AiRetreatUntil){Note(u,"Committed local disengagement",new(OrderKind.Move,u.AiRetreatGoal));return true;}
        if(CommanderSystem.Is(u,"methodical") && u.Cohesion<55 && u.CombatState!=CombatState.Melee)
        {if(battle.Time>=u.AiNextReform){u.AiReformUntil=battle.Time+8;u.AiNextReform=battle.Time+28;}if(battle.Time<u.AiReformUntil){Note(u,"Methodical preparation: cohesion below 55 (bounded 8 s)",new());return true;}}
        var policy=CommanderSystem.Policy(u);double own=u.Strength*u.Archetype.Melee*(.3+u.Cohesion/100),hostile=nearest.Strength*nearest.Archetype.Melee*(.3+nearest.Cohesion/100);
        if(battle.Terrain.Forests.Count>0){double cover=battle.Combat.ForestCover(u),other=battle.Combat.ForestCover(nearest);own*=ForestPower(u,cover);hostile*=ForestPower(nearest,other);}
        var support=AssessSupport(u,nearest);own+=support.Friendly;hostile+=support.Hostile;
        u.AiFriendlySupport=support.Friendly;u.AiEnemySupport=support.Hostile;u.AiThreatRatio=hostile/Math.Max(.1,own);
        bool melee=u.AiMeleeSince is { } since && battle.Time-since>=policy.DisengageSeconds,threatened=CommanderSystem.Is(u,"cautious") && (nearest.Position-u.Position).Length<90;
        if(u.Archetype.Category!=UnitCategory.Artillery && !Vulnerable(nearest) && battle.Time>=u.AiNextRetreat && (melee||threatened) && hostile>own*policy.Overmatch)
        {Retreat(u,nearest,$"Preserving regiment: threat ratio {u.AiThreatRatio:F2} exceeds {policy.Overmatch:F2}");return true;}
        return false;
    }
    private static double ForestPower(Regiment u,double cover)=>Math.Max(.2,1-.45*cover*(u.Formation==Formation.Skirmish?.25:u.Formation==Formation.Column?.6:1))*(1+(u.Archetype.ForestMeleeDamage-1)*SpecialistSystem.WoodlandSkill(cover))*u.Archetype.MeleeDamage;
    public double OpportunityScore(Regiment u,Regiment e)=>(e.Position-u.Position).Length*.12+e.Cohesion*.4-(Vulnerable(e)?80:0)-(Math.Abs(Vec2.AngleDelta(e.Facing,Vec2.AngleTo(e.Position,u.Position)))>1.5?20:0);
    public Regiment SelectOpportunity(Regiment u,Regiment[] enemies,Regiment nearest)
    {
        if(!CommanderSystem.Is(u,"opportunistic"))return nearest;
        var current=enemies.FirstOrDefault(e=>e.Id==u.AiTarget);
        if(current is not null && battle.Time<u.AiTargetUntil)return current;
        var best=enemies.OrderBy(e=>OpportunityScore(u,e)).ThenBy(e=>e.Id).First();
        if(current is not null && OpportunityScore(u,best)>OpportunityScore(u,current)-15)best=current;
        if(best.Id!=u.AiTarget){u.AiTargetUntil=battle.Time+10;if(u.Archetype.Category==UnitCategory.Cavalry){u.CavalryTargetId=best.Id;u.AiWaypoint=null;u.Order=new(OrderKind.Attack,TargetId:best.Id);}}u.AiTargetScore=OpportunityScore(u,best);return best;
    }
    public double CavalryScore(Regiment u,Regiment e)=>e.Cohesion+(e.Position-u.Position).Length*.12+(e.Archetype.Category==UnitCategory.Infantry?60:-40)+50*CavalrySystem.Readiness(u,e)-(e.State is MoraleState.Wavering or MoraleState.Routing?90:0);
    public void Plan(Regiment u,string strategy)
    {
        long started=Stopwatch.GetTimestamp();battle.Metrics.AiDecisions++;u.Decisions++;
        try
        {
            if(!u.Effective || !Autonomous(u) || u.InfantryCharging)return;
            if(u.Archetype.Category==UnitCategory.Cavalry && u.CavalryState is CavalryState.Charging or CavalryState.Pursuit or CavalryState.Recoil or CavalryState.Reforming)return;
            var armyPlan=Director.Get(u.Army,strategy);DescribeRole(u,armyPlan);
            RefreshAssignment(u);
            var enemies=Detected(u,strategy);
            if(MountedDecision(u,enemies,strategy,armyPlan))return;
            if(ExecuteAssignment(u,enemies))return;
            if(enemies.Length==0){if(strategy=="hold_the_line")Note(u,"Defend anchor; no detected enemy",(u.Position-DefensiveAnchor(u)).Length>8?new(OrderKind.Move,DefensiveAnchor(u)):new());else {u.AiTarget=null;var goal=u.LastSeenTargetPosition??new Vec2(battle.Rules.Width*.5,u.Position.Y);Note(u,"No detected enemy: advance to last contact / army centre",(goal-u.Position).Length>8?new(OrderKind.Move,goal):new());}u.AiTarget=null;return;}
            var nearest=SupportedTarget(u,enemies);if(Preparation(u,nearest))return;nearest=SelectOpportunity(u,enemies,nearest);
            if(u.Archetype.Category!=UnitCategory.Cavalry || strategy=="hold_the_line")RecordTarget(u,nearest);
            if(strategy=="hold_the_line" && u.Archetype.Category!=UnitCategory.Artillery)
            {Note(u,"Hold deployment anchor",(u.Position-DefensiveAnchor(u)).Length>8?new(OrderKind.Move,DefensiveAnchor(u)):u.Archetype.Category==UnitCategory.Cavalry && (nearest.Position-u.Position).Length<120 && Vulnerable(nearest)?new(OrderKind.Attack,TargetId:nearest.Id):new());return;}
            if(u.Archetype.Category==UnitCategory.Artillery){Battery(u,nearest);return;}
            if(u.Archetype.Skirmisher && strategy!="all_out_attack")
            {if(TryFiringPosition(u,nearest,strategy))return;SelectCover(u,nearest);Note(u,"Skirmish at effective range",new(OrderKind.Skirmish,nearest.Position,TargetId:nearest.Id));ChooseFormation(u,Formation.Skirmish);return;}
            if(u.Archetype.MeleeOnly)
            {
                bool rush=u.Cohesion>=35 && (nearest.Position-u.Position).Length<110;
                Note(u,rush?"Close assault: melee-only formation exploits contact":"Close assault: advance using cover; no firearm",new(rush?OrderKind.Charge:OrderKind.Attack,TargetId:nearest.Id));
                ChooseFormation(u,(nearest.Position-u.Position).Length>180?Formation.Column:Formation.Line);return;
            }
            if(TryFiringPosition(u,nearest,strategy))return;
            if(u.Archetype.Role=="militia" && (nearest.Position-u.Position).Length<=(u.Archetype.Weapon?.Range??0)*.9 && !Vulnerable(nearest))
            {ChooseFormation(u,Formation.Line);Note(u,"Citizen defence: hold cohesive firing line",new(OrderKind.Defend,u.Position));return;}
            if(u.Archetype.Category==UnitCategory.Cavalry)
            {
                var current=enemies.FirstOrDefault(e=>e.Id==u.Order.TargetId)??enemies.FirstOrDefault(e=>e.Id==u.CavalryTargetId)??enemies.FirstOrDefault(e=>e.Id==u.AiTarget);
                var exposed=current??enemies.OrderBy(e=>CavalryScore(u,e)).ThenBy(e=>e.Id).First();
                RecordTarget(u,exposed);u.CavalryTargetId=exposed.Id;u.AiTargetScore=CavalryScore(u,exposed);
                if(u.AiCommitAt==0)u.AiCommitAt=battle.Time+18*CommanderSystem.Policy(u).Commitment;
                bool prepared=CavalrySystem.Readiness(u,exposed)>.5;
                bool light=u.Archetype.Role=="light_cavalry";
                bool ready=(!light && strategy=="all_out_attack") || Vulnerable(exposed) || !prepared && (exposed.Position-u.Position).Length<150 || battle.Time>=u.AiCommitAt && !prepared;
                if(light && (prepared || exposed.Archetype.Category==UnitCategory.Cavalry && exposed.Archetype.Melee>u.Archetype.Melee*1.5 && !Vulnerable(exposed)))ready=false;
                if(ready && exposed.State!=MoraleState.Routing && strategy!="all_out_attack" && AssessEngagement(u,exposed)>CommanderSystem.Policy(u).Overmatch*1.25)ready=false;
                if(ready){Note(u,"Charge opportunity: vulnerability/readiness and commitment evaluated",new(OrderKind.Attack,TargetId:exposed.Id));return;}
                if(u.AiWaypoint is null){double sign=u.Position.Y<battle.Rules.Height/2?-1:1;u.AiWaypoint=Clamp(u,exposed.Position+new Vec2(u.Army==0?-100:100,sign*100));}
                if((u.Position-u.AiWaypoint.Value).Length<15){Note(u,"Cavalry reserve: prepared front; wait for disruption",new());if(battle.Time>=u.AiCommitAt+20){u.AiWaypoint=null;u.AiCommitAt=battle.Time+10;}}
                else Note(u,"Bounded flank approach; avoid prepared frontal charge",new(OrderKind.Move,u.AiWaypoint));return;
            }
            if(InfantryReserve(u,armyPlan,nearest))return;
            if(strategy=="skirmish"){Note(u,"Army skirmish objective",new(OrderKind.Skirmish,nearest.Position,TargetId:nearest.Id));return;}
            if(u.Archetype.Role=="assault" && u.Cohesion>=50 && u.AiThreatRatio<CommanderSystem.Policy(u).Overmatch && (nearest.Position-u.Position).Length<95 && (Vulnerable(nearest) || (nearest.Position-u.Position).Length<45 && u.Strength*u.Archetype.Melee>nearest.Strength*1.15))
            {Note(u,"Assault infantry: exploit local close-combat advantage",new(OrderKind.Charge,TargetId:nearest.Id));ChooseFormation(u,Formation.Line);return;}
            if((CommanderSystem.Is(u,"aggressive") || CommanderSystem.Is(u,"opportunistic")) && Vulnerable(nearest) && (nearest.Position-u.Position).Length<60 && u.Cohesion>=50){Note(u,"Bayonet assault: exposed enemy within 60 m",new(OrderKind.Charge,TargetId:nearest.Id));return;}
            bool holding=(CommanderSystem.Is(u,"stalwart") || CommanderSystem.Has(u,"defensive_tactician") || UpgradeSystem.Has(u,"steadfast_defence")) && (nearest.Position-u.Position).Length<(u.Archetype.Weapon?.Range??0)*.85;
            Note(u,holding?"Defensive commander: retain firing position":strategy=="all_out_attack"?"All-out attack: commit centre":"Advance to firing line",holding?new():strategy=="all_out_attack"?new(OrderKind.Attack,TargetId:nearest.Id):new(OrderKind.Advance,nearest.Position,TargetId:CommanderSystem.Is(u,"opportunistic")?nearest.Id:null));
            double distance=(nearest.Position-u.Position).Length,range=u.Archetype.Weapon?.Range??155;
            if(distance<range*1.15)ChooseFormation(u,Formation.Line);else if(distance>range*1.8)ChooseFormation(u,Formation.Column);
        }
        finally{battle.Metrics.AiMilliseconds+=Stopwatch.GetElapsedTime(started).TotalMilliseconds;}
    }
    private Regiment[] Detected(Regiment u,string strategy)
    {
        bool Eligible(Regiment e)=>e.Active && e.Army!=u.Army && (u.Archetype.Category==UnitCategory.Cavalry || e.Effective) && !(e.Id==u.AiAvoidTarget && battle.Time<u.AiAvoidUntil);
        bool Seen(Regiment e){battle.Metrics.AiTargetEvaluations++;return battle.Perceives(u,e);}
        // Light horse and pursuit specialists may abandon an intact prepared front
        // for a nearby rout. Charge/recoil commitment and player orders are checked
        // before this query; a valid pursuit target remains locked by ordinary AI.
        if(u.Archetype.Category==UnitCategory.Cavalry && (u.Archetype.Role=="light_cavalry" || HistoricalCommanders.Has(u,"relentless_pursuit_signature")) &&
            battle.Unit(u.AiTarget??-1)?.State!=MoraleState.Routing)
        {
            var routedOpportunity=battle.Combat.Nearby(u.Position,220).Where(e=>Eligible(e) && e.State==MoraleState.Routing && (e.Position-u.Position).Length<=220)
                .OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).FirstOrDefault(Seen);
            if(routedOpportunity is not null)return [routedOpportunity];
        }
        bool opportunity=CommanderSystem.Is(u,"opportunistic"),cavalry=u.Archetype.Category==UnitCategory.Cavalry;
        Regiment? current=null;
        var ids=opportunity?new[]{u.AiTarget}:cavalry?new[]{u.Order.TargetId,u.CavalryTargetId,u.AiTarget}:u.Archetype.Category==UnitCategory.Infantry?new[]{u.AiTarget}:Array.Empty<int?>();
        foreach(var id in ids.Distinct())if(battle.Unit(id??-1)is { } candidate && Eligible(candidate) && Seen(candidate)){current=candidate;break;}
        bool currentSeen=current is not null;
        bool locked=currentSeen && (opportunity?battle.Time<u.AiTargetUntil:cavalry);
        bool scoring=!locked && (opportunity || cavalry && strategy!="hold_the_line");
        double Score(Regiment e)=>opportunity?OpportunityScore(u,e):CavalryScore(u,e);
        double best=currentSeen?Score(current!):double.PositiveInfinity;
        var found=new List<Regiment>();
        foreach(var e in battle.Units.Where(Eligible).OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id))
        {
            // Cohesion/readiness are nonnegative; maximum vulnerability/flank
            // bonuses bound any farther score. Strict > preserves score ties.
            if(scoring && found.Count>0 && (e.Position-u.Position).Length*.12-(opportunity?100:130)>best)break;
            bool visible=e.Id==current?.Id?currentSeen:Seen(e);
            if(!visible)continue;
            found.Add(e);if(scoring)best=Math.Min(best,Score(e));else if(u.Archetype.Category!=UnitCategory.Infantry || found.Count>=3 || (e.Position-u.Position).Length>350)break;
        }
        if(currentSeen && !found.Any(e=>e.Id==current!.Id))found.Add(current!);
        return found.OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).ToArray();
    }
    private void RecordTarget(Regiment u,Regiment target){if(u.AiTarget!=target.Id){u.TargetChanges++;battle.Metrics.AiTargetChanges++;}u.AiTarget=target.Id;}
    private void ChooseFormation(Regiment u,Formation f)
    {if(u.Navigation.Route.Count==0 && !u.PlayerFormationPinned && u.TransitionLeft<=0 && u.Formation!=f && u.Archetype.Formations.Contains(f) && battle.Time>=u.AiFormationUntil){battle.ChangeFormation(u,f);u.AiFormationUntil=battle.Time+20;}}
    private void Battery(Regiment u,Regiment target)
    {
        if(u.Order.Kind==OrderKind.Move && u.Order.Destination is { } d && battle.Time<u.AiPositionUntil && (u.Position-d).Length>15)return;
        if(u.Limbered || battle.Time<u.AiPositionUntil)return;
        bool blocked=battle.Combat.Sight(u,target).Reason=="ridge";
        bool unsafeShot=UnsafeShot(u,target);
        if(blocked || unsafeShot)
        {
            var options=new List<(double Score,double X,double Y,Vec2 P)>();
            foreach(var offset in new[]{new Vec2(60,0),new(-60,0),new(0,60),new(0,-60),new(40,40),new(40,-40),new(-40,40),new(-40,-40)})
            {
                var point=Clamp(u,u.Position+offset);var box=new OrientedRect(point,u.Facing,u.Width,u.Depth);
                if(battle.Units.Any(e=>e.Active && e.Id!=u.Id && OrientedRect.Separation(box,e.Rect)is not null))continue;
                if(battle.Visibility.Query(point,target.Position).Visible && !UnsafeShot(u,target,point))options.Add((battle.Terrain.ForestDensity(point)*3+battle.Terrain.Gradient(point).Length,offset.X,offset.Y,point));
            }
            if(options.Count>0){var p=options.OrderBy(o=>o.Score).ThenBy(o=>o.X).ThenBy(o=>o.Y).First().P;Note(u,"Battery relocation: clear ridge/friendly firing corridor",new(OrderKind.Move,p));u.AiPositionUntil=battle.Time+60;return;}
        }
        bool closing=(target.Position-u.Position).Length>(u.Archetype.Weapon?.Range??0)*.85;
        Note(u,closing?"Battery: advance into range":"Battery: deployed bombardment",closing?new(OrderKind.Advance,target.Position,TargetId:target.Id):new(OrderKind.FireAt,TargetId:target.Id));
    }
    public bool UnsafeShot(Regiment u,Regiment target,Vec2? origin=null)
    {
        var start=origin??u.Position;double distance=(target.Position-start).Length,flight=Math.Max(.1,distance/100),z=battle.Terrain.Elevation(start)+1.2;
        double vz=(battle.Terrain.Elevation(target.Position)-z+.5*battle.Rules.Gravity*flight*flight)/flight;
        foreach(var friend in battle.Combat.SegmentCandidates(start,target.Position))
        {if(!friend.Active || friend.Id==u.Id || friend.Army!=u.Army || friend.Formation==Formation.Skirmish)continue;if(OrientedRect.Segment(start,target.Position,friend.Rect)is not { } entry)continue;double t=entry*flight;var p=start+(target.Position-start)*entry;if(z+vz*t-.5*battle.Rules.Gravity*t*t<=battle.Terrain.Elevation(p)+3)return true;}
        return false;
    }
    private void SelectCover(Regiment u,Regiment target)
    {
        if(battle.Terrain.Forests.Count==0 || battle.Combat.ForestCover(u)>.4 || (target.Position-u.Position).Length<80 || u.AiCoverGoal is not null && battle.Time<u.AiCoverUntil)return;
        var options=new List<(double Score,Vec2 Point)>();double desired=(u.Archetype.Weapon?.Range??155)*.75,current=battle.Terrain.ForestDensity(u.Position);
        foreach(var f in battle.Terrain.Forests)
        {
            var centre=new Vec2(f.X,f.Y);var point=Clamp(u,u.Position+(centre-u.Position).Normalized*Math.Min(60,(centre-u.Position).Length));
            if((point-u.Position).Length>75 || battle.Terrain.ForestDensity(point)<current+.2 || (point-target.Position).Length<80 || !battle.Visibility.Query(point,target.Position).Visible)continue;
            double score=battle.Terrain.ForestDensity(point)*100-(point-u.Position).Length*.3-Math.Abs((point-target.Position).Length-desired)*.1;options.Add((score,point));
        }
        if(options.Count>0){u.AiCoverGoal=options.OrderByDescending(o=>o.Score).ThenBy(o=>o.Point.X).ThenBy(o=>o.Point.Y).First().Point;u.AiCoverUntil=battle.Time+30;}
    }
    public Vec2? Skirmish(Regiment u,Regiment target)
    {
        if(battle.Tick==0)u.ForestCover=battle.Combat.ForestCover(u);
        double distance=(target.Position-u.Position).Length,range=u.Archetype.Weapon?.Range??155,close=target.Archetype.Category==UnitCategory.Cavalry?100:Math.Min(80,range*.45);
        bool stronger=target.Strength*target.Archetype.Melee>u.Strength*.8 || target.Archetype.Category==UnitCategory.Cavalry;
        if(u.ForestCover>0 && u.Archetype.ForestMeleeDamage>1 && target.Archetype.Category==UnitCategory.Infantry)stronger=target.Strength*target.Archetype.Melee>u.Strength*.8*(1+(u.Archetype.ForestMeleeDamage-1)*SpecialistSystem.WoodlandSkill(u.ForestCover));
        if(u.SkirmishRetreat && battle.Time>=u.SkirmishUntil){u.SkirmishRetreat=false;u.SkirmishUntil=battle.Time+10;}
        if(!u.SkirmishRetreat && battle.Time>=u.SkirmishUntil && distance<close && stronger)
        {double turn=Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(target.Position,u.Position)))/Math.Max(.1,u.Archetype.TurnRate*Formations.Get(u.Formation).Turn);u.SkirmishRetreat=true;u.SkirmishUntil=battle.Time+6+Math.Min(4,turn);}
        if(u.SkirmishRetreat){u.AiIntention="Skirmish: turning out / bounded withdrawal";var away=(u.Position-target.Position).Normalized;if(away.Length<.1)away=new(u.Army==0?-1:1,0);return Clamp(u,u.Position+away*65);}
        if(Autonomous(u) && u.AiCoverGoal is { } cover && battle.Time<u.AiCoverUntil && (cover-u.Position).Length>5){u.AiIntention="Skirmish: local covered firing position";return cover;}
        if(distance>range*(u.Archetype.Role=="rifles"?.82:.72) || !battle.Combat.Sight(u,target).Visible){u.AiIntention="Skirmish: approaching effective firing distance";return target.Position;}
        u.AiIntention="Skirmish: fire and hold distance";battle.Combat.FaceThreat(u,target.Position);return null;
    }
    public bool LimitPursuit(Regiment u,Regiment target)
    {
        if(!Autonomous(u) || u.CavalryState!=CavalryState.Pursuit || target.State!=MoraleState.Routing)return false;
        if(u.AiPursuitTarget!=target.Id){u.AiPursuitTarget=target.Id;u.AiPursuitOrigin=u.Position;}
        double limit=CommanderSystem.Policy(u).PursuitDistance*(CommanderSystem.Has(u,"firebrand")?1.15:1);
        if((u.Position-u.AiPursuitOrigin!.Value).Length<=limit)return false;
        Retreat(u,target,"Break off extended pursuit");u.AiAvoidTarget=target.Id;u.AiAvoidUntil=battle.Time+30;u.AiPursuitOrigin=null;u.AiPursuitTarget=null;battle.Cavalry.Cancel(u,"Autonomous pursuit limit");return true;
    }
}
