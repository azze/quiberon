namespace Quiberon.Simulation;

public readonly record struct VolleyCalculation(int Shots,double Probability,double LaneFactor,double Distance);
public readonly record struct MeleeCalculation(double Power,double Shock,double Flank,double Terrain);

/// <summary>Shared musket, damage and sustained-melee rules from combat.py; no army AI planner.</summary>
public sealed class CombatSystem(BattleSimulation battle)
{
    private SpatialIndex? index;
    private readonly Dictionary<int,int> groups=new();
    private bool groupsDirty=true;
    private readonly Dictionary<(int,int),int> meleeNext=new();
    private HashSet<(int,int)> engaged=new(),contacts=new();
    public int EngagementCount=>engaged.Count;
    public bool IsEngaged(Regiment a,Regiment b)=>a.Active && b.Active && engaged.Contains(Key(a,b)) && OrientedRect.Touching(a.Rect,b.Rect,battle.Rules.MeleeDisengageDistance);
    public void PreparePhase(IReadOnlyList<Regiment> active)
    { index=active.Count>=12?new SpatialIndex(active):null;groupsDirty=true; }
    public Visibility Sight(Regiment a,Regiment b)
    =>SightFrom(a,b,a.Position);
    public Visibility SightFrom(Regiment a,Regiment b,Vec2 origin)
    {double opacity=HistoricalCommanders.Has(a,"cossack_screen")?.9:1;if(battle.Rules.SpecialistsEnabled && battle.Terrain.Forests.Count>0){opacity*=1+(b.Archetype.Concealment-1)*battle.Terrain.ForestDensity(b.Position);opacity*=1-(1-a.Archetype.ForestVision)*battle.Terrain.ForestDensity(origin);}return battle.Visibility.Query(origin,b.Position,opacity);}
    private static bool Enemy(Regiment a,Regiment? b)=>b is {Active:true} && a.Id!=b.Id && a.Army!=b.Army;
    public Regiment? Designated(Regiment u)=>u.Order.Kind is OrderKind.Attack or OrderKind.Charge or OrderKind.Pursue or OrderKind.FireAt && Enemy(u,battle.Unit(u.Order.TargetId??-1))?battle.Unit(u.Order.TargetId!.Value):null;
    public IEnumerable<Regiment> Nearby(Vec2 point,double radius)=>Candidates(point,point,radius);
    public bool CanMelee(Regiment u)=>!u.NonCombatant && (u.Archetype.MeleeOnly || u.CombatCapable || battle.Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry || battle.Rules.MoraleEnabled && u.Archetype.Category!=UnitCategory.Cavalry);
    private Regiment? NearestVisible(Regiment u)
    {
        var preferred=battle.Unit(u.Order.TargetId??-1);
        if(Enemy(u,preferred) && Sight(u,preferred!).Visible)return preferred;
        return battle.Units.Where(e=>Enemy(u,e)).OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).FirstOrDefault(e=>Sight(u,e).Visible);
    }
    public void FaceThreat(Regiment u,Vec2 point)
    {
        if(u.Navigation.Route.Count>0 || u.InfantryCharging || u.TransitionLeft>0 || u.SettlingFacing is not null || battle.Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry && u.CavalryState is CavalryState.Charging or CavalryState.Recoil or CavalryState.Reforming)return;
        double limit=u.Archetype.TurnRate*.65*Rules.Dt;
        double turn=Math.Clamp(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,point)),-limit,limit);
        u.Facing+=turn;if(turn!=0)groupsDirty=true;
    }
    public Vec2? Intent(Regiment u)
    {
        u.TargetId=null;u.PursuitId=null;u.SightState="none";
        if(battle.Rules.MoraleEnabled)
        {
            if(u.State==MoraleState.Routing)return RoutingSystem.Destination(battle,u);
            u.RoutHeading=null;u.RoutNextPlan=0;
            if(u.Order.Kind==OrderKind.Withdraw)
            {
                if(u.Position.X<18 || u.Position.X>battle.Rules.Width-18)
                {u.Withdrawn=true;battle.Metrics.Escapes++;battle.Emit("withdraw",u,null,u.Position,2,0,$"{u.Name}: ordered withdrawal, {u.Strength} survivors");return null;}
                return new Vec2(u.Army==0?10:battle.Rules.Width-10,u.Position.Y);
            }
            if(u.State==MoraleState.Rallying)return null;
        }
        bool cavalry=battle.Rules.CavalryEnabled && u.Archetype.Category==UnitCategory.Cavalry;
        if(u.Order.Kind is OrderKind.HoldFire or OrderKind.ResumeFire) { return null; }
        if(!u.CombatCapable && !cavalry && !u.Archetype.MeleeOnly)return u.Order.Kind is OrderKind.Move or OrderKind.Disengage or OrderKind.Advance or OrderKind.Defend?u.Order.Destination:null;
        if(u.Order.Kind==OrderKind.Pursue && battle.Unit(u.Order.TargetId??-1) is not {Active:true,State:MoraleState.Routing})
        {if(cavalry)battle.Cavalry.Cancel(u,"Explicit pursuit target escaped, died or recovered");u.Order=new(OrderKind.Hold);return null;}
        var target=Designated(u)??NearestVisible(u);
        if(target is not null)
        {
            u.TargetId=target.Id;var sight=Sight(u,target);
            u.SightState=sight.Visible?sight.State:sight.Reason;u.SightTransmission=sight.Transmission;
            if(sight.Visible)u.LastSeenTargetPosition=target.Position;
            else if(battle.Rules.MoraleEnabled)u.TargetId=null;
        }
        if(cavalry && target is {State:MoraleState.Routing} && u.TargetId==target.Id && u.Order.Kind is OrderKind.Attack or OrderKind.Advance or OrderKind.Charge or OrderKind.Pursue)u.PursuitId=target.Id;
        if(u.Order.Kind is OrderKind.Move or OrderKind.Disengage || u.Order.Kind==OrderKind.Advance && u.Order.Facing is not null && u.Order.Destination is { } d && (d-u.Position).Length<1)return u.Order.Destination;
        if(u.Order.Kind==OrderKind.Skirmish && battle.Rules.AiEnabled && target is not null)return battle.Ai.Skirmish(u,target);
        if(u.Order.Kind is OrderKind.Attack or OrderKind.Advance or OrderKind.Charge or OrderKind.Pursue or OrderKind.FireAt)
        {
            if(target is null)return u.Order.Destination;
            if(u.Archetype.Category!=UnitCategory.Artillery && !Sight(u,target).Visible)return u.LastSeenTargetPosition??u.Order.Destination;
            if(u.Order.Kind==OrderKind.FireAt){FaceThreat(u,target.Position);return null;}
            var key=Key(u,target);
            bool pursuing=cavalry && target.State==MoraleState.Routing && u.Cohesion>=battle.Rules.PursuitMinCohesion && u.Fatigue<battle.Rules.PursuitMaxFatigue;
            if(!pursuing && battle.Tick<=meleeNext.GetValueOrDefault(key,-1) && OrientedRect.Touching(u.Rect,target.Rect)) { FaceThreat(u,target.Position);return null; }
            if(cavalry || u.Archetype.MeleeOnly || u.Order.Kind==OrderKind.Charge)return target.Position;
            double range=u.Archetype.Weapon!.Range, distance=(target.Position-u.Position).Length;
            if(Designated(u) is { } designated && distance<=range)
            {
                var blocker=FiringBlocker(u,designated);
                if(blocker?.Army==u.Army)return designated.Position;
                FaceThreat(u,designated.Position);return null;
            }
            if(distance<=range*(battle.Ai.Autonomous(u)?CommanderSystem.Policy(u).FiringDistance:.85)){FaceThreat(u,target.Position);return null;}
            return target.Position;
        }
        if(u.Order.Kind==OrderKind.Defend && u.Order.Destination is { } anchor && (u.Position-anchor).Length>20)return anchor;
        if(target is not null && (target.Position-u.Position).Length<=(u.Archetype.Weapon?.Range??0) && Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,target.Position)))<Math.PI/2)FaceThreat(u,target.Position);
        return null;
    }
    public static bool InArc(Regiment shooter,Regiment target,double halfArc)=>Math.Abs(Vec2.AngleDelta(shooter.Facing,Vec2.AngleTo(shooter.Position,target.Position)))<=halfArc;
    public IEnumerable<Regiment> SegmentCandidates(Vec2 a,Vec2 b)=>Candidates(a,b);
    private IEnumerable<Regiment> Candidates(Vec2 a,Vec2 b,double padding=0)=>index?.Segment(a,b,padding)??battle.Units;
    private void EnsureGroups()
    {
        if(!groupsDirty)return;
        groups.Clear();var active=battle.Units.Where(u=>u.Active).ToArray();
        foreach(var u in active)groups[u.Id]=u.Id;
        int Root(int id){while(groups[id]!=id){groups[id]=groups[groups[id]];id=groups[id];}return id;}
        foreach(var(a,b) in SpatialIndex.Candidates(active))if(a.Army==b.Army && OrientedRect.Separation(a.Rect,b.Rect)is not null)groups[Root(b.Id)]=Root(a.Id);
        foreach(var u in active)groups[u.Id]=Root(u.Id);
        groupsDirty=false;
    }
    public double LaneCover(Regiment shooter,Regiment target,Regiment obstacle,Vec2? origin=null)
    {
        var start=origin??shooter.Position;
        var side=Vec2.Direction(Vec2.AngleTo(start,target.Position)+Math.PI/2);
        double sourceZ=0,targetZ=0,obstacleZ=0;
        if(!battle.Terrain.Empty){sourceZ=battle.Terrain.Elevation(start)+1.7;targetZ=battle.Terrain.Elevation(target.Position)+1.7;obstacleZ=battle.Terrain.Elevation(obstacle.Position)+1.7;}
        int covered=0;
        foreach(double fraction in new[]{-.35,0,.35})
        {
            var shift=side*(shooter.Width*fraction);
            if(OrientedRect.Segment(start+shift,target.Position+shift,obstacle.Rect) is not { } entry)continue;
            if(!battle.Terrain.Empty && sourceZ+(targetZ-sourceZ)*entry>obstacleZ+battle.Rules.FriendlyFireClearance)continue;
            covered++;
        }
        return covered/3.0;
    }
    public Regiment? FiringBlocker(Regiment shooter,Regiment target,Vec2? origin=null)
    {
        if(shooter.Archetype.Category==UnitCategory.Artillery)return null;
        battle.Metrics.FiringBlockerChecks++;EnsureGroups();var start=origin??shooter.Position;
        Regiment? best=null;double first=double.PositiveInfinity;
        foreach(var u in Candidates(start,target.Position))
        {
            if(!u.Active || u.Id==shooter.Id || u.Id==target.Id)continue;
            if(OrientedRect.Segment(start,target.Position,u.Rect) is not { } entry)continue;
            if(groups[u.Id]==groups[target.Id])continue;
            if(origin is null && groups[u.Id]==groups[shooter.Id] && OrientedRect.IntersectionArea(shooter.Rect,u.Rect)>1e-8)continue;
            if(u.Army==shooter.Army && (u.Formation==Formation.Skirmish || LaneCover(shooter,target,u,origin)<.99))continue;
            if(entry<first || entry==first && u.Id<best!.Id){first=entry;best=u;}
        }
        return best;
    }
    public double FriendlyFireFactor(Regiment shooter,Regiment target)
    {
        if(shooter.Archetype.Category!=UnitCategory.Infantry)return 1;
        double shared=1,cover=0;
        foreach(var friend in Candidates(shooter.Position,target.Position,shooter.Width/2))
        {
            if(friend.Id==shooter.Id || !friend.Active || friend.Army!=shooter.Army)continue;
            double density=friend.Formation==Formation.Skirmish?battle.Rules.FriendlyLooseDensity:1;
            double radius=(shooter.Width+shooter.Depth+friend.Width+friend.Depth)/2;
            double area=(friend.Position-shooter.Position).Length<radius?OrientedRect.IntersectionArea(shooter.Rect,friend.Rect):0;
            if(area>1e-8)shared+=Math.Min(1,area/(shooter.Width*shooter.Depth))*density;
            else cover=Math.Max(cover,LaneCover(shooter,target,friend)*density);
        }
        return Math.Clamp((1-cover)/shared,0,1);
    }
    public bool CanFire(Regiment shooter,Regiment target)
    {
        if(!battle.Terrain.Environment.InVisibility(shooter.Position,target.Position) || shooter.Archetype.Category==UnitCategory.Artillery && (shooter.TransitCompact || shooter.Navigation.CrossingId.Length>0) || shooter.InfantryCharging || shooter.HoldFire || shooter.Archetype.Category==UnitCategory.Artillery && (shooter.Limbered || shooter.SetupLeft>0))return false;
        if(shooter.Archetype.Weapon is null || !shooter.Effective || !shooter.CombatCapable || !Enemy(shooter,target))return false;
        double range=shooter.Archetype.Weapon!.Range;
        if((target.Position-shooter.Position).LengthSquared>range*range || !InArc(shooter,target,battle.Rules.FiringHalfArc))return false;
        if(shooter.Archetype.Category==UnitCategory.Artillery && battle.Ai.Autonomous(shooter) && (!battle.Perceives(shooter,target) || battle.Ai.UnsafeShot(shooter,target)))return false;
        return (shooter.Archetype.Category==UnitCategory.Artillery || Sight(shooter,target).Visible) && FiringBlocker(shooter,target)is null;
    }
    public Regiment? SelectFireTarget(Regiment u)
    {
        if(u.Archetype.Weapon is null)return null;
        if(Designated(u)is { } designated)return CanFire(u,designated)?designated:null;
        var preferred=battle.Unit(u.Order.TargetId??-1);
        if(preferred is not null && CanFire(u,preferred))return preferred;
        double range=u.Archetype.Weapon!.Range;
        return Candidates(u.Position,u.Position,range).Where(e=>Enemy(u,e) && (e.Position-u.Position).LengthSquared<=range*range)
            .OrderBy(e=>(e.Position-u.Position).LengthSquared).ThenBy(e=>e.Id).FirstOrDefault(e=>CanFire(u,e) && battle.Perceives(u,e));
    }
    public double ForestCover(Regiment u)=>battle.Terrain.Forests.Count>0?battle.Terrain.MovementEffect(u,Vec2.Zero).Forest:0;
    public VolleyCalculation CalculateVolley(Regiment u,Regiment target)
    {
        var weapon=u.Archetype.Weapon??throw new InvalidOperationException("Combat-disabled unit");
        double lane=FriendlyFireFactor(u,target),distance=(target.Position-u.Position).Length;
        double firing=u.Formation switch{Formation.Line=>1,Formation.Column=>.32,_=>.52};
        int shots=Math.Max(1,(int)(u.Strength*.42*firing*lane));
        double p=battle.Rules.MusketAccuracy*(1-.65*distance/weapon.Range)*(.3+u.Cohesion/140)*weapon.Accuracy;
        if(SpecialistSystem.Has(u,"drill"))p*=.85+.30*SpecialistSystem.Drill(u);
        p*=Math.Min(1.5,SpecialistSystem.Aimed(u,Sight(u,target).Transmission)*CommanderSystem.Accuracy(u,Sight(u,target).Transmission));
        if(target.Formation==Formation.Skirmish)p*=.65;
        if(!battle.Terrain.Empty)
        {
            var sight=Sight(u,target);double cover=ForestCover(u),targetCover=ForestCover(target);
            double depth=Math.Min(1,sight.Vegetation/40),protection=.60*targetCover*Math.Min(1,sight.Vegetation/4);
            var a=u.Archetype;bool special=battle.Rules.SpecialistsEnabled;
            double transmission=Math.Pow(sight.Transmission,1-(1-(special?a.ForestAim:1))*cover);
            p*=transmission*Math.Max(.1,1-.45*cover*(special?a.ForestFire:1)*depth)*Math.Max(.15,1-protection)*(1+((special?a.ForestAccuracy:1)-1)*SpecialistSystem.WoodlandSkill(cover));
        }
        p*=battle.Terrain.Environment.Defence(target,u.Position);
        if(u.Speed>.1)p*=.45;
        if(battle.Rules.MoraleEnabled)
        {if(u.State==MoraleState.Shaken)p*=battle.Rules.ShakenAccuracyFactor;else if(u.State==MoraleState.Wavering)p*=battle.Rules.WaveringAccuracyFactor;}
        return new(shots,Math.Clamp(p,0,.95),lane,distance);
    }
    public int ScaleCasualties(int losses,double multiplier)
    {
        if(losses<=0 || multiplier==1)return losses;
        double scaled=Math.Max(0,losses*multiplier),fraction=scaled-(int)scaled;
        return (int)scaled+(fraction>1e-9 && battle.Random.NextDouble()<fraction?1:0);
    }
    public bool Fire(Regiment u,Regiment target)
    {
        if(!u.Effective || !u.CombatCapable || u.CombatState==CombatState.Melee || u.ReloadLeft>0 || u.TransitionLeft>0 || !CanFire(u,target))return false;
        var volley=CalculateVolley(u,target);u.FireLaneFactor=volley.LaneFactor;
        if(volley.LaneFactor<=0)return false;
        u.ReloadLeft=Math.Max(.5,SpecialistSystem.Reload(u)*UpgradeSystem.VolleyReload(battle,u));u.CombatState=CombatState.Firing;u.TargetId=target.Id;
        battle.Metrics.FirstEngagement??=battle.Time;u.ShotsFired++;
        if(u.Archetype.Category==UnitCategory.Artillery){battle.Artillery.Salvo(u,target);return true;}
        if(SpecialistSystem.Aimed(u,Sight(u,target).Transmission)>1.05)SpecialistSystem.Activate(battle,u,"Aimed Fire: stationary precision volley");
        if(SpecialistSystem.Drill(u)>.2)SpecialistSystem.Activate(battle,u,"Prussian Drill: coordinated volley");
        if(SpecialistSystem.Has(u,"woodland") && ForestCover(u)>.2)SpecialistSystem.Activate(battle,u,"Woodland Warfare: firing from cover");
        u.LastVolleyProbability=volley.Probability;u.LastVolleyShots=volley.Shots;battle.Metrics.Volleys++;
        battle.Emit("volley",u,target,u.Position+Vec2.Direction(u.Facing)*(u.Depth/2+2),3,0,$"{u.Name}: volley at {target.Name}");
        int losses=0;for(int i=0;i<volley.Shots;i++)if(battle.Random.NextDouble()<volley.Probability)losses++;
        int before=target.Strength;
        Damage(target,ScaleCasualties(losses,battle.Rules.InfantryVolleyDamage),u,.9*volley.LaneFactor,"musket volley");
        if(u.Commander.Upgrades is {Count:>0})UpgradeSystem.OnVolley(battle,u,target,before-target.Strength);
        return true;
    }
    public MeleeCalculation CalculateMelee(Regiment a,Regiment target)
    {
        double angle=Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,a.Position)));
        double flank=angle<Math.PI/3?1:angle<2.3?1.6:2.2;
        double density=a.Formation==Formation.Skirmish?.25:a.Formation==Formation.Column?.6:1;
        double terrain=Math.Max(.2,1-.45*ForestCover(a)*density);
        if(!battle.Terrain.Empty)
        {
            double grade=(battle.Terrain.Elevation(target.Position)-battle.Terrain.Elevation(a.Position))/Math.Max(10,(target.Position-a.Position).Length);
            terrain/=1+Math.Max(0,grade)*2;
        }
        double skill=SpecialistSystem.WoodlandSkill(ForestCover(a));
        double forestPower=battle.Rules.SpecialistsEnabled?1+(a.Archetype.ForestMeleeDamage-1)*skill:1;
        double power=a.Strength*.013*(.3+a.Cohesion/100)*flank*terrain*forestPower;
        if(a.Formation==Formation.Skirmish)power*=.65;
        if(target.Archetype.Category==UnitCategory.Artillery)power*=battle.Rules.ArtilleryMeleeVulnerability;
        double state=battle.Rules.MoraleEnabled?MoraleSystem.MeleeEffectiveness(a,battle.Rules):1;
        if(battle.Rules.MoraleEnabled || battle.Rules.CavalryEnabled)power*=a.Archetype.Melee;
        if(a.Archetype.Category==UnitCategory.Cavalry)power*=battle.Rules.CavalryMeleeFactor;
        double shock=flank*terrain*state*(battle.Rules.MoraleEnabled||battle.Rules.CavalryEnabled?a.Archetype.MeleeShock:1);
        if(battle.Rules.SpecialistsEnabled)shock*=1+(a.Archetype.ForestMeleeShock-1)*skill;
        if(a.Archetype.Category==UnitCategory.Artillery){power*=.10;shock*=.10;}
        power*=CommanderSystem.FrontalPenalty(a,target)*HistoricalEffects.Melee(a);
        return new(power*state,shock,flank,terrain);
    }
    public void Damage(Regiment target,int losses,Regiment attacker,double shock,string reason)
    {
        if(!target.Active)return;
        losses=Math.Clamp(losses,0,target.Strength);target.Strength-=losses;
        if(battle.Rules.MoraleEnabled)
        {
            double actualShock=shock*Math.Max(UpgradeSystem.Has(target,"steadfast_defence")?.55:.65,target.Archetype.ShockResistance*CommanderSystem.Shock(target));
            target.Morale=Math.Clamp(target.Morale-(losses/(double)target.MaximumStrength*battle.Rules.CasualtyMorale*HistoricalEffects.CasualtyMorale(target)+actualShock)/target.Archetype.Discipline,0,100);
            if(losses>0)attacker.Morale=Math.Min(100,attacker.Morale+losses*.025);
            if(losses>0 || actualShock>0)target.LastAttackerId=attacker.Id;
        }
        target.Cohesion=Math.Max(0,target.Cohesion-(losses/(double)target.MaximumStrength*130+shock*.35)*CommanderSystem.Defence(target,attacker));
        if(battle.Rules.MoraleEnabled)UpgradeSystem.Inspired(battle,attacker,target,losses);
        attacker.DamageInflicted+=losses;if(losses>0)battle.Metrics.FirstEngagement??=battle.Time;
        battle.Metrics.Casualties+=losses;
        if(losses>0)battle.Emit("casualties",target,attacker,target.Position,1.5,losses,$"{target.Name}: {losses} lost to {reason}");
        if(!target.Active)
        {
            target.Speed=0;target.Velocity=Vec2.Zero;target.CombatState=CombatState.Destroyed;target.TargetId=null;groupsDirty=true;
            battle.Emit("destroyed",target,attacker,target.Position,3,0,$"{target.Name} destroyed");
        }
    }
    private static (int,int) Key(Regiment a,Regiment b)=>(Math.Min(a.Id,b.Id),Math.Max(a.Id,b.Id));
    public void ResolveMelee(IReadOnlyList<Regiment> active)
    {
        contacts.Clear();
        foreach(var(a,b) in SpatialIndex.Candidates(active,Math.Max(1.5,battle.Rules.MeleeDisengageDistance)))
        {
            if(!a.Active || !b.Active || a.Army==b.Army || !CanMelee(a) && !CanMelee(b))continue;
            var key=Key(a,b);bool touching=OrientedRect.Touching(a.Rect,b.Rect);
            if(!touching && !(engaged.Contains(key) && OrientedRect.Touching(a.Rect,b.Rect,battle.Rules.MeleeDisengageDistance)))continue;
            if(battle.Rules.CavalryEnabled && battle.Cavalry.Contact(a,b,touching))continue;
            // Only physical contact can deliver a new impact, not the retention halo.
            if(touching && battle.Rules.InfantryChargesEnabled){battle.InfantryCharges.Impact(a,b);battle.InfantryCharges.Impact(b,a);}
            if(!a.Active || !b.Active)continue;
            contacts.Add(key);
            if(!engaged.Contains(key))battle.Emit("melee_enter",a,b,(a.Position+b.Position)/2,2,0,$"{a.Name} in melee with {b.Name}");
            a.CombatState=b.CombatState=CombatState.Melee;a.TargetId=b.Id;b.TargetId=a.Id;
            if(battle.Tick<meleeNext.GetValueOrDefault(key,0))continue;
            meleeNext[key]=battle.Tick+Math.Max(1,(int)Math.Round(battle.Rules.MeleeInterval/Rules.Dt));battle.Metrics.MeleePulses++;
            Strike(a,b);Strike(b,a);
        }
        foreach(var key in engaged.OrderBy(k=>k.Item1).ThenBy(k=>k.Item2))
            if(!contacts.Contains(key))Leave(key);
        (engaged,contacts)=(contacts,engaged);
        void Strike(Regiment a,Regiment b)
        {
            if(!a.Active || !b.Active || !CanMelee(a) || a.ChargeImpactTick==battle.Tick)return;
            var hit=CalculateMelee(a,b);
            double rolled=hit.Power*(.65+(1.35-.65)*battle.Random.NextDouble());
            int losses=a.Archetype.Category==UnitCategory.Artillery || !a.Effective?
                (int)rolled+(battle.Random.NextDouble()<rolled-(int)rolled?1:0):Math.Max(1,(int)rolled);
            if(battle.Rules.MoraleEnabled || battle.Rules.CavalryEnabled)losses=ScaleCasualties(losses,a.Archetype.MeleeDamage);
            Damage(b,losses,a,hit.Shock,"melee");
        }
    }
    private void Leave((int,int) key)
    {
        var a=battle.Unit(key.Item1);var b=battle.Unit(key.Item2);
        if(a is not null && b is not null)battle.Emit("melee_leave",a,b,(a.Position+b.Position)/2,1,0,$"{a.Name} disengaged from {b.Name}");
    }
    public void Cleanup()
    {
        foreach(var key in engaged.Where(k=>battle.Unit(k.Item1)?.Active!=true || battle.Unit(k.Item2)?.Active!=true).ToArray()) {engaged.Remove(key);meleeNext.Remove(key);Leave(key);}
        foreach(var key in meleeNext.Where(p=>!engaged.Contains(p.Key) && p.Value<=battle.Tick).Select(p=>p.Key).ToArray())meleeNext.Remove(key);
        foreach(var u in battle.Units)
        {
            if(u.TargetId is { } id && !Enemy(u,battle.Unit(id)))u.TargetId=null;
            if(u.Order.TargetId is { } ordered && !Enemy(u,battle.Unit(ordered)))u.Order=u.Order with {TargetId=null};
            if(!u.Active || !u.Effective || u.InfantryChargeTargetId is { } chargeTarget && battle.Unit(chargeTarget)?.Active!=true)battle.InfantryCharges.Cancel(u);
            if(!u.Active){u.CombatState=u.Withdrawn?CombatState.Withdrawn:CombatState.Destroyed;u.TargetId=null;u.ReloadLeft=0;u.Speed=0;u.Velocity=Vec2.Zero;SeparationSystem.Reset(u);}
            else if(u.CombatState==CombatState.Melee && !engaged.Any(k=>k.Item1==u.Id||k.Item2==u.Id))u.CombatState=CombatState.Idle;
        }
    }
}
