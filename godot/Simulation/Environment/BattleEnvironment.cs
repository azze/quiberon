namespace Quiberon.Simulation;

/// <summary>Immutable scenario geometry and weather. No scene nodes or RNG.</summary>
public sealed class BattleEnvironment
{
    public IReadOnlyList<RiverDefinition> Rivers { get; }
    public IReadOnlyList<CrossingGeometry> Crossings { get; }
    public IReadOnlyList<RoadDefinition> Roads { get; }
    public IReadOnlyList<DefenceDefinition> Defences { get; }
    public IReadOnlyList<WaterPolygon> Water { get; }
    public WeatherDefinition Weather { get; }
    public bool Legacy { get; }
    public long GeometryQueries { get; private set; }
    private readonly FeatureGrid<WaterPolygon> waterGrid;
    private readonly FeatureGrid<(RoadDefinition Road,Vec2 A,Vec2 B)> roadGrid;
    private readonly FeatureGrid<DefenceDefinition> defenceGrid;
    public EnvironmentDefinition Definition=>new(1,Rivers.ToArray(),Crossings.Select(c=>c.Definition).ToArray(),Roads.ToArray(),Defences.ToArray(),Weather);
    public BattleEnvironment(EnvironmentDefinition? definition=null)
    {
        var d=definition??new();if(d.Version!=1)throw new ArgumentException("Unsupported terrain.environment version.");
        Rivers=Array.AsReadOnly((d.Rivers??[]).Select(r=>r with{Points=Array.AsReadOnly(r.Points.ToArray())}).ToArray());
        Roads=Array.AsReadOnly((d.Roads??[]).Select(r=>r with{Points=Array.AsReadOnly(r.Points.ToArray())}).ToArray());
        Defences=Array.AsReadOnly((d.Defences??[]).ToArray());Weather=d.Weather??new();
        var ids=new HashSet<string>(StringComparer.Ordinal);
        void Id(string id){if(string.IsNullOrWhiteSpace(id) || id.Length>96 || id.Any(char.IsControl) || !ids.Add(id))throw new ArgumentException("Environmental IDs must be printable, stable and unique.");}
        void Path(IReadOnlyList<Vec2> points,double width){if(points.Count is <2 or >256 || !double.IsFinite(width) || width is <1 or >300 || points.Any(p=>!p.Finite || Math.Abs(p.X)>10000 || Math.Abs(p.Y)>10000) || points.Zip(points.Skip(1)).Any(p=>(p.First-p.Second).Length<.1))throw new ArgumentException("Invalid environmental polyline or width.");}
        if(Rivers.Count>32 || Roads.Count>128 || Defences.Count>256 || (d.Crossings?.Length??0)>64 || Rivers.Sum(r=>r.Points.Count)>1024)throw new ArgumentException("Environmental feature budget exceeded.");
        foreach(var r in Rivers){Id(r.Id);Path(r.Points,r.Width);if(!double.IsFinite(r.WaterHeight+r.Depth) || Math.Abs(r.WaterHeight)>200 || r.Depth is <.5 or >10)throw new ArgumentException("Invalid river elevation/depth.");}
        foreach(var r in Roads){Id(r.Id);Path(r.Points,r.Width);if(!Enum.IsDefined(r.Surface) || !double.IsFinite(r.Multiplier) || r.Multiplier is <.8 or >1.15)throw new ArgumentException("Invalid road surface modifier.");}
        foreach(var f in Defences){Id(f.Id);if(!f.Position.Finite || Math.Abs(f.Position.X)>10000 || Math.Abs(f.Position.Y)>10000 || !double.IsFinite(f.Facing+f.Width+f.Depth+f.ProtectionDepth+f.MusketExposure+f.ChargeResistance) || f.Width is <2 or >500 || f.Depth is <.5 or >15 || f.ProtectionDepth is <2 or >60 || f.MusketExposure is <.35 or >1 || f.ChargeResistance is <.35 or >1 || !Enum.IsDefined(f.Kind))throw new ArgumentException("Invalid defensive position.");}
        if(!Enum.IsDefined(Weather.Type) || !double.IsFinite(Weather.VisibilityLimit+Weather.InfantryWetSpeed+Weather.CavalryWetSpeed+Weather.ArtilleryWetSpeed+Weather.FirearmReload+Weather.ArtilleryReload+Weather.WetDisorder) || Weather.VisibilityLimit is <40 or >2000 || Weather.InfantryWetSpeed is <.6 or >1 || Weather.CavalryWetSpeed is <.6 or >1 || Weather.ArtilleryWetSpeed is <.5 or >1 || Weather.FirearmReload is <1 or >1.3 || Weather.ArtilleryReload is <1 or >1.2 || Weather.WetDisorder is <1 or >1.5)throw new ArgumentException("Invalid weather parameters.");
        var pieces=new List<WaterPolygon>();foreach(var r in Rivers)for(int i=1;i<r.Points.Count;i++)pieces.Add(new(r.Id,EnvironmentGeometry.Capsule(r.Points[i-1],r.Points[i],r.Width/2),r.WaterHeight));
        Water=Array.AsReadOnly(pieces.ToArray());waterGrid=new(pieces.ToArray(),p=>Bounds2.Of(p.Points));
        var crossings=new List<CrossingGeometry>();
        foreach(var original in d.Crossings??[])
        {
            var c=original with{Permitted=original.Permitted is null?null:Array.AsReadOnly(original.Permitted.ToArray())};Id(c.Id);
            var river=Rivers.FirstOrDefault(r=>r.Id==c.RiverId)??throw new ArgumentException("Crossing references an unknown river.");
            if(!c.Position.Finite || Math.Abs(c.Position.X)>10000 || Math.Abs(c.Position.Y)>10000 || !double.IsFinite(c.Facing+c.Length+c.Width+(c.Speed??1)+c.CohesionPerMetre+(c.SurfaceHeight??0)) || c.Length is <5 or >600 || c.Width is <2 or >200 || c.Speed is <.1 or >1 || c.CohesionPerMetre is <0 or >1 || !Enum.IsDefined(c.Kind) || !Enum.IsDefined(c.FordDepth) || c.Permitted?.Any(p=>!Enum.IsDefined(p))==true || c.Permitted is {Count:0})throw new ArgumentException("Invalid crossing geometry/permissions.");
            var axis=Vec2.Direction(c.Facing);var entry=c.Position-axis*c.Length/2;var exit=c.Position+axis*c.Length/2;
            if(!InRiver(c.Position,c.RiverId) || InRiver(entry,c.RiverId) || InRiver(exit,c.RiverId))throw new ArgumentException("A crossing must span its river, with both endpoints on dry banks.");
            double surface=c.SurfaceHeight??(river.WaterHeight+(c.Kind==CrossingKind.Bridge?.55:-.15));
            if(Math.Abs(surface-river.WaterHeight)>5)throw new ArgumentException("Crossing surface must be within 5 m of water level.");
            crossings.Add(new(c,new(c.Position,c.Facing,c.Width,c.Length),entry,exit,surface));
        }
        Crossings=Array.AsReadOnly(crossings.ToArray());
        var segments=new List<(RoadDefinition,Vec2,Vec2)>();foreach(var r in Roads)for(int i=1;i<r.Points.Count;i++)segments.Add((r,r.Points[i-1],r.Points[i]));
        roadGrid=new(segments.ToArray(),s=>Bounds2.Of(new[]{s.Item2,s.Item3},s.Item1.Width/2));
        defenceGrid=new(Defences.ToArray(),f=>Bounds2.Of(EnvironmentGeometry.Corners(new(f.Position,f.Facing,f.Width,f.ProtectionDepth*2+f.Depth))));
        Legacy=Rivers.Count==0 && Roads.Count==0 && Defences.Count==0 && Weather.Type==WeatherType.Clear;
    }
    public bool InRiver(Vec2 p,string? river=null)
    {GeometryQueries++;return waterGrid.Query(new(p.X,p.Y,p.X,p.Y)).Any(w=>(river is null || w.RiverId==river) && EnvironmentGeometry.Contains(w.Points,p));}
    public double? WaterHeight(Vec2 p)
    {foreach(var w in waterGrid.Query(new(p.X,p.Y,p.X,p.Y)))if(EnvironmentGeometry.Contains(w.Points,p))return w.Height;return null;}
    public CrossingGeometry? CrossingAt(Vec2 p)=>Crossings.FirstOrDefault(c=>c.Rect.Contains(p));
    public double Elevation(Vec2 p,double baseline)
    {
        if(Rivers.Count==0)return baseline;
        var crossing=CrossingAt(p);if(crossing?.Definition.Kind==CrossingKind.Bridge)return crossing.SurfaceHeight;
        if(WaterHeight(p) is not { } height)return baseline;
        if(crossing is not null)return crossing.SurfaceHeight;
        double depth=Rivers.First(r=>InRiver(p,r.Id)).Depth;return height-depth;
    }
    public bool PolygonPassable(IReadOnlyList<Vec2> polygon,UnitCategory category,bool crossings=true)
    {
        if(Water.Count==0)return true;GeometryQueries++;
        foreach(var water in waterGrid.Query(Bounds2.Of(polygon)))
        {
            var overlap=EnvironmentGeometry.Clip(polygon,water.Points);if(overlap.Length<3)continue;
            double area=0;for(int i=0;i<overlap.Length;i++)area+=Vec2.Cross(overlap[i],overlap[(i+1)%overlap.Length]);if(Math.Abs(area)<1e-6)continue;
            if(!crossings || !Crossings.Any(c=>c.Definition.RiverId==water.RiverId && c.Permits(category) && overlap.All(c.Rect.Contains)))return false;
        }
        return true;
    }
    public bool Passable(OrientedRect rect,UnitCategory category,bool crossings=true)
    {
        double radius=rect.Radius+.15;
        if(Water.Count==0 || !waterGrid.Intersects(new(rect.Position.X-radius,rect.Position.Y-radius,rect.Position.X+radius,rect.Position.Y+radius)))return true;
        return PolygonPassable(EnvironmentGeometry.Corners(new(rect.Position,rect.Facing,rect.Width+.10,rect.Depth+.10)),category,crossings);
    }
    public bool Swept(OrientedRect from,OrientedRect to,UnitCategory category,bool crossings=true)
    {
        if(Water.Count==0)return true;
        double radius=Math.Max(from.Radius,to.Radius)+.15;
        if(!waterGrid.Intersects(new(Math.Min(from.Position.X,to.Position.X)-radius,Math.Min(from.Position.Y,to.Position.Y)-radius,Math.Max(from.Position.X,to.Position.X)+radius,Math.Max(from.Position.Y,to.Position.Y)+radius)))return true;
        int steps=Math.Max(1,(int)Math.Ceiling(Math.Abs(Vec2.AngleDelta(from.Facing,to.Facing))/.025));
        if(steps>4096)return false;var previous=from;
        for(int i=1;i<=steps;i++)
        {
            double t=i/(double)steps;var next=new OrientedRect(from.Position+(to.Position-from.Position)*t,from.Facing+Vec2.AngleDelta(from.Facing,to.Facing)*t,to.Width+.10,to.Depth+.10);
            if(!PolygonPassable(EnvironmentGeometry.Hull(EnvironmentGeometry.Corners(previous).Concat(EnvironmentGeometry.Corners(next))),category,crossings))return false;previous=next;
        }
        return true;
    }
    public Vec2? ClosestBankAway(Vec2 point)
    {
        double best=double.PositiveInfinity;Vec2? result=null;
        foreach(var r in Rivers)for(int i=1;i<r.Points.Count;i++){var closest=EnvironmentGeometry.Closest(point,r.Points[i-1],r.Points[i]);double d=(point-closest).Length;if(d<best){best=d;result=(point-closest).Normalized;}}
        return result;
    }
    public bool Fording(Regiment u)=>Crossings.Any(c=>c.Definition.Kind==CrossingKind.Ford && c.Permits(u.Archetype.Category) && OrientedRect.Touching(c.Rect,u.Rect,0)) && !Passable(u.Rect,u.Archetype.Category,false);
    public (string Id,double Bonus,double RainProtection) Road(Regiment u,Vec2 motion)
    {
        if(Roads.Count==0)return ("",1,0);GeometryQueries++;double bonus=1,protection=0;string id="";
        foreach(var s in roadGrid.Query(new(u.Position.X,u.Position.Y,u.Position.X,u.Position.Y)))
        {
            if(EnvironmentGeometry.Distance(u.Position,s.A,s.B)>s.Road.Width/2)continue;
            double shelter=s.Road.Surface==RoadSurface.MainRoad?.8:.4;protection=Math.Max(protection,shelter);
            double alignment=motion.Length<.01?1:Math.Abs(motion.Normalized.Dot((s.B-s.A).Normalized));
            double gain=u.Archetype.Category==UnitCategory.Artillery?.20:u.Archetype.Category==UnitCategory.Cavalry?.05:u.Formation==Formation.Column?.08:0;
            if(s.Road.Surface==RoadSurface.Track)gain*=.45;
            if(u.CavalryState==CavalryState.Charging || u.InfantryCharging)gain=0;
            double value=alignment>.85?Math.Clamp((1+gain)*s.Road.Multiplier,1,1.25):1;
            if(value>bonus || id==""){bonus=value;id=s.Road.Id;}
        }
        return(id,bonus,protection);
    }
    public TerrainEffect Movement(Regiment u,Vec2 motion,TerrainEffect baseline)
    {
        if(Legacy)return baseline;var road=Road(u,motion);u.RoadId=road.Id;
        double wet=1,loss=baseline.LossPerMetre;
        if(Weather.Type==WeatherType.Rain){double raw=u.Archetype.Category switch{UnitCategory.Artillery=>Weather.ArtilleryWetSpeed,UnitCategory.Cavalry=>Weather.CavalryWetSpeed,_=>Weather.InfantryWetSpeed};wet=raw+(1-raw)*road.RainProtection;loss=loss*Weather.WetDisorder+.004*(1-road.RainProtection);}
        double crossSpeed=1;if(Fording(u)){var c=Crossings.First(c=>c.Definition.Kind==CrossingKind.Ford && OrientedRect.Touching(c.Rect,u.Rect,0));crossSpeed=c.Speed;loss+=c.Definition.CohesionPerMetre;}
        else if(CrossingAt(u.Position) is {Definition.Kind:CrossingKind.Bridge} bridge)crossSpeed=bridge.Speed;
        return baseline with{Speed=Math.Clamp(baseline.Speed*road.Bonus*wet*crossSpeed,.10,1.30),LossPerMetre=loss};
    }
    public double Reload(UnitCategory category)=>Weather.Type==WeatherType.Rain?(category==UnitCategory.Artillery?Weather.ArtilleryReload:Weather.FirearmReload):1;
    public bool InVisibility(Vec2 a,Vec2 b)=>Weather.Type!=WeatherType.Fog || (b-a).Length<=Weather.VisibilityLimit;
    public Visibility Sight(Vec2 a,Vec2 b,Visibility original)
    {
        if(Weather.Type!=WeatherType.Fog)return original;
        double distance=(b-a).Length;if(distance>Weather.VisibilityLimit)return new(false,0,original.Vegetation,"fog",original.Samples);
        if(!original.Visible)return original;
        double attenuation=1-.65*Math.Clamp((distance/Weather.VisibilityLimit-.55)/.45,0,1);
        return original with{Transmission=original.Transmission*attenuation,Reason=attenuation<.99?"fog":original.Reason};
    }
    public double Defence(Regiment defender,Vec2 attacker,bool charge=false)
    {
        if(Defences.Count==0 || !defender.Effective || charge && defender.State!=MoraleState.Steady || defender.Cohesion<45 || defender.Speed>.1 || defender.TransitionLeft>0 || defender.Formation==Formation.Skirmish)return 1;
        GeometryQueries++;double factor=1;
        foreach(var f in defenceGrid.Query(new(defender.Position.X,defender.Position.Y,defender.Position.X,defender.Position.Y)))
        {
            var front=Vec2.Direction(f.Facing);var side=new Vec2(-front.Y,front.X);var offset=defender.Position-f.Position;
            double behind=offset.Dot(front);if(behind+defender.Rect.Extent(front)> -f.Depth/2 || behind< -f.ProtectionDepth || Math.Abs(offset.Dot(side))+defender.Rect.Extent(side)>f.Width/2 || Math.Abs(Vec2.AngleDelta(defender.Facing,f.Facing))>Math.PI/4)continue;
            if((attacker-f.Position).Dot(front)<=0 || (attacker-defender.Position).Normalized.Dot(front)<.5)continue;
            factor=Math.Min(factor,charge?f.ChargeResistance:f.MusketExposure);
        }
        return factor;
    }
}
