namespace Quiberon.Simulation;

public readonly struct OrientedRect
{
    public readonly Vec2 Position, Forward, Side;
    public readonly double Facing, Width, Depth, Radius;
    private readonly Vec2 a, b, c, d;
    public OrientedRect(Vec2 position, double facing, double width, double depth)
    {
        Position = position; Facing = facing; Width = width; Depth = depth;
        Forward = Vec2.Direction(facing); Side = Vec2.Direction(facing + Math.PI / 2);
        Radius = Math.Sqrt(width * width + depth * depth) / 2;
        a = position + Forward * (depth / 2) + Side * (width / 2);
        b = position + Forward * (depth / 2) - Side * (width / 2);
        c = position - Forward * (depth / 2) - Side * (width / 2);
        d = position - Forward * (depth / 2) + Side * (width / 2);
    }
    public Vec2 Corner(int i) => i switch { 0 => a, 1 => b, 2 => c, _ => d };
    public bool Contains(Vec2 point) => Math.Abs((point - Position).Dot(Forward)) <= Depth / 2 && Math.Abs((point - Position).Dot(Side)) <= Width / 2;
    public double Extent(Vec2 axis) => Math.Abs(Forward.Dot(axis)) * Depth / 2 + Math.Abs(Side.Dot(axis)) * Width / 2;
    public static bool Touching(OrientedRect a, OrientedRect b, double margin = .75)
    {
        if ((a.Position-b.Position).Length > a.Radius+b.Radius+margin*2) return false;
        var delta=b.Position-a.Position;
        Span<Vec2> axes=stackalloc Vec2[] {a.Forward,a.Side,b.Forward,b.Side};
        foreach(var axis in axes) if(Math.Abs(delta.Dot(axis))>a.Extent(axis)+b.Extent(axis)+margin) return false;
        return true;
    }
    public static Vec2? Separation(OrientedRect a, OrientedRect b)
    {
        if ((b.Position - a.Position).LengthSquared > Math.Pow(a.Radius + b.Radius, 2) + 1e-8) return null;
        double best = double.PositiveInfinity; Vec2 answer = default;
        Span<Vec2> axes = stackalloc Vec2[] { a.Forward, a.Side, b.Forward, b.Side };
        foreach (var axis in axes)
        {
            double amin = double.PositiveInfinity, amax = double.NegativeInfinity, bmin = amin, bmax = amax;
            for (int i = 0; i < 4; i++)
            {
                double pa = a.Corner(i).Dot(axis), pb = b.Corner(i).Dot(axis);
                amin = Math.Min(amin, pa); amax = Math.Max(amax, pa); bmin = Math.Min(bmin, pb); bmax = Math.Max(bmax, pb);
            }
            double overlap = Math.Min(amax, bmax) - Math.Max(amin, bmin);
            if (overlap <= 0) return null;
            if (overlap < best) { best = overlap; answer = axis * ((b.Position - a.Position).Dot(axis) >= 0 ? -overlap : overlap); }
        }
        return answer;
    }
    public static double? Segment(Vec2 start, Vec2 end, OrientedRect box, double padding = 0)
    {
        var delta = end - start; var offset = start - box.Position;
        double lo = 0, hi = 1;
        for (int i = 0; i < 2; i++)
        {
            var axis = i == 0 ? box.Forward : box.Side; double half = (i == 0 ? box.Depth : box.Width) / 2 + padding;
            double p = offset.Dot(axis), v = delta.Dot(axis);
            if (Math.Abs(v) < 1e-9) { if (Math.Abs(p) > half) return null; }
            else
            {
                double t1 = (-half - p) / v, t2 = (half - p) / v;
                lo = Math.Max(lo, Math.Min(t1, t2)); hi = Math.Min(hi, Math.Max(t1, t2));
                if (lo > hi) return null;
            }
        }
        return lo;
    }
    public static double IntersectionArea(OrientedRect a, OrientedRect b)
    {
        Span<Vec2> polygon = stackalloc Vec2[16]; Span<Vec2> output = stackalloc Vec2[16];
        for (int i = 0; i < 4; i++) polygon[i] = a.Corner(i);
        int count = 4; double winding = 0;
        for (int i = 0; i < 4; i++) winding += Vec2.Cross(b.Corner(i), b.Corner((i + 1) % 4));
        winding = winding > 0 ? 1 : -1;
        for (int edgeIndex = 0; edgeIndex < 4; edgeIndex++)
        {
            if (count == 0) return 0;
            var start = b.Corner(edgeIndex); var edge = b.Corner((edgeIndex + 1) % 4) - start;
            int n = 0; var previous = polygon[count - 1]; double dp = winding * Vec2.Cross(edge, previous - start);
            for (int i = 0; i < count; i++)
            {
                var current = polygon[i]; double dc = winding * Vec2.Cross(edge, current - start);
                if ((dc >= 0) != (dp >= 0)) output[n++] = previous + (current - previous) * (dp / (dp - dc));
                if (dc >= 0) output[n++] = current;
                previous = current; dp = dc;
            }
            output[..n].CopyTo(polygon); count = n;
        }
        double area = 0;
        for (int i = 0; i < count; i++) area += Vec2.Cross(polygon[i], polygon[(i + 1) % count]);
        return Math.Abs(area) / 2;
    }
}
