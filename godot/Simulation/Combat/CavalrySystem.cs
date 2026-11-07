namespace Quiberon.Simulation;

/// <summary>Charge lifecycle/moving pursuit from cavalry.py; ordinary melee is shared.</summary>
public sealed class CavalrySystem(BattleSimulation battle)
{
    private readonly Dictionary<int,int> pursuitNext = new();
    private readonly SortedDictionary<int,List<Regiment>> groups = new();
    private static double Clamp(double x) => Math.Clamp(x,0,1);
    private static double Support(Regiment u,Vec2 axis)=>Math.Abs(Vec2.Direction(u.Facing).Dot(axis))*u.Depth/2+
        Math.Abs(Vec2.Direction(u.Facing+Math.PI/2).Dot(axis))*u.Width/2;
    public static double Gap(Regiment a,Regiment b)
    {var offset=b.Position-a.Position;var axis=offset.Normalized;return offset.Length-Support(a,axis)-Support(b,axis);}
    public static double Readiness(Regiment attacker,Regiment target)
    {
        if(target.Archetype.Category!=UnitCategory.Infantry || target.State!=MoraleState.Steady || target.TransitionLeft>0 || target.Formation==Formation.Skirmish)return 0;
        double front=Clamp(1-Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,attacker.Position)))/(Math.PI/3));
        return front*Clamp(1-target.Speed/1.5)*Clamp((target.Cohesion-40)/50);
    }
    public bool CanPursue(Regiment u,Regiment target)=>u.Effective && target.Active && target.State==MoraleState.Routing &&
        u.Order.Kind is OrderKind.Attack or OrderKind.Advance or OrderKind.Charge or OrderKind.Pursue &&
        (target.Id==u.TargetId || target.Id==u.Order.TargetId) && u.Cohesion>=battle.Rules.PursuitMinCohesion && u.Fatigue<battle.Rules.PursuitMaxFatigue;
    public void Cancel(Regiment u,string reason="Order or target changed")
    {
        if(u.CavalryState==CavalryState.Charging)
        {battle.Metrics.AbortedCharges++;Emit("charge_aborted",u,battle.Unit(u.CavalryTargetId??-1),reason);}
        if(u.CavalryState==CavalryState.Pursuit)Emit("pursuit_end",u,battle.Unit(u.CavalryTargetId??-1),reason);
        u.CavalryState=CavalryState.Approach;u.CavalryTargetId=null;u.ChargeMomentum=0;u.ChargeDistance=0;
        u.RecoilGoal=null;u.PursuitSpeedLimit=null;u.PursuitId=null;
        // Sequence, impact lock, clearance and cooldown survive repeated orders.
    }
    public void Recoil(Regiment u,Regiment target)
    {
        var away=(u.Position-target.Position).Normalized;if(away.Length<.1)away=Vec2.Direction(u.Facing+Math.PI);
        var point=u.Position+away*battle.Rules.ChargeRecoilDistance;double radius=u.Rect.Radius+1;
        u.RecoilGoal=new(Math.Clamp(point.X,radius,battle.Rules.Width-radius),Math.Clamp(point.Y,radius,battle.Rules.Height-radius));
        u.CavalryState=CavalryState.Recoil;u.CavalryRetreatUntil=battle.Time+10;u.ChargeMomentum=0;
        Emit("charge_repulsed",u,target,"Charge held; recoil and reform");
    }
    public Vec2? Intent(Regiment u,Vec2? destination)
    {
        var r=battle.Rules;u.PursuitSpeedLimit=null;
        if(u.Navigation.Route.Count>0 || u.TransitCompact){Cancel(u,"Crossing travel mode");return destination;}double reform=r.ChargeReformSeconds*HistoricalEffects.Reform(u)*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_reform"):1);
        if(!u.ChargeReady)
        {
            var previous=battle.Unit(u.ChargeImpactTargetId??-1);
            bool clear=previous is null || !previous.Active || Gap(u,previous)>=r.ChargeClearance;
            if(clear && battle.Time-u.ChargeContactAt>reform)
            {
                u.ChargeClearSince??=battle.Time;
                if(battle.Time-u.ChargeClearSince.Value>=reform && u.ChargeCooldown<=0)u.ChargeReady=true;
            }
            else u.ChargeClearSince=null;
        }
        var target=battle.Unit(u.TargetId??-1);
        if(!u.Effective || u.Order.Kind is not (OrderKind.Attack or OrderKind.Advance or OrderKind.Charge or OrderKind.Pursue) || target is null || !target.Active)
        {Cancel(u,u.Effective?"No active charge/pursuit order":"Regiment no longer combat-effective");return destination;}
        if(u.CavalryTargetId is not null && u.CavalryTargetId!=target.Id)Cancel(u);
        u.CavalryTargetId=target.Id;
        if(u.Order.Kind==OrderKind.Pursue && target.State!=MoraleState.Routing)
        {Cancel(u,"Target recovered; explicit pursuit ended");u.Order=new(OrderKind.Hold);return null;}
        if(battle.Ai.LimitPursuit(u,target))return u.AiRetreatGoal;
        if(battle.Ai.Autonomous(u) && u.CavalryState==CavalryState.Melee && battle.Time-u.ChargeMeleeSince>CommanderSystem.Policy(u).DisengageSeconds && target.State!=MoraleState.Routing && (u.Cohesion<50 || target.Strength>u.Strength*CommanderSystem.Policy(u).Overmatch)){Recoil(u,target);return u.RecoilGoal;}
        double distance=(target.Position-u.Position).Length,clearance=Gap(u,target);
        if(CanPursue(u,target))
        {
            u.PursuitId=target.Id;
            if(clearance<=CommanderSystem.PursuitGap(u,r.PursuitContactGap))
            {
                if(u.CavalryState==CavalryState.Charging)return target.Position;
                EnterPursuit(u,target);
                var axis=(target.Position-u.Position).Normalized;
                var velocity=target.Velocity??Vec2.Direction(target.Facing)*target.Speed;
                u.PursuitSpeedLimit=Math.Max(0,velocity.Dot(axis))+Math.Max(0,clearance-.25)/Rules.Dt;
                return target.Position;
            }
            if(u.CavalryState==CavalryState.Pursuit)
            {Emit("pursuit_end",u,target,"Contact lost; closing distance");u.CavalryState=CavalryState.Approach;u.ChargeMomentum=0;}
        }
        else if(u.CavalryState==CavalryState.Pursuit)
        {
            Emit("pursuit_end",u,target,"Target rallied or cavalry too disorganized/tired");
            u.CavalryState=OrientedRect.Touching(u.Rect,target.Rect)?CavalryState.Melee:CavalryState.Approach;u.ChargeMomentum=0;u.PursuitId=null;
        }
        if(u.CavalryState==CavalryState.Recoil)
        {
            if((u.Position-u.RecoilGoal!.Value).Length<4 || battle.Time>=u.CavalryRetreatUntil)
            {
                if(OrientedRect.Touching(u.Rect,target.Rect)){u.CavalryState=CavalryState.Melee;u.ChargeMeleeSince=battle.Time;}
                else {u.CavalryState=CavalryState.Reforming;u.CavalryRetreatUntil=battle.Time+reform;}
            }
            else return u.RecoilGoal;
        }
        if(u.CavalryState==CavalryState.Reforming)
        {if(battle.Time<u.CavalryRetreatUntil)return null;u.CavalryState=CavalryState.Approach;}
        if(u.CavalryState==CavalryState.Melee && !OrientedRect.Touching(u.Rect,target.Rect) && !battle.Combat.IsEngaged(u,target))u.CavalryState=CavalryState.Approach;
        if(u.CavalryState==CavalryState.Charging)
        {
            if(u.Cohesion<r.PursuitMinCohesion || u.Fatigue>=r.PursuitMaxFatigue || u.ForestCover>Math.Max(.65,r.ChargeMaxForest) ||
                Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,target.Position)))>1.3 || battle.Time-u.ChargeStarted>r.ChargeMaxSeconds)
            {Cancel(u,"Charge lost alignment, cohesion, time or suitable terrain");u.ChargeCooldown=Math.Max(u.ChargeCooldown,3);}
            return destination;
        }
        bool aligned=Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,target.Position)))<.55;
        if(battle.Tick==0 && !battle.Terrain.Empty)
        {var ground=battle.Terrain.MovementEffect(u,Vec2.Direction(u.Facing));u.ForestCover=ground.Forest;u.GroundSlope=ground.Slope;}
        if(u.ChargeReady && u.ChargeCooldown<=0 && destination is not null && clearance>=r.ChargeMinRun && distance<=r.ChargeRange &&
            aligned && u.Cohesion>=r.ChargeMinCohesion && u.Fatigue<75 && u.ForestCover<=r.ChargeMaxForest && u.GroundSlope<=r.ChargeMaxSlope &&
            u.TerrainWaypoint is null && u.AvoidanceGoal is null)
        {
            u.CavalryState=CavalryState.Charging;u.ChargeSequence++;u.ChargeDistance=0;u.ChargeStarted=battle.Time;u.ChargeMomentum=0;
            battle.Metrics.ChargeStarts++;Emit("charge_start",u,target,$"Charging from {distance:F0} m");
        }
        return destination;
    }
    public void AfterMove(Regiment u,Vec2 before)
    {
        if(u.CavalryState!=CavalryState.Charging)return;
        var r=battle.Rules;u.ChargeDistance+=(u.Position-before).Length;
        var target=battle.Unit(u.CavalryTargetId??-1);if(target is null){u.ChargeMomentum=0;return;}
        var velocity=u.Velocity??Vec2.Zero;
        double alignment=Clamp(velocity.Normalized.Dot((target.Position-u.Position).Normalized)*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_alignment"):1));
        double speed=Clamp((velocity.Length-r.ChargeMinSpeed)/Math.Max(.1,r.ChargeMaxSpeed*u.Archetype.ChargeSpeed-r.ChargeMinSpeed));
        double terrain=Clamp(1-.8*u.ForestCover)/(1+u.GroundSlope*5);
        u.ChargeMomentum=Clamp(speed*Clamp(u.ChargeDistance/r.ChargeMinRun)*u.Cohesion/100*alignment*terrain);
    }
    public void Impact(Regiment u,Regiment target)
    {
        if(!u.Effective || u.CavalryState!=CavalryState.Charging || u.ChargeImpactedSequence==u.ChargeSequence)return;
        var r=battle.Rules;
        u.ChargeImpactedSequence=u.ChargeSequence;u.ChargeImpactTargetId=target.Id;u.ChargeImpactTick=battle.Tick;
        u.ChargeReady=false;u.ChargeClearSince=null;u.ChargeCooldown=r.ChargeCooldownSeconds*HistoricalEffects.Cooldown(u)*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_cooldown"):1);u.ChargeContactAt=battle.Time;
        u.ChargeMeleeSince=battle.Time;u.CavalryState=CavalryState.Melee;
        var velocity=u.Velocity??Vec2.Zero;
        double momentum=u.ChargeMomentum*Clamp(velocity.Normalized.Dot((target.Position-u.Position).Normalized)*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_alignment"):1));
        u.ChargeLastMomentum=momentum;u.ChargeMomentum=0;
        double environmentalDefence=battle.Terrain.Environment.Defence(target,u.Position,true);
        double ready=Readiness(u,target),angle=Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,u.Position)));
        double flank=angle<Math.PI/3?1:angle<2.3?1.5:1.9,resistance=environmentalDefence*(1-.85*ready)*(ready>.5?CommanderSystem.Defence(target,u):1);
        double exploit=SpecialistSystem.Exploit(u,target,ready>.5);
        double power=u.Strength*r.ChargeDamage*momentum*flank*resistance*exploit*u.Archetype.Impact*CommanderSystem.FrontalPenalty(u,target);
        if(target.Formation==Formation.Column)power*=.85;
        int losses=Math.Max(0,(int)(power*(.8+(1.2-.8)*battle.Random.NextDouble())));
        double boost=CommanderSystem.ChargeShock(u,target,momentum,ready>.5);
        double shock=r.ChargeShock*momentum*flank*resistance*exploit*boost*u.Archetype.Impact;
        if(boost>1 && HistoricalCommanders.Has(u,"vorwarts"))u.Cohesion=Math.Max(0,u.Cohesion-2*momentum);
        if(boost>1 && CommanderSystem.Has(u,"firebrand"))u.Cohesion=Math.Max(0,u.Cohesion-CommanderSystem.T("firebrand_disorder")*momentum);
        if(exploit>1)SpecialistSystem.Activate(battle,u,"Exploit the Break: disrupted enemy charged");int before=target.Strength;
        battle.Combat.Damage(target,losses,u,shock,"charge impact");
        target.Cohesion=Math.Max(0,target.Cohesion-r.ChargeCohesionDamage*momentum*resistance);
        int inflicted=before-target.Strength;
        u.Charges++;battle.Metrics.ChargeImpacts++;battle.Metrics.ImpactCasualties+=inflicted;battle.Metrics.ImpactMomentum+=momentum;
        battle.Metrics.ImpactMoraleShock+=shock*target.Archetype.ShockResistance;
        bool success=momentum>.1 && (inflicted>=target.MaximumStrength*.05 || target.Morale<=r.RoutThreshold && ready<.5);
        if(success)battle.Metrics.ChargeSuccesses++;
        bool failed=ready>.5 && target.Active && target.Morale>r.RoutThreshold;
        if(failed)
        {
            battle.Metrics.FailedCharges++;u.Cohesion=Math.Max(0,u.Cohesion-14*momentum*ready*(UpgradeSystem.Has(u,"controlled_charge")?UpgradeSystem.T("controlled_disorder"):1));u.Morale=Math.Max(0,u.Morale-6*momentum*ready);
        }
        u.ChargeResult=failed?"prepared front":success && target.Effective?"breakthrough":"exposed formation";
        Emit("charge_impact",u,target,$"Impact: {inflicted} losses, momentum {momentum:P0} ({u.ChargeResult})",inflicted);
        if(failed)Recoil(u,target);
        else if(success)Emit("breakthrough",u,target,"Formation disrupted by charge");
    }
    private void EnterPursuit(Regiment u,Regiment target)
    {
        if(u.CavalryState!=CavalryState.Pursuit)Emit("pursuit_start",u,target,$"Pursuing broken {target.Name}");
        u.CavalryState=CavalryState.Pursuit;
    }
    public bool Contact(Regiment a,Regiment b,bool physicalContact=true)
    {
        return One(a,b) || One(b,a);
        bool One(Regiment u,Regiment target)
        {
            if(u.Archetype.Category!=UnitCategory.Cavalry || !u.Effective)return false;
            if(physicalContact)Impact(u,target);u.ChargeContactAt=battle.Time;
            if(CanPursue(u,target))
            {
                // Physical contact identifies the fugitive even if a narrow
                // ridge concealed its centre before this movement phase.
                u.CavalryTargetId=target.Id;u.PursuitId=target.Id;
                EnterPursuit(u,target);
                pursuitNext.TryAdd(target.Id,battle.Tick+IntervalTicks);
                return true;
            }
            if(u.CavalryState is not (CavalryState.Recoil or CavalryState.Reforming))
            {if(u.CavalryState!=CavalryState.Melee)u.ChargeMeleeSince=battle.Time;u.CavalryState=CavalryState.Melee;}
            return false;
        }
    }
    private int IntervalTicks=>Math.Max(1,(int)Math.Round(battle.Rules.PursuitInterval/Rules.Dt));
    public void Pursuits(IReadOnlyList<Regiment> units)
    {
        groups.Clear();var r=battle.Rules;
        foreach(var u in units)
        {
            if(u.Archetype.Category!=UnitCategory.Cavalry || u.CavalryState!=CavalryState.Pursuit || u.CombatState==CombatState.Melee)continue;
            var target=battle.Unit(u.CavalryTargetId??-1);
            if(target is null || !CanPursue(u,target) || Gap(u,target)>CommanderSystem.PursuitGap(u,r.PursuitContactGap))continue;
            u.CombatState=CombatState.Pursuit;u.TargetId=target.Id;u.ChargeContactAt=battle.Time;target.CombatState=CombatState.Pursuit;
            battle.Metrics.PursuitSeconds+=Rules.Dt;
            if(!groups.TryGetValue(target.Id,out var followers))groups[target.Id]=followers=new();followers.Add(u);
        }
        foreach(var (targetId,followers) in groups)
        {
            var target=battle.Unit(targetId)!;pursuitNext.TryAdd(targetId,battle.Tick+IntervalTicks);
            if(battle.Tick<pursuitNext[targetId])continue;
            pursuitNext[targetId]=battle.Tick+IntervalTicks;battle.Metrics.PursuitPulses++;
            var weights=new double[followers.Count];double total=0;
            for(int i=0;i<followers.Count;i++)
            {
                var u=followers[i];weights[i]=u.Strength*(.3+.7*u.Cohesion/100)*Math.Min(UpgradeSystem.Has(u,"relentless_pursuit")?1.8:1.45,u.Archetype.Pursuit*CommanderSystem.Pursuit(u))*
                    Math.Max(.15,1-.8*u.ForestCover)/(1+u.GroundSlope*5);total+=weights[i];
            }
            int casualties=Math.Min(Math.Min(target.Strength,(int)(target.MaximumStrength*r.PursuitMaxFraction)),
                Math.Max(0,(int)(total*r.PursuitDamage/Math.Sqrt(followers.Count)*(.85+(1.15-.85)*battle.Random.NextDouble()))));
            int remaining=casualties;
            for(int i=0;i<followers.Count;i++)
            {
                int losses=i==followers.Count-1?remaining:Math.Min(remaining,(int)(casualties*weights[i]/Math.Max(.001,total)));remaining-=losses;
                int before=target.Strength;battle.Combat.Damage(target,losses,followers[i],.8*weights[i]/Math.Max(.001,total),"cavalry pursuit");
                battle.Metrics.PursuitCasualties+=before-target.Strength;
            }
            target.Cohesion=Math.Max(0,target.Cohesion-2);
            Emit("pursuit_casualties",followers[0],target,$"Pursuit inflicted {casualties} losses",casualties);
            if(target.Active)
            {
                double resistance=target.Strength*r.PursuitResistance*r.RoutingMeleeFactor*(.3+target.Cohesion/100);
                double rolled=resistance*(.65+(1.35-.65)*battle.Random.NextDouble());
                int losses=(int)rolled+(battle.Random.NextDouble()<rolled-(int)rolled?1:0);
                var victim=followers[(battle.Tick/IntervalTicks)%followers.Count];int before=victim.Strength;
                battle.Combat.Damage(victim,losses,target,r.RoutingMeleeFactor*.5,"pursuit resistance");battle.Metrics.PursuitLosses+=before-victim.Strength;
            }
        }
        // One timer per initial regiment, bounded by army size. Preserve a due
        // pulse across a temporary gap just as Python does.
        foreach(var key in pursuitNext.Keys.Where(id=>battle.Unit(id)?.Active!=true).ToArray())pursuitNext.Remove(key);
    }
    public void Cleanup()
    {
        foreach(var u in battle.Units)
            if(u.Archetype.Category==UnitCategory.Cavalry && (!u.Active || u.CavalryTargetId is { } id && battle.Unit(id)?.Active!=true))Cancel(u,"Target escaped/destroyed or pursuer unavailable");
    }
    public static void PursuitLanes(BattleSimulation battle,IReadOnlyList<Regiment> units,Dictionary<int,Vec2?> intents)
    {
        foreach(var group in units.Where(u=>u.PursuitId is not null && intents[u.Id] is not null).GroupBy(u=>u.PursuitId!.Value))
        {
            var target=battle.Unit(group.Key);var followers=group.ToArray();if(target is null || followers.Length<2)continue;
            var side=Vec2.Direction(target.Facing+Math.PI/2);double limit=Math.Min(24,target.Width*.3);
            for(int i=0;i<followers.Length;i++)
            {
                var u=followers[i];double offset=Math.Clamp((i-(followers.Length-1)/2.0)*battle.Rules.PursuitLaneSpacing,-limit,limit);
                offset*=Clamp(((u.Position-target.Position).Length-25)/80);var p=target.Position+side*offset;double radius=u.Rect.Radius+1;
                intents[u.Id]=new Vec2(Math.Clamp(p.X,radius,battle.Rules.Width-radius),Math.Clamp(p.Y,radius,battle.Rules.Height-radius));
            }
        }
    }
    private void Emit(string kind,Regiment u,Regiment? target,string message,int losses=0)
    {u.StateReason=message;battle.Emit(kind,u,target,u.Position,kind=="charge_impact"?1:3,losses,$"{u.Name}: {message}");}
}
