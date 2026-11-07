namespace Quiberon.Simulation;

internal readonly record struct Bounds2(double MinX,double MinY,double MaxX,double MaxY)
{
    public bool Overlaps(Bounds2 b)=>MinX<=b.MaxX && MaxX>=b.MinX && MinY<=b.MaxY && MaxY>=b.MinY;
    public static Bounds2 Of(IEnumerable<Vec2> points,double margin=0)=>new(points.Min(p=>p.X)-margin,points.Min(p=>p.Y)-margin,points.Max(p=>p.X)+margin,points.Max(p=>p.Y)+margin);
}
/// <summary>Static 100 m broad phase. Queries are stable and never iterate all river segments.</summary>
internal sealed class FeatureGrid<T>
{
    private readonly Dictionary<(int,int),int[]> cells;
    private readonly T[] values;
    private readonly Bounds2[] bounds;
    public FeatureGrid(T[] values,Func<T,Bounds2> box)
    {
        this.values=values;bounds=values.Select(box).ToArray();var build=new Dictionary<(int,int),List<int>>();
        long cellBudget=0;
        for(int i=0;i<values.Length;i++){var b=bounds[i];cellBudget+=((long)Math.Floor(b.MaxX/100)-(long)Math.Floor(b.MinX/100)+1)*((long)Math.Floor(b.MaxY/100)-(long)Math.Floor(b.MinY/100)+1);if(cellBudget>200000)throw new ArgumentException("Environmental spatial-index budget exceeded; split long diagonal polylines into shorter segments.");for(int x=(int)Math.Floor(b.MinX/100);x<=Math.Floor(b.MaxX/100);x++)for(int y=(int)Math.Floor(b.MinY/100);y<=Math.Floor(b.MaxY/100);y++){if(!build.TryGetValue((x,y),out var list))build[(x,y)]=list=new();list.Add(i);}}
        cells=build.ToDictionary(p=>p.Key,p=>p.Value.ToArray());
    }
    // Allocation-free broad phase before constructing swept hulls/clip buffers.
    public bool Intersects(Bounds2 b)
    {
        for(int x=(int)Math.Floor(b.MinX/100);x<=Math.Floor(b.MaxX/100);x++)
            for(int y=(int)Math.Floor(b.MinY/100);y<=Math.Floor(b.MaxY/100);y++)
                if(cells.TryGetValue((x,y),out var list))foreach(int i in list)if(bounds[i].Overlaps(b))return true;
        return false;
    }
    public IEnumerable<T> Query(Bounds2 b)
    {
        int x0=(int)Math.Floor(b.MinX/100),x1=(int)Math.Floor(b.MaxX/100),y0=(int)Math.Floor(b.MinY/100),y1=(int)Math.Floor(b.MaxY/100);
        if(x0==x1 && y0==y1){if(cells.TryGetValue((x0,y0),out var single))foreach(int i in single)if(bounds[i].Overlaps(b))yield return values[i];yield break;}
        var seen=new HashSet<int>();
        for(int x=x0;x<=x1;x++)for(int y=y0;y<=y1;y++)if(cells.TryGetValue((x,y),out var list))foreach(int i in list)if(seen.Add(i) && bounds[i].Overlaps(b))yield return values[i];
    }
}
public static class EnvironmentGeometry
{
    public static Vec2[] Corners(OrientedRect r)=>Enumerable.Range(0,4).Select(r.Corner).ToArray();
    public static double Distance(Vec2 p,Vec2 a,Vec2 b)=> (p-Closest(p,a,b)).Length;
    public static Vec2 Closest(Vec2 p,Vec2 a,Vec2 b){var d=b-a;return a+d*Math.Clamp((p-a).Dot(d)/Math.Max(1e-12,d.LengthSquared),0,1);}
    // Convex capsule with eight edges per semicircle. This exact polygon is also
    // exported to Godot: there is no circular/visual containment disagreement.
    public static Vec2[] Capsule(Vec2 a,Vec2 b,double radius)
    {
        double angle=Vec2.AngleTo(a,b);var result=new List<Vec2>();
        for(int i=0;i<=8;i++)result.Add(b+Vec2.Direction(angle-Math.PI/2+i*Math.PI/8)*radius);
        for(int i=0;i<=8;i++)result.Add(a+Vec2.Direction(angle+Math.PI/2+i*Math.PI/8)*radius);
        return result.ToArray();
    }
    public static bool Contains(IReadOnlyList<Vec2> polygon,Vec2 p)
    {for(int i=0;i<polygon.Count;i++)if(Vec2.Cross(polygon[(i+1)%polygon.Count]-polygon[i],p-polygon[i]) < -1e-8)return false;return true;}
    public static Vec2[] Clip(IReadOnlyList<Vec2> polygon,IReadOnlyList<Vec2> clip)
    {
        var input=polygon.ToList();double winding=0;for(int i=0;i<clip.Count;i++)winding+=Vec2.Cross(clip[i],clip[(i+1)%clip.Count]);winding=winding>=0?1:-1;
        for(int edge=0;edge<clip.Count && input.Count>0;edge++)
        {
            var output=new List<Vec2>(input.Count+2);var a=clip[edge];var direction=clip[(edge+1)%clip.Count]-a;var previous=input[^1];double dp=winding*Vec2.Cross(direction,previous-a);
            foreach(var point in input){double dc=winding*Vec2.Cross(direction,point-a);if((dc>=0)!=(dp>=0))output.Add(previous+(point-previous)*(dp/(dp-dc)));if(dc>=0)output.Add(point);previous=point;dp=dc;}input=output;
        }
        return input.ToArray();
    }
    public static Vec2[] Hull(IEnumerable<Vec2> input)
    {
        var p=input.Distinct().OrderBy(v=>v.X).ThenBy(v=>v.Y).ToArray();if(p.Length<=2)return p;
        var hull=new List<Vec2>();foreach(var v in p){while(hull.Count>=2 && Vec2.Cross(hull[^1]-hull[^2],v-hull[^1])<=0)hull.RemoveAt(hull.Count-1);hull.Add(v);}int first=hull.Count;
        for(int i=p.Length-2;i>=0;i--){while(hull.Count>first && Vec2.Cross(hull[^1]-hull[^2],p[i]-hull[^1])<=0)hull.RemoveAt(hull.Count-1);hull.Add(p[i]);}hull.RemoveAt(hull.Count-1);return hull.ToArray();
    }
}
