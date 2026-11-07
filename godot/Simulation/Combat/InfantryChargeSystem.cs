namespace Quiberon.Simulation;

/// <summary>Python infantry_charge.py: a short bayonet rush and one impact, then shared melee.</summary>
public sealed class InfantryChargeSystem(BattleSimulation battle)
{
    public void Cancel(Regiment u)
    {
        if (u.InfantryCharging) battle.Metrics.AbortedCharges++;
        u.InfantryCharging = false; u.InfantryChargeTargetId = null; u.ChargeMomentum = 0; u.ChargeDistance = 0;
    }
    public Vec2? Intent(Regiment u, Vec2? destination)
    {
        var r = battle.Rules;
        if(u.Navigation.Route.Count>0){Cancel(u);return destination;}
        if (!u.ChargeReady)
        {
            var previous = battle.Unit(u.ChargeImpactTargetId ?? -1);
            bool clear = previous is null || !previous.Active || CavalrySystem.Gap(u, previous) >= r.InfantryChargeClearance;
            if (clear && u.CombatState != CombatState.Melee)
            { u.ChargeClearSince ??= battle.Time; if (battle.Time - u.ChargeClearSince >= r.InfantryChargeReform && u.ChargeCooldown <= 0) u.ChargeReady = true; }
            else u.ChargeClearSince = null;
        }
        var target = battle.Unit(u.TargetId ?? -1);
        if (u.Order.Kind != OrderKind.Charge || !u.Effective || target is null || !target.Active || u.TransitionLeft > 0 || u.Cohesion < r.InfantryChargeMinCohesion || u.Fatigue >= 85)
        { Cancel(u); return destination; }
        if (u.InfantryChargeTargetId is not null && u.InfantryChargeTargetId != target.Id) Cancel(u);
        u.InfantryChargeTargetId = target.Id;
        if (!u.InfantryCharging && u.ChargeReady && u.ChargeCooldown <= 0 && destination is not null && (target.Position-u.Position).Length <= r.InfantryChargeRange &&
            CavalrySystem.Gap(u,target) >= r.InfantryChargeMinRun && Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,target.Position))) < .7)
        {
            u.InfantryCharging = true; u.ChargeSequence++; u.ChargeStarted = battle.Time; u.ChargeDistance = 0;
            battle.Metrics.ChargeStarts++; battle.Emit("charge_start",u,target,u.Position,2,0,$"{u.Name}: bayonet charge against {target.Name}");
        }
        if (u.InfantryCharging && (battle.Time-u.ChargeStarted > 30 || Math.Abs(Vec2.AngleDelta(u.Facing,Vec2.AngleTo(u.Position,target.Position))) > 1.4))
        { Cancel(u); u.ChargeCooldown = Math.Max(u.ChargeCooldown,3); }
        return destination;
    }
    public double SpeedCap(Regiment u) => u.Archetype.Speed * Formations.Get(u.Formation).Speed * battle.Rules.InfantryChargeSpeed;
    public void AfterMove(Regiment u, Vec2 before)
    {
        u.ChargeDistance += (u.Position-before).Length;
        var target = battle.Unit(u.InfantryChargeTargetId ?? -1);
        if (target is null) { u.ChargeMomentum=0; return; }
        var velocity = u.Velocity ?? Vec2.Zero;
        u.ChargeMomentum = Math.Clamp(velocity.Length/SpeedCap(u),0,1) * Math.Clamp(u.ChargeDistance/battle.Rules.InfantryChargeMinRun,0,1) * u.Cohesion/100 *
            Math.Clamp(velocity.Normalized.Dot((target.Position-u.Position).Normalized),0,1);
        if (u.Speed > .1) u.Fatigue = Math.Min(100,u.Fatigue+Rules.Dt*.06);
    }
    public void Impact(Regiment u, Regiment target)
    {
        if (u.Archetype.Category != UnitCategory.Infantry || !u.InfantryCharging || !u.Effective || !target.Active || u.ChargeImpactedSequence == u.ChargeSequence) return;
        var r=battle.Rules; double momentum=u.ChargeMomentum;
        u.InfantryCharging=false;u.ChargeReady=false;u.ChargeClearSince=null;u.ChargeImpactedSequence=u.ChargeSequence;
        u.ChargeImpactTargetId=target.Id;u.ChargeImpactTick=battle.Tick;u.ChargeContactAt=battle.Time;u.ChargeCooldown=r.InfantryChargeCooldown;
        u.ChargeLastMomentum=momentum;u.ChargeMomentum=0;
        double angle=Math.Abs(Vec2.AngleDelta(target.Facing,Vec2.AngleTo(target.Position,u.Position))),flank=angle<Math.PI/3?1:angle<2.3?1.3:1.6;
        double density=u.Formation==Formation.Skirmish?.25:u.Formation==Formation.Column?.6:1,cover=battle.Combat.ForestCover(u);
        double terrain=Math.Max(.2,1-.45*cover*density);
        terrain/=1+Math.Max(0,battle.Terrain.Elevation(target.Position)-battle.Terrain.Elevation(u.Position))/Math.Max(10,(target.Position-u.Position).Length)*2;
        double skill=SpecialistSystem.WoodlandSkill(cover),forestPower=u.SpecialistsEnabled?1+(u.Archetype.ForestMeleeDamage-1)*skill:1;
        double forestShock=u.SpecialistsEnabled?1+(u.Archetype.ForestMeleeShock-1)*skill:1;
        double power=u.Strength*r.InfantryChargeDamage*momentum*u.Archetype.Melee*MoraleSystem.MeleeEffectiveness(u,r)*flank*terrain*forestPower;
        if(u.Formation==Formation.Skirmish)power*=.65;
        double boost=CommanderSystem.ChargeShock(u,target,momentum,false),shock=r.InfantryChargeShock*momentum*flank*terrain*forestShock*boost;
        int losses=battle.Combat.ScaleCasualties((int)(power*(.8+.4*battle.Random.NextDouble())),u.Archetype.MeleeDamage),before=target.Strength;
        battle.Combat.Damage(target,losses,u,shock,"bayonet charge");target.Cohesion=Math.Max(0,target.Cohesion-4*momentum*terrain);
        u.ChargeResult="bayonet impact";u.Charges++;battle.Metrics.ChargeImpacts++;battle.Metrics.ImpactCasualties+=before-target.Strength;
        battle.Metrics.ImpactMomentum+=momentum;battle.Metrics.ImpactMoraleShock+=shock*target.Archetype.ShockResistance;
        if(before-target.Strength>=target.MaximumStrength*.03)battle.Metrics.ChargeSuccesses++;
        if(boost>1 && CommanderSystem.Has(u,"firebrand"))u.Cohesion=Math.Max(0,u.Cohesion-CommanderSystem.T("firebrand_disorder")*momentum);
        battle.Emit("charge_impact",u,target,u.Position,.8,before-target.Strength,$"{u.Name}: bayonet impact, {before-target.Strength} losses");
    }
}
