namespace Quiberon.Simulation;

/// <summary>Absolute elevation, swept OBB hits, analytic terrain normals; never Godot physics.</summary>
public sealed class Projectile
{
    public long Id { get; internal set; }
    public int OwnerId { get; init; }
    public int Army { get; internal set; }
    public Vec2 Position { get; set; }
    public Vec2 Velocity { get; set; }
    public double Height { get; set; }
    public double VerticalSpeed { get; set; }
    public double Energy { get; set; }=1;
    public double Age { get; set; }
    public int Bounces { get; set; }
    public string Type { get; init; } = "round_shot";
    public double Distance { get; internal set; }
    public HashSet<int> HitIds { get; }=new();
}
public sealed record ProjectileSnapshot(long Id,int OwnerId,int Army,Vec2 Position,Vec2 Velocity,double Height,double VerticalSpeed,double Energy,int Bounces,double Age,string Type="round_shot");

public sealed class ArtillerySystem(BattleSimulation battle)
{
    private readonly List<Projectile> shots=new();
    private readonly List<(double Entry,int Id,Regiment Unit)> hits=new();
    private long nextId;
    public IReadOnlyList<Projectile> Projectiles=>shots.AsReadOnly();
    public Projectile Add(Projectile p)
    {
        if(p.Type is not ("round_shot" or "canister") || !p.Position.Finite || !p.Velocity.Finite || !double.IsFinite(p.Height+p.VerticalSpeed+p.Energy+p.Age) || p.Energy<=0 || p.Age<0 || p.Bounces<0 || battle.Unit(p.OwnerId)is null)throw new ArgumentException("Invalid projectile");
        p.Army=battle.Unit(p.OwnerId)!.Army;p.Id=nextId++;shots.Add(p);battle.Metrics.PeakProjectiles=Math.Max(battle.Metrics.PeakProjectiles,shots.Count);return p;
    }
    // Corrected Euclidean norm, like Python math.hypot: a 1-ulp error at
    // exactly 100 m/s changes ceil(speed*dt/2), hence the clipped bounce step.
    internal static double Length(Vec2 v)
    {
        double maximum=Math.Max(Math.Abs(v.X),Math.Abs(v.Y));if(maximum==0)return 0;
        int exponent=Math.ILogB(maximum);double x=Math.ScaleB(v.X,-exponent),y=Math.ScaleB(v.Y,-exponent);
        double xx=x*x,yy=y*y,sum=xx+yy;
        double tail=xx>=yy?yy-(sum-xx):xx-(sum-yy);
        double h=Math.Sqrt(sum);
        double correction=(Math.FusedMultiplyAdd(x,x,-xx)+Math.FusedMultiplyAdd(y,y,-yy)+tail+Math.FusedMultiplyAdd(-h,h,sum))/(2*h);
        return Math.ScaleB(h+correction,exponent);
    }
    private double Uniform(double a,double b)=>a+(b-a)*battle.Random.NextDouble();
    public Projectile Launch(Regiment u,Regiment target,Vec2? origin=null)
    {
        var start=origin??u.Position;var r=battle.Rules;
        double cover=battle.Terrain.Empty?0:battle.Terrain.MovementEffect(u,Vec2.Zero).Forest;
        double scatter=Math.Min(r.ArtilleryScatter*(1+cover),Length(target.Position-start)*.5)*CommanderSystem.Scatter(u);
        var aim=target.Position+new Vec2(Uniform(-scatter,scatter),Uniform(-scatter,scatter));
        var delta=aim-start;double distance=Length(delta);
        double flight=Math.Max(.1,distance/100),z=battle.Terrain.Elevation(start)+1.2;
        double vz=(battle.Terrain.Elevation(aim)-z+.5*r.Gravity*flight*flight)/flight;
        if(battle.Terrain.Empty)vz=Math.Max(0,vz);
        if(r.ArtilleryVerticalScatter>0)vz+=Uniform(-r.ArtilleryVerticalScatter*CommanderSystem.Scatter(u),r.ArtilleryVerticalScatter*CommanderSystem.Scatter(u));
        var p=Add(new(){OwnerId=u.Id,Army=u.Army,Position=start,Velocity=(distance>0?delta/distance:Vec2.Zero)*100,Height=z,VerticalSpeed=vz,Energy=u.Archetype.ProjectilePower});
        battle.Metrics.ArtilleryShots++;battle.Emit("gun_fired",u,target,start,1,0,$"{u.Name}: round shot {p.Id}");return p;
    }
    public void Salvo(Regiment u,Regiment target)
    {
        var side=Vec2.Direction(u.Facing+Math.PI/2);int count=u.AvailableGuns;
        bool canister=u.Archetype.CanisterRange>0 && (target.Position-u.Position).Length<=u.Archetype.CanisterRange;
        for(int i=0;i<count;i++)
        {
            var origin=u.Position+side*(((i+.5)/count-.5)*u.Width*.8);
            if(!canister){Launch(u,target,origin);continue;}
            // Eight statistical shot groups per gun, each a real swept projectile.
            // Spread, height, hills and friendly footprints determine every hit.
            double flight=Math.Max(.1,(target.Position-origin).Length/100),z=battle.Terrain.Elevation(origin)+1.2;
            double vz=(battle.Terrain.Elevation(target.Position)+1-z+.5*battle.Rules.Gravity*flight*flight)/flight;
            for(int pellet=0;pellet<8;pellet++)Add(new(){OwnerId=u.Id,Position=origin,
                Velocity=Vec2.Direction(Vec2.AngleTo(origin,target.Position)+Uniform(-.12,.12))*100,
                Height=z,VerticalSpeed=vz+Uniform(-.6,.6),Energy=u.Archetype.ProjectilePower,Type="canister"});
            battle.Metrics.ArtilleryShots++;battle.Emit("gun_fired",u,target,origin,1,0,$"{u.Name}: physical canister");
        }
        battle.Emit("artillery_fire",u,target,u.Position,3,0,$"{u.Name}: {count}-gun {(canister?"canister":"round shot")} salvo");
    }
    private double Surface(Vec2 point)=>Math.Max(battle.Terrain.Elevation(point),battle.Terrain.Environment.CrossingAt(point)?.Definition.Kind==CrossingKind.Bridge?double.NegativeInfinity:battle.Terrain.Environment.WaterHeight(point)??double.NegativeInfinity);
    public void AdvancePiece(Projectile p,double dt,bool terrainEnabled)
    {
        var t=battle.Terrain;var r=battle.Rules;var old=p.Position;double oldZ=p.Height,vertical=p.VerticalSpeed;
        var end=old+p.Velocity*dt;double endZ=oldZ+vertical*dt-.5*r.Gravity*dt*dt,ground=Surface(end);
        bool collision=endZ<=ground;double fraction=1;
        if(collision && terrainEnabled)
        {
            double lo=0,hi=1;
            for(int i=0;i<16;i++){double f=(lo+hi)/2;var point=old+p.Velocity*(dt*f);double z=oldZ+vertical*dt*f-.5*r.Gravity*Math.Pow(dt*f,2);if(z<=Surface(point))hi=f;else lo=f;}
            fraction=hi;end=old+p.Velocity*(dt*fraction);ground=Surface(end);endZ=ground;
        }
        p.Distance+=Length(end-old);p.Position=end;p.Height=endZ;p.VerticalSpeed=vertical-r.Gravity*dt*fraction;hits.Clear();
        foreach(var u in battle.Combat.SegmentCandidates(old,end))
        {
            if(!u.Active || u.Id==p.OwnerId || p.HitIds.Contains(u.Id))continue;
            battle.Metrics.ProjectileCollisionChecks++;
            if(OrientedRect.Segment(old,end,u.Rect)is not { } entry)continue;
            var point=old+(end-old)*entry;double z=oldZ+(endZ-oldZ)*entry;
            if(z<=t.Elevation(point)+3)hits.Add((entry,u.Id,u));
        }
        hits.Sort((a,b)=>{int c=a.Entry.CompareTo(b.Entry);return c!=0?c:a.Id.CompareTo(b.Id);});
        foreach(var hit in hits)
        {
            if(p.Type=="canister" && p.Distance-Length(end-old)+Length(end-old)*hit.Entry>105)continue;
            var u=hit.Unit;int losses=(int)(Uniform(p.Type=="canister"?1:5,p.Type=="canister"?3:13)*p.Energy*(u.Formation==Formation.Skirmish?.75:1));
            int before=u.Strength;var owner=battle.Unit(p.OwnerId)!;
            battle.Combat.Damage(u,losses,owner,(p.Type=="canister"?.6:5)*p.Energy,p.Type);
            p.HitIds.Add(u.Id);p.Energy*=.75;battle.Metrics.ProjectileHits++;
            bool friendly=u.Army==p.Army;if(friendly && before>u.Strength)battle.Metrics.FriendlyFireHits++;
            battle.Emit(friendly?"friendly_fire":"projectile_hit",owner,u,old+(end-old)*hit.Entry,.8,before-u.Strength,$"{(p.Type=="canister"?"Canister":"Round shot")} {p.Id} struck {u.Name}{(friendly?" (friendly fire)":"")}");
            if(p.Type=="canister"){p.Energy=0;break;}
        }
        if(terrainEnabled && t.Forests.Count>0)
        {var middle=(old+end)*.5;if((oldZ+endZ)/2<t.Elevation(middle)+12)p.Energy*=Math.Exp(-t.ForestDensity(middle)*Length(end-old)*r.ProjectileForestDrag);}
        if(collision)
        {
            if(battle.Terrain.Environment.WaterHeight(end) is { } water && battle.Terrain.Environment.CrossingAt(end)?.Definition.Kind!=CrossingKind.Bridge && p.Height<=water+.02)
            {p.Energy=0;battle.Emit("projectile_water",battle.Unit(p.OwnerId)!,null,end,1,0,$"{p.Type}: water impact");return;}
            if(p.Type=="canister"){p.Energy=0;return;}
            p.Height=ground+(terrainEnabled?.01:0);var gradient=t.Gradient(end);double norm=Math.Sqrt(1+gradient.Dot(gradient));var normal=gradient*(-1/norm);double nz=1/norm;
            double dot=p.Velocity.Dot(normal)+p.VerticalSpeed*nz;
            if(dot<0){p.Velocity=p.Velocity*.78-normal*(1.26*dot);p.VerticalSpeed=p.VerticalSpeed*.78-nz*1.26*dot;}
            else {p.Velocity*=.78;p.VerticalSpeed=Math.Abs(p.VerticalSpeed)*.48;}
            p.Energy*=.72;p.Bounces++;battle.Metrics.ProjectileBounces++;
            battle.Emit("projectile_bounce",battle.Unit(p.OwnerId)!,null,p.Position,1,0,$"Round shot {p.Id}: ground impact/ricochet {p.Bounces}");
        }
    }
    public void Update()
    {
        bool terrain=!battle.Terrain.Empty;
        for(int i=0;i<shots.Count;)
        {
            var p=shots[i];int pieces=terrain?Math.Max(1,Math.Max((int)Math.Ceiling(Length(p.Velocity)*Rules.Dt/battle.Terrain.SampleStep(battle.Rules.ProjectileStep)),(int)Math.Ceiling(Rules.Dt/.025))):1;
            p.Age+=Rules.Dt;
            for(int j=0;j<pieces;j++){AdvancePiece(p,Rules.Dt/pieces,terrain);if(p.Bounces>=5 || p.Energy<=.15)break;}
            if(p.Age<battle.Rules.ProjectileLifetime && (p.Type!="canister" || p.Distance<=105) && p.Bounces<5 && p.Energy>.15 && p.Position.X> -50 && p.Position.X<battle.Rules.Width+50 && p.Position.Y> -50 && p.Position.Y<battle.Rules.Height+50){i++;continue;}
            battle.Emit("projectile_end",battle.Unit(p.OwnerId)!,null,p.Position,.4,0,$"{(p.Type=="canister"?"Canister":"Round shot")} {p.Id} terminated");shots.RemoveAt(i);
        }
    }
    public void Clear()=>shots.Clear();
    public ProjectileSnapshot[] Snapshot()=>shots.Select(p=>new ProjectileSnapshot(p.Id,p.OwnerId,p.Army,p.Position,p.Velocity,p.Height,p.VerticalSpeed,p.Energy,p.Bounces,p.Age,p.Type)).ToArray();
}
