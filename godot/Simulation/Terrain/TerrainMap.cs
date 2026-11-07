namespace Quiberon.Simulation;

public sealed record Hill(double X, double Y, double RadiusX, double RadiusY, double Height, bool Compact = false);
public sealed record Forest(double X, double Y, double RadiusX, double RadiusY, double Density = 1);
public readonly record struct TerrainEffect(double Speed = 1, double LossPerMetre = 0, double Forest = 0, double Slope = 0, double Grade = 0);
public readonly record struct TerrainProfile(double ForestSlow, double ForestLoss, double Uphill, double SlopeLoss, double RouteAversion);
public sealed class TerrainMap
{
    public IReadOnlyList<Hill> Hills { get; }
    public IReadOnlyList<Forest> Forests { get; }
    public BattleEnvironment Environment { get; }
    public bool Empty => Hills.Count == 0 && Forests.Count == 0 && Environment.Legacy;
    private readonly Dictionary<(Vec2, double, double, double), Sample> footprintCache = new();
    private readonly Dictionary<(int, int), int[]>? hillCells, forestCells;
    private readonly int[] globalHills;
    private readonly record struct Sample(double Forest, Vec2[] Gradients, double Slope);
    public TerrainMap(Hill[]? hills = null, Forest[]? forests = null,EnvironmentDefinition? environment=null)
    {
        Environment=new(environment);
        Hills = Array.AsReadOnly(hills?.ToArray() ?? []); Forests = Array.AsReadOnly(forests?.ToArray() ?? []);
        if (Hills.Count > 256 || Forests.Count > 256 || Hills.Any(h => !new Vec2(h.X, h.Y).Finite || !double.IsFinite(h.Height) || !double.IsFinite(h.RadiusX + h.RadiusY) || Math.Min(h.RadiusX, h.RadiusY) < 1) || Forests.Any(f => !new Vec2(f.X, f.Y).Finite || !double.IsFinite(f.Density + f.RadiusX + f.RadiusY) || Math.Min(f.RadiusX, f.RadiusY) < 1 || f.Density is < 0 or > 1)) throw new ArgumentException("Invalid terrain geometry");
        globalHills = Enumerable.Range(0, Hills.Count).Where(i => !Hills[i].Compact).ToArray();
        // Oversized/remote features stay on the exact bounded linear path rather
        // than allocating unbounded cell ranges from an untrusted fixture.
        bool Indexable(double x,double y,double rx,double ry) => Math.Abs(x)+rx<1e9 && Math.Abs(y)+ry<1e9 && (2*rx/200+2)*(2*ry/200+2)<=4096;
        if (Hills.Count > 16 && Hills.All(h => !h.Compact || Indexable(h.X,h.Y,h.RadiusX*3,h.RadiusY*3))) hillCells = BuildCells(Hills.Count, i => (Hills[i].X, Hills[i].Y, Hills[i].RadiusX * 3, Hills[i].RadiusY * 3), i => Hills[i].Compact, globalHills);
        if (Forests.Count > 16 && Forests.All(f => Indexable(f.X,f.Y,f.RadiusX,f.RadiusY))) forestCells = BuildCells(Forests.Count, i => (Forests[i].X, Forests[i].Y, Forests[i].RadiusX, Forests[i].RadiusY), _ => true, []);
    }
    private static Dictionary<(int, int), int[]> BuildCells(int count, Func<int, (double X, double Y, double RX, double RY)> bounds, Func<int, bool> local, int[] globals)
    {
        var cells = new Dictionary<(int, int), List<int>>();
        for (int i = 0; i < count; i++)
        {
            if (!local(i)) continue;
            var (x, y, rx, ry) = bounds(i);
            for (int cx = (int)Math.Floor((x - rx) / 200); cx <= (int)Math.Floor((x + rx) / 200); cx++)
                for (int cy = (int)Math.Floor((y - ry) / 200); cy <= (int)Math.Floor((y + ry) / 200); cy++)
                { if (!cells.TryGetValue((cx, cy), out var items)) cells[(cx, cy)] = items = new(); items.Add(i); }
        }
        return cells.ToDictionary(p => p.Key, p => p.Value.Concat(globals).Order().ToArray());
    }
    private IEnumerable<int> HillCandidates(Vec2 p) => hillCells is null ? Enumerable.Range(0, Hills.Count) : hillCells.GetValueOrDefault(((int)Math.Floor(p.X / 200), (int)Math.Floor(p.Y / 200)), globalHills);
    private IEnumerable<int> ForestCandidates(Vec2 p) => forestCells is null ? Enumerable.Range(0, Forests.Count) : forestCells.GetValueOrDefault(((int)Math.Floor(p.X / 200), (int)Math.Floor(p.Y / 200)), []);
    public double SampleStep(double maximum)
    { foreach(var h in Hills)maximum=Math.Min(maximum,Math.Min(h.RadiusX,h.RadiusY)/4);foreach(var f in Forests)maximum=Math.Min(maximum,Math.Min(f.RadiusX,f.RadiusY)/4);return maximum; }
    public double Elevation(Vec2 p)
    {
        double height = 0;
        foreach (int i in HillCandidates(p))
        {
            var h = Hills[i]; double squared = Math.Pow((p.X - h.X) / h.RadiusX, 2) + Math.Pow((p.Y - h.Y) / h.RadiusY, 2);
            height += h.Height * (h.Compact ? Math.Pow(Math.Max(0, 1 - squared / 9), 4) : Math.Exp(-.5 * squared));
        }
        return Environment.Rivers.Count>0?Environment.Elevation(p,height):height;
    }
    public Vec2 Gradient(Vec2 p)
    {
        if(Environment.Rivers.Count>0)return new((Elevation(p+new Vec2(1,0))-Elevation(p-new Vec2(1,0)))/2,(Elevation(p+new Vec2(0,1))-Elevation(p-new Vec2(0,1)))/2);
        double gx = 0, gy = 0;
        foreach (int i in HillCandidates(p))
        {
            var h = Hills[i]; double squared = Math.Pow((p.X - h.X) / h.RadiusX, 2) + Math.Pow((p.Y - h.Y) / h.RadiusY, 2);
            double factor = h.Compact ? -8 * h.Height * Math.Pow(Math.Max(0, 1 - squared / 9), 3) / 9 : -h.Height * Math.Exp(-.5 * squared);
            gx += factor * (p.X - h.X) / (h.RadiusX * h.RadiusX); gy += factor * (p.Y - h.Y) / (h.RadiusY * h.RadiusY);
        }
        return new(gx, gy);
    }
    public double ForestDensity(Vec2 p)
    {
        double density = 0;
        foreach (int i in ForestCandidates(p))
        {
            var f = Forests[i]; double dx = p.X - f.X, dy = p.Y - f.Y;
            if (Math.Abs(dx) >= f.RadiusX || Math.Abs(dy) >= f.RadiusY) continue;
            double t = Math.Clamp((1 - new Vec2(dx / f.RadiusX, dy / f.RadiusY).Length) / .2, 0, 1);
            density = Math.Max(density, f.Density * t * t * (3 - 2 * t));
        }
        return density;
    }
    public static TerrainProfile Profile(UnitCategory category) => category switch
    {
        UnitCategory.Infantry => new(.35, .10, 4, .8, 0),
        UnitCategory.Cavalry => new(.65, .25, 5, 1.4, 1),
        _ => new(.75, .18, 8, 1, 1.4)
    };
    public Visibility Visibility(Vec2 from,Vec2 to,double opacity=1)=>Environment.Sight(from,to,GeometricVisibility(from,to,opacity));
    private Visibility GeometricVisibility(Vec2 from,Vec2 to,double opacity)
    {
        if(Hills.Count==0 && Forests.Count==0)return Quiberon.Simulation.Visibility.Clear;
        double distance=(to-from).Length;
        if(distance<1e-8)return Quiberon.Simulation.Visibility.Clear;
        double step=4;
        foreach(var h in Hills)step=Math.Min(step,Math.Min(h.RadiusX,h.RadiusY)/4);
        foreach(var f in Forests)step=Math.Min(step,Math.Min(f.RadiusX,f.RadiusY)/4);
        int count=Math.Max(1,(int)Math.Ceiling(distance/step));
        double start=Elevation(from)+1.7,end=Elevation(to)+1.7,vegetation=0;
        for(int i=0;i<count;i++)
        {
            double t=(i+.5)/count;var p=from+(to-from)*t;
            double ground=Elevation(p),height=start+(end-start)*t;
            if(ground>height)return new(false,0,vegetation,"ridge",i+1);
            if(height<ground+12)
            {
                vegetation+=ForestDensity(p)*distance/count*opacity;
                if(vegetation>=75)return new(false,0,vegetation,"forest",i+1);
            }
        }
        return new(true,Math.Exp(-vegetation/60),vegetation,vegetation>1?"forest":"clear",count);
    }
    public TerrainEffect MovementEffect(Regiment unit, Vec2 motion)
    {
        if (Empty) return new(1);
        if(Hills.Count==0 && Forests.Count==0 && Environment.Rivers.Count==0)return Environment.Movement(unit,motion,new(1));
        var key = (unit.Position, unit.Facing, unit.Width, unit.Depth);
        if (!footprintCache.TryGetValue(key, out var sample))
        {
            var gradients = new Vec2[5]; double forest = 0, slope = 0;
            for (int i = 0; i < 5; i++)
            {
                var point = i == 0 ? unit.Position : unit.Rect.Corner(i - 1);
                forest += ForestDensity(point); gradients[i] = Gradient(point); slope += gradients[i].Length;
            }
            sample = new(forest / 5, gradients, slope / 5);
            if (footprintCache.Count >= 2048) footprintCache.Clear();
            footprintCache[key] = sample;
        }
        var heading = motion.Normalized; double grade = 0;
        foreach (var g in sample.Gradients) grade += g.Dot(heading);
        grade /= 5;
        var profile = Profile(unit.Archetype.Category); var archetype = unit.Archetype;
        double column = unit.Formation == Formation.Column ? .55 : unit.Formation == Formation.Skirmish ? .45 : 1;
        double path=CommanderSystem.Has(unit,"pathfinder")?1-CommanderSystem.T("pathfinder_forest"):1;
        double uphill=profile.Uphill*(CommanderSystem.Has(unit,"pathfinder")?1-CommanderSystem.T("pathfinder_uphill"):1);
        double forestSpeed = 1 - profile.ForestSlow * sample.Forest * column * archetype.ForestSlow*path;
        double slopeSpeed = grade >= 0 ? 1 / (1 + uphill * grade) : Math.Min(1.12, 1 - grade * .5) / (1 + uphill * Math.Max(0, -grade - .15));
        double loss = sample.Forest * profile.ForestLoss * column * archetype.ForestLoss + Math.Max(0, sample.Slope - .05) * profile.SlopeLoss * archetype.SlopeLoss;
        if(CommanderSystem.Has(unit,"pathfinder"))loss*=1-CommanderSystem.T("pathfinder_disruption");
        return Environment.Movement(unit,motion,new(Math.Clamp(forestSpeed * slopeSpeed, .2, 1.12), loss, sample.Forest, sample.Slope, grade));
    }
}
